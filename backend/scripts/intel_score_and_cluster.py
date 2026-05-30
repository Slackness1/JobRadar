"""Task E — 情报打分 + 多源印证 + 硬门槛交叉验证。

跑顺序: 先 A(知乎入库)、B(809 XHS 反查),让 XhsInsight 有真数据,再跑本脚本。

做的事:
  E1 跨源聚类: 每家公司内部,按 embedding cosine ≥ 0.78 聚类; 簇横跨 ≥2 信源
      → 簇内所有 insight confidence='verified', corroboration_json 互写 sibling id。
      信源判定:note_id 前缀 — zh_ = 知乎, xhsp_ = 历史 XHS, xhs_ = 现 XHS。
  E2 分歧检测: 先用 LLM (DeepSeek Pro) 判定口径/表述/数值/潜规则冲突;
      LLM 失败时回落到旧 regex 版 (数字硬差异)。
  E3 硬门槛验证: 每个 sub_cat 的 hard_requirements 项,在该赛道相关公司的情报库里
      找 cosine > 0.55 的匹配;命中 ≥3 → 该硬门槛 payload 加 verified_by=[insight_ids]。
  E4-helper: 输出每档 confidence 的统计 + 抽样几条 verified,让人肉评估。

跑法 (cwd=backend):
    PYTHONPATH=. .venv/bin/python scripts/intel_score_and_cluster.py
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# E2 分歧检测 — 旧 regex 版 (fallback)
# ─────────────────────────────────────────────
# 抓"N 轮/N 面/N 年/N 万"这种关键事实的硬数字差异
_CONFLICT_RE = re.compile(r"(\d+)\s*(轮|面|分钟|小时|天|周|w|W|万)")  # 排除 年/月/人 等高噪关键词


def _claims(text: str) -> dict[str, set[str]]:
    by_kw: dict[str, set[str]] = defaultdict(set)
    for m in _CONFLICT_RE.finditer(text or ""):
        by_kw[m.group(2)].add(m.group(1))
    return by_kw


def _cluster_conflict(members_texts: list[str]) -> tuple[bool, dict[str, list[str]]]:
    """旧版: 同簇内同 keyword 出现 ≥2 不同数字 → True + 冲突明细。LLM 失败时的 fallback。"""
    agg: dict[str, set[str]] = defaultdict(set)
    for t in members_texts:
        for kw, nums in _claims(t).items():
            agg[kw].update(nums)
    dispute = {kw: sorted(nums) for kw, nums in agg.items() if len(nums) > 1}
    return bool(dispute), dispute


# ─────────────────────────────────────────────
# E2 分歧检测 — LLM 版 (主路径, DeepSeek Pro)
# ─────────────────────────────────────────────
_CONFLICT_SYSTEM = """你是一个情报质量审核助手。
你会收到多条来自不同信源（知乎/小红书）关于同一家公司同一类岗位的描述片段。
请判断这些描述之间是否存在事实或口径上的冲突。

冲突的四类典型例子:
1. 数值差异: "面试 3 轮" vs "面试 6 轮"、"薪资 30W" vs "薪资 50W"
2. 口径矛盾: "门槛 985+硕士" vs "本科也能进"、"只招应届" vs "社招也收"
3. 工作状态相反: "朝九晚六 几乎不加班" vs "周常 996 几乎没有休息"
4. 公司潜规则相反: "晋升快 氛围好" vs "天花板低 内卷严重"

注意:
- "略有侧重不同"不是冲突 (如一条讲薪资、另一条讲氛围)
- 主观感受程度差异 (如"还不错" vs "很好") 不算冲突
- 只有实质上互相矛盾才算 conflict

