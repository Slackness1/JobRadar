"""产品 + AI 应用条线 聚焦重分类（只做这条线，省力版，2026-06-11）。

候选 = 现有 4 桶（产品经理 / AI PM / Agent工程师 / AI应用开发工程师）的在招岗。
把它们重分进 10 个精细 sub_cat（产品 5 + AI 应用梯度 5）。
**只输出 JSONL + 分布到 sync 给用户 review，不写 DB**（落库走后续 --commit 步骤）。

模型走 build_enrich_client()（当前=deepseek-v4-pro，OpenCode）。
Usage:
  PYTHONPATH=. .venv/bin/python scripts/phase_g/33_reclassify_product_ai_line.py [--limit N] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401
from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm import build_enrich_client, enrich_model_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reclassify_line")

SOURCE_SUBCATS = ["产品经理", "AI PM", "Agent工程师", "AI应用开发工程师"]
OUT = Path("/home/ubuntu/jobradar-sync/subcat-taxonomy-review-2026-06-11/product_ai_line_reclassify.jsonl")

# 10 目标桶 + 兜底（命名 v5）
LABELS = [
    "用户/增长产品经理", "商业化/广告/交易产品经理", "策略/数据产品经理",
    "平台/工具/ToB产品经理", "金融科技/支付/风控产品经理",
    "AI产品经理", "Agent/工作流产品经理", "AI产品工程师/Product Engineer",
    "LLM/RAG应用工程师", "Agent平台工程师",
    "其他-非本条线",
]

SYSTEM_PROMPT = """你是中国互联网/AI 校招岗位精细分类器。读 JD，**按下面优先级顺序，命中即归**，只输出 JSON。不要只看标题关键词，要看核心职责对象。

## 第 0 步（硬门，最高优先级，先判这个）：是不是"训模型/算法研发"岗？
只要 JD 出现以下任一信号，**一律归「其他-非本条线」**，不再往下走（哪怕标题写"应用开发/AI应用"）：
- 模型训练 / 微调 / SFT / RLHF / DPO / PPO / LoRA / post-train / 预训练 / 强化学习样本
- 多模态/CV/NLP 算法研发、推理优化 / 推理加速 / 模型部署 / TensorRT / 端侧优化 / 量化蒸馏
- 搜索/推荐/广告 算法、风控/增长/定价 算法、运筹优化算法、AI4SE/代码大模型 预训练
- 自动驾驶感知/规控/VLA/VLM 模型研发、算法/研究型岗（"研究""探索""算法工程师"且核心是模型本身）
判据：**核心是"造/调模型本身" → 其他；核心是"用现成模型搭应用/产品" → 才进下面的桶。**
注意："大模型应用开发""智能化应用开发""AI 研发"这类标题，若 JD 正文含上面训模型信号，仍归其他。

## 第一步：是产品岗还是工程岗？
- 不写生产代码、做需求/场景/指标/ROI/迭代 → 走【产品类】
- 写代码/做工程实现/系统集成 → 走【AI 应用工程类】

## 【产品类】按序命中即归（前面优先）
1. AI/Agent 是**产品本体**（而非某个功能）→ 转去【AI 应用工程类】里的产品桶（AI产品经理 / Agent/工作流产品经理）判定
2. 支付/信贷/风控/反欺诈/合规/金融账户/资金链路是产品本体（**即便用了 AI**）→ 金融科技/支付/风控产品经理
3. 广告/交易/商业化/GMV/营收/投放效率/商家成交是**核心 KPI** → 商业化/广告/交易产品经理
4. 推荐/搜索/数据中台/策略平台是产品对象**且不直接背收入目标** → 策略/数据产品经理
5. 企业 SaaS/工具/中台/工作台/管理后台（**AI 只是 feature**）→ 平台/工具/ToB产品经理
6. C 端体验/增长/留存/用户生命周期 → 用户/增长产品经理

## 【AI 应用工程类】按序命中即归（前面优先）
1. 训模型/SFT/RLHF/post-train/多模态/推理优化/搜推广算法/风控算法工程 → 其他-非本条线
2. Agent runtime/多 Agent 协作/tool calling 框架/workflow engine/planner/memory/sandbox/编排平台 → Agent平台工程师
3. RAG/知识库/Prompt/上下文工程/模型 API 集成/AI 后端服务/业务应用落地 → LLM/RAG应用工程师
4. 产品+原型+API demo/低代码/快速验证/MVP/prompt/工作流配置，**且不背生产级后端稳定性/架构/服务治理** → AI产品工程师/Product Engineer
5. 需求/场景/ROI/bad case/产品迭代、不写代码：
   - JD 明确 智能体平台/Agent 工作流/工具调用/插件生态/任务编排/流程自动化/智能客服机器人/企业助手/Bot 配置平台/应用搭建平台 → Agent/工作流产品经理
   - 否则（即便标题带 Agent）→ AI产品经理

