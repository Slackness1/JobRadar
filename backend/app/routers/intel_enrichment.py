"""Intel-card enrichment endpoints.

GET /api/intel/company-card?company=...&role=...&refresh=0
GET /api/intel/demo-page?company=...&role=...     # standalone HTML preview
"""
from __future__ import annotations

import html

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.intel import enrichment

router = APIRouter(prefix="/api/intel", tags=["intel"])


@router.get("/company-card")
def company_card(
    company: str = Query(..., min_length=1, description="Canonical company name (e.g. 中金公司)"),
    role: str | None = Query(default=None, description="Canonical role name (e.g. 投行承做)"),
    k: int = Query(default=20, ge=5, le=40, description="Number of insights to feed LLM"),
    refresh: int = Query(default=0, description="1 to bypass 30-day cache"),
    db: Session = Depends(get_db),
):
    return enrichment.enrich(
        db,
        company=company,
        role=role,
        k=k,
        use_cache=(refresh == 0),
    )


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _render_list(items, empty_msg: str = "—") -> str:
    if not items:
        return f'<span class="empty">{empty_msg}</span>'
    return "".join(f"<li>{_esc(i)}</li>" for i in items)


def _render_card_html(card: dict) -> str:
    comp = card.get("compensation") or {}
    req = card.get("requirements") or {}
    itv = card.get("interview") or {}
    voices = card.get("voices") or []
    company = _esc(card.get("company"))
    role = _esc(card.get("role")) or "全部岗位"
    summary = _esc(card.get("summary"))

    voice_html = "".join(
        f'''<div class="voice">
              <blockquote>{_esc(v.get("quote"))}</blockquote>
              <div class="vmeta">— @{_esc(v.get("author"))} · ❤ {_esc(v.get("likes"))}
                  · <a href="{_esc(v.get("url"))}" target="_blank">原帖</a></div>
            </div>''' for v in voices
    ) or '<span class="empty">无</span>'

    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"/>
<title>{company} · {role} 情报卡 — JobRadar</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", sans-serif;
         max-width: 760px; margin: 32px auto; padding: 0 18px;
         color: #2a2a2a; line-height: 1.55; background: #f5f4ed; }}
  .card {{ background: #fff; border-radius: 14px; padding: 24px 28px;
          box-shadow: 0 2px 12px rgba(0,0,0,.06); }}
  h1 {{ font-family: 'Fraunces', serif; font-size: 26px; margin: 0 0 4px;
       color: #c96442; }}
  h1 small {{ color: #888; font-weight: 400; font-size: 16px; }}
  .summary {{ background: #fdf5ef; border-left: 3px solid #c96442;
            padding: 12px 14px; margin: 18px 0 22px; border-radius: 6px; }}
  h2 {{ font-size: 15px; color: #c96442; margin: 22px 0 8px;
       border-bottom: 1px solid #ead7c8; padding-bottom: 4px; }}
  ul {{ margin: 4px 0 0; padding-left: 20px; }}
  ul li {{ margin: 2px 0; }}
  .empty {{ color: #aaa; }}
  .kv {{ display: grid; grid-template-columns: 90px 1fr; gap: 6px 12px; margin: 6px 0; }}
  .kv .k {{ color: #888; }}
  .voice {{ margin: 12px 0; }}
  .voice blockquote {{ margin: 0; padding: 8px 12px; background: #fafafa;
                       border-left: 2px solid #ddd; font-size: 14px; }}
  .vmeta {{ color: #888; font-size: 12px; margin-top: 3px; }}
  .footer {{ color: #aaa; font-size: 11px; margin-top: 24px; text-align: right; }}
  a {{ color: #c96442; }}
</style>
</head><body><div class="card">
  <h1>{company} <small>· {role}</small></h1>
  <div class="summary">{summary or '（暂无总结）'}</div>

  <h2>💰 待遇</h2>
  <div class="kv"><span class="k">薪资段</span><span>{_esc(comp.get("package")) or "—"}</span></div>
  <div class="kv"><span class="k">细节</span><span>{_esc(comp.get("details")) or "—"}</span></div>
  <div class="kv"><span class="k">补充</span><span>{_esc(comp.get("notes")) or "—"}</span></div>

  <h2>📋 岗位要求</h2>
  <div><b>硬条件</b><ul>{_render_list(req.get("hard"))}</ul></div>
  <div><b>软条件</b><ul>{_render_list(req.get("soft"))}</ul></div>

  <h2>🎯 面试体感</h2>
  <div class="kv"><span class="k">轮次</span><span>{_esc(itv.get("rounds")) or "—"}</span></div>
  <div class="kv"><span class="k">形式</span><span>{_esc(itv.get("format")) or "—"}</span></div>
  <div class="kv"><span class="k">难度</span><span>{_esc(itv.get("difficulty")) or "—"}</span></div>
  <div><b>真题/考点</b><ul>{_render_list(itv.get("key_questions"))}</ul></div>

  <h2>📝 日常工作</h2>
  <ul>{_render_list(card.get("daily_work"))}</ul>

  <h2>📈 进阶路径</h2>
  <div>{_esc(card.get("career_path")) or "—"}</div>

  <h2>💬 同辈原话（{len(voices)} 条逐字引用）</h2>
  {voice_html}

  <div class="footer">
    基于 {card.get("n_insights_used")} 条小红书 high-confidence 同辈洞察提炼 ·
    生成于 {card.get("generated_at")}
    {"· 命中缓存" if card.get("_from_cache") else ""}
  </div>
</div></body></html>"""


@router.get("/demo-page", response_class=HTMLResponse)
def demo_page(
    company: str = Query(default="中金公司"),
    role: str | None = Query(default="投行承做"),
    refresh: int = Query(default=0),
    db: Session = Depends(get_db),
):
    card = enrichment.enrich(db, company=company, role=role, k=20, use_cache=(refresh == 0))
    return HTMLResponse(_render_card_html(card))


# ---------------------------------------------------------------------------
# Job-intel card  GET /api/job-intel/card?job_id=&refresh=
# ---------------------------------------------------------------------------
from app.services.intel.job_card import build_job_card  # noqa: E402

job_intel_router = APIRouter(prefix="/api/job-intel", tags=["job-intel"])


@job_intel_router.get("/card")
def job_intel_card(
    job_id: int,
    refresh: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    from app.services.llm_json import deepseek_json_fn

    return build_job_card(db, job_id, use_cache=(refresh == 0), llm_fn=deepseek_json_fn)
