import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def is_smtp_configured() -> bool:
    return bool(SMTP_EMAIL and SMTP_PASSWORD)


def send_credentials_email(to_email: str, full_name: str, email: str, password: str) -> bool:
    if not is_smtp_configured():
        return False

    html = f"""\
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:520px;margin:0 auto;padding:32px;background:#fff;border-radius:12px;border:1px solid #e5e7eb">
      <div style="text-align:center;margin-bottom:24px">
        <div style="display:inline-block;background:#7c3aed;color:#fff;font-weight:700;font-size:18px;padding:10px 18px;border-radius:10px;letter-spacing:1px">FD</div>
        <div style="margin-top:8px;font-size:20px;font-weight:700;color:#1a1a2e">Fintech Drive</div>
        <div style="font-size:13px;color:#6b7280">Система андеррайтинга</div>
      </div>
      <div style="margin-bottom:20px;font-size:15px;color:#374151">
        Здравствуйте, <strong>{full_name}</strong>!
      </div>
      <div style="font-size:14px;color:#374151;margin-bottom:16px">
        Для вас создан аккаунт в системе андеррайтинга Fintech Drive. Ваши данные для входа:
      </div>
      <div style="background:#f3f0ff;border-radius:8px;padding:16px 20px;margin-bottom:20px">
        <div style="font-size:13px;color:#6b7280;margin-bottom:4px">Email (логин)</div>
        <div style="font-size:15px;font-weight:600;color:#1a1a2e;margin-bottom:12px">{email}</div>
        <div style="font-size:13px;color:#6b7280;margin-bottom:4px">Пароль</div>
        <div style="font-size:15px;font-weight:600;color:#1a1a2e;font-family:monospace;letter-spacing:0.5px">{password}</div>
      </div>
      <div style="font-size:13px;color:#6b7280;margin-bottom:8px">
        Рекомендуем сменить пароль после первого входа.
      </div>
      <div style="border-top:1px solid #e5e7eb;margin-top:24px;padding-top:16px;font-size:12px;color:#9ca3af;text-align:center">
        Fintech Drive &copy; 2026. Это письмо отправлено автоматически.
      </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Fintech Drive — Ваши данные для входа"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception:
        return False
