"""Send listing summaries — Resend API (preferred) or SMTP fallback."""
from __future__ import annotations

import html
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests

import config


def _row_html(L: dict[str, Any]) -> str:
    price = L.get("price_display") or f"${L.get('price', 0):,}"
    if L.get("listing_kind") == "rent" and not L.get("price_display"):
        price = f"${L.get('price', 0):,}/mo"
    url = html.escape(L.get("url") or "#")
    title = html.escape(L.get("title") or "")
    addr = html.escape(f"{L.get('address', '')}, {L.get('city', '')}")
    return f"""<tr>
<td style="padding:10px;border-bottom:1px solid #eee">{title}</td>
<td style="padding:10px;border-bottom:1px solid #eee">{price}</td>
<td style="padding:10px;border-bottom:1px solid #eee">{L.get('beds')}bd</td>
<td style="padding:10px;border-bottom:1px solid #eee">{addr}</td>
<td style="padding:10px;border-bottom:1px solid #eee"><a href="{url}">Link</a></td>
</tr>"""


def _build_html(listings: list[dict[str, Any]]) -> str:
    rows = "".join(_row_html(L) for L in listings[:25])
    return f"""<!DOCTYPE html><html><body style="font-family:system-ui,sans-serif">
<p>Here are <strong>{len(listings)}</strong> properties from Aria.</p>
<table style="border-collapse:collapse;width:100%;max-width:720px">
<thead><tr style="background:#f5f5f5">
<th align="left">Title</th><th>Price</th><th>Beds</th><th>Address</th><th></th>
</tr></thead><tbody>{rows}</tbody></table>
</body></html>"""


def _send_resend(to_addr: str, subject: str, html_body: str) -> tuple[bool, str]:
    key = (config.RESEND_API_KEY or "").strip()
    if not key:
        return False, ""
    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "from": config.RESEND_FROM,
            "to": [to_addr.strip()],
            "subject": subject,
            "html": html_body,
        },
        timeout=60,
    )
    if r.status_code in (200, 201):
        return True, f"Sent via Resend to {to_addr.strip()}."
    try:
        err = r.json()
        msg = err.get("message") or err.get("name") or r.text
    except Exception:
        msg = r.text[:200]
    return False, f"Resend error {r.status_code}: {msg}"


def _send_smtp(to_addr: str, subject: str, html_body: str) -> tuple[bool, str]:
    user = (config.SMTP_USER or "").strip()
    password = (config.SMTP_PASS or "").strip().replace(" ", "")
    if not user or not password:
        return False, ""

    frm = (config.SMTP_FROM or user).strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = to_addr.strip()
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    payload = msg.as_string()

    def _ssl() -> None:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, 465, context=ctx, timeout=45) as s:
            s.login(user, password)
            s.sendmail(frm, [to_addr.strip()], payload)

    def _tls() -> None:
        with smtplib.SMTP(config.SMTP_HOST, 587, timeout=45) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, password)
            s.sendmail(frm, [to_addr.strip()], payload)

    try:
        _ssl()
        return True, f"Sent {to_addr.strip()} (SMTP)."
    except Exception as e1:
        try:
            _tls()
            return True, f"Sent {to_addr.strip()} (SMTP 587)."
        except Exception as e2:
            return False, f"SMTP failed: {str(e1)[:100]} / {str(e2)[:80]}"


def send_listings_email(
    to_addr: str,
    listings: list[dict[str, Any]],
    subject: str = "Your property list from Aria",
) -> tuple[bool, str]:
    if not listings:
        return False, "No listings to send—run a search first."

    body_html = _build_html(listings)

    if config.RESEND_API_KEY:
        ok, note = _send_resend(to_addr, subject, body_html)
        if ok:
            return True, note + f" ({len(listings)} listings)"
        # fall through to SMTP if Resend failed and SMTP configured
        if config.SMTP_USER and config.SMTP_PASS:
            ok2, note2 = _send_smtp(to_addr, subject, body_html)
            if ok2:
                return True, note2
        return False, note + " Add RESEND_FROM with a verified domain, or fix SMTP as backup."

    user = (config.SMTP_USER or "").strip()
    password = (config.SMTP_PASS or "").strip().replace(" ", "")
    if not user or not password:
        return (
            False,
            "No mailer configured. Set **RESEND_API_KEY** in backend/.env (recommended) "
            "or SMTP_USER + SMTP_PASS. GET /health/smtp",
        )

    ok, note = _send_smtp(to_addr, subject, body_html)
    if ok:
        return True, f"Sent {len(listings)} listings to {to_addr.strip()}."
    return False, note