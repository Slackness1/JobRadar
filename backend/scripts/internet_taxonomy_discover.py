"""互联网大厂 JD 赛道发现(给 sub_cat 定桶出清单,人工审定用)。

流程: 取今日 tata 大厂岗(有JD) → DashScope embedding → KMeans 聚类 →
每簇取代表样本喂 DeepSeek 命名+定边界+质量tier(进池/不进池) → 产出清单 md+json。
**纯发现**: 不动 taxonomy / 不动管道 / 不进池。

用法:
  PYTHONPATH=. .venv/bin/python scripts/internet_taxonomy_discover.py [--k 40] [--reembed]
"""
from __future__ import annotations
import argparse, json, sqlite3, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _load_env_local():
    import os
    envf = BACKEND / ".env.local"
    if envf.exists():
        for line in envf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_local()  # 把 DASHSCOPE_API_KEY / DISCOVER_LLM_* 灌进 os.environ
DB = BACKEND / "data" / "jobradar.db"
CACHE = BACKEND / "data" / "_phase_g" / "internet_jd_emb"
OUT_MD = Path("/home/ubuntu/jobradar-sync/internet-taxonomy-discover.md")
OUT_JSON = BACKEND / "data" / "_phase_g" / "internet_taxonomy_clusters.json"

from app.services.podcasts.embed import embed_batch  # noqa: E402
from openai import OpenAI  # noqa: E402


def _env(key, default=None):
    import os
    if os.environ.get(key):
        return os.environ[key]
    envf = BACKEND / ".env.local"
    if envf.exists():
        for line in envf.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def build_discover_llm():
    """GPT-5.5 via Responses API(xhyapi 0.03x 渠道),key 从 .env.local 读,不硬编码。"""
    client = OpenAI(api_key=_env("DISCOVER_LLM_API_KEY"),
                    base_url=_env("DISCOVER_LLM_BASE_URL", "https://xhyapi.com/v1"))
    return client, _env("DISCOVER_LLM_MODEL", "gpt-5.5")


def load_jobs():
    # 32 大厂白名单(= Step3 导入时的 --company 名),去掉今天混入的非大厂 tata 岗
    man = json.loads(Path("/home/ubuntu/jobradar-sync/out/fanout_manifest.json").read_text())
    names = [r["name"] for r in man]
    con = sqlite3.connect(DB)
    ph = ",".join("?" * len(names))
    rows = con.execute(
        f"SELECT id, company, job_title, COALESCE(job_duty,''), COALESCE(job_req,'') "
        f"FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' "
        f"AND company IN ({ph}) "
        f"AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))>=50", names
    ).fetchall()
    con.close()
    jobs = []
    for jid, comp, title, duty, req in rows:
        jd = (duty + " " + req).strip().replace("\n", " ")
        jobs.append({"id": jid, "company": comp, "title": title or "",
                     "text": (title + " | " + jd)[:500], "jd": jd[:420]})
    return jobs


def get_embeddings(jobs, reembed):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    npy, idj = CACHE.with_suffix(".npy"), CACHE.with_suffix(".ids.json")
    if not reembed and npy.exists() and idj.exists():
        ids = json.loads(idj.read_text())
        if ids == [j["id"] for j in jobs]:
            print(f"复用缓存 embedding ({len(ids)})")
            return np.load(npy)
    print(f"embedding {len(jobs)} 条(DashScope, 10/批,多线程)…")
    texts = [j["text"] for j in jobs]
    batches = [texts[i:i + 10] for i in range(0, len(texts), 10)]

    def do(b):
        for _ in range(3):
            try:
                return [np.asarray(v, dtype=np.float32) for v in embed_batch(b)]
            except Exception:
                continue
        return [np.zeros(1024, dtype=np.float32) for _ in b]

    vecs = []
    with ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(do, batches)):
            vecs.extend(r)
            if i % 30 == 0:
                print(f"  {min((i+1)*10,len(texts))}/{len(texts)}", flush=True)
    arr = np.vstack(vecs)
    np.save(npy, arr)
    idj.write_text(json.dumps([j["id"] for j in jobs]))
    return arr