## 6 条硬规则
- R1 商业化优先于策略：背收入/GMV/投放 → 商业化;只服务推荐搜索数据中台且不背收入 → 策略。
- R2 金融业务对象优先于 AI 标签:支付/风控/信贷即便用 AI 也归金科产品。
- R3 AI 是 feature → ToB 产品;AI 是产品本体 → AI 产品/Agent 产品。
- R4 Product Engineer 必须同时有产品职责+轻开发信号，且不背生产级后端;否则归 LLM/RAG应用工程师。
- R5 "不确定先归 LLM/RAG"只限**已确认是 AI 开发岗**;无工程/代码/集成信号 → 回看 AI PM/Agent PM/非本条线。
- R6 Agent PM 不能只凭标题带 Agent;要有编排/工作流/平台/Bot 配置等产品组织信号。

输出 JSON：{"label": "<上面某个完整桶名，必须从这 11 个里选>", "confidence": 0-1, "reasoning": "一句中文依据，点明命中哪条优先级"}
合法 label：用户/增长产品经理｜商业化/广告/交易产品经理｜策略/数据产品经理｜平台/工具/ToB产品经理｜金融科技/支付/风控产品经理｜AI产品经理｜Agent/工作流产品经理｜AI产品工程师/Product Engineer｜LLM/RAG应用工程师｜Agent平台工程师｜其他-非本条线"""


def _classify(job: Job) -> dict:
    client = build_enrich_client()
    jd = f"公司：{job.company}\n岗位：{job.job_title}\n职责：{(job.job_duty or '')[:1200]}\n要求：{(job.job_req or '')[:800]}"
    resp = client.chat.completions.create(
        model=enrich_model_name(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": jd},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    d = json.loads(raw)
    label = d.get("label", "").strip()
    if label not in LABELS:
        # 容错：取最接近的，否则兜底
        label = next((l for l in LABELS if l in label or label in l), "其他-非本条线")
    return {"label": label, "confidence": d.get("confidence"), "reasoning": d.get("reasoning", "")}


def _candidates(limit):
    db = SessionLocal()
    try:
        q = (db.query(Job.id, Job.company, Job.job_title, Job.sub_category)
             .filter(Job.sub_category.in_(SOURCE_SUBCATS),
                     Job.quality_label.in_(["good", "internship_only"]),
                     ((Job.link_status.is_(None)) | (Job.link_status != "dead")))
             .order_by(Job.id))
        if limit:
            q = q.limit(limit)
        return [(r[0], r[1], r[2], r[3]) for r in q.all()]
    finally:
        db.close()


def _process(row):
    jid, company, title, old = row
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=jid).first()
        if not job:
            return None
        r = None
        last_err = ""
        for _attempt in range(3):  # 重试 3 次降 ERROR（JSON 解析/瞬时失败）
            try:
                r = _classify(job)
                break
            except Exception as e:
                last_err = str(e)[:120]
        if r is None:
            return {"job_id": jid, "company": company, "title": title,
                    "old": old, "new": "ERROR", "err": last_err}
        return {"job_id": jid, "company": company, "title": title, "old": old,
                "new": r["label"], "confidence": r["confidence"], "reasoning": r["reasoning"]}
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=str, default=str(OUT))
    args = ap.parse_args()

    out_path = Path(args.out)
    rows = _candidates(args.limit or None)
    log.info("候选 %d 个 | 模型 %s | out %s", len(rows), enrich_model_name(), out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    dist = Counter()
    with out_path.open("w", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_process, r): r for r in rows}
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            if not res:
                continue
            results.append(res)
            dist[res["new"]] += 1
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            if i % 50 == 0:
                log.info("  %d/%d done", i, len(rows))
    log.info("=== 新桶分布 ===")
    for label, n in dist.most_common():
        log.info("  %4d  %s", n, label)
    log.info("输出: %s", OUT)


if __name__ == "__main__":
    main()
