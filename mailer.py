import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

def send_dry_run_report(to_email, publisher_name, find_string, replace_string,
                        matched, skipped, total_units, job_id):
    """Dry run sonucunu AM'e email ile gönder"""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAIL] SMTP ayarları eksik — email gönderilmedi ({to_email})")
        return False

    approve_url = f"{APP_URL}?tab=approvals&job_id={job_id}"

    subject = f"ADSYIELD — {publisher_name} Dry Run: {matched} eslesme"

    html = f"""
    <div style="font-family: 'Courier New', monospace; background: #0d0d0d; color: #e0e0e0; padding: 32px; max-width: 600px;">
        <div style="border-bottom: 1px solid #222; padding-bottom: 16px; margin-bottom: 24px;">
            <span style="color: #00ff88; font-size: 18px; font-weight: bold; letter-spacing: 3px;">ADSYIELD</span>
            <span style="color: #555; font-size: 12px; margin-left: 12px;">Dry Run Raporu</span>
        </div>

        <table style="width: 100%; font-size: 14px; color: #ccc;">
            <tr><td style="color: #555; padding: 8px 0;">Publisher</td><td style="font-weight: bold; color: #fff;">{publisher_name}</td></tr>
            <tr><td style="color: #555; padding: 8px 0;">Taranan ad unit</td><td>{total_units}</td></tr>
            <tr><td style="color: #555; padding: 8px 0;">Eslesme</td><td style="color: #00ff88; font-weight: bold;">{matched}</td></tr>
            <tr><td style="color: #555; padding: 8px 0;">Atlanan</td><td>{skipped}</td></tr>
            <tr><td style="color: #555; padding: 8px 0;">Find</td><td><code style="background: #1a1a1a; color: #ff6b6b; padding: 2px 8px;">{find_string}</code></td></tr>
            <tr><td style="color: #555; padding: 8px 0;">Replace</td><td><code style="background: #1a1a1a; color: #00ff88; padding: 2px 8px;">{replace_string}</code></td></tr>
        </table>

        <div style="margin-top: 32px; text-align: center;">
            <a href="{approve_url}"
               style="display: inline-block; padding: 12px 32px; border: 1px solid #00ff88; color: #00ff88;
                      text-decoration: none; font-family: monospace; font-size: 14px; letter-spacing: 1px;">
                Sonuclari Gor ve Onayla
            </a>
        </div>

        <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #222; color: #555; font-size: 11px;">
            Bu onay 48 saat icerisinde gecerlidir. Onaylanmazsa hicbir islem yapilmaz.
            <br>Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[MAIL] Gonderildi: {to_email} — {publisher_name} ({matched} eslesme)")
        return True
    except Exception as e:
        print(f"[MAIL] HATA: {e}")
        return False
