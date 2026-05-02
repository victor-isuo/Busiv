"""
Email Delivery — Busiv
========================
Delivers formatted intelligence briefings via Gmail SMTP.

HTML email with:
- Priority alert banner (if regulatory/urgent signal detected)
- Section cards per signal category
- Source citations as clickable links
- Mobile-responsive layout

Gmail setup required:
1. Enable 2FA on Gmail account
2. Generate App Password: Google Account → Security → App Passwords
3. Use the 16-char app password as SMTP_PASSWORD in .env
   (not your Gmail login password)
"""

import os
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
load_dotenv()

import aiosmtplib

logger = logging.getLogger(__name__)


def _build_html(briefing: dict) -> str:
    """Build the HTML email body from briefing data."""

    date          = briefing.get("date", datetime.utcnow().strftime("%B %d, %Y"))
    headline      = briefing.get("headline", "Nigerian Fintech Intelligence Briefing")
    exec_summary  = briefing.get("executive_summary", "")
    priority_alert = briefing.get("priority_alert", {})
    sections      = briefing.get("sections", {})
    companies     = briefing.get("companies_active_today", [])
    article_count = briefing.get("article_count", 0)

    # Priority alert banner
    alert_html = ""
    if priority_alert.get("has_alert") and priority_alert.get("alert_text"):
        alert_type = priority_alert.get("alert_type", "regulatory").upper()
        alert_html = f"""
        <div style="background:#c0392b;padding:16px 24px;margin-bottom:24px;">
          <div style="font-family:monospace;font-size:10px;letter-spacing:2px;
                      color:rgba(255,255,255,0.7);margin-bottom:6px;">
            ⚠ PRIORITY ALERT — {alert_type}
          </div>
          <div style="font-family:Georgia,serif;font-size:16px;color:#fff;
                      font-style:italic;line-height:1.5;">
            {priority_alert['alert_text']}
          </div>
        </div>"""

    # Section colours
    section_colors = {
        "regulatory": "#c0392b",
        "product":    "#1a5276",
        "market":     "#1e8449",
        "hiring":     "#784212",
    }

    section_labels = {
        "regulatory": "Regulatory",
        "product":    "Product",
        "market":     "Market",
        "hiring":     "Hiring",
    }

    sections_html = ""
    for key in ["regulatory", "product", "market", "hiring"]:
        section = sections.get(key, {})
        if not section.get("has_content"):
            continue

        color   = section_colors.get(key, "#1a3a5c")
        label   = section_labels.get(key, key.title())
        summary = section.get("summary", "")

        findings_html = ""
        for f in section.get("findings", []):
            url      = f.get("url", "#")
            citation = f.get("citation", "")
            sig      = f.get("significance", "MEDIUM")
            companies_list = ", ".join(f.get("companies_mentioned", []))

            sig_color = {"HIGH": "#c0392b", "MEDIUM": "#b7950b", "LOW": "#1e8449"}.get(sig, "#555")

            findings_html += f"""
            <div style="border-left:2px solid {color};padding:12px 16px;
                        margin-bottom:12px;background:#fafafa;">
              <div style="font-family:Georgia,serif;font-size:15px;
                          font-weight:600;color:#0f1c2e;margin-bottom:6px;">
                {f.get('title', '')}
              </div>
              <div style="font-size:13px;color:#444;line-height:1.65;margin-bottom:8px;">
                {f.get('detail', '')}
              </div>
              <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
                <span style="font-family:monospace;font-size:9px;letter-spacing:1px;
                             color:{sig_color};border:1px solid {sig_color};
                             padding:2px 8px;">{sig}</span>
                {f'<span style="font-size:11px;color:#888;">{companies_list}</span>' if companies_list else ''}
                {f'<a href="{url}" style="font-size:11px;color:{color};text-decoration:none;">Read → {citation}</a>' if url != "#" else f'<span style="font-size:11px;color:#888;">{citation}</span>'}
              </div>
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:28px;">
          <div style="border-top:2px solid {color};padding-top:14px;margin-bottom:12px;">
            <span style="font-family:monospace;font-size:9px;letter-spacing:2px;
                         color:{color};text-transform:uppercase;">{label}</span>
          </div>
          <div style="font-family:Georgia,serif;font-size:14px;font-style:italic;
                      color:#555;line-height:1.7;margin-bottom:14px;">{summary}</div>
          {findings_html}
        </div>"""

    companies_html = ""
    if companies:
        chips = "".join(
            f'<span style="font-family:monospace;font-size:9px;letter-spacing:1px;'
            f'color:#1a3a5c;border:1px solid #ccd8e8;padding:3px 10px;'
            f'margin:3px;display:inline-block;">{c}</span>'
            for c in companies
        )
        companies_html = f"""
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid #e8e0d0;">
          <div style="font-family:monospace;font-size:9px;letter-spacing:2px;
                      color:#999;margin-bottom:10px;">COMPANIES ACTIVE TODAY</div>
          <div>{chips}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0ead8;font-family:Georgia,serif;">
<div style="max-width:640px;margin:0 auto;padding:20px 0;">

  <!-- Header -->
  <div style="background:#0f1c2e;padding:28px 32px;border-bottom:2px solid #b8943a;">
    <div style="font-family:monospace;font-size:9px;letter-spacing:3px;
                color:rgba(184,148,58,0.7);margin-bottom:8px;">
      BUSIV · NIGERIAN FINTECH INTELLIGENCE
    </div>
    <div style="font-family:Georgia,serif;font-size:11px;font-style:italic;
                color:rgba(248,244,236,0.5);">
      {date} · {article_count} articles analysed
    </div>
  </div>

  <!-- Headline -->
  <div style="background:#fff;padding:28px 32px;border-bottom:1px solid #e8e0d0;">
    {alert_html}
    <div style="font-family:Georgia,serif;font-size:22px;font-weight:600;
                color:#0f1c2e;line-height:1.25;margin-bottom:14px;font-style:italic;">
      {headline}
    </div>
    <div style="font-size:14px;color:#555;line-height:1.8;">
      {exec_summary}
    </div>
  </div>

  <!-- Sections -->
  <div style="background:#fff;padding:28px 32px;">
    {sections_html}
    {companies_html}
  </div>

  <!-- Footer -->
  <div style="background:#0f1c2e;padding:16px 32px;text-align:center;">
    <div style="font-family:monospace;font-size:8px;letter-spacing:2px;
                color:rgba(248,244,236,0.3);">
      BUSIV · AI-GENERATED INTELLIGENCE · NOT FINANCIAL ADVICE
    </div>
  </div>

</div>
</body></html>"""


async def deliver_briefing(briefing: dict, to_email: str) -> bool:
    """
    Send formatted HTML briefing via Gmail SMTP.

    Args:
        briefing:  Structured briefing dict from synthesis agent
        to_email:  Recipient email address

    Returns:
        True if delivered successfully
    """
    smtp_host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.getenv("SMTP_PORT", "587"))
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email    = os.getenv("EMAIL_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        logger.warning("SMTP credentials not configured — skipping email delivery")
        return False

    date     = briefing.get("date", datetime.utcnow().strftime("%B %d, %Y"))
    subject  = f"Busiv · Nigerian Fintech Intelligence · {date}"
    has_alert = briefing.get("priority_alert", {}).get("has_alert", False)
    if has_alert:
        subject = f"⚠ {subject}"

    html_body = _build_html(briefing)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_email
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            start_tls=True,
            username=smtp_user,
            password=smtp_password,
        )
        logger.info(f"Email delivered to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Email delivery failed: {e}")
        return False




