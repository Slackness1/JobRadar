"""从 SAIF MF 就业报告 PDF 抽取流向数据 (公司 / 岗位 / 人数)。

输出: backend/data/saif_employment_reports_extracted.json
   {
     "2023": [{"company": "易方达基金", "role_type": "行业研究员", "count": 3, "industry": "公募基金"}, ...],
     "2024": [...],
     "2025": [...]
   }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pdfplumber
from openai import OpenAI

REPORT_DIR = Path("backend/data/_private/saif_reports")
OUTPUT = Path("backend/data/saif_employment_reports_extracted.json")
YEARS = ["2023", "2024", "2025"]


SYSTEM_PROMPT = """你是金融求职报告结构化抽取器。读取上海高级金融学院 (SAIF) MF 项目年度就业报告 PDF 文本,
抽出每个学生的去向: 公司名 / 岗位类型 / 行业大类。

只关心**投研相关方向**: 公募 / 私募 / 资管 / 量化 / 卖方研究 / 险资。
不关心: 银行管培 / IBD / 咨询 / 体制内 / FinTech。

输出纯 JSON 数组, 每条:
{
  "company": "<标准化公司全名, 如 易方达基金管理有限公司>",
  "role_type": "<行业研究员/量化研究员/固收研究/FOF 投资经理/卖方分析师/...>",
  "count": <人数, 报告里如有数字就用, 没有就 1>,
  "industry": "<公募基金/私募/保险资管/券商资管/银行理财子/量化私募/券商研究所>"
}

如果某段是岗位介绍而非学生流向, 跳过。
"""


def extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(p.extract_text() or "" for p in pdf.pages)


def extract_year(year: str, client: OpenAI) -> list[dict]:
    pdf_path = REPORT_DIR / f"saif_mf_{year}.pdf"
    text = extract_text(pdf_path)
    # 报告很长, 分块跑 (每块约 8000 字, 留 buffer 给 prompt)
    chunks = [text[i:i + 8000] for i in range(0, len(text), 8000)]
    all_records = []
    for idx, chunk in enumerate(chunks):
        print(f"  [{year}] chunk {idx+1}/{len(chunks)} 抽取中...")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"年度: {year}\n\n报告片段:\n{chunk}\n\n请输出 JSON 数组 (key 直接是 records, 顶层 dict 包一层方便解析)"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
            records = data.get("records") or data.get("students") or data.get("data") or []
            if isinstance(records, list):
                all_records.extend(records)
        except (json.JSONDecodeError, KeyError):
            print(f"    [WARN] chunk {idx+1} parse failed, skip")
    return all_records


def main() -> None:
    api_key = os.environ.get("RESUME_COPILOT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: 缺 RESUME_COPILOT_API_KEY", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    out: dict[str, list[dict]] = {}
    for year in YEARS:
        pdf = REPORT_DIR / f"saif_mf_{year}.pdf"
        if not pdf.exists():
            print(f"[SKIP] {pdf} not found")
            continue
        print(f"处理 {year}...")
        out[year] = extract_year(year, client)
        print(f"  → {len(out[year])} 条记录")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写入 {OUTPUT}")
    print(f"  2023={len(out.get('2023',[]))} / 2024={len(out.get('2024',[]))} / 2025={len(out.get('2025',[]))}")


if __name__ == "__main__":
    main()
