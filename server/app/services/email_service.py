import logging
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, code: str) -> bool:
    if not settings.smtp_host:
        logger.warning("SMTP not configured, skipping email send")
        return False

    html = f"""\
<div style="max-width:480px;margin:0 auto;padding:32px 24px;font-family:'Segoe UI',Arial,sans-serif;background:#f9fafb;border-radius:12px;">
  <div style="text-align:center;margin-bottom:24px;">
    <h2 style="color:#1f2937;margin:0;">FriendAuto</h2>
    <p style="color:#6b7280;font-size:14px;margin:4px 0 0;">邮箱验证码</p>
  </div>
  <div style="background:#fff;border-radius:8px;padding:32px 24px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
    <p style="color:#374151;font-size:15px;margin:0 0 20px;">您的验证码为：</p>
    <div style="background:#f3f4f6;border-radius:8px;padding:16px 32px;display:inline-block;">
      <span style="font-size:36px;font-weight:700;letter-spacing:8px;color:#2563eb;font-family:monospace;">{code}</span>
    </div>
    <p style="color:#9ca3af;font-size:13px;margin:20px 0 0;">验证码有效期为 10 分钟，请勿泄露给他人。</p>
  </div>
  <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:20px;">本邮件由系统自动发送，请勿回复。</p>
</div>"""

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"您的 FriendAuto 验证码：{code}"
    msg["From"] = f"{settings.smtp_from_name or 'FriendAuto'} <{settings.smtp_user}>"
    msg["To"] = email

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_port == 465,
        )
        logger.info("Verification email sent to %s", email)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", email, e)
        return False
