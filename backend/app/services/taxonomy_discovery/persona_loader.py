"""Persona loader — 读 backend/data/personas/P{1,2,3,6}.{pdf,json}。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PERSONA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "personas"
DEMO_IDS = ["P1", "P2", "P3", "P6"]


@dataclass
class Persona:
    id: str
    resume_text: str                # 从 PDF 提取的纯文本
    hidden_highlights: list[dict]   # 上帝视角隐藏亮点
    target_jd_anchors: list[str]    # 目标岗位关键词
    persona_voice: dict             # 说话风格
    raw_json: dict                  # 原始 JSON, 后面 LLM prompt 全文喂


def _extract_pdf_text(pdf_path: Path) -> str:
    """用 pdfplumber 提文字。pdfplumber 已在 requirements。"""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)


def load_persona(persona_id: str) -> Persona:
    """加载 persona: 优先用 .pdf, 没有 PDF 就 fallback 到 .md / .txt (生产用户上传的 markdown 简历直接读)。"""
    pdf = PERSONA_DIR / f"{persona_id}.pdf"
    js = PERSONA_DIR / f"{persona_id}.json"
    md = PERSONA_DIR / f"{persona_id}.md"
    txt = PERSONA_DIR / f"{persona_id}.txt"
    if not js.exists():
        raise FileNotFoundError(f"persona json missing for {persona_id}: {js}")
    raw = json.loads(js.read_text(encoding="utf-8"))

    if pdf.exists():
        resume_text = _extract_pdf_text(pdf)
    elif md.exists():
        resume_text = md.read_text(encoding="utf-8")
    elif txt.exists():
        resume_text = txt.read_text(encoding="utf-8")
    elif raw.get("resume_text"):
        # 兜底: JSON 内嵌 resume_text 字段
        resume_text = raw["resume_text"]
    else:
        raise FileNotFoundError(f"persona resume missing for {persona_id} (no .pdf/.md/.txt/raw_json.resume_text)")

    return Persona(
        id=persona_id,
        resume_text=resume_text,
        hidden_highlights=raw.get("hidden_highlights", []),
        target_jd_anchors=raw.get("target_jd_anchors", []),
        persona_voice=raw.get("persona_voice", {}),
        raw_json=raw,
    )


def load_all_demo_personas() -> list[Persona]:
    return [load_persona(pid) for pid in DEMO_IDS]
