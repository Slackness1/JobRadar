"""Jerry-flavored interview rubric anchors.

10 份与 senior 战略咨询老师 Jerry 的逐字稿提炼为：
- `jerry_anchors.json`：6 维 rubric × 3 档 anchor + 6 条反模式
- `jerry_qa_seed.jsonl`：10 条 (问题, 理想骨架, 常见踩坑, Jerry 原话引用)

注入 LLM judge / interviewer system prompt 后，反馈语气与评分标尺与
Jerry 实际辅导一致 —— 不必 fine-tune，靠 few-shot 锚点即可。

Loader 用 module-level 缓存：anchors 文件几 KB，进程内只 IO 一次。
"""

from __future__ import annotations

import json
import pathlib
import threading

_ANCHORS_PATH = pathlib.Path(__file__).parent / 'jerry_anchors.json'
_QA_SEED_PATH = pathlib.Path(__file__).parent / 'jerry_qa_seed.jsonl'

_lock = threading.Lock()
_anchors_cache: dict = {}
_qa_seeds_cache: list = []


def load_rubric_anchors() -> dict:
    """Return the parsed `jerry_anchors.json` dict. Cached per-process."""
    global _anchors_cache
    if _anchors_cache:
        return _anchors_cache
    with _lock:
        if not _anchors_cache:
            _anchors_cache = json.loads(_ANCHORS_PATH.read_text(encoding='utf-8'))
    return _anchors_cache


def load_qa_seeds() -> list:
    """Return list of QA-seed dicts from `jerry_qa_seed.jsonl`. Cached per-process."""
    global _qa_seeds_cache
    if _qa_seeds_cache:
        return _qa_seeds_cache
    seeds: list = []
    for line in _QA_SEED_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        seeds.append(json.loads(line))
    with _lock:
        if not _qa_seeds_cache:
            _qa_seeds_cache = seeds
    return _qa_seeds_cache


def build_judge_prompt_fragment(track: str | None = None) -> str:
    """Build a markdown prompt fragment to inject into the report-LLM system prompt.

    Args:
        track: optional track filter — if given, only QA seeds whose `track`
            list contains this string (or "all") are included as few-shot.
            None = include first 3 seeds regardless.

    The fragment names the dimensions, gives Jerry's anchor quote for the
    "5-level" target description, and lists anti-patterns. Token budget
    ~1.5K — fits comfortably in any modern context window.
    """
    anchors = load_rubric_anchors()

    lines: list[str] = []
    lines.append('## 评分锚点')
    lines.append('')
    lines.append('对以下 6 个维度逐项打分（0-100）。反馈应简练、有具体落地建议、')
    lines.append('引用行业洞察、用第二人称提醒。**不要在输出中提及锚点来源或"老师"等字眼**。')
    lines.append('')

    for dim in anchors['dimensions']:
        weight_pct = int(dim['weight'] * 100)
        top_anchor = next((a for a in dim['anchors'] if a['level'] == 5), None)
        bottom_anchor = next((a for a in dim['anchors'] if a['level'] == 1), None)
        lines.append(f"### {dim['name']} ({dim['id']}, 权重 {weight_pct}%)")
        lines.append(f"**核心理念**：{dim['rationale']}")
        if top_anchor:
            lines.append(f"**满分锚点**：{top_anchor['description']}")
            lines.append(f"  > Jerry 原话：「{top_anchor['quote']}」")
        if bottom_anchor:
            lines.append(f"**典型踩坑**：{bottom_anchor['description']}")
        lines.append('')

    lines.append('## 反模式触发器')
    lines.append('如下任一情形触发，在 `improvements` 中必须包含对应建议：')
    for ap in anchors['anti_patterns']:
        lines.append(f"- **{ap['label']}** ({ap['id']})：{ap['trigger']}")
    lines.append('')

    lines.append('## 反馈语气示范')
    seeds = load_qa_seeds()
    if track and track != 'all':
        relevant = [s for s in seeds if track in s.get('track', []) or 'all' in s.get('track', [])]
    else:
        relevant = seeds[:3]
    for s in relevant[:3]:
        lines.append(f"问题：{s['question']}")
        lines.append(f"  理想骨架：{' / '.join(s['ideal_skeleton'][:3])}")
        lines.append(f"  常见踩坑：{s['common_pitfalls'][0]}")
        lines.append(f"  Jerry 原话：「{s['jerry_quote'][:80]}…」")
        lines.append('')

    return '\n'.join(lines)


__all__ = [
    'load_rubric_anchors',
    'load_qa_seeds',
    'build_judge_prompt_fragment',
]
