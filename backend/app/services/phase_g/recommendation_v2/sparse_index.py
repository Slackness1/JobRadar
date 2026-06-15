"""S1 稀疏召回 — SQLite FTS5 全文检索(BM25)+ jieba 中文分词。

把 Vespa/ES 的 BM25 塞进 SQLite 重量级:FTS5 是内置扩展,零新组件。

⚠️ 中文必须预分词:FTS5 unicode61 默认把整段中文当**一个 token**("量化研究"=一个词),
不分词的话只能精确匹配整串、召回极差。所以这里用 **jieba** 把 中文切成空格分隔词,
再喂 FTS5;英文技术词(Agent/RAG/LLM)jieba 默认整体保留。

字段分列加权:title / company / body 三列分开,bm25() 给 title、company 更高权重
(标题/公司命中比正文命中更相关)。

实验期 CREATE VIRTUAL TABLE IF NOT EXISTS;上 prod 前补正式建表/迁移。
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.services.phase_g.recommendation_v2.dense_index import _DOC_MAXLEN

# jieba 懒加载:sparse 是默认关的 opt-in 召回腿(评测证明 BM25 净拖累),
# 纯 dense 路径不应依赖它。只在真正用到分词时才 import + warm 词典,
# 这样 prod 走纯 dense 时无需安装 jieba。
_jieba = None


def _get_jieba():
    global _jieba
    if _jieba is None:
        import jieba  # noqa: PLC0415
        jieba.initialize()  # 首次 ~1s 建词典
        _jieba = jieba
    return _jieba


_EN_NUM = re.compile(r"[A-Za-z0-9]")


def segment(s: str) -> str:
    """jieba 切词 → 空格分隔。英文/数字 token 原样保留(jieba 不拆 Agent/RAG)。

    过滤纯标点/空白 token;结果喂给 FTS5 unicode61(它再按空格分词)。
    """
    s = (s or "").strip()[:_DOC_MAXLEN]
    if not s:
        return ""
    toks = []
    for t in _get_jieba().cut(s, cut_all=False):
        t = t.strip()
        if not t:
            continue
        # 单字纯标点跳过;保留中文词、英文、数字
        if len(t) == 1 and not (_EN_NUM.match(t) or "一" <= t <= "鿿"):
            continue
        toks.append(t)
    return " ".join(toks)


def fts5_available(db: Session) -> bool:
    try:
        db.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"))
        db.execute(text("DROP TABLE IF EXISTS _fts5_probe"))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def ensure_index(db: Session) -> None:
    """懒建 FTS5 虚表 job_fts:title/company/body 三列(已分词文本),rowid=jobs.id。"""
    db.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS job_fts USING fts5("
        " title, company, body,"
        " tokenize = 'unicode61'"   # 喂的是 jieba 分好的空格文本,unicode61 按空格切即可
        ")"
    ))
    db.commit()


def rebuild_index(db: Session, *, limit: Optional[int] = None) -> int:
    """全量重建 FTS 索引(只索引过质量闸、活链、有 JD 的岗)。返回索引条数。"""
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
        body = segment((duty or "") + " " + (req or ""))
        ttl = segment(title or "")
        comp = segment(company or "")
        if not (ttl or comp or body):
            continue
        db.execute(
            text("INSERT INTO job_fts (rowid, title, company, body) "
                 "VALUES (:rid, :t, :c, :b)"),
            {"rid": int(jid), "t": ttl, "c": comp, "b": body},
        )
        n += 1
    db.commit()
    return n


def _to_match_query(query_text: str) -> str:
    """jieba 切查询 → FTS5 MATCH(OR 连接,引号防注入)。"""
    seg = segment(query_text)
    toks = [t for t in seg.split() if t]
    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq:
        return ""
    return " OR ".join(f'"{t}"' for t in uniq[:64])


def sparse_search(
    db: Session,
    query_text: str,
    *,
    allowed_ids: Optional[Sequence[int]] = None,
    k: int = 200,
) -> list[tuple[int, float]]:
    """FTS5 BM25 召回(title>company>body 加权)。返回 [(job_id, score)] 降序(越大越相关)。

    bm25(job_fts, w_title, w_company, w_body):权重越大越重要;bm25() 本身越小越相关,
    取负统一成"越大越好"。
    """
    mq = _to_match_query(query_text)
    if not mq:
        return []
    try:
        rows = db.execute(
            text(
                "SELECT rowid, bm25(job_fts, 5.0, 3.0, 1.0) AS s FROM job_fts "
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
        out.append((rid, -float(s)))
        if len(out) >= k:
            break
    return out
