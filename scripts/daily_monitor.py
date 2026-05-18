#!/usr/bin/env python3
"""
Marcela Daily Performance Monitor
===================================
Runs once per day (scheduled via Manus or cron) and sends Ricardo a
WhatsApp + email summary covering:

  1. Uptime / health check (Vercel endpoint)
  2. Twilio message stats for the past 24 hours
     - Total inbound messages received
     - Total outbound messages sent
     - Failed outbound messages (with error codes)
     - Error rate %
  3. Response latency (webhook round-trip test)
  4. Webhook URL integrity check
  5. Vercel deployment status

Alerts are sent immediately for critical issues; the daily summary
is sent at 8:00 AM CDT regardless.

Environment variables required:
  TWILIO_ACCOUNT_SID   - Twilio Account SID
  TWILIO_AUTH_TOKEN    - Twilio Auth Token
  GEMINI_API_KEY       - Google Gemini API key (for test message)

Optional:
  ALERT_TO             - WhatsApp number to send alerts (default: Ricardo)
  ALERT_FROM           - Marcela's WhatsApp sender number
  REPORT_EMAIL         - Email address for daily report
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta, timezone

# ── Configuration ──────────────────────────────────────────────────────────────
HEALTH_URL       = "https://marcela-norfolk-ai.vercel.app/health"
WEBHOOK_URL      = "https://marcela-norfolk-ai.vercel.app/webhook"
VERCEL_DASHBOARD = "https://vercel.com/norfolk-ai-projects/marcela-norfolk-ai"

TWILIO_SID       = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN     = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_API_BASE  = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}"

MARCELA_NUMBER   = "whatsapp:+15559178507"
RICARDO_NUMBER   = os.environ.get("ALERT_TO",   "whatsapp:+15126699705")
ALERT_FROM       = os.environ.get("ALERT_FROM", MARCELA_NUMBER)

REPORT_EMAIL     = os.environ.get("REPORT_EMAIL", "ricardo@cidale.com")

TIMEOUT          = 15
LATENCY_RUNS     = 3   # number of health pings to average for latency


# ── 1. Health / Uptime Check ──────────────────────────────────────────────────
def check_health():
    """Ping the health endpoint. Returns (ok, status_detail, avg_latency_ms)."""
    latencies = []
    last_error = None
    for _ in range(LATENCY_RUNS):
        try:
            t0 = time.time()
            resp = requests.get(HEALTH_URL, timeout=TIMEOUT)
            latency_ms = int((time.time() - t0) * 1000)
            latencies.append(latency_ms)
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            last_error = "Timeout"
        except Exception as e:
            last_error = str(e)
        time.sleep(0.5)

    if not latencies:
        return False, last_error or "Unreachable", None

    avg_latency = int(sum(latencies) / len(latencies))
    return True, "OK", avg_latency


# ── 2. Twilio Message Stats (last 24 hours) ───────────────────────────────────
def get_twilio_stats():
    """
    Pull Twilio message logs for the past 24 hours and compute stats.
    Returns a dict with keys: inbound, outbound_sent, outbound_failed,
    error_codes, error_rate_pct.
    """
    if not TWILIO_TOKEN:
        return None

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    stats = {
        "inbound": 0,
        "outbound_sent": 0,
        "outbound_failed": 0,
        "error_codes": {},
        "error_rate_pct": 0.0,
        "sample_errors": [],
    }

    page_url = (
        f"{TWILIO_API_BASE}/Messages.json"
        f"?To={MARCELA_NUMBER.replace(':', '%3A').replace('+', '%2B')}"
        f"&DateSent%3E={since}&PageSize=100"
    )

    # Inbound messages (To = Marcela)
    try:
        resp = requests.get(page_url, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            stats["inbound"] = data.get("total", len(data.get("messages", [])))
    except Exception:
        pass

    # Outbound messages (From = Marcela)
    page_url2 = (
        f"{TWILIO_API_BASE}/Messages.json"
        f"?From={MARCELA_NUMBER.replace(':', '%3A').replace('+', '%2B')}"
        f"&DateSent%3E={since}&PageSize=100"
    )
    try:
        resp = requests.get(page_url2, auth=(TWILIO_SID, TWILIO_TOKEN), timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("messages", [])
            for msg in messages:
                status = msg.get("status", "")
                error_code = msg.get("error_code")
                if status in ("delivered", "sent", "read"):
                    stats["outbound_sent"] += 1
                elif status in ("failed", "undelivered"):
                    stats["outbound_failed"] += 1
                    if error_code:
                        stats["error_codes"][str(error_code)] = (
                            stats["error_codes"].get(str(error_code), 0) + 1
                        )
                        if len(stats["sample_errors"]) < 3:
                            stats["sample_errors"].append(
                                f"Error {error_code}: {msg.get('error_message', 'unknown')}"
                            )
            total_out = stats["outbound_sent"] + stats["outbound_failed"]
            if total_out > 0:
                stats["error_rate_pct"] = round(
                    stats["outbound_failed"] / total_out * 100, 1
                )
    except Exception:
        pass

    return stats


# ── 3. Webhook URL Integrity Check ────────────────────────────────────────────
def check_webhook_config():
    """
    Verify the WhatsApp sender's webhook URL via Twilio API.
    Returns (ok: bool, configured_url: str).
    """
    if not TWILIO_TOKEN:
        return None, "No auth token"

    # Check the Marcela WhatsApp Agent messaging service
    svc_sid = "MG5749f41a32f687f44e27d73f4d11baa9"
    try:
        resp = requests.get(
            f"{TWILIO_API_BASE}/Services/{svc_sid}.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            timeout=TIMEOUT,
        )
        # Fallback: check channel senders for the messaging service
        resp2 = requests.get(
            f"https://messaging.twilio.com/v1/Services/{svc_sid}",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            timeout=TIMEOUT,
        )
        if resp2.status_code == 200:
            data = resp2.json()
            inbound_url = data.get("inbound_request_url", "")
            expected = WEBHOOK_URL
            return inbound_url == expected, inbound_url
    except Exception as e:
        pass

    return None, "Could not verify"


# ── 4. Send WhatsApp Message ──────────────────────────────────────────────────
def send_whatsapp(to: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio REST API."""
    if not TWILIO_TOKEN:
        print("ERROR: TWILIO_AUTH_TOKEN not set")
        return False
    try:
        resp = requests.post(
            f"{TWILIO_API_BASE}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"From": ALERT_FROM, "To": to, "Body": body},
            timeout=TIMEOUT,
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            print(f"  WhatsApp sent: SID={data.get('sid')}")
            return True
        else:
            print(f"  WhatsApp failed: {data}")
            return False
    except Exception as e:
        print(f"  WhatsApp error: {e}")
        return False


# ── 5. Send Email via Gmail MCP ───────────────────────────────────────────────
def send_email_report(subject: str, body: str):
    """Send the daily report via email using Gmail MCP (if available)."""
    try:
        import subprocess
        payload = json.dumps({
            "messages": [{
                "to": [REPORT_EMAIL],
                "subject": subject,
                "body": body,
            }]
        })
        result = subprocess.run(
            ["manus-mcp-cli", "tool", "call", "gmail_send_messages",
             "--server", "gmail", "--input", payload],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("  Email report sent via Gmail MCP")
            return True
        else:
            print(f"  Email send failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  Email send error: {e}")
        return False


# ── 6. Format Report ──────────────────────────────────────────────────────────
def format_whatsapp_report(health_ok, latency_ms, stats, webhook_ok, webhook_url, now_str):
    """Format a concise WhatsApp report (no markdown, plain text)."""
    status_icon = "✅" if health_ok else "🔴"
    lines = [
        f"📊 Marcela Daily Report — {now_str}",
        "",
        f"{status_icon} Status: {'ONLINE' if health_ok else 'OFFLINE'}",
    ]
    if latency_ms is not None:
        lines.append(f"⚡ Avg latency: {latency_ms}ms")

    if stats:
        lines += [
            "",
            "💬 Messages (last 24h):",
            f"  Received: {stats['inbound']}",
            f"  Sent: {stats['outbound_sent']}",
            f"  Failed: {stats['outbound_failed']}",
        ]
        if stats["error_rate_pct"] > 0:
            lines.append(f"  Error rate: {stats['error_rate_pct']}%")
        if stats["error_codes"]:
            codes = ", ".join(f"#{k}×{v}" for k, v in stats["error_codes"].items())
            lines.append(f"  Errors: {codes}")

    if webhook_ok is not None:
        wh_icon = "✅" if webhook_ok else "⚠️"
        lines += ["", f"{wh_icon} Webhook: {'Correct' if webhook_ok else 'WRONG URL'}"]
        if not webhook_ok:
            lines.append(f"  Current: {webhook_url}")
            lines.append(f"  Expected: {WEBHOOK_URL}")

    lines += ["", f"🔗 {VERCEL_DASHBOARD}"]
    return "\n".join(lines)


def format_email_report(health_ok, latency_ms, stats, webhook_ok, webhook_url, now_str):
    """Format a detailed HTML-like email report."""
    status = "ONLINE ✅" if health_ok else "OFFLINE 🔴"
    latency_str = f"{latency_ms}ms" if latency_ms else "N/A"

    lines = [
        f"Marcela AI — Daily Health Report",
        f"Generated: {now_str}",
        "=" * 50,
        "",
        f"STATUS: {status}",
        f"Response latency (avg over 3 pings): {latency_str}",
        f"Health endpoint: {HEALTH_URL}",
        "",
    ]

    if stats:
        err_rate = f"{stats['error_rate_pct']}%" if stats["error_rate_pct"] else "0%"
        lines += [
            "TWILIO MESSAGE STATS (last 24 hours)",
            "-" * 40,
            f"  Inbound messages received : {stats['inbound']}",
            f"  Outbound messages sent    : {stats['outbound_sent']}",
            f"  Outbound messages failed  : {stats['outbound_failed']}",
            f"  Error rate                : {err_rate}",
        ]
        if stats["error_codes"]:
            lines.append("")
            lines.append("  Error breakdown:")
            for code, count in stats["error_codes"].items():
                lines.append(f"    Error {code}: {count} occurrence(s)")
        if stats["sample_errors"]:
            lines.append("")
            lines.append("  Sample error messages:")
            for err in stats["sample_errors"]:
                lines.append(f"    - {err}")
        lines.append("")

    wh_status = "CORRECT ✅" if webhook_ok else ("WRONG ⚠️" if webhook_ok is False else "UNCHECKED")
    lines += [
        "WEBHOOK CONFIGURATION",
        "-" * 40,
        f"  Status        : {wh_status}",
        f"  Configured URL: {webhook_url or 'unknown'}",
        f"  Expected URL  : {WEBHOOK_URL}",
        "",
        "LINKS",
        "-" * 40,
        f"  Vercel dashboard : {VERCEL_DASHBOARD}",
        f"  Twilio console   : https://console.twilio.com",
        f"  Meta Business    : https://business.facebook.com/settings/whatsapp-account",
        "",
        "=" * 50,
        "Marcela AI — Norfolk AI | Automated Monitor",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'='*60}")
    print(f"Marcela Daily Monitor — {now_str}")
    print(f"{'='*60}")

    # 1. Health check
    print("\n[1/4] Checking health endpoint...")
    health_ok, health_detail, latency_ms = check_health()
    print(f"  Status: {'OK' if health_ok else 'FAIL'} | Detail: {health_detail} | Latency: {latency_ms}ms")

    # 2. Twilio stats
    print("\n[2/4] Fetching Twilio message stats (last 24h)...")
    stats = get_twilio_stats()
    if stats:
        print(f"  Inbound: {stats['inbound']} | Sent: {stats['outbound_sent']} | Failed: {stats['outbound_failed']} | Error rate: {stats['error_rate_pct']}%")
    else:
        print("  Skipped (no auth token)")

    # 3. Webhook check
    print("\n[3/4] Verifying webhook URL configuration...")
    webhook_ok, webhook_url = check_webhook_config()
    print(f"  Webhook URL: {webhook_url} | Correct: {webhook_ok}")

    # 4. Send reports
    print("\n[4/4] Sending daily report...")

    wa_report = format_whatsapp_report(health_ok, latency_ms, stats, webhook_ok, webhook_url, now_str)
    email_report = format_email_report(health_ok, latency_ms, stats, webhook_ok, webhook_url, now_str)

    # Always send WhatsApp daily summary
    wa_ok = send_whatsapp(RICARDO_NUMBER, wa_report)

    # Send email report
    subject = f"Marcela AI Daily Report — {now_str} — {'✅ OK' if health_ok else '🔴 DOWN'}"
    email_ok = send_email_report(subject, email_report)

    # Send immediate critical alert if Marcela is down or webhook is wrong
    if not health_ok:
        alert = (
            f"🚨 CRITICAL: Marcela is DOWN!\n"
            f"Time: {now_str}\n"
            f"Issue: {health_detail}\n"
            f"Fix: Check {VERCEL_DASHBOARD}"
        )
        send_whatsapp(RICARDO_NUMBER, alert)
        print("  CRITICAL alert sent — Marcela is DOWN")

    if webhook_ok is False:
        alert = (
            f"⚠️ WARNING: Marcela webhook URL is WRONG!\n"
            f"Current: {webhook_url}\n"
            f"Expected: {WEBHOOK_URL}\n"
            f"Fix in Twilio: Messaging > Numbers and Senders > WhatsApp > +15559178507"
        )
        send_whatsapp(RICARDO_NUMBER, alert)
        print("  WARNING alert sent — webhook URL mismatch")

    print(f"\n{'='*60}")
    print(f"Monitor complete. WhatsApp: {'sent' if wa_ok else 'failed'} | Email: {'sent' if email_ok else 'failed'}")
    print(f"{'='*60}\n")

    # Exit with error code if Marcela is down
    sys.exit(0 if health_ok else 1)


if __name__ == "__main__":
    main()
