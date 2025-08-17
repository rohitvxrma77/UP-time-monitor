from __future__ import annotations
import os, time, argparse, requests, smtplib
from email.mime.text import MIMEText
from typing import Optional

def notify_console(msg: str):
    print(msg)

def notify_telegram(token: str, chat: str, msg: str):
    if not (token and chat): return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg}, timeout=10)
    except Exception: pass

def notify_pushbullet(token: str, title: str, body: str):
    if not token: return
    try:
        requests.post("https://api.pushbullet.com/v2/pushes",
                      headers={"Access-Token": token, "Content-Type": "application/json"},
                      json={"type": "note", "title": title, "body": body}, timeout=10)
    except Exception: pass

def notify_email(host: str, port: int, user: str, pwd: str, to: str, subject: str, body: str):
    if not (host and port and user and pwd and to): return
    try:
        msg = MIMEText(body, "plain", "utf-8"); msg["Subject"]=subject; msg["From"]=user; msg["To"]=to
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls(); s.login(user, pwd); s.sendmail(user, [to], msg.as_string())
    except Exception: pass

def health_check(url: str, timeout: int = 10) -> int:
    r = requests.get(url, timeout=timeout)
    return r.status_code

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--timeout", type=int, default=10)
    args = p.parse_args()

    tg_token = os.getenv("TG_TOKEN", ""); tg_chat = os.getenv("TG_CHAT", "")
    pb_token = os.getenv("PB_TOKEN", "")
    smtp_host = os.getenv("SMTP_HOST", ""); smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", ""); smtp_pass = os.getenv("SMTP_PASS", ""); email_to = os.getenv("EMAIL_TO", "")

    backoff = args.interval
    fail_count = 0
    max_backoff = 10*args.interval

    print(f"Monitoring {args.url} every {args.interval}s")
    while True:
        try:
            code = health_check(args.url, args.timeout)
            ts = time.strftime("%H:%M:%S")
            if 200 <= code < 400:
                if fail_count > 0:
                    msg = f"{ts} RECOVERY: {args.url} is back (status {code})"
                    notify_console(msg); notify_telegram(tg_token, tg_chat, msg)
                    notify_pushbullet(pb_token, "Uptime", msg)
                    notify_email(smtp_host, smtp_port, smtp_user, smtp_pass, email_to, "Uptime Recovery", msg)
                else:
                    print(f"{ts} OK: {code}")
                fail_count = 0
                backoff = args.interval
            else:
                fail_count += 1
                msg = f"{ts} FAIL#{fail_count}: status {code} at {args.url}"
                notify_console(msg); notify_telegram(tg_token, tg_chat, msg)
                notify_pushbullet(pb_token, "Uptime", msg)
                notify_email(smtp_host, smtp_port, smtp_user, smtp_pass, email_to, "Uptime Alert", msg)
                backoff = min(max_backoff, max(args.interval, int(backoff * 1.8)))
        except Exception as e:
            fail_count += 1
            msg = f"{time.strftime('%H:%M:%S')} ERROR#{fail_count}: {e}"
            notify_console(msg); notify_telegram(tg_token, tg_chat, msg)
            notify_pushbullet(pb_token, "Uptime", msg)
            notify_email(smtp_host, smtp_port, smtp_user, smtp_pass, email_to, "Uptime Error", msg)
            backoff = min(max_backoff, max(args.interval, int(backoff * 1.8)))
        time.sleep(backoff)

if __name__ == "__main__":
    main()