def label_cluster(client, model, cid, members):
    from collections import Counter
    titles = [m["title"] for m in members]
    top_titles = [t for t, _ in Counter(titles).most_common(12)]
    # 代表样本: 取前 10 个不同标题的 JD
    seen, samples = set(), []
    for m in members:
        if m["title"] not in seen:
            seen.add(m["title"])
            samples.append(f"【{m['title']}】{m['jd'][:200]}")
        if len(samples) >= 10:
            break
    prompt = (
        "你是互联网招聘赛道分类专家。下面是一个聚类簇里的岗位(同一类角色)。"
        "请给它命名并判定。只输出 JSON。\n\n"
        f"高频标题: {top_titles}\n\n代表岗位:\n" + "\n".join(samples) +
        "\n\n输出 JSON: {\"name\":\"赛道名(如 AI产品经理/后端开发/管培生/用户运营/客服)\","
        "\"role_desc\":\"一句话这是干什么的\","
        "\"boundary\":\"和相邻赛道的边界\","
        "\"is_ai\":true/false(是否AI/算法/大模型相关),"
        "\"quality_tier\":\"进池/不进池/边界\"(SAIF金融硕士/MBA视角:产品/AI/算法/管培/战略/高阶运营/研发=进池;"
        "骑手/客服/门店/地推/外包/基础运营=不进池),"
        "\"tier_reason\":\"为什么这么判\"}"
    )
    prompt += "\n\n只输出 JSON,不要 markdown 代码块、不要解释。"
    try:
        r = client.responses.create(
            model=model, input=prompt,
            reasoning={"effort": "medium"}, max_output_tokens=4000)
        txt = (getattr(r, "output_text", "") or "").strip()
        if txt.startswith("```"):
            txt = txt.split("```", 2)[1].lstrip("json").strip() if "```" in txt else txt
        d = json.loads(txt)
    except Exception as e:
        d = {"name": f"簇{cid}", "role_desc": f"(标注失败 {type(e).__name__}:{str(e)[:60]})",
             "boundary": "", "is_ai": False, "quality_tier": "边界", "tier_reason": ""}
    d["cluster_id"] = cid
    d["size"] = len(members)
    d["top_titles"] = top_titles[:8]
    from collections import Counter as C
    d["companies"] = [c for c, _ in C(m["company"] for m in members).most_common(5)]
    return d


EXISTING_AI = ["LLM算法post-train", "Agent工程师", "多模态推理优化", "AI PM", "AI算法业务", "AI应用开发工程师"]
OUT_MD2 = Path("/home/ubuntu/jobradar-sync/internet-taxonomy-final.md")


