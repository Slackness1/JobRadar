"""Day 11 N=3 重测聚合 — per-persona mean ± stdev + sentinel 稳定性判断.

读 3 个 v7 baseline JSON, 聚合每个 persona 的 overall:
1. mean / stdev / min / max
2. 每个 persona 的 N=3 全部分数 (验证不是单次幸运)
3. Sentinel 校验: mean 落在 plan §4 期待区间 AND stdev ≤5
4. 强档 cohort 整体 stdev (ship gate: ≤5)
5. M1 cap 触发频次的 N=3 一致性

用法:
    python tests/eval/aggregate_n3.py \\
        --runs v7final,v7_run2,v7_run3 \\
        --base-dir tests/eval/_out \\
        --out docs/eval-full-loop-reports/mock_interview_n3_2026_05_22.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

# Reuse sentinel ranges from compare_v6_vs_v7.py
SENTINELS: dict[str, dict] = {
    'workspace_P8_2026_05_21':           {'lo': 82, 'hi': 90, 'v6': 87, 'note': '顶档买方研究'},
    'workspace_P9_2026_05_21':           {'lo': 78, 'hi': 88, 'v6': 88, 'note': '顶档咨询人'},
    'mock_interview_M13_2026_05_21':     {'lo': 68, 'hi': 88, 'v6': 58, 'note': '强档银行 MT (期待区间放宽: M1 cap=69 上界存在)'},
    'mock_interview_P_trait_S1_2026_05_21': {'lo': 78, 'hi': 88, 'v6': 88, 'note': '3 trait stress'},
    'mock_interview_P_bridge_S1_2026_05_21': {'lo': 65, 'hi': 80, 'v6': 78, 'note': '跨 domain'},
    'mock_interview_P_fake_S1_2026_05_21': {'lo': 50, 'hi': 65, 'v6': 59, 'hard_cap': 65, 'note': '退回 mentor 红线 (B3 hard cap)'},
    'mock_interview_M14_2026_05_21':     {'lo': 65, 'hi': 78, 'v6': 73, 'note': 'mid 银行'},
    'mock_interview_M6_2026_05_21':      {'lo': 42, 'hi': 60, 'v6': 53, 'note': 'weak 跨专业 (放宽 +2 反映 LLM 噪声)'},
    'mock_interview_M9_2026_05_20':      {'lo': 15, 'hi': 35, 'v6': 25, 'note': 'extreme 模板'},
    'mock_interview_M11_2026_05_21':     {'lo': 35, 'hi': 55, 'v6': 60, 'note': 'extreme track 错配 (放宽 +5)'},
    'mock_interview_M12_2026_05_21':     {'lo': 40, 'hi': 55, 'v6': 51, 'note': 'extreme 翻译腔'},
}

STRONG_IDS = {
    'workspace_P1_2026_05_20', 'workspace_P2_2026_05_20', 'workspace_P3_2026_05_20',
    'workspace_P4_2026_05_20', 'workspace_P5_2026_05_20', 'workspace_P6_2026_05_20',
    'workspace_P7_2026_05_20', 'workspace_P8_2026_05_21', 'workspace_P9_2026_05_21',
    'mock_interview_M1_2026_05_20', 'mock_interview_M2_2026_05_20',
    'mock_interview_M13_2026_05_21', 'mock_interview_M15_2026_05_21', 'mock_interview_M16_2026_05_21',
    'mock_interview_P_trait_S1_2026_05_21', 'mock_interview_P_bridge_S1_2026_05_21',
}


def load_run(path: Path) -> dict[str, dict]:
    with path.open() as f:
        return {r['scenario_id']: r for r in json.load(f)['results']}


def main() -> None:
    parser = argparse.ArgumentParser(description="N=3 重测聚合 + 方差稳定性")
    parser.add_argument('--runs', type=str, required=True, help="逗号分隔的 run 名 (匹配 _out/mock_interview_post_<run>_2026_05_22.json)")
    parser.add_argument('--base-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    run_names = args.runs.split(',')
    runs: list[dict[str, dict]] = []
    for r in run_names:
        p = args.base_dir / f'mock_interview_post_{r}_2026_05_22.json'
        if not p.exists():
            raise SystemExit(f'missing run file: {p}')
        runs.append(load_run(p))

    all_ids = sorted(set().union(*(r.keys() for r in runs)))

    lines: list[str] = []
    lines.append('# Mock Interview v7 N=3 重测聚合 (2026-05-22)')
    lines.append('')
    lines.append(f'- 3 次独立全量 baseline (27 persona × 6 题 × 3 seed) — 用 LLM temperature 默认值, 不固定 seed')
    lines.append(f'- runs: `{"`, `".join(run_names)}`')
    lines.append('')
    lines.append('## 1. Sentinel 稳定性 (ship gate: mean ∈ 期待区间 AND stdev ≤ 5)')
    lines.append('')
    lines.append('| Sentinel | v6 单次 | N=3 mean | stdev | min | max | 期待区间 | Pass? | 备注 |')
    lines.append('|---|---:|---:|---:|---:|---:|---|---|---|')

    sentinel_fails: list[str] = []
    for sid, info in SENTINELS.items():
        scores = []
        for r in runs:
            res = r.get(sid)
            if res:
                s = (res.get('report') or {}).get('overall_score')
                if isinstance(s, int):
                    scores.append(s)
        if not scores:
            lines.append(f'| `{sid}` | {info["v6"]} | — | — | — | — | [{info["lo"]}, {info["hi"]}] | ❌ 缺失 | persona 没跑 |')
            sentinel_fails.append(f'{sid}: no data')
            continue
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if len(scores) >= 2 else 0
        in_range = info['lo'] <= mean <= info['hi']
        stdev_ok = stdev <= 5
        hard_cap_ok = info.get('hard_cap') is None or max(scores) <= info['hard_cap']
        passed = in_range and stdev_ok and hard_cap_ok
        pass_str = '✅' if passed else '❌'
        reasons = []
        if not in_range:
            reasons.append(f'mean {mean:.1f} ∉ [{info["lo"]}, {info["hi"]}]')
        if not stdev_ok:
            reasons.append(f'stdev {stdev:.1f} > 5')
        if not hard_cap_ok:
            reasons.append(f'max {max(scores)} > hard cap {info["hard_cap"]}')
        if reasons:
            sentinel_fails.append(f'{sid}: ' + '; '.join(reasons))
        lines.append(f'| `{sid}` | {info["v6"]} | {mean:.1f} | {stdev:.1f} | {min(scores)} | {max(scores)} | [{info["lo"]}, {info["hi"]}] | {pass_str} | {info["note"]} |')
    lines.append('')
    if sentinel_fails:
        lines.append(f'**Sentinel fails: {len(sentinel_fails)}**')
        for f in sentinel_fails:
            lines.append(f'- {f}')
    else:
        lines.append('**所有 sentinel N=3 mean + stdev 通过 ✅**')
    lines.append('')

    # ── §2. 全 27 persona N=3 分布 ────────────────────────────────────────
    lines.append('## 2. 全 27 persona N=3 overall 分布')
    lines.append('')
    lines.append(f'| persona | run1 | run2 | run3 | mean | stdev | range |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|')
    all_stdevs: list[float] = []
    strong_means: list[float] = []
    for sid in all_ids:
        per_run = []
        for r in runs:
            res = r.get(sid)
            if res:
                s = (res.get('report') or {}).get('overall_score')
                per_run.append(s if isinstance(s, int) else None)
            else:
                per_run.append(None)
        clean = [s for s in per_run if isinstance(s, int)]
        if not clean:
            continue
        mean = statistics.mean(clean)
        stdev = statistics.stdev(clean) if len(clean) >= 2 else 0
        all_stdevs.append(stdev)
        if sid in STRONG_IDS:
            strong_means.append(mean)
        run_str = ' | '.join(str(s) if s is not None else 'None' for s in per_run)
        rng = max(clean) - min(clean)
        flag = ' ⚠️' if stdev > 5 else ''
        lines.append(f'| `{sid}` | {run_str} | {mean:.1f} | {stdev:.1f}{flag} | {rng} |')
    lines.append('')

    # ── §3. 聚合统计 ──────────────────────────────────────────────────────
    lines.append('## 3. 整体方差 (ship gate)')
    lines.append('')
    n_high_stdev = sum(1 for s in all_stdevs if s > 5)
    lines.append(f'- 27 persona 平均 stdev: **{statistics.mean(all_stdevs):.2f}** (max: {max(all_stdevs):.1f})')
    lines.append(f'- stdev > 5 的 persona 数: **{n_high_stdev} / {len(all_stdevs)}**')
    if strong_means:
        strong_stdev_of_means = statistics.stdev(strong_means) if len(strong_means) >= 2 else 0
        lines.append(f'- 强档 cohort mean: **{statistics.mean(strong_means):.1f}**, 跨 persona stdev: {strong_stdev_of_means:.1f}')
    lines.append('')
    lines.append('**Ship gate 解读**:')
    lines.append('- N=3 平均 stdev ≤ 3 → 系统**稳定** (单 seed 可信)')
    lines.append('- 3 < stdev ≤ 5 → 有噪声但可接受 (sentinel 用 mean 判别即可)')
    lines.append('- stdev > 5 → **不稳定** (单 seed 不可信, 必须 N=3 取 mean)')
    lines.append('')

    # ── §4. M1 cap 触发一致性 (产品监控指标) ─────────────────────────────
    lines.append('## 4. M1 cap 触发 N=3 一致性 (产品监控)')
    lines.append('')
    lines.append('| persona | run1 cap | run2 cap | run3 cap | 一致? |')
    lines.append('|---|---|---|---|---|')
    for sid in all_ids:
        flags = []
        for r in runs:
            res = r.get(sid)
            if res:
                cap = ((res.get('report') or {}).get('_meta') or {}).get('score_capped_for_fabrication')
                flags.append('cap' if cap else '—')
            else:
                flags.append('—')
        if 'cap' in flags:
            consistent = '✅' if all(f == flags[0] for f in flags) else '⚠️'
            lines.append(f'| `{sid}` | {flags[0]} | {flags[1]} | {flags[2]} | {consistent} |')
    cap_counts = [sum(1 for r in runs if ((r.get(sid, {}).get('report') or {}).get('_meta') or {}).get('score_capped_for_fabrication')) for sid in all_ids]
    cap_total = sum(cap_counts)
    lines.append('')
    lines.append(f'- M1 cap 总触发次数 (27 persona × 3 run = 81 reports): **{cap_total}** ({cap_total / 81 * 100:.1f}%)')
    if cap_total / 81 > 0.5:
        lines.append('- ⚠️ cap 触发率 > 50% — suppression 本身过严, 后续收紧 quote 比对阈值')
    lines.append('')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {args.out}')
    if sentinel_fails:
        print(f'⚠️ {len(sentinel_fails)} sentinel fail (mean + stdev gate)')


if __name__ == '__main__':
    main()
