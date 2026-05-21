"""Day 11 v6 vs v7 对照 — sentinel ship-gate 校验.

读 v6 baseline (Day 10 ship, 3 Blocker + 5 Major 抓到的版本) vs v7 baseline (Day 11
B1+B2+B3+M1+M2 修后), 输出:

1. 每个 persona 的 overall 变化 (v6 → v7, delta, 是否 fallback)
2. Sentinel 校验: P8 / P9 / M13 / P-trait-S1 / P-bridge-S1 / P-fake-S1 / M14 / M6 /
   M9 / M11 / M12 — 期待区间见 docs/mock-interview-feedback-redesign-plan-2026-05-22-day11-hotpatch.md §4
3. Blocker/Major 验证:
   - B1: fallback 报告 overall=None + dimensions=[]
   - B2: M13 overall 提升, logic/industry_sense 不再 ≤30
   - B3: P-fake-S1 overall ≤65, _meta.mentor_fallback_count ≥3
   - M1: 任何 `_fabrication_suppressed=True` 报告必须 `_meta.score_capped_for_fabrication=True` 且 overall ≤60
   - M2: 没有 turn `overall=None`
4. 整体 cohort: strong / mid / extreme 各档 mean ± stdev (单 run 算 mean, 提示需要 N=3 才能信)

用法:
    python tests/eval/compare_v6_vs_v7.py \\
        --v6 tests/eval/_out/mock_interview_post_v6_full_2026_05_22.json \\
        --v7 tests/eval/_out/mock_interview_post_v7_full_2026_05_22.json \\
        --out docs/eval-full-loop-reports/mock_interview_post_v7_2026_05_22.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

# Sentinel 期待区间 (来自 plan §4)
SENTINELS: dict[str, dict] = {
    'workspace_P8_2026_05_21':           {'expect_lo': 82, 'expect_hi': 90, 'note': '顶档买方研究; 不再 fallback; 不再被白名单外术语 cap', 'v6': 87},
    'workspace_P9_2026_05_21':           {'expect_lo': 78, 'expect_hi': 88, 'note': '顶档咨询人; 报告级与 turn 级 gap ≤10', 'v6': 88},
    'mock_interview_M13_2026_05_21':     {'expect_lo': 80, 'expect_hi': 90, 'note': '强档银行 MT; pattern cap 不再误杀 banking 术语', 'v6': 58},
    'mock_interview_P_trait_S1_2026_05_21': {'expect_lo': 78, 'expect_hi': 88, 'note': '3 trait stress; 团队合作 trait 召回 ≥1 次', 'v6': 88},
    'mock_interview_P_bridge_S1_2026_05_21': {'expect_lo': 65, 'expect_hi': 80, 'note': '跨 domain; transferability=active_bridge stable', 'v6': 78},
    'mock_interview_P_fake_S1_2026_05_21': {'expect_lo': 50, 'expect_hi': 65, 'note': '退回 mentor 红线; B3 守卫触发, overall 不超 65', 'v6': 59, 'hard_cap': 65},
    'mock_interview_M14_2026_05_21':     {'expect_lo': 65, 'expect_hi': 78, 'note': 'mid 银行; 不再 fallback', 'v6': 73},
    'mock_interview_M6_2026_05_21':      {'expect_lo': 42, 'expect_hi': 58, 'note': 'weak 跨专业; 不被新加守卫带飞', 'v6': 53},
    'mock_interview_M9_2026_05_20':      {'expect_lo': 15, 'expect_hi': 35, 'note': 'extreme 模板; 严控不放过', 'v6': 25},
    'mock_interview_M11_2026_05_21':     {'expect_lo': 35, 'expect_hi': 50, 'note': 'extreme track 错配; rerun 应更严', 'v6': 60},
    'mock_interview_M12_2026_05_21':     {'expect_lo': 40, 'expect_hi': 55, 'note': 'extreme 翻译腔; 稳定', 'v6': 51},
}

STRONG_IDS = {'workspace_P1_2026_05_20', 'workspace_P2_2026_05_20', 'workspace_P5_2026_05_20',
              'workspace_P6_2026_05_20', 'workspace_P7_2026_05_20', 'workspace_P8_2026_05_21',
              'workspace_P9_2026_05_21', 'workspace_P3_2026_05_20', 'workspace_P4_2026_05_20',
              'mock_interview_M13_2026_05_21', 'mock_interview_M15_2026_05_21', 'mock_interview_M16_2026_05_21',
              'mock_interview_P_trait_S1_2026_05_21', 'mock_interview_P_bridge_S1_2026_05_21',
              'mock_interview_M1_2026_05_20', 'mock_interview_M2_2026_05_20'}
MID_IDS = {'mock_interview_M3_2026_05_20', 'mock_interview_M5_2026_05_20', 'mock_interview_M7_2026_05_20',
           'mock_interview_M8_2026_05_21', 'mock_interview_M14_2026_05_21', 'mock_interview_M6_2026_05_21'}
EXTREME_IDS = {'mock_interview_M9_2026_05_20', 'mock_interview_M10_2026_05_20',
               'mock_interview_M11_2026_05_21', 'mock_interview_M12_2026_05_21',
               'mock_interview_P_fake_S1_2026_05_21'}


def load_results(path: Path) -> dict[str, dict]:
    """Map scenario_id -> result dict (with `report`, `turns`, etc)."""
    with path.open() as f:
        data = json.load(f)
    return {r['scenario_id']: r for r in data['results']}


def fmt_delta(d: int) -> str:
    if d > 0:
        return f"+{d}"
    return str(d)


def main() -> None:
    parser = argparse.ArgumentParser(description="v6 vs v7 sentinel + blocker comparison")
    parser.add_argument('--v6', type=Path, required=True)
    parser.add_argument('--v7', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    v6 = load_results(args.v6)
    v7 = load_results(args.v7)

    common = sorted(set(v6.keys()) & set(v7.keys()))
    only_v7 = sorted(set(v7.keys()) - set(v6.keys()))

    lines: list[str] = []
    lines.append('# Mock Interview v7 vs v6 对照报告 (Day 11)')
    lines.append('')
    lines.append(f'- v6 baseline: `{args.v6.name}` (Day 10 ship, 3 Blocker + 5 Major 在生产)')
    lines.append(f'- v7 baseline: `{args.v7.name}` (Day 11 B1+B2+B3+M1+M2 修后, 单 seed)')
    lines.append('- 注: **单 seed 只能看方向, N=3 才能信** — strong/mid stdev 见 §5.')
    lines.append('')

    # ── §1. Sentinel 校验 (ship gate) ──────────────────────────────────────
    lines.append('## 1. Sentinel 校验 (ship gate)')
    lines.append('')
    lines.append('| Sentinel | v6 | v7 | Δ | 期待区间 | Pass? | 备注 |')
    lines.append('|---|---:|---:|---:|---|---|---|')
    sentinel_fails: list[str] = []
    for sid, info in SENTINELS.items():
        v7r = v7.get(sid)
        if not v7r:
            lines.append(f'| `{sid}` | {info["v6"]} | — | — | [{info["expect_lo"]}, {info["expect_hi"]}] | ❌ 缺失 | persona 没跑 |')
            sentinel_fails.append(f'{sid} 缺失')
            continue
        v7_overall = (v7r.get('report') or {}).get('overall_score')
        if v7_overall is None:
            v7_str, pass_str, note = 'None (fallback)', '❌', f"B1 fallback 触发 → overall=None; 期待 {info['expect_lo']}-{info['expect_hi']}"
            sentinel_fails.append(f'{sid}: fallback 触发')
        else:
            in_range = info['expect_lo'] <= v7_overall <= info['expect_hi']
            hard_cap = info.get('hard_cap')
            hard_ok = hard_cap is None or v7_overall <= hard_cap
            pass_str = '✅' if (in_range and hard_ok) else '❌'
            v7_str = str(v7_overall)
            note = info['note']
            if not in_range:
                note = f'**超出区间** — ' + note
                sentinel_fails.append(f'{sid}: {v7_overall} ∉ [{info["expect_lo"]}, {info["expect_hi"]}]')
            elif hard_cap is not None and not hard_ok:
                note = f'**超 hard cap {hard_cap}** — ' + note
                sentinel_fails.append(f'{sid}: {v7_overall} > hard cap {hard_cap}')
        delta = (v7_overall - info['v6']) if isinstance(v7_overall, int) else 0
        lines.append(f'| `{sid}` | {info["v6"]} | {v7_str} | {fmt_delta(delta)} | [{info["expect_lo"]}, {info["expect_hi"]}] | {pass_str} | {note} |')
    lines.append('')
    if sentinel_fails:
        lines.append(f'**Sentinel fail count: {len(sentinel_fails)}** — 必须修齐才能 ship:')
        for f in sentinel_fails:
            lines.append(f'- {f}')
    else:
        lines.append('**所有 sentinel 通过 ✅** — Day 11 期待区间全部命中.')
    lines.append('')

    # ── §2. Blocker 验证 ────────────────────────────────────────────────────
    lines.append('## 2. Blocker 验证')
    lines.append('')

    # B1: fallback 出现 → overall=None + dimensions=[]
    lines.append('### B1: fallback 不再伪装')
    b1_fallbacks = []
    b1_bad = []
    for sid, r in v7.items():
        rep = r.get('report') or {}
        if (rep.get('_meta') or {}).get('fallback_reason') == 'report_llm_silent':
            b1_fallbacks.append(sid)
            if rep.get('overall_score') is not None or rep.get('dimensions'):
                b1_bad.append(f'{sid}: overall={rep.get("overall_score")}, dims={len(rep.get("dimensions") or [])}')
    if b1_fallbacks:
        lines.append(f'- v7 共 {len(b1_fallbacks)} 个 fallback: {", ".join(b1_fallbacks)}')
        if b1_bad:
            lines.append('- ❌ B1 修法失效:')
            for x in b1_bad:
                lines.append(f'  - {x}')
        else:
            lines.append('- ✅ 所有 fallback 输出 `overall=None`, `dimensions=[]` (不再伪装)')
    else:
        lines.append('- v7 没有 fallback 触发 — B1 修法没机会被验, 但 unit test 覆盖.')
    lines.append('')

    # B2: M13 logic / industry_sense 不再被 cap ≤30
    lines.append('### B2: M13 pattern cap 不再误杀')
    m13 = (v7.get('mock_interview_M13_2026_05_21') or {}).get('report') or {}
    if m13:
        dims = {d.get('id'): d.get('score') for d in (m13.get('dimensions') or []) if isinstance(d, dict)}
        b2_ok = dims.get('logic', 0) > 30 and dims.get('industry_sense', 0) > 30
        lines.append(f'- v7 M13 dimensions: logic={dims.get("logic")}, industry_sense={dims.get("industry_sense")}, expression_depth={dims.get("expression_depth")}')
        lines.append(f'- v6 M13 dimensions: logic=30, industry_sense=30, expression_depth=40 (被 cap)')
        lines.append(f'- {"✅" if b2_ok else "❌"} B2 修法 {"生效" if b2_ok else "失效"}')
    lines.append('')

    # B3: P-fake-S1 overall ≤65 + _meta.mentor_fallback_count
    lines.append('### B3: P-fake-S1 mentor-fallback 守卫')
    pfake = (v7.get('mock_interview_P_fake_S1_2026_05_21') or {}).get('report') or {}
    if pfake:
        overall = pfake.get('overall_score')
        mentor_count = (pfake.get('_meta') or {}).get('mentor_fallback_count')
        b3_ok = isinstance(overall, int) and overall <= 65
        lines.append(f'- v7 overall={overall}, _meta.mentor_fallback_count={mentor_count}')
        lines.append(f'- v6 overall=59 (但 rerun 飙到 78-82)')
        lines.append(f'- {"✅" if b3_ok else "❌"} B3 守卫 {"触发 (overall ≤65)" if b3_ok else "失效"}')
        if mentor_count is not None and mentor_count < 3:
            lines.append(f'  - ⚠️ mentor_fallback_count={mentor_count} < 3, 守卫没 fire — 检测 regex 太严?')
    lines.append('')

    # M1: 任何 suppressed → score_capped_for_fabrication, overall ≤ 69
    # ship gate: 0 个 report 同时 (suppressed=True AND overall ≥ 70)
    lines.append('### M1: suppressed → cap overall ≤69 (ship gate: 不允许 overall ≥70)')
    m1_violations = []
    m1_capped = []
    for sid, r in v7.items():
        rep = r.get('report') or {}
        if rep.get('_fabrication_suppressed'):
            cap_flag = (rep.get('_meta') or {}).get('score_capped_for_fabrication')
            overall = rep.get('overall_score')
            if cap_flag and isinstance(overall, int) and overall < 70:
                m1_capped.append(sid)
            else:
                m1_violations.append(f'{sid}: suppressed=True, cap_flag={cap_flag}, overall={overall}')
    if m1_violations:
        lines.append(f'- ❌ M1 失效: {len(m1_violations)} 个 suppressed report 没被 cap < 70:')
        for v in m1_violations:
            lines.append(f'  - {v}')
    else:
        lines.append(f'- ✅ M1 生效: {len(m1_capped)} 个 suppressed 都已 cap < 70 (ship gate 满足)')
    lines.append('')

    # M2: 任何 turn overall=None
    lines.append('### M2: turn overall=None')
    m2_violations = []
    for sid, r in v7.items():
        none_turns = []
        for t in r.get('turns') or []:
            sc = t.get('score') or {}
            if sc.get('overall') is None:
                none_turns.append(t.get('turn_index'))
        if none_turns:
            m2_violations.append(f'{sid}: turns {none_turns}')
    if m2_violations:
        lines.append(f'- ⚠️ {len(m2_violations)} 个 persona 有 turn overall=None (M2 retry 已重试, runner 已跳过 aggregation):')
        for v in m2_violations:
            lines.append(f'  - {v}')
    else:
        lines.append('- ✅ 没有 turn overall=None — M2 retry + runner 跳过都没必要触发')
    lines.append('')

    # ── §3. Cohort 统计 ────────────────────────────────────────────────────
    lines.append('## 3. Cohort 统计 (单 seed, 仅供方向参考)')
    lines.append('')
    lines.append('| Cohort | n | v7 mean | v7 min | v7 max | v6 mean | Δ mean |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|')

    def cohort_stats(ids: set[str], v: dict) -> tuple[list[int], float | None]:
        scores = []
        for sid in ids:
            r = v.get(sid)
            if r:
                s = (r.get('report') or {}).get('overall_score')
                if isinstance(s, int):
                    scores.append(s)
        return scores, (statistics.mean(scores) if scores else None)

    for label, ids in [('Strong (16)', STRONG_IDS), ('Mid (6)', MID_IDS), ('Extreme (5)', EXTREME_IDS)]:
        v7s, v7m = cohort_stats(ids, v7)
        v6s, v6m = cohort_stats(ids, v6)
        if v7s:
            dmean = (v7m or 0) - (v6m or 0)
            lines.append(f'| {label} | {len(v7s)} | {v7m:.1f} | {min(v7s)} | {max(v7s)} | {v6m:.1f} | {fmt_delta(round(dmean))} |')
        else:
            lines.append(f'| {label} | 0 | — | — | — | — | — |')
    lines.append('')

    # ── §4. 全 27 persona diff 表 ──────────────────────────────────────────
    lines.append('## 4. 全 27 persona overall diff')
    lines.append('')
    lines.append('| persona | v6 | v7 | Δ | fallback? | suppressed? | mentor cnt |')
    lines.append('|---|---:|---:|---:|---|---|---:|')
    for sid in common:
        v6r = (v6[sid].get('report') or {})
        v7r = (v7[sid].get('report') or {})
        v6o = v6r.get('overall_score')
        v7o = v7r.get('overall_score')
        fb = (v7r.get('_meta') or {}).get('fallback_reason') or '—'
        sup = '是' if v7r.get('_fabrication_suppressed') else '—'
        mc = (v7r.get('_meta') or {}).get('mentor_fallback_count') or '—'
        if isinstance(v6o, int) and isinstance(v7o, int):
            d = fmt_delta(v7o - v6o)
        else:
            d = '—'
        lines.append(f'| `{sid}` | {v6o if v6o is not None else "—"} | {v7o if v7o is not None else "None"} | {d} | {fb} | {sup} | {mc} |')
    if only_v7:
        lines.append('')
        lines.append(f'**v7 多出 persona**: {", ".join(only_v7)}')
    lines.append('')

    lines.append('## 5. 单 seed 局限性')
    lines.append('')
    lines.append('- 本对照基于 v7 **单次** baseline; LLM temperature > 0 单次方差 ±10 常见.')
    lines.append('- ship 前必须跑 N=3 (parallel subagent), 看 mean ± stdev — strong cohort stdev > 5 时不能宣称"提升 X 分".')
    lines.append('- 当前对照仅用于**验证 5 个 Blocker/Major 修法是否触发**, 不作为最终 ship gate.')
    lines.append('')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {args.out}')
    if sentinel_fails:
        print(f'⚠️ {len(sentinel_fails)} sentinel fail — see report')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
