"""入库后岗位卫生：跨源去重 + 描述回填。

每次日爬 / tier 爬结束由 scheduler 调用（`dedup_jobs`），保证新入库岗位不会让
学生看到同一个岗两遍（典型：Tata 聚合器与直爬官网命中同一 postId）。

安全键 = (detail_url, job_title)。只折叠 **URL 完全相同且岗位名也相同** 的行，
因此共享门户 URL（建行机构页 / JD `campus.jd.com/#/jobs` / 得物 portal — 同一
URL 挂多个不同岗）天然被排除，不会误删真岗。

保留行优先级：非死链 > 描述更全 > scraped_at 更新。删前把胜出行的空
job_duty / job_req 从被删行回填，避免「留了 alive 的空壳、丢了有描述的旧抓」。

用 raw SQL 批量 UPDATE/DELETE — 避开 ORM before_update 钩子（canonical_track
hook 在 inner-flush 时会被上千次 update 拖崩，link_prober 同款规避）。
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session

_STATUS_RANK = {"alive": 2, None: 1, "dead": 0}


def _row_score(r) -> tuple:
    """胜出排序键，越大越该保留。"""
    status_rank = _STATUS_RANK.get(r["link_status"], 1)
    content = (r["duty_len"] or 0) + (r["req_len"] or 0)
    scraped = r["scraped_at"] or ""
    return (status_rank, content, scraped)


def dedup_jobs(db: Session, apply: bool = True) -> dict:
    """折叠 (detail_url, job_title) 完全相同的重复岗位。

    apply=False 时只统计不改库（dry-run）。返回 stats dict。
    """
    rows = db.execute(
        text(
            """
            SELECT id, company, job_title, source,
                   detail_url AS url, link_status, scraped_at,
                   length(COALESCE(job_duty, '')) AS duty_len,
                   length(COALESCE(job_req, ''))  AS req_len
            FROM jobs
            WHERE detail_url IS NOT NULL AND detail_url != ''
              AND job_title  IS NOT NULL AND job_title  != ''
            """
        )
    ).mappings().all()

    by_url: dict[str, list] = defaultdict(list)
    for r in rows:
        by_url[r["url"].strip()].append(r)

    delete_ids: list[int] = []
    backfills: list[dict] = []
    dup_groups = 0
    cross_source_groups = 0
    portal_skipped = 0

    for _url, members in by_url.items():
        if len(members) < 2:
            continue
        # 共享门户判定：同一 URL 对应多个不同岗位名 -> 不是 per-job URL，跳过，
        # 避免误删建行机构页 / JD 门户下的不同岗。
        if len({(m["job_title"] or "").strip() for m in members}) > 1:
            portal_skipped += 1
            continue
        dup_groups += 1
        if len({m["source"] for m in members}) > 1:
            cross_source_groups += 1

        members.sort(key=_row_score, reverse=True)
        winner = members[0]
        losers = members[1:]

        # 回填：胜出行描述为空时，从被删行取最长的非空描述
        need_duty = (winner["duty_len"] or 0) == 0
        need_req = (winner["req_len"] or 0) == 0
        if need_duty or need_req:
            best_duty_id = max(
                (m for m in losers if (m["duty_len"] or 0) > 0),
                key=lambda m: m["duty_len"], default=None,
            )
            best_req_id = max(
                (m for m in losers if (m["req_len"] or 0) > 0),
                key=lambda m: m["req_len"], default=None,
            )
            patch = {}
            if need_duty and best_duty_id is not None:
                patch["duty_from"] = best_duty_id["id"]
            if need_req and best_req_id is not None:
                patch["req_from"] = best_req_id["id"]
            if patch:
                patch["target"] = winner["id"]
                backfills.append(patch)

        delete_ids.extend(m["id"] for m in losers)

    stats = {
        "dup_groups": dup_groups,
        "cross_source_groups": cross_source_groups,
        "portal_skipped": portal_skipped,
        "to_delete": len(delete_ids),
        "to_backfill": len(backfills),
        "applied": apply,
    }

    if not apply or not delete_ids:
        return stats

    # 回填描述（从被删行 -> 胜出行）
    for bf in backfills:
        if "duty_from" in bf:
            db.execute(
                text("UPDATE jobs SET job_duty = (SELECT job_duty FROM jobs WHERE id = :src) WHERE id = :tgt"),
                {"src": bf["duty_from"], "tgt": bf["target"]},
            )
        if "req_from" in bf:
            db.execute(
                text("UPDATE jobs SET job_req = (SELECT job_req FROM jobs WHERE id = :src) WHERE id = :tgt"),
                {"src": bf["req_from"], "tgt": bf["target"]},
            )

    # 批量删除冗余行（500 一批）
    for i in range(0, len(delete_ids), 500):
        chunk = delete_ids[i : i + 500]
        placeholders = ",".join(str(int(x)) for x in chunk)
        db.execute(text(f"DELETE FROM jobs WHERE id IN ({placeholders})"))

    db.commit()
    return stats


if __name__ == "__main__":
    import sys
    from app.database import SessionLocal

    apply = "--apply" in sys.argv
    db = SessionLocal()
    try:
        result = dedup_jobs(db, apply=apply)
        mode = "APPLY" if apply else "DRY-RUN"
        print(f"[job_hygiene {mode}] {result}")
    finally:
        db.close()