请严格输出 JSON，不要有任何额外文字:
{"conflict": true/false, "details": {"<冲突点简短描述>": ["<说法1>", "<说法2>"]}}
如果无冲突，details 为空对象 {}。"""


def _cluster_conflict_llm(members_texts: list[str]) -> tuple[bool, dict]:
    """LLM 版分歧检测 (DeepSeek Flash — 速度优先, 分类任务不需要 Pro reasoning)。
    失败时返 (False, {}) — 不阻塞 pipeline。"""
    try:
        from app.services.crawler_llm import build_flash_client, flash_model_name, safe_json_extract
    except ImportError as e:
        log.warning("crawler_llm import failed: %s", e)
        return False, {}

    # 拼装用户消息: 每条片段截断到 1500 字符，避免超长
    parts = []
    for idx, text in enumerate(members_texts, 1):
        snippet = (text or "").strip()[:1500]
        parts.append(f"[片段 {idx}]\n{snippet}")
    user_msg = "\n\n".join(parts)

    try:
        client = build_flash_client()
        resp = client.chat.completions.create(
            model=flash_model_name(),
            messages=[
                {"role": "system", "content": _CONFLICT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or ""
        parsed = safe_json_extract(raw)
        if not isinstance(parsed, dict):
            log.warning("LLM conflict: unexpected response type, raw=%r", raw[:200])
            return False, {}
        conflict = bool(parsed.get("conflict", False))
        details = parsed.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        return conflict, details
    except Exception as exc:
        log.warning("LLM conflict detection failed (%s), falling back to regex", exc)
        return False, {}  # fallback 交给调用方处理

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))


def _source_of(note_id: str) -> str:
    nid = (note_id or "").lower()
    if nid.startswith("zh_"):
        return "zhihu"
    if nid.startswith("xhsp_"):
        return "xhs-historical"
    if nid.startswith("xhs_"):
        return "xhs"
    return "unknown"


COS_THRESHOLD = 0.78          # 同簇阈值 (embeddings 已归一, dot=cosine)
HARD_REQ_THRESHOLD = 0.55     # 硬门槛匹配 (略低, 表述差异大)
HARD_REQ_MIN_HITS = 3         # ≥3 条情报印证 → 验证


def main() -> int:
    from app.database import SessionLocal
    from app.models import AccountMemory, KnowledgeSubcategory, XhsInsight  # noqa: F401
    from app.services.podcasts.embed import embed_one, from_blob

    db = SessionLocal()
    try:
        # === E1: 跨源聚类 ===
        print("=== E1 跨源聚类 ===")
        rows = list(db.query(XhsInsight).filter(XhsInsight.embedding.isnot(None)).all())
        print(f"  待处理 insights: {len(rows)}")
        by_company: dict[str, list] = defaultdict(list)
        for r in rows:
            try:
                tgts = json.loads(r.company_target_json or "[]")
            except Exception:
                tgts = []
            for c in tgts:
                if c:
                    by_company[c].append(r)

        n_verified = 0
        n_conflict = 0
        for company, items in by_company.items():
            if len(items) < 2:
                continue
            vecs = []
            valid = []
            for it in items:
                try:
                    v = from_blob(it.embedding)
                    if v.size > 0:
                        vecs.append(v); valid.append(it)
                except Exception:
                    pass
            if len(valid) < 2:
                continue
            M = np.stack(vecs)
            sim = M @ M.T
            n = len(valid)
            parent = list(range(n))
            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]; x = parent[x]
                return x
            for i in range(n):
                for j in range(i+1, n):
                    if sim[i, j] >= COS_THRESHOLD:
                        a, b = find(i), find(j)
                        if a != b:
                            parent[a] = b
            clusters: dict[int, list[int]] = defaultdict(list)
            for i in range(n):
                clusters[find(i)].append(i)
            for cid, members in clusters.items():
                if len(members) < 2:
                    continue
                sources = {_source_of(valid[i].source_note_id) for i in members}
                if len(sources) < 2:
                    continue
                sibling_ids = [valid[i].insight_id for i in members]
                # E2 分歧: LLM 主路径 → 失败回落 regex
                texts = [valid[i].content for i in members]
                in_conflict, dispute = _cluster_conflict_llm(texts)
                if not in_conflict and not dispute:
                    # LLM 无冲突 or 失败 → 再跑 regex 兜底
                    regex_conflict, regex_dispute = _cluster_conflict(texts)
                    # 只在 LLM 明确失败 (dispute 空 dict 且 in_conflict=False) 时才用 regex
                    # 但无法区分"LLM 判定无冲突"和"LLM 调用失败后返(False,{})"
                    # 保守策略: 两者都判 False → 取 regex 结果 (regex False → 不标 conflict)
                    if regex_conflict:
                        in_conflict, dispute = regex_conflict, regex_dispute
                tag = "conflicting" if in_conflict else "verified"
                if in_conflict:
                    n_conflict += 1
                    print(f"  ⚔ {company}: 簇内分歧 {dict(dispute)} ({len(members)} 条)")
                for i in members:
                    valid[i].confidence = tag
                    valid[i].corroboration_json = json.dumps(
                        [s for s in sibling_ids if s != valid[i].insight_id],
                        ensure_ascii=False,
                    )
                    if tag == "verified":
                        n_verified += 1
        db.commit()
        # 统计
        conf_dist = Counter(r.confidence for r in db.query(XhsInsight).all())
        print(f"  verified 标记: {n_verified} | conflicting 标记: {n_conflict} | 当前 confidence 分布: {dict(conf_dist)}")

        # === E3: 硬门槛交叉验证 ===
        print("\n=== E3 硬门槛交叉验证 ===")
        # 取 ground_truth 把 sub_cat ↔ 公司 对上
        gt = json.loads(Path("data/ground_truth_companies_v1.json").read_text(encoding="utf-8"))["ground_truth"]
        sc_to_companies = {sc: [(c.get("name") or "").strip() for c in lst if c.get("name")] for sc, lst in gt.items()}

        kb_rows = list(db.query(KnowledgeSubcategory).all())
        # 重建 insight 向量索引(只取有 company_target 的)
        all_insights = [r for r in db.query(XhsInsight).filter(XhsInsight.embedding.isnot(None)).all()]
        if not all_insights:
            print("  无 insight,跳过 E3"); return 0
        all_vecs = np.stack([from_blob(r.embedding) for r in all_insights])
        all_companies = [json.loads(r.company_target_json or "[]") for r in all_insights]

        n_verified_hr = 0
        for kb in kb_rows:
            try:
                payload = json.loads(kb.payload_json or "{}")
            except Exception:
                continue
            hrs = payload.get("hard_requirements") or []
            if not hrs:
                continue
            companies = set(sc_to_companies.get(kb.sub_cat, []))
            if not companies:
                continue
            new_hrs = []
            sc_changed = False
            for hr in hrs:
                hr_text = hr if isinstance(hr, str) else (hr.get("text") if isinstance(hr, dict) else str(hr))
                if not hr_text:
                    new_hrs.append(hr); continue
                try:
                    q = embed_one(hr_text)
                except Exception:
                    new_hrs.append(hr); continue
                sims = all_vecs @ q
                hits = []
                for i, s in enumerate(sims):
                    if s < HARD_REQ_THRESHOLD: continue
                    if not any(c in companies for c in all_companies[i]): continue
                    hits.append((float(s), all_insights[i].insight_id))
                hits.sort(reverse=True)
                if len(hits) >= HARD_REQ_MIN_HITS:
                    obj = {"text": hr_text} if isinstance(hr, str) else dict(hr)
                    obj["verified_by"] = [h[1] for h in hits[:5]]
                    new_hrs.append(obj)
                    sc_changed = True
                    n_verified_hr += 1
                else:
                    new_hrs.append(hr)
            if sc_changed:
                payload["hard_requirements"] = new_hrs
                kb.payload_json = json.dumps(payload, ensure_ascii=False)
        db.commit()
        print(f"  已验证硬门槛: {n_verified_hr} 条 (写入 knowledge_subcategories.payload_json.hard_requirements[i].verified_by)")

        # === 抽样几条 verified 看看 ===
        print("\n=== 抽样 5 条 verified 情报 ===")
        for r in db.query(XhsInsight).filter_by(confidence="verified").limit(5).all():
            try:
                sib = json.loads(r.corroboration_json or "[]")
            except Exception:
                sib = []
            print(f"  [{json.loads(r.company_target_json or '[]')} · {_source_of(r.source_note_id)}] 印证 {len(sib)} 条 | {r.content[:80]}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
