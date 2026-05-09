from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, 'connect')
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    # 5s busy_timeout 在 tier-crawl + API 并发时不够（2026-05-09 09:00 cron
    # 在第一次 INSERT 字节跳动 行就被锁挂全部 5 个 tier block 失败）。
    # 30s 给 tier-crawl 写入留足缓冲，正常 API 不会真等满 30s。
    cursor.execute('PRAGMA busy_timeout=30000')
    cursor.close()
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