def consolidate(client, model, results):
    """把 N 个碎簇归并成干净的独立互联网赛道 taxonomy(映射已有6 AI桶 + 新增非AI桶)。"""
    brief = [{"name": r["name"], "size": r["size"], "is_ai": r.get("is_ai"),
              "tier": r["quality_tier"], "titles": r.get("top_titles", [])[:5]} for r in results]
    prompt = (
        "你在为面向 SAIF(金融硕士/MBA)的求职平台,把互联网大厂岗位整理成一套**独立的互联网赛道 taxonomy**"
        "(与金融赛道并列)。下面是对 1.2 万条大厂 JD 聚类后、每个簇的草标。请**归并**成一套干净、互斥、"
        "可用于打标推荐的 sub_cat 清单(目标 15-22 个桶,别太碎)。\n\n"
        f"已存在的 6 个 AI 桶(尽量复用,别另起重名): {EXISTING_AI}\n\n"
        f"聚类草标(JSON):\n{json.dumps(brief, ensure_ascii=False)}\n\n"
        "规则:① 按**角色**归并,不要按业务线(抖音/TikTok/飞书不单列,拆回角色);"
        "② AI/算法类尽量映射到上面 6 个已有桶,确实不同才新增(如 搜索推荐算法、具身智能/自动驾驶算法 可新增);"
        "③ 非AI高薪桶按需新增(产品经理、数据/商业分析、管培综合、体验设计 等);"
        "④ tier: SAIF 视角 产品/AI/算法/研发/管培/战略/数据分析=进池;骑手/客服/门店/地推/基础HR执行/外包=不进池;拿不准=边界;"
        "⑤ est_size 用所归并簇的 size 之和估算。\n\n"
        "只输出 JSON 数组,每个元素: {\"bucket\":\"赛道名\",\"strategy_group\":\"AI应用_PM_开发|互联网产品运营|互联网研发|"
        "互联网数据分析|互联网设计|综合管培|其它\",\"maps_to_existing_ai\":\"6个之一或null\",\"is_new\":true/false,"
        "\"is_ai\":true/false,\"tier\":\"进池|不进池|边界\",\"est_size\":数字,\"boundary\":\"一句边界\","
        "\"merged_from\":[\"被归并的草标名\"]}。不要 markdown 代码块。"
    )
    r = client.responses.create(model=model, input=prompt,
                                reasoning={"effort": "high"}, max_output_tokens=16000)
    txt = (getattr(r, "output_text", "") or "").strip()
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1].lstrip("json").strip()
    return json.loads(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=40)
    ap.add_argument("--reembed", action="store_true")
    args = ap.parse_args()

    jobs = load_jobs()
    print(f"岗位 {len(jobs)}")
    emb = get_embeddings(jobs, args.reembed)
    # 归一化 → KMeans(cosine)
    from sklearn.cluster import KMeans
    norm = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
    print(f"KMeans k={args.k}…")
    km = KMeans(n_clusters=args.k, random_state=42, n_init=4).fit(norm)
    labels = km.labels_
    clusters = {}
    for j, lb in zip(jobs, labels):
        clusters.setdefault(int(lb), []).append(j)

    client, model = build_discover_llm()
    print(f"标注 {len(clusters)} 簇(model={model})…")
    results = []
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(label_cluster, client, model, cid, mem) for cid, mem in clusters.items()]
        for i, f in enumerate(futs):
            results.append(f.result())
            print(f"  标注 {i+1}/{len(futs)}", flush=True)
    results.sort(key=lambda d: -d["size"])
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=1))

    # 清单 md
    pool = [r for r in results if r["quality_tier"] == "进池"]
    nopool = [r for r in results if r["quality_tier"] == "不进池"]
    edge = [r for r in results if r["quality_tier"] == "边界"]
    ai = [r for r in results if r.get("is_ai")]
    L = [f"# 互联网大厂赛道发现清单(聚类草稿,待审)\n",
         f"> 来源:{len(jobs)} 条今日入库大厂活岗 JD,KMeans {args.k} 簇,DeepSeek 标注。",
         f"> **纯发现,未动 taxonomy/管道/池子。** 你审定后我再开桶。\n",
         f"**汇总**:进池 {sum(r['size'] for r in pool)} 岗 / {len(pool)} 类 · "
         f"不进池 {sum(r['size'] for r in nopool)} 岗 / {len(nopool)} 类 · "
         f"边界 {sum(r['size'] for r in edge)} 岗 / {len(edge)} 类 · 其中 AI 相关 {sum(r['size'] for r in ai)} 岗\n"]
    for tier, lst in [("✅ 建议进池", pool), ("🟡 边界(你定)", edge), ("⛔ 建议不进池", nopool)]:
        L.append(f"\n## {tier}\n")
        L.append("| 赛道 | 岗数 | AI | 是什么 / 边界 | 代表标题 | 主要公司 |")
        L.append("|---|--:|:-:|---|---|---|")
        for r in lst:
            L.append(f"| **{r['name']}** | {r['size']} | {'🤖' if r.get('is_ai') else ''} | "
                     f"{r.get('role_desc','')};{r.get('boundary','')[:40]} | "
                     f"{'、'.join(r.get('top_titles',[])[:4])} | {'、'.join(r.get('companies',[])[:3])} |")
    OUT_MD.write_text("\n".join(L))
    print(f"原始 {len(results)} 簇清单: {OUT_MD}")

    # === 归并成干净 taxonomy ===
    print("GPT-5.5 归并中(high reasoning)…", flush=True)
    try:
        buckets = consolidate(client, model, results)
    except Exception as e:
        print(f"归并失败 {type(e).__name__}: {str(e)[:120]}")
        return
    (BACKEND / "data" / "_phase_g" / "internet_taxonomy_final.json").write_text(
        json.dumps(buckets, ensure_ascii=False, indent=1))
    buckets.sort(key=lambda b: (b.get("tier") != "进池", -int(b.get("est_size") or 0)))
    P = [b for b in buckets if b.get("tier") == "进池"]
    M2 = [f"# 互联网独立赛道 sub_cat 清单(归并定稿,待审)\n",
          f"> {len(jobs)} 条大厂 JD → {args.k} 簇 → GPT-5.5 归并成 {len(buckets)} 桶。**纯发现,未动 taxonomy/管道/池子。**",
          f"> 复用已有 6 AI 桶 {EXISTING_AI}\n",
          f"**进池 {sum(int(b.get('est_size') or 0) for b in P)} 岗 / {len(P)} 桶**(AI {sum(b.get('is_ai') for b in P)} 桶)\n",
          "| 赛道桶 | tier | 岗数 | AI | 归属组 | 映射已有AI桶/新增 | 边界 | 由哪些簇归并 |",
          "|---|:-:|--:|:-:|---|---|---|---|"]
    for b in buckets:
        tag = "✅" if b.get("tier") == "进池" else ("⛔" if b.get("tier") == "不进池" else "🟡")
        mp = b.get("maps_to_existing_ai") or ("🆕新增" if b.get("is_new") else "")
        M2.append(f"| **{b.get('bucket')}** | {tag}{b.get('tier')} | {b.get('est_size')} | "
                  f"{'🤖' if b.get('is_ai') else ''} | {b.get('strategy_group','')} | {mp} | "
                  f"{b.get('boundary','')[:50]} | {'、'.join(b.get('merged_from',[])[:4])} |")
    OUT_MD2.write_text("\n".join(M2))
    print(f"\n★ 定稿清单: {OUT_MD2}")
    print(f"归并 {len(buckets)} 桶 | 进池 {len(P)} 桶 / {sum(int(b.get('est_size') or 0) for b in P)} 岗")


if __name__ == "__main__":
    main()
