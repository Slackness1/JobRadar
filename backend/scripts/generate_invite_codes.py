"""生成邀请码 + 插入 invite_codes 表。

跑法 (在 backend/ 下):
    PYTHONPATH=. .venv/bin/python scripts/generate_invite_codes.py --count 5 --note alpha-1

格式: JR-XXXXXXXX (3 前缀 + 8 random,去掉 O/0/I/1/L 等易混字符)。
8 char × 32 字母 = 32^8 ≈ 1.1T 组合,5 个码碰撞概率为 0。
"""
from __future__ import annotations

import argparse
import secrets
import sys
from datetime import datetime, timezone, timedelta

# 触发 .env.local 加载 + alembic upgrade
import app.config  # noqa: F401
from sqlalchemy import text
from app.database import SessionLocal


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉 O/0/I/1/L
_PREFIX = "JR-"


def _gen_code(length: int = 8) -> str:
    return _PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5, help="生成多少个 (默认 5)")
    parser.add_argument("--note", type=str, default="", help="备注,例如 'alpha-1'")
    parser.add_argument("--expires-days", type=int, default=0, help="多少天后过期 (0 = 永不)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires = (now + timedelta(days=args.expires_days)) if args.expires_days > 0 else None

    db = SessionLocal()
    try:
        # 先确保表在 (lifespan 没跑过的话 alembic upgrade 也没跑)
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                note TEXT,
                created_at TIMESTAMP NOT NULL,
                consumed_at TIMESTAMP,
                consumed_by_user_key TEXT,
                expires_at TIMESTAMP
            )
        """))
        db.commit()

        generated: list[str] = []
        for _ in range(args.count):
            for _ in range(10):  # 重试 10 次防碰撞
                code = _gen_code()
                exists = db.execute(
                    text("SELECT 1 FROM invite_codes WHERE code = :c"),
                    {"c": code},
                ).first()
                if exists is None:
                    db.execute(
                        text("""
                            INSERT INTO invite_codes (code, note, created_at, expires_at)
                            VALUES (:code, :note, :created_at, :expires_at)
                        """),
                        {
                            "code": code,
                            "note": args.note or None,
                            "created_at": now,
                            "expires_at": expires,
                        },
                    )
                    generated.append(code)
                    break
            else:
                print(f"WARN: 10 次重试都碰撞,跳过一个", file=sys.stderr)

        db.commit()
    finally:
        db.close()

    print(f"\n✓ 生成 {len(generated)} 个邀请码 (note={args.note!r}, expires={expires}):\n")
    for code in generated:
        print(f"    {code}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
