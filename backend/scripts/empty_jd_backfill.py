"""Worklist-driven empty-JD backfill (multi-engine, ROI-ordered).

Reads data/_phase_g/empty_jd_backfill_worklist.json (id/source/company/title/detail_url),
dispatches each row to an engine fetcher by source/host, and writes job_duty/job_req
back to the dev DB — ONLY when the fetched JD is non-empty (空-content 守卫; never
overwrite with "").  fetch 404/撤 → mark link_status='dead'.  Idempotent: a row whose
JD is already >=30 chars is skipped; attempts logged to avoid hammering dead engines.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/empty_jd_backfill.py --engine tata   --workers 6
  PYTHONPATH=. .venv/bin/python scripts/empty_jd_backfill.py --engine greenhouse
  PYTHONPATH=. .venv/bin/python scripts/empty_jd_backfill.py --engine workday
  ... --engine zhiye | oracle | feishu | eightfold | list
"""
from __future__ import annotations
import argparse, html, json, re, sqlite3, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "jobradar.db"
WORKLIST = ROOT / "data" / "_phase_g" / "empty_jd_backfill_worklist.json"
FILLED_IDS = ROOT / "data" / "_phase_g" / "empty_jd_filled_ids.json"
TOKEN_FILE = Path("/home/ubuntu/jobradar-sync/tata-token.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# ---------- helpers ----------
import ssl
_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE

def _get(url, headers=None, timeout=25, insecure=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    ctx = _INSECURE if insecure else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")

def _post(url, body, headers=None, timeout=25):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _strip_html(s):
    if not s: return ""
    s = html.unescape(s)            # decode &lt; &#39; &quot; (may be double-encoded)
    if "&lt;" in s or "&#" in s or "&quot;" in s:
        s = html.unescape(s)
    s = re.sub(r"<\s*br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</\s*(p|div|li|tr|h\d)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", s).strip()

# return: (duty, req, weburl_or_None, status)  status in {ok, offline, dead, err:<msg>}

# ---------- tata VIP ----------
def _tata_hdr():
    t = json.loads(TOKEN_FILE.read_text())
    return {"TATA-X-OPEN-ID": t["openId"],
            "Authorization": t.get("bearer") or ("Bearer " + t["token"])}

def fetch_tata(row):
    vid = row["job_id"][5:] if row.get("job_id", "").startswith("tata_") else None
    if not vid:
        return ("", "", None, "err:no_vid")
    try:
        raw = _post(f"https://www.tatawangshen.com/api/recruit/vacancy/vacancy/{vid}", {}, _tata_hdr())
        d = (json.loads(raw) or {}).get("data")
        if not isinstance(d, dict):
            return ("", "", None, "offline")
        duty = _strip_html(d.get("responsibility") or "")
        req = _strip_html(d.get("raw_position_require") or "")
        url = None
        try:
            rc = _post("https://www.tatawangshen.com/api/recruit/position/click",
                       {"_id": vid, "scene": "total"}, _tata_hdr())
            url = ((json.loads(rc) or {}).get("data") or {}).get("position_web_url") or None
        except Exception:
            pass
        if duty or req:
            return (duty, req, url, "ok")
        return ("", "", None, "offline")
    except Exception as e:
        return ("", "", None, f"err:{type(e).__name__}")

# ---------- greenhouse family (greenhouse.io / optiver gh_jid / boards) ----------
def fetch_greenhouse(row):
    u = row["detail_url"]
    m = re.search(r"gh_jid=(\d+)", u) or re.search(r"/jobs/(\d+)", u) or re.search(r"/job/(\d+)", u)
    jid = m.group(1) if m else None
    # board token: greenhouse.io/<board>/...  OR derive from gh_jid w/ embed
    board = None
    mb = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?#]+)", u)
    if mb: board = mb.group(1)
    if not jid:
        return ("", "", None, "err:no_id")
    candidates = []
    if board:
        candidates.append(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
    # generic embed fallback by job id requires board; try common derivations later
    for api in candidates:
        try:
            d = json.loads(_get(api))
            content = _strip_html(d.get("content") or "")
            if len(content) >= 30:
                return (content, "", d.get("absolute_url"), "ok")
            return ("", "", None, "offline")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return ("", "", None, "dead")
        except Exception as e:
            return ("", "", None, f"err:{type(e).__name__}")
    return ("", "", None, "err:no_board")

# ---------- Workday ----------
def fetch_workday(row):
    u = row["detail_url"]
    p = urlparse(u)
    host = p.netloc
    # path: /en-US/<site>/job/<loc>/<title>_<reqid>   or  /<site>/job/...
    parts = [x for x in p.path.split("/") if x]
    try:
        ji = parts.index("job")
    except ValueError:
        return ("", "", None, "err:no_job")
    # site = the segment before 'job' (skip locale like en-US)
    site = parts[ji - 1]
    ext_path = "/".join(parts[ji:])  # job/...
    tenant = host.split(".")[0]
    api = f"https://{host}/wday/cxs/{tenant}/{site}/job/{'/'.join(parts[ji+1:])}"
    last = "err:?"
    for attempt in range(4):
        try:
            d = json.loads(_get(api, headers={"Accept": "application/json",
                "Referer": f"https://{host}/{site}"}))
            info = d.get("jobPostingInfo") or {}
            desc = _strip_html(info.get("jobDescription") or "")
            if len(desc) >= 30:
                return (desc, "", info.get("externalUrl"), "ok")
            return ("", "", None, "offline")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return ("", "", None, "dead")
            last = f"err:HTTP{e.code}"
            time.sleep(1.5 * (attempt + 1))   # 403 throttle backoff
        except Exception as e:
            last = f"err:{type(e).__name__}"
            time.sleep(1.0)
    return ("", "", None, last)

# ---------- feishu jobs ----------
def fetch_feishu(row):
    u = row["detail_url"]
    p = urlparse(u)
    tenant = p.netloc.split(".")[0]
    m = re.search(r"/position/(\d+)", u)
    if not m:
        return ("", "", None, "err:no_id")
    pid = m.group(1)
    api = f"https://{p.netloc}/api/v1/job/posts/{pid}"
    try:
        d = json.loads(_get(api, headers={"Accept": "application/json"}))
        jp = ((d.get("data") or {}).get("job_post_detail") or {})
        desc = _strip_html(jp.get("description") or "")
        req = _strip_html(jp.get("requirement") or "")
        if len(desc) + len(req) >= 30:
            return (desc, req, None, "ok")
        return ("", "", None, "offline")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return ("", "", None, "dead")
        return ("", "", None, f"err:HTTP{e.code}")
    except Exception as e:
        return ("", "", None, f"err:{type(e).__name__}")

# ---------- Oracle CX (JPMC) ----------
def fetch_oracle(row):
    u = row["detail_url"]
    p = urlparse(u)
    m = re.search(r"/job/(\d+)", u)
    ms = re.search(r"/sites/([^/]+)/", u)
    if not (m and ms):
        return ("", "", None, "err:no_id")
    jid, site = m.group(1), ms.group(1)
    api = (f"https://{p.netloc}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
           f"?expand=all&onlyData=true&finder=ItemsToBeSearchedFinder;jobId={jid},siteNumber={site}")
    try:
        d = json.loads(_get(api, headers={"Accept": "application/json"}))
        items = d.get("items") or []
        if not items:
            return ("", "", None, "dead")
        it = items[0]
        desc = _strip_html(it.get("ExternalDescriptionStr") or it.get("ExternalQualificationsStr") or "")
        req = _strip_html(it.get("ExternalQualificationsStr") or "")
        if len(desc) + len(req) >= 30:
            return (desc, req, None, "ok")
        return ("", "", None, "offline")
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return ("", "", None, "dead")
        return ("", "", None, f"err:HTTP{e.code}")
    except Exception as e:
        return ("", "", None, f"err:{type(e).__name__}")

# ---------- 北森 zhiye (campus uuid API / zpdetail HTML / campusxq) ----------
def fetch_zhiye(row):
    u = row["detail_url"]
    base = urlparse(u).netloc.rstrip(".")
    # form 1: campus/detail?jobAdId=<uuid> → GetJobAdInfo (SSL bypass for custom domains)
    mu = re.search(r"jobAdId=([a-f0-9\-]{8,})", u)
    if mu:
        api = f"https://{base}/api/Jobad/GetJobAdInfo?jobAdId={mu.group(1)}"
        try:
            data = (json.loads(_get(api, insecure=True)).get("Data") or {})
            duty = _strip_html(data.get("Duty") or "")
            req = _strip_html(data.get("Require") or "")
            if len(duty) + len(req) >= 30:
                return (duty, req, None, "ok")
            return ("", "", None, "offline")
        except urllib.error.HTTPError as e:
            return ("", "", None, "dead" if e.code in (404, 410) else f"err:HTTP{e.code}")
        except Exception as e:
            return ("", "", None, f"err:{type(e).__name__}")
    # form 2: /zpdetail/<num> → legacy HTML, regex 工作职责/任职资格
    if "/zpdetail/" in u:
        try:
            h = _get(u, insecure=True, timeout=30)
        except urllib.error.HTTPError as e:
            return ("", "", None, "dead" if e.code in (404, 410) else f"err:HTTP{e.code}")
        except Exception as e:
            return ("", "", None, f"err:{type(e).__name__}")
        dm = re.search(r'<p class="title">工作职责：</p>\s*<p>(.*?)</p>', h, re.S)
        rm = re.search(r'<p class="title">任职资格：</p>\s*<p>(.*?)</p>', h, re.S)
        duty = _strip_html(dm.group(1)) if dm else ""
        req = _strip_html(rm.group(1)) if rm else ""
        if len(duty) + len(req) >= 30:
            return (duty, req, None, "ok")
        return ("", "", None, "offline")
    # form 3: campusxq?jobId=<num> → campus GetJobAdInfo by numeric id
    mc = re.search(r"jobId=(\d+)", u)
    if mc and "campusxq" in u:
        api = f"https://{base}/api/Jobad/GetJobAdInfo?jobAdId={mc.group(1)}"
        try:
            data = (json.loads(_get(api, insecure=True)).get("Data") or {})
            duty = _strip_html(data.get("Duty") or "")
            req = _strip_html(data.get("Require") or "")
            if len(duty) + len(req) >= 30:
                return (duty, req, None, "ok")
            return ("", "", None, "offline")
        except Exception as e:
            return ("", "", None, f"err:{type(e).__name__}")
    return ("", "", None, "err:no_id")

# ---------- wecruit / hotjob (北森 hotjob 线) ----------
def _hotjob_wt_html(u):
    """Family C: <suite>.hotjob.cn/wt/.../getOnePosition — server-rendered full JD."""
    try:
        html_s = _get(u, timeout=25)
    except urllib.error.HTTPError as e:
        return ("", "", None, "dead" if e.code in (404, 410) else f"err:HTTP{e.code}")
    except Exception as e:
        return ("", "", None, f"err:{type(e).__name__}")
    def block(label):
        m = re.search(label + r"\s*</div>\s*<p[^>]*>(.*?)</p>", html_s, re.S)
        return _strip_html(m.group(1)) if m else ""
    duty = block("职位描述") or block("岗位职责") or block("工作职责")
    req = block("任职要求") or block("职位要求") or block("任职资格")
    if len(duty) + len(req) >= 30:
        return (duty, req, None, "ok")
    return ("", "", None, "offline")

def fetch_hotjob(row):
    import urllib.parse
    u = row["detail_url"]
    if "getOnePosition" in u:
        return _hotjob_wt_html(u)
    after = u.split("hotjob.cn/", 1)[1] if "hotjob.cn/" in u else ""
    suite = after.split("/")[0]
    mp = re.search(r"postId=([a-zA-Z0-9]+)", u)
    if not (suite and mp):
        return ("", "", None, "err:no_id")
    pid = mp.group(1)
    # recruitType: social=2, everything else (campus/school/intern)=1
    rt = "2" if ("social" in u) else "1"
    api = f"https://wecruit.hotjob.cn/wecruit/positionInfo/listPositionDetail/{suite}"
    body = urllib.parse.urlencode({"postId": pid, "recruitType": rt}).encode()
    last = "err:?"
    for attempt in range(4):
        try:
            req = urllib.request.Request(api, data=body, method="POST",
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
            resp = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace"))
            st = resp.get("state")
            if st in (1017, "1017"):       # 校招岗下线 / expired → out of pool
                return ("", "", None, "dead")
            d = resp.get("data")
            if not isinstance(d, dict) or not d:
                return ("", "", None, "offline")
            duty = _strip_html(d.get("workContent") or "")
            rq = _strip_html(d.get("serviceCondition") or "")
            if len(duty) + len(rq) >= 30:
                return (duty, rq, None, "ok")
            return ("", "", None, "offline")
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return ("", "", None, "dead")
            last = f"err:HTTP{e.code}"
        except Exception as e:
            last = f"err:{type(e).__name__}"
        time.sleep(1.2 * (attempt + 1))
    return ("", "", None, last)

ENGINES = {
    "hotjob": (lambda r: "hotjob.cn" in r["detail_url"], fetch_hotjob),
    "greenhouse": (lambda r: "greenhouse.io" in r["detail_url"], fetch_greenhouse),
    "workday": (lambda r: "myworkdayjobs" in r["detail_url"], fetch_workday),
    "feishu": (lambda r: "jobs.feishu.cn" in r["detail_url"], fetch_feishu),
    "oracle": (lambda r: "oraclecloud.com" in r["detail_url"], fetch_oracle),
    "zhiye": (lambda r: ("zhiye.com" in r["detail_url"]) or ("campus/detail?jobAdId=" in r["detail_url"]), fetch_zhiye),
    "tata": (lambda r: r["source"] == "tatawangshen", fetch_tata),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--probe", type=int, default=0, help="just fetch N, print, no DB write")
    args = ap.parse_args()

    rows = json.loads(WORKLIST.read_text())
    # attach job_id from DB (worklist json only carries id/source/company/title/detail_url)
    _c = sqlite3.connect(DB, timeout=30)
    jid_map = dict(_c.execute(
        f"SELECT id, job_id FROM jobs WHERE id IN ({','.join('?'*len(rows))})",
        [r["id"] for r in rows]).fetchall())
    _c.close()
    for r in rows:
        r["job_id"] = jid_map.get(r["id"], "")
    if args.engine == "list":
        import collections
        c = collections.Counter()
        for r in rows:
            for name, (pred, _) in ENGINES.items():
                if pred(r):
                    c[name] += 1; break
            else:
                c["(unhandled)"] += 1
        for k, v in c.most_common():
            print(f"{v:5d}  {k}")
        return
    pred, fetch = ENGINES[args.engine]
    targets = [r for r in rows if pred(r)]
    if args.limit:
        targets = targets[:args.limit]
    print(f"engine={args.engine}  targets={len(targets)}")

    if args.probe:
        for r in targets[:args.probe]:
            duty, req, url, st = fetch(r)
            print(f"\n[{st}] id={r['id']} {r['company']} | {r['title'][:50]}")
            print(f"  url={url}")
            print(f"  duty({len(duty)}): {duty[:160]!r}")
            print(f"  req({len(req)}): {req[:120]!r}")
        return

    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=15000")
    cur = con.cursor()
    filled = offline = dead = errs = 0
    filled_ids = []
    CHUNK = 80
    for s in range(0, len(targets), CHUNK):
        batch = targets[s:s + CHUNK]
        res = list(ThreadPoolExecutor(args.workers).map(fetch, batch))
        for r, (duty, req, url, st) in zip(batch, res):
            if st == "ok" and (len(duty) + len(req) >= 30):
                if url:
                    cur.execute("UPDATE jobs SET job_duty=?, job_req=?, detail_url=? WHERE id=?", (duty, req, url, r["id"]))
                else:
                    cur.execute("UPDATE jobs SET job_duty=?, job_req=? WHERE id=?", (duty, req, r["id"]))
                filled += 1; filled_ids.append(r["id"])
            elif st == "dead":
                cur.execute("UPDATE jobs SET link_status='dead' WHERE id=?", (r["id"],)); dead += 1
            elif st == "offline":
                offline += 1
            else:
                errs += 1
        con.commit()
        print(f"  {min(s+CHUNK,len(targets))}/{len(targets)}  填{filled} 下线{offline} 死{dead} 错{errs}")
    con.close()
    # merge filled ids into the cumulative file
    prev = []
    if FILLED_IDS.exists():
        try: prev = json.loads(FILLED_IDS.read_text())
        except Exception: prev = []
    merged = sorted(set(prev) | set(filled_ids))
    FILLED_IDS.write_text(json.dumps(merged))
    print(f"\n[{args.engine}] 补全 {filled} | 下线 {offline} | 死链 {dead} | 错 {errs}  (filled_ids 累计 {len(merged)})")

if __name__ == "__main__":
    main()
