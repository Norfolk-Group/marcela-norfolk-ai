#!/usr/bin/env python3
"""
Marcela Health Monitor
Checks the Marcela WhatsApp agent health endpoint and sends a WhatsApp alert
via Twilio if the service is down.

Run via cron or scheduled task every hour.
"""

import os
import sys
import requests
import json
from datetime import datetime

# Configuration
HEALTH_URL = "https://marcela-norfolk-ai.vercel.app/health"
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
ALERT_TO = os.environ.get("ALERT_TO", "whatsapp:+15126699705")   # Ricardo's number
ALERT_FROM = os.environ.get("ALERT_FROM", "whatsapp:+15559178507")  # Marcela's number
TIMEOUT = 15


def check_health():
    """Check Marcela's health endpoint. Returns (ok: bool, detail: str)."""
    try:
        resp = requests.get(HEALTH_URL, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                return True, f"OK — {data}"
            return False, f"Unhealthy response: {data}"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        return False, "Timeout after 15 seconds"
    except Exception as e:
        return False, f"Error: {e}"


def send_whatsapp_alert(message: str):
    """Send a WhatsApp alert via Twilio REST API."""
    if not TWILIO_AUTH_TOKEN:
        print("ERROR: TWILIO_AUTH_TOKEN not set — cannot send alert")
        return False

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    try:
        resp = requests.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": ALERT_FROM, "To": ALERT_TO, "Body": message},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            print(f"Alert sent: SID={data.get('sid')}")
            return True
        else:
            print(f"Alert failed: {data}")
            return False
    except Exception as e:
        print(f"Alert send error: {e}")
        return False


def main():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    ok, detail = check_health()

    if ok:
        print(f"[{now}] Marcela is healthy: {detail}")
        sys.exit(0)
    else:
        msg = (
            f"⚠️ *Marcela is DOWN* ⚠️\n"
            f"Time: {now}\n"
            f"Issue: {detail}\n"
            f"URL: {HEALTH_URL}\n\n"
            f"Check Vercel dashboard: https://vercel.com/norfolk-ai-projects/marcela-norfolk-ai"
        )
        print(f"[{now}] ALERT — Marcela is DOWN: {detail}")
        send_whatsapp_alert(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
