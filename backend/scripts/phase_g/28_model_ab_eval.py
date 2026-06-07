"""Phase G — deepseek-pro vs gpt-5.5 头对头质量评测(quality_label + sub_cat Pass1/Pass2)。

忠实复用线上三个函数(enrich_job_quality_label_v3 / pass1_classify_strategy /
pass2_classify_subcat,含 Pass2 知识库检索),只把底层模型换掉:
  - deepseek = OpenCode Go(RESUME_COPILOT_LLM_*,deepseek-v4-pro / deepseek-v4-flash)
  - gpt55    = xhyapi 中转(ENRICH_LLM_*,gpt-5.5)  ← 跑前需临时取消 .env.local 里那三行注释

做法: 对同一批 GT 公司金融岗,分别用两套模型跑整条管道,比一致率 + 分歧明细 +
gpt-5.5 是否系统性"偏宽"(更爱判 good)。纯读,不写库。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/28_model_ab_eval.py [--limit 45] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config as cfg  # noqa: F401 — 触发 .env.local 加载
from openai import OpenAI

import app.services.crawler_llm_enrich as ce
import app.services.phase_g.sub_cat_enricher as sce
from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v3
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.sub_cat_enricher import (
    pass1_classify_strategy,
    pass2_classify_subcat,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT = BACKEND_ROOT / "data" / "_phase_g" / "model_ab_eval.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("model_ab")

# quality_label "进池倾向"打分: 越大越宽松(越往池子里放)。用于量化 gpt-5.5 是否偏宽。
_LENIENCY = {"good": 2, "internship_only": 1,
             "support_role": 0, "low_signal": 0, "spam": 0, "low_pay": 0, "agency": 0}


def _make_provider(name: str):
    """返回 (client, model_fn(tier)->str)。"""
    if name == "deepseek":
        client = OpenAI(base_url=cfg.RESUME_COPILOT_LLM_BASE_URL,
                        api_key=cfg.RESUME_COPILOT_LLM_API_KEY, timeout=120)
        def model_fn(tier: str = "pro") -> str:
            return cfg.CRAWLER_LLM_FLASH_MODEL if tier == "flash" else cfg.CRAWLER_LLM_PRO_MODEL
        return client, model_fn
    if name == "gpt55":
        if not (cfg.ENRICH_LLM_BASE_URL and cfg.ENRICH_LLM_API_KEY and cfg.ENRICH_LLM_MODEL):
            raise SystemExit("ENRICH_LLM_* 未配置 — 跑前临时取消 backend/.env.local 里那三行注释")
        client = OpenAI(base_url=cfg.ENRICH_LLM_BASE_URL,
                        api_key=cfg.ENRICH_LLM_API_KEY, timeout=120)
        def model_fn(tier: str = "pro") -> str:
            return cfg.ENRICH_LLM_MODEL
        return client, model_fn
    raise ValueError(name)


def _patch(client, model_fn) -> None:
    """把两个模块里的 build_enrich_client / enrich_model_name 换成固定 provider。"""
    for mod in (ce, sce):
        mod.build_enrich_client = lambda tier="pro", _c=client: _c
        mod.enrich_model_name = lambda tier="pro", _m=model_fn: _m(tier)


def _sample_ids(limit: int) -> list[int]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Job.id)
            .filter(Job.quality_label.in_(("good", "internship_only", "support_role", "low_signal")))
            .order_by(Job.id.desc())
            .limit(limit * 5)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _eval_one(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job or not build_company_kb_block(job.company or ""):
            return None  # 只评 GT 公司金融岗(否则 sub_cat 必 off_target)
        jd = {"company": job.company or "", "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        q = enrich_job_quality_label_v3(jd).get("quality_label")
        p1 = pass1_classify_strategy(jd)
        strat = p1.get("strategy_type") if p1.get("confidence", 0) >= 0.5 else None
        sub = None
        if strat:
            p2 = pass2_classify_subcat(jd, strat)
            sub = p2.get("sub_category") if p2.get("confidence", 0) >= 0.3 else None
        return {"id": job_id, "company": job.company or "", "title": job.job_title or "",
                "quality": q, "strategy": strat, "sub": sub}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def _run_provider(name: str, ids: list[int], workers: int) -> dict[int, dict]:
    client, model_fn = _make_provider(name)
    _patch(client, model_fn)
    out: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_eval_one, i): i for i in ids}
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                out[r["id"]] = r
    log.info("[%s] done: %d jobs", name, len(out))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=45)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    ids = _sample_ids(args.limit)
    log.info("running deepseek pass ...")
    ds = _run_provider("deepseek", ids, args.workers)
    log.info("running gpt55 pass ...")
    gp = _run_provider("gpt55", ids, args.workers)

    common = [i for i in ids if i in ds and i in gp][: args.limit]
    n = len(common)

    q_agree = sum(ds[i]["quality"] == gp[i]["quality"] for i in common)
    strat_agree = sum(ds[i]["strategy"] == gp[i]["strategy"] for i in common)
    both_sub = [i for i in common if ds[i]["sub"] and gp[i]["sub"]]
    sub_agree = sum(ds[i]["sub"] == gp[i]["sub"] for i in both_sub)

    # gpt-5.5 偏宽度: gpt55 进池倾向 > deepseek 的次数
    gpt_more_lenient = sum(
        _LENIENCY.get(gp[i]["quality"], 0) > _LENIENCY.get(ds[i]["quality"], 0) for i in common
    )
    ds_more_lenient = sum(
        _LENIENCY.get(ds[i]["quality"], 0) > _LENIENCY.get(gp[i]["quality"], 0) for i in common
    )

    report = {
        "sample_size": n,
        "quality_label": {
            "agree_rate": round(q_agree / max(n, 1), 3),
            "gpt55_more_lenient": gpt_more_lenient,
            "deepseek_more_lenient": ds_more_lenient,
            "deepseek_dist": dict(Counter(ds[i]["quality"] for i in common)),
            "gpt55_dist": dict(Counter(gp[i]["quality"] for i in common)),
        },
        "pass1_strategy": {"agree_rate": round(strat_agree / max(n, 1), 3)},
        "pass2_subcat": {
            "n_both_nonnull": len(both_sub),
            "agree_rate": round(sub_agree / max(len(both_sub), 1), 3),
        },
        "quality_disagreements": [
            {"id": i, "company": ds[i]["company"], "title": ds[i]["title"],
             "deepseek": ds[i]["quality"], "gpt55": gp[i]["quality"]}
            for i in common if ds[i]["quality"] != gp[i]["quality"]
        ][:40],
        "subcat_disagreements": [
            {"id": i, "company": ds[i]["company"], "title": ds[i]["title"],
             "deepseek": ds[i]["sub"], "gpt55": gp[i]["sub"]}
            for i in both_sub if ds[i]["sub"] != gp[i]["sub"]
        ][:40],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("=" * 60)
    log.info("sample=%d", n)
    log.info("quality_label agree = %.1f%% | gpt55 偏宽 %d 次 vs deepseek 偏宽 %d 次",
             report["quality_label"]["agree_rate"] * 100, gpt_more_lenient, ds_more_lenient)
    log.info("pass1 strategy agree = %.1f%%", report["pass1_strategy"]["agree_rate"] * 100)
    log.info("pass2 sub_cat  agree = %.1f%% (n=%d 双非空)",
             report["pass2_subcat"]["agree_rate"] * 100, len(both_sub))
    log.info("report → %s", OUT)


if __name__ == "__main__":
    main()
