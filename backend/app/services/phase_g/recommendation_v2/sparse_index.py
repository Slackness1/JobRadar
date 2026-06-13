"""S1 稀疏召回 — SQLite FTS5 全文检索(BM25)。

把 Vespa/ES 的 BM25 塞进我们 SQLite 重量级:FTS5 是 SQLite 内置扩展,零新组件。
索引岗位的 公司+标题+职责+要求(与 dense 文档同源,但 FTS 走关键词倒排 + BM25 打分)。

实验期 CREATE VIRTUAL TABLE IF NOT EXISTS;上 prod 前补正式建表/迁移。
BM25 在 FTS5 里分数越小越相关(SQLite 约定 bm25() 返回负值/升序),这里统一转成"越大越好"。
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.phase_g.recommendation_v2.dense_index import job_document


def fts5_available(db: Session) -> bool:
    """探测当前 SQLite 是否编译了 FTS5(老构建可能没有)。"""
    try:
        db.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"))
        db.execute(text("DROP TABLE IF EXISTS _fts5_probe"))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def ensure_index(db: Session) -> None:
    """懒建 FTS5 虚表 job_fts(content rowid = jobs.id)。"""
    db.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS job_fts USING fts5("
        " doc,"                       # 公司+标题+职责+要求
        " tokenize = 'unicode61'"     # unicode61 对中文按 codepoint 切;够用(BM25 词频)
        ")"
    ))
    db.commit()


def rebuild_index(db: Session, *, limit: Optional[int] = None) -> int:
    """全量重建 FTS 索引(只索引过质量闸、活链、有 JD 的岗)。返回索引条数。

    FTS5 外部内容表较繁,这里用最简的"内容内嵌"虚表:rowid=jobs.id,doc=拼接文本。
    """
    ensure_index(db)
    db.execute(text("DELETE FROM job_fts"))
    q = (
        "SELECT id, company, job_title, job_duty, job_req FROM jobs "
        "WHERE quality_label IN ('good','internship_only') "
        "AND (link_status IS NULL OR link_status != 'dead') "
        "AND (COALESCE(job_duty,'')!='' OR COALESCE(job_req,'')!='')"
    )
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = db.execute(text(q)).fetchall()
    n = 0
    for jid, company, title, duty, req in rows:
        doc = job_document(company, title, duty, req)
        if not doc:
            continue
        db.execute(
            text("INSERT INTO job_fts (rowid, doc) VALUES (:rid, :doc)"),
            {"rid": int(jid), "doc": doc},
        )
        n += 1
    db.commit()
    return n


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]")


def _to_match_query(query_text: str) -> str:
    """把自由文本转成 FTS5 MATCH 查询:抽 token,OR 连接,加引号防语法注入。

    unicode61 把中文按单字切,所以用单字 OR 近似(够 BM25 词频召回)。
    """
    toks = _TOKEN_RE.findall(query_text or "")
    toks = [t for t in toks if t.strip()]
    if not toks:
        return ""
    # 去重保序,cap 防超长 MATCH
    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return " OR ".join(f'"{t}"' for t in uniq[:64])


def sparse_search(
    db: Session,
    query_text: str,
    *,
    allowed_ids: Optional[Sequence[int]] = None,
    k: int = 200,
) -> list[tuple[int, float]]:
    """FTS5 BM25 召回。返回 [(job_id, score)] 降序(score 越大越相关),top-k。

    FTS5 的 bm25() 越小越相关 → 这里取负,统一"越大越好"。allowed_ids 限定范围。
    """
    mq = _to_match_query(query_text)
    if not mq:
        return []
    try:
        rows = db.execute(
            text(
                "SELECT rowid, bm25(job_fts) AS s FROM job_fts "
                "WHERE job_fts MATCH :mq ORDER BY s LIMIT :lim"
            ),
            {"mq": mq, "lim": int(k) * (4 if allowed_ids else 1)},
        ).fetchall()
    except Exception:
        db.rollback()
        return []
    out: list[tuple[int, float]] = []
    allow = set(int(x) for x in allowed_ids) if allowed_ids is not None else None
    for rid, s in rows:
        rid = int(rid)
        if allow is not None and rid not in allow:
            continue
        out.append((rid, -float(s)))  # bm25 越小越好 → 取负变"越大越好"
        if len(out) >= k:
            break
    return out
