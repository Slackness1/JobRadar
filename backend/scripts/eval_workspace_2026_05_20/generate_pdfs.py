#!/usr/bin/env python3
"""Generate PDF resumes for 8 workspace eval personas.

Tries pdf_export.render_resume_pdf first (Playwright + LXGW WenKai).
Falls back to a simpler fpdf2 + LXGW WenKai template when Playwright isn't
installed locally — the parser only needs text-extractable PDF bytes anyway.

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_workspace_2026_05_20/generate_pdfs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/
PERSONA_DIR = ROOT / "tests" / "eval" / "personas" / "workspace_2026_05_20"
OUT_DIR = ROOT / "scripts" / "_out" / "eval_workspace_2026_05_20" / "pdfs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# LXGW WenKai font (handles CJK glyphs). On dev VPS it lives under
# /home/ubuntu/opencode-worktrees/.../fonts/; locally we copied it to /tmp.
FONT_CANDIDATES = [
    Path("/tmp/LXGWWenKai-Regular.ttf"),
    ROOT / "app" / "services" / "resume_copilot" / "fonts" / "LXGWWenKai-Regular.ttf",
    Path("/home/ubuntu/opencode-worktrees/jobrador-edit/backend/app/services/resume_copilot/fonts/LXGWWenKai-Regular.ttf"),
]


def _find_font() -> Path | None:
    for p in FONT_CANDIDATES:
        if p.is_file():
            return p
    return None


def _persona_to_payload(persona: dict) -> dict:
    """Reshape persona['resume'] into a ResumeProfilePayload-compatible dict."""
    resume = persona["resume"]
    return {
        "basic_info": resume.get("basic_info", {}),
        "education": resume.get("education", []),
        "internships": resume.get("internships", []),
        "projects": resume.get("projects", []),
        "skills": resume.get("skills", {"technical": [], "tools": [], "languages": []}),
        "languages": [],
        "awards": resume.get("awards", []),
        "candidate_summary": resume.get("candidate_summary", ""),
        "inferred_roles": resume.get("inferred_roles", []),
        "inferred_tracks": resume.get("inferred_tracks", []),
    }


def _try_playwright_pdf(payload: dict, out_path: Path) -> bool:
    """Returns True iff rendered successfully via app.services.resume_copilot.pdf_export."""
    try:
        from app.schemas_resume_copilot import ResumeProfilePayload
        from app.services.resume_copilot.pdf_export import render_resume_pdf
    except ImportError:
        return False
    try:
        profile = ResumeProfilePayload.model_validate(payload)
        pdf_bytes = render_resume_pdf(profile)
    except Exception as exc:
        print(f"  [playwright] failed: {exc}", file=sys.stderr)
        return False
    out_path.write_bytes(pdf_bytes)
    return True


def _fpdf_fallback_pdf(payload: dict, out_path: Path, font_path: Path) -> None:
    """fpdf2 + LXGW WenKai. Simple linear layout, text-extractable via pypdf."""
    from fpdf import FPDF

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("LXGW", "", str(font_path))
    pdf.add_page()

    bi = payload.get("basic_info", {}) or {}
    name = bi.get("name", "简历")
    headline = bi.get("headline", "")
    contact_parts = [bi.get(k, "") for k in ("email", "phone", "location")]
    contact = " · ".join(p for p in contact_parts if p)

    # Title block
    pdf.set_font("LXGW", size=20)
    pdf.cell(0, 12, name, new_x="LMARGIN", new_y="NEXT", align="C")
    if headline:
        pdf.set_font("LXGW", size=10)
        pdf.cell(0, 6, headline, new_x="LMARGIN", new_y="NEXT", align="C")
    if contact:
        pdf.set_font("LXGW", size=9)
        pdf.cell(0, 6, contact, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    def _h2(title: str) -> None:
        pdf.set_font("LXGW", size=13)
        pdf.cell(page_w, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(120, 120, 120)
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.line(x, y, x + page_w, y)
        pdf.ln(1)

    def _para(text: str, size: int = 10) -> None:
        if not text:
            return
        pdf.set_font("LXGW", size=size)
        pdf.multi_cell(page_w, 5.5, text)

    def _bullet(text: str) -> None:
        pdf.set_font("LXGW", size=10)
        pdf.multi_cell(page_w, 5.5, f"- {text}")

    # Summary
    summary = payload.get("candidate_summary") or ""
    if summary:
        _h2("个人简介")
        _para(summary)
        pdf.ln(1)

    # Education
    if payload.get("education"):
        _h2("教育背景")
        for edu in payload["education"]:
            head = " · ".join(str(edu.get(k, "")) for k in ("school", "degree", "major") if edu.get(k))
            dates = f"{edu.get('start_date', '')} – {edu.get('end_date', '')}"
            pdf.set_font("LXGW", size=11)
            pdf.cell(page_w, 6,f"{head}   ({dates})", new_x="LMARGIN", new_y="NEXT")
            for h in edu.get("highlights", []):
                _bullet(h)
            pdf.ln(1)

    # Internships
    if payload.get("internships"):
        _h2("实习经历")
        for it in payload["internships"]:
            head = " · ".join(str(it.get(k, "")) for k in ("company", "role") if it.get(k))
            dates = f"{it.get('start_date', '')} – {it.get('end_date', '')}"
            pdf.set_font("LXGW", size=11)
            pdf.cell(page_w, 6,f"{head}   ({dates})", new_x="LMARGIN", new_y="NEXT")
            for b in it.get("bullets", []):
                _bullet(b)
            pdf.ln(1)

    # Projects
    if payload.get("projects"):
        _h2("项目经历")
        for p in payload["projects"]:
            head = " · ".join(str(p.get(k, "")) for k in ("name", "role") if p.get(k))
            dur = p.get("duration", "")
            pdf.set_font("LXGW", size=11)
            pdf.cell(page_w, 6,f"{head}   ({dur})", new_x="LMARGIN", new_y="NEXT")
            desc = p.get("description", "")
            if desc:
                _para(desc, size=10)
            for b in p.get("bullets", []):
                _bullet(b)
            pdf.ln(1)

    # Skills
    sk = payload.get("skills") or {}
    if any(sk.get(k) for k in ("technical", "tools", "languages")):
        _h2("专业技能")
        if sk.get("technical"):
            _para("技术: " + " / ".join(sk["technical"]))
        if sk.get("tools"):
            _para("工具: " + " / ".join(sk["tools"]))
        if sk.get("languages"):
            _para("语言: " + " / ".join(sk["languages"]))
        pdf.ln(1)

    # Awards
    if payload.get("awards"):
        _h2("荣誉奖项")
        for a in payload["awards"]:
            _bullet(a)

    pdf.output(str(out_path))


def main() -> int:
    font_path = _find_font()
    if not font_path:
        print("ERROR: LXGW WenKai font not found in any candidate path.", file=sys.stderr)
        return 2
    print(f"[font] {font_path}")

    persona_files = sorted(PERSONA_DIR.glob("P*.json"))
    if not persona_files:
        print(f"ERROR: no persona files found in {PERSONA_DIR}", file=sys.stderr)
        return 2

    results = []
    for p_file in persona_files:
        persona = json.loads(p_file.read_text(encoding="utf-8"))
        payload = _persona_to_payload(persona)
        out_path = OUT_DIR / f"{p_file.stem}.pdf"

        # Try playwright pipeline first
        ok = _try_playwright_pdf(payload, out_path)
        engine = "playwright"
        if not ok:
            _fpdf_fallback_pdf(payload, out_path, font_path)
            engine = "fpdf2"
        size = out_path.stat().st_size
        results.append((p_file.stem, engine, size, out_path))
        print(f"  [{engine}] {p_file.stem}.pdf  {size:>7} bytes  →  {out_path}")

    print()
    print(json.dumps(
        {"out_dir": str(OUT_DIR), "files": [
            {"persona": r[0], "engine": r[1], "size_bytes": r[2], "path": str(r[3])}
            for r in results
        ]},
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
