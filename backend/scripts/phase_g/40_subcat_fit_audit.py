"""对口准确率审计 — 跨厂商判官(qwen)审 v1 sub_category 标签是否真对口。

目的:nDCG 的地基是"对口"。先量化:enrich 打的 sub_category 标签,judge 认不认同。
方法:按 v1 真源逐桶抽样 → qwen-plus(阿里,跨 DeepSeek 厂商)给每个岗判
      对口/部分对口/不对口(带 SAIF 金融领域消歧规则)→ 出逐桶 + 总准确率。

跑:cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/40_subcat_fit_audit.py [--per N]
判官:DASHSCOPE_API_KEY → qwen-plus(OpenAI 兼容端点,直连)。
"""
from __future__ import annotations
import argparse, json, re, sqlite3, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from openai import OpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "data", "jobradar.db")
REG = os.path.join(ROOT, "data", "_phase_g", "finance_taxonomy_v1.json")

def _env(k):
    for line in open(os.path.join(ROOT, ".env.local")):
        m = re.match(rf"\s*{k}\s*=\s*(.+?)\s*$", line)
        if m: return m.group(1)
    return None

# 判官 = GLM-5.1 走 OpenCode Go 中转(智谱,跨 DeepSeek 厂商,正规通道)。
# GLM-5.1 是推理模型 → max_tokens 要给够(否则 reasoning 吃光、content 空);UA 要 Mozilla(zen 封 urllib)。
JUDGE_MODEL = "glm-5.1"
_client = OpenAI(base_url=_env("RESUME_COPILOT_LLM_BASE_URL"), api_key=_env("RESUME_COPILOT_LLM_API_KEY"),
                 http_client=httpx.Client(trust_env=False, timeout=120, headers={"User-Agent": "Mozilla/5.0"}))

SYS = """你是中国金融校招的资深 HR 评审,熟悉买方/卖方/投行/量化各细分岗。判断一个岗位是否真属于给定的"细分方向"。
关键消歧规则(务必遵守):
- 机构销售 = 面向机构客户(公募/私募/保险/同业)的销售,**不含**面向个人的零售理财/渠道经理。
- 卖方研究 = 券商研究所;买方研究 = 公募/私募内部研究。两者不可混。
- 卖方固收研究员 = 券商研究所的固收/债券/利率研究,**不含**银行/资管/自营的固收。
- 公募/资管行业研究员 = 买方按行业做研究;与卖方研究区分开。
- 中后台/运营/风控(基金产品运营、合规、估值)≠ 前台投研。
- 量化各档(中频/高频/因子/开发QD/AI量化)按职责区分,别和买方基本面研究混。
只输出 JSON:{"verdict":"对口"|"部分对口"|"不对口","reason":"<20字内>"}"""

def judge(title, jd, subcat):
    prompt = f"细分方向:{subcat}\n岗位标题:{title}\n岗位JD(节选):{jd[:600]}\n\n这个岗位真属于「{subcat}」吗?只输出一行JSON。"
    try:
        r = _client.chat.completions.create(model=JUDGE_MODEL, temperature=0, max_tokens=4000,
            messages=[{"role": "system", "content": SYS}, {"role": "user", "content": prompt}])
        txt = r.choices[0].message.content or ""
        mm = re.search(r"\{.*\}", txt, re.S)  # 推理模型可能在 JSON 前带思考文本,抠出 JSON
        d = json.loads(mm.group(0)) if mm else {}
        return d.get("verdict", "?"), d.get("reason", "")
    except Exception as e:
        return "ERR", str(e)[:50]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--per", type=int, default=5); a = ap.parse_args()
    reg = json.load(open(REG))
    v1 = [sc for t in reg["tracks"] for sc in t["sub_cats"]]
    # 反查:v1 名 → 库内实际字符串集(DB 字符串尚未归一,旧名仍在用)
    rev = {sc: [sc] for sc in v1}
    for old, new in reg["canonical_map_old_to_new"].items():
        if new in rev and old not in rev[new]:
            rev[new].append(old)
    c = sqlite3.connect(DB).cursor()
    samples = []
    for sc in v1:
        names = rev[sc]
        ph = ",".join("?" * len(names))
        rows = c.execute(
            f"SELECT job_title, COALESCE(job_duty,'')||' '||COALESCE(job_req,'') FROM jobs "
            f"WHERE sub_category IN ({ph}) AND quality_label IN('good','internship_only') "
            "ORDER BY RANDOM() LIMIT ?", (*names, a.per)).fetchall()
        for t, jd in rows:
            samples.append((sc, t, jd))
    print(f"判官={JUDGE_MODEL} | v1 桶 {len(v1)} | 抽样 {len(samples)} 岗\n", flush=True)

    results = {}
    def _one(item):
        sc, t, jd = item
        v, r = judge(t, jd, sc)
        return sc, v, t, r
    with ThreadPoolExecutor(max_workers=6) as ex:
        for fut in as_completed([ex.submit(_one, it) for it in samples]):
            sc, v, t, r = fut.result()
            results.setdefault(sc, []).append((v, t, r))

    print(f"{'细分方向':32} {'n':>3} {'对口':>4} {'部分':>4} {'不对口':>5} {'准确率':>6}")
    rows_out = []
    tot_ok = tot_n = 0
    for sc in v1:
        rs = results.get(sc, [])
        n = len(rs); ok = sum(1 for v, _, _ in rs if v == "对口")
        part = sum(1 for v, _, _ in rs if v == "部分对口"); bad = sum(1 for v, _, _ in rs if v == "不对口")
        acc = (ok + 0.5 * part) / n if n else 0
        tot_ok += ok + 0.5 * part; tot_n += n
        rows_out.append((sc, n, ok, part, bad, round(acc, 2)))
    for sc, n, ok, part, bad, acc in sorted(rows_out, key=lambda x: x[5]):
        flag = "  ⚠️低" if acc < 0.8 and n else ""
        print(f"{sc:32} {n:>3} {ok:>4} {part:>4} {bad:>5} {acc:>6.0%}{flag}")
    print(f"\n总体对口准确率 = {tot_ok/tot_n:.1%}  (n={tot_n})")

    # 存档 + 列出判为不对口的样例(系统性误判线索)
    out = {"judge": JUDGE_MODEL, "per": a.per, "overall_acc": round(tot_ok/tot_n, 3),
           "by_subcat": {sc: {"n": n, "ok": ok, "part": part, "bad": bad, "acc": acc}
                         for sc, n, ok, part, bad, acc in rows_out},
           "misjudged": {sc: [(t, r) for v, t, r in rs if v == "不对口"] for sc, rs in results.items()}}
    op = os.path.join(ROOT, "data", "_phase_g", "subcat_fit_audit.json")
    json.dump(out, open(op, "w"), ensure_ascii=False, indent=1)
    print(f"\n存档 → {op}")
    print("\n不对口样例(系统性误判线索):")
    for sc, rs in results.items():
        bads = [(t, r) for v, t, r in rs if v == "不对口"]
        for t, r in bads[:2]:
            print(f"  [{sc}] {t[:30]} — {r}")

if __name__ == "__main__":
    main()
