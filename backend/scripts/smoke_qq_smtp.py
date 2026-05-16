"""QQ SMTP 连通烟雾测试 — 给自己发一封测试邮件。

跑法 (backend/ 下):
    PYTHONPATH=. .venv/bin/python scripts/smoke_qq_smtp.py [收件邮箱]
    默认收件人 = 发件邮箱 (给自己发,确认 SMTP 配置对)
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr

import app.config  # noqa: F401  触发 .env.local


def main() -> int:
    host = os.environ.get("QQ_SMTP_HOST", "smtp.qq.com")
    port = int(os.environ.get("QQ_SMTP_PORT", "465"))
    user = os.environ.get("QQ_SMTP_USER", "")
    auth_code = os.environ.get("QQ_SMTP_AUTH_CODE", "")
    sender_name = os.environ.get("QQ_SMTP_SENDER_NAME", "JobRadar")

    if not user or not auth_code:
        print("FAIL: QQ_SMTP_USER 或 QQ_SMTP_AUTH_CODE 未设置", file=sys.stderr)
        return 1

    to_email = sys.argv[1] if len(sys.argv) > 1 else user

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, user))
    msg["To"] = to_email
    msg["Subject"] = "[JobRadar] SMTP 烟雾测试"
    msg.set_content(
        "这是 JobRadar 账号系统的 SMTP 连通测试邮件。\n\n"
        "如果你收到这封,说明发件配置已通,可以开始走"
        "邮箱验证码 + 邀请码注册的流程了。\n\n"
        "—— JobRadar 内测"
    )

    print(f"[{host}:{port}] 发件人={user} → 收件人={to_email}")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
            smtp.login(user, auth_code)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        print(f"FAIL · 认证失败: {exc}", file=sys.stderr)
        print("  → 检查 QQ_SMTP_AUTH_CODE 是不是 16 位授权码 (不是 QQ 密码)", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL · {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("✓ 发送成功 — 去收件箱看,可能在垃圾邮件里")
    return 0


if __name__ == "__main__":
    sys.exit(main())
