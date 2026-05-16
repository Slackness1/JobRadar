"""QQ SMTP 发邮件 wrapper。

只支持 QQ 邮箱 SMTP_SSL。配置在 backend/.env.local:
  QQ_SMTP_HOST=smtp.qq.com
  QQ_SMTP_PORT=465
  QQ_SMTP_USER=1067407386@qq.com
  QQ_SMTP_AUTH_CODE=<16 位授权码 from QQ 邮箱设置,不是 QQ 密码>
  QQ_SMTP_SENDER_NAME=JobRadar
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _smtp_config() -> tuple[str, int, str, str, str]:
    host = os.environ.get("QQ_SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("QQ_SMTP_PORT", "465"))
    user = os.environ.get("QQ_SMTP_USER", "")
    code = os.environ.get("QQ_SMTP_AUTH_CODE", "")
    sender_name = os.environ.get("QQ_SMTP_SENDER_NAME", "JobRadar")
    return host, port, user, code, sender_name


def is_configured() -> bool:
    _, _, user, code, _ = _smtp_config()
    return bool(user and code)


def send_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    timeout_seconds: int = 30,
) -> None:
    """发一封邮件。失败抛异常,调用方 catch 后做"邮件发送失败,验证码已打印到 console" 的降级。"""
    host, port, user, code, sender_name = _smtp_config()
    if not user or not code:
        raise RuntimeError("QQ_SMTP_USER / QQ_SMTP_AUTH_CODE 未配置")

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, user))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout_seconds) as smtp:
        smtp.login(user, code)
        smtp.send_message(msg)
    logger.info("email sent · to=%s subject=%s", to_email, subject)


def send_verification_code(*, to_email: str, code: str) -> None:
    """发 6 位邮箱验证码 (注册流程)。"""
    subject = f"[JobRadar] 邮箱验证码 {code}"
    body_text = (
        f"你好,\n\n你的 JobRadar 注册验证码是: {code}\n\n"
        f"验证码 10 分钟内有效。如果不是你本人操作,请忽略本邮件。\n\n"
        f"—— JobRadar 内测"
    )
    body_html = f"""<!DOCTYPE html>
<html><body style="font-family: -apple-system, sans-serif; color: #2c2925; line-height: 1.6;">
  <div style="max-width: 480px; margin: 0 auto; padding: 32px;">
    <h2 style="color: #c96442; margin: 0 0 16px;">JobRadar 邮箱验证</h2>
    <p>你的注册验证码是:</p>
    <div style="font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 700;
                letter-spacing: 8px; padding: 16px 24px; background: #f5f4ed;
                border-radius: 8px; text-align: center; color: #c96442;">{code}</div>
    <p style="color: #8a8276; font-size: 13px; margin-top: 24px;">
      验证码 10 分钟内有效。如果不是你本人操作,请忽略本邮件。
    </p>
    <p style="color: #8a8276; font-size: 12px; margin-top: 32px;">— JobRadar 内测</p>
  </div>
</body></html>"""
    send_email(
        to_email=to_email, subject=subject,
        body_text=body_text, body_html=body_html,
    )
