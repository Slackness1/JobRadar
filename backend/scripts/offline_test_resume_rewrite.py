"""SAIF 简历改写 离线评测 harness — 简历模块三个 metric:
  ④ Evidence Groundedness — 改写建议是否基于已有证据 (跑 audit_draft + _detect_fabricated_numbers)
  ⑤ Overclaim Rate — 严重 fabrication (metric / role / tech) 命中率
  ⑥ Actionability — 所有 RewriteOption 还能 apply (有 field_path + improved)

目标:
  - Evidence Groundedness rate (clean options / 总 options) ≥ 90%
  - Overclaim Rate (severe risks / 总 options) ≤ 5%
  - Actionability rate (有 field_path + improved 的 options / 总 options) = 100%

用法:
  PYTHONPATH=. .venv/bin/python scripts/offline_test_resume_rewrite.py \\
    --load-profiles data/offline_test_rerank_ubuntu.json \\
    --n-bullets-per-profile 4
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumeProfilePayload,
    ResumeProjectItem,
    ResumeSkillsPayload,
    RewriteOption,
)
from app.services.resume_copilot.chat import (
    _audit_rewrite_options,
    _detect_fabricated_numbers,
    _profile_anchor_numbers,
    _profile_to_evidence_list,
)
from tests.eval.clients import build_simulator_client


SYSTEM_PROMPT = (
    "你是 SAIF 投研学生的简历改写助手。给定一条 internship bullet 原文 + 学生简历背景,"
    "**生成 2 个改写选项 (A / B)**:\n"
    "- A 是保守改写,主要在动词/连接词上微调,数字与角色保持原样\n"
    "- B 是大幅改写,允许重新表述,但**严格禁止**:\n"
    "  * 把 '参与/协助/辅助/配合/支持' 升级成 '主导/负责/带领/管理' (角色升级 = 编造)\n"
    "  * 引入原文里没有的数字 (如 5 改成 50,或加 '业内排名前三' 等)\n"
    "  * 引入原文里没有的技术栈/工具名 (如 Bloomberg / Wind 没提就别加)\n"
    "  * 引入原文里没有的成果声明 (如 '获奖' / '被采纳' / '获 leader 表扬')\n"
    "- 两个选项都要保留原文核心事实。如果原文写 '参与',改写也写 '参与/协助/支持',不要写 '主导'\n"
    "返回严格 JSON:{\"option_a\": str, \"option_b\": str}。不要 markdown。"
)


def generate_rewrite_options(client, profile: ResumeProfilePayload, target_bullet: str) -> dict:
    """调 LLM 生成一次 rewrite 的 A/B 两个 option text。"""
    raw = client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"学生简历:\n{profile.model_dump_json(exclude={'basic_info'})}\n\n"
                    f"待改写的 bullet:\n{target_bullet}\n\n"
                    "请给出 A / B 两个改写选项 (严格 JSON)。"
                ),
            },
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    return json.loads(raw)


def iter_internship_bullets(profile: ResumeProfilePayload, max_per_profile: int):
    """枚举 profile 的 internship bullets,每份最多取 max_per_profile 个。"""
    yielded = 0
    for i_idx, intern in enumerate(profile.internships or []):
        for b_idx, bullet in enumerate(intern.bullets or []):
            if not bullet or len(bullet) < 10:
                continue
            yield i_idx, b_idx, intern.company, bullet
            yielded += 1
            if yielded >= max_per_profile:
                return


def evaluate_options(
    options: list[RewriteOption],
    profile_dict: dict,
) -> dict:
    """对一组 options 跑 audit + 统计。

    返:
      {'total': N, 'evidence_clean': K, 'severe': S, 'warn': W, 'actionable': A}
    """
    # In-place audit
    _audit_rewrite_options(options, profile_dict)
    # 数字 fabrication (chat.py 的旧 fast-path)
    anchor = _profile_anchor_numbers(profile_dict)

    total = len(options)
    evidence_clean = 0
    severe = 0
    warn = 0
    actionable = 0
    risk_kind_counter = Counter()

    for opt in options:
        if opt.field_path and opt.improved:
            actionable += 1
        if not opt.audit_risks:
            evidence_clean += 1
        else:
            for risk in opt.audit_risks:
                risk_kind_counter[risk['kind']] += 1
            severity = opt.warning_severity or 'info'
            if severity == 'severe':
                severe += 1
            elif severity == 'warn':
                warn += 1
        # legacy 数字 fabrication
        if anchor and opt.improved:
            fabricated = _detect_fabricated_numbers(opt.improved, anchor)
            if fabricated:
                risk_kind_counter['legacy_number_fab'] += len(fabricated)

    return {
        'total': total,
        'evidence_clean': evidence_clean,
        'severe': severe,
        'warn': warn,
        'actionable': actionable,
        'risk_kinds': dict(risk_kind_counter),
    }


def load_profiles_from_recommendation_report(path: Path) -> list[ResumeProfilePayload]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    profiles = []
    for p_dict in raw.get('profiles') or []:
        try:
            profiles.append(ResumeProfilePayload.model_validate(p_dict))
        except Exception as exc:
            print(f"  skip profile (validation error: {exc!r})")
    return profiles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--load-profiles",
        default="data/offline_test_rerank_ubuntu.json",
        help="从已有 N 份模拟简历的 recommendation report 中复用 profiles",
    )
    parser.add_argument(
        "--n-bullets-per-profile",
        type=int,
        default=3,
        help="每份简历测多少个 bullet 的改写 (默认 3)",
    )
    parser.add_argument(
        "--out",
        default="data/offline_test_rewrite.json",
    )
    args = parser.parse_args()

    profiles = load_profiles_from_recommendation_report(Path(args.load_profiles))
    print(f"loaded {len(profiles)} profiles from {args.load_profiles}")

    client = build_simulator_client()
    agg = Counter()
    risk_kinds_agg = Counter()
    per_profile = []
    total_options = 0
    bullet_count = 0

    for p_idx, profile in enumerate(profiles):
        profile_dict = profile.model_dump()
        profile_options: list[RewriteOption] = []
        bullets_for_profile = list(iter_internship_bullets(profile, args.n_bullets_per_profile))

        print(f"\n[{p_idx+1}/{len(profiles)}] profile with {len(bullets_for_profile)} bullets to rewrite")
        for i_idx, b_idx, company, bullet in bullets_for_profile:
            print(f"  bullet ({company}): {bullet[:50]}…")
            try:
                raw = generate_rewrite_options(client, profile, bullet)
            except Exception as exc:
                print(f"    LLM ERROR: {exc!r}")
                continue
            field_path = f'internships.{i_idx}.bullets'
            for letter, key in [('A', 'option_a'), ('B', 'option_b')]:
                improved_text = str(raw.get(key, '') or '').strip()
                if not improved_text:
                    continue
                profile_options.append(RewriteOption(
                    option_id=letter,
                    label=f'方案 {letter}',
                    section='internships',
                    field_path=field_path,
                    target_title=f'{company} (bullet {b_idx})',
                    original=[bullet],
                    improved=[improved_text],
                    rationale='',
                ))
            bullet_count += 1

        if not profile_options:
            continue
        report = evaluate_options(profile_options, profile_dict)
        per_profile.append({
            'profile_idx': p_idx,
            'options_n': report['total'],
            **report,
        })
        for k in ('total', 'evidence_clean', 'severe', 'warn', 'actionable'):
            agg[k] += report[k]
        for kind, cnt in (report.get('risk_kinds') or {}).items():
            risk_kinds_agg[kind] += cnt
        total_options += report['total']

    # Aggregate
    print('\n=== aggregate ===')
    print(f'  profiles tested: {len(per_profile)}')
    print(f'  bullets rewritten: {bullet_count}')
    print(f'  total options: {total_options}')

    if total_options:
        evidence_rate = 100 * agg['evidence_clean'] / total_options
        severe_rate = 100 * agg['severe'] / total_options
        warn_rate = 100 * agg['warn'] / total_options
        actionable_rate = 100 * agg['actionable'] / total_options
        print(f'  ④ Evidence Groundedness:  {evidence_rate:.1f}% clean (目标 ≥ 90%)')
        print(f'  ⑤ Overclaim (severe):     {severe_rate:.1f}% (目标 ≤ 5%)')
        print(f'      Warn (soft risks):    {warn_rate:.1f}% (建议 ≤ 30%)')
        print(f'  ⑥ Actionability:          {actionable_rate:.1f}% (目标 = 100%)')
    print('\n  risk_kinds 分布:')
    for k, v in risk_kinds_agg.most_common():
        print(f'    {k:25} {v}')

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        'profiles_n': len(per_profile),
        'bullets_rewritten': bullet_count,
        'total_options': total_options,
        'aggregate': dict(agg),
        'risk_kinds': dict(risk_kinds_agg),
        'per_profile': per_profile,
    }, ensure_ascii=False, indent=2), 'utf-8')
    print(f'\nfull report → {out_path}')


if __name__ == '__main__':
    main()
