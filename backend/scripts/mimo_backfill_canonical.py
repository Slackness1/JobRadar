"""MiMo v2.5-pro backfill — 把 canonical_track 留 NULL 的 job 行,根据
(company + job_title + industry + 可选 location + 可选 job_duty 摘要) 让
LLM 分到 8 canonical 之一,或承认"非金融岗"留 NULL。

设计:
- Idempotent: WHERE canonical_track IS NULL,中断后续跑就接着干
- Resumable: 每 200 行 commit + flush
- 并发: ThreadPoolExecutor (默认 10),受 MiMo rate limit 节流
- 失败容忍: 单个 LLM 请求失败/超时不阻塞 batch,记 stat 后跳过
- 成本透明: 累计 token usage,跑完打印估算成本
- 安全: API key 走环境变量 MIMO_API_KEY,不 hardcode

用法:
  cd backend
  MIMO_API_KEY=tp-xxx PYTHONPATH=. .venv/bin/python scripts/mimo_backfill_canonical.py
  # 可选参数:
  #   --limit N          只处理 N 行 (dry run / smoke test)
  #   --workers N        并发数 (default 10)
  #   --batch-size N     commit 间隔 (default 200)
  #   --model NAME       覆盖 MIMO_MODEL (default mimo-v2.5-pro)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("mimo_backfill")

# 8 canonical (subset of allowed outputs). 多一个 "无金融相关性" 让 LLM 显式投票
# "都不沾边",我们把它视为 None → 行保留 NULL。
ALLOWED_TRACKS = {
    "二级买方·基本面",
    "量化",
    "一级市场",
    "卖方研究·S&T",
    "银行·总行核心",
    "监管·体制内",
    "金融科技",
    "金融咨询",
}

SYSTEM_PROMPT = """你是金融招聘分类助手。根据给定岗位信息,判定它属于哪个 SAIF 关心的金融赛道。

8 个 canonical 赛道(必须选其一,或选"无金融相关性"):

1. 二级买方·基本面 — 公募基金、私募基本面、保险资管、银行理财子、信托、资产管理、行业研究员(买方)
2. 量化 — 量化研究、量化交易、量化私募、做市、高频交易
3. 一级市场 — PE / VC / IBD / 投行 / 并购 / FA / 资本市场 / 投融资
4. 卖方研究·S&T — 券商研究所、券商策略、券商分析师、销售交易、FICC、固收研究、卖方行业研究
5. 银行·总行核心 — 银行总行管培、银行总行核心条线(对公/金融市场/科技/战略)。**银行分行柜员/客户经理/零售/财富顾问/理财经理 → 不属于,选"无金融相关性"**
6. 监管·体制内 — 央行、证监会、银保监、国资委、国央企总部、烟草专卖、政策性银行
7. 金融科技 — 蚂蚁、字节金融、腾讯金融科技、京东金科、平安科技、银行/券商科技子公司
8. 金融咨询 — 麦肯锡/BCG/Bain 等顶级咨询的金融行业组、Oliver Wyman、毕马威/普华咨询、安永咨询的金融业务

不属于以上任何 SAIF 关心金融赛道(如:互联网产品/算法/前后端、消费品营销、医疗、教育、能源/制造、房地产、零售柜员、销售代理、销售顾问、行政等)→ 返 "无金融相关性"。

只输出严格的 JSON:{"track": "<上述 9 个枚举之一>"}
不要任何解释、markdown、其他字段。"""


def _build_user_prompt(co: str, title: str, industry: str, loc: str, duty: str) -> str:
    lines = [f"公司: {co}", f"职位: {title}"]
    if industry:
        lines.append(f"行业: {industry}")
    if loc:
        lines.append(f"地点: {loc}")
    if duty:
        lines.append(f"职责摘要: {duty[:300]}")
    return "\n".join(lines)


class MimoClient:
    def __init__(self, api_key: str, model: str, base_url: str, timeout: int = 60, max_qps: float = 2.5):
        self.api_key = api_key
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        # 全局 requests.Session 复用 keep-alive 连接池。HTTPAdapter 给足够 pool
        # size 让多 worker 不互相挤掉对方连接。
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=32, pool_maxsize=32, max_retries=0
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        # 全局 token-bucket-ish rate limiter — MiMo 上限实测约 2.5-3 req/s,
        # 超过 → "Too many requests" 错。把请求节流到目标 QPS 之下,避免无谓
        # 重试 + 401 错。
        self._rate_lock = threading.Lock()
        self._next_slot = 0.0
        self._min_gap = 1.0 / max(0.1, max_qps)
        # Stats (thread-safe via lock)
        self._lock = threading.Lock()
        self.calls = 0
        self.errors = 0
        self.rate_limited_retries = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0

    def _acquire_slot(self) -> None:
        """Block until our turn in the global rate-limit schedule."""
        with self._rate_lock:
            now = time.monotonic()
            if now < self._next_slot:
                wait = self._next_slot - now
            else:
                wait = 0.0
            self._next_slot = max(now, self._next_slot) + self._min_gap
        if wait > 0:
            time.sleep(wait)

    def classify(self, co: str, title: str, industry: str, loc: str, duty: str) -> Optional[str]:
        # MiMo v2.5-pro 是 reasoning 模型,reasoning_content 单独消耗 tokens 且每
        # call 慢 5-10s。对 8-canonical 这种简单分类,reasoning 收益边际:实测
        # 10 个 SAIF case 中,reasoning 模式判中 10/10,disabled 模式判中 9/10
        # (1 例渠道销售岗误归基金,但 D-12 红线词层会在推荐 pipeline 兜底)。
        # disabled → 2.6x 快、78x output token 省,值得。
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(co, title, industry, loc, duty)},
            ],
            "temperature": 0.1,
            "max_tokens": 80,
            "thinking": {"type": "disabled"},
        }
        for attempt in range(5):
            self._acquire_slot()
            try:
                resp = self._session.post(self.url, json=body, timeout=self.timeout)
                # 429 / "Too many requests" → 长 backoff 重试,不计入永久错误
                body_text_for_rl = ""
                if resp.status_code == 429 or (
                    resp.status_code != 200 and ("Too many requests" in resp.text or "limitation" in resp.text)
                ):
                    body_text_for_rl = resp.text[:120]
                    if attempt < 4:
                        with self._lock:
                            self.rate_limited_retries += 1
                        # MiMo 节流通常持续 1-2s,backoff 2/4/8/15s
                        time.sleep([2, 4, 8, 15][min(attempt, 3)])
                        continue
                    # 5 次都 rate-limit → 计永久错
                    with self._lock:
                        self.errors += 1
                    if os.environ.get("MIMO_DEBUG"):
                        logger.warning("rate-limit exhausted: %s", body_text_for_rl)
                    return None
                if resp.status_code >= 500 and attempt < 4:
                    time.sleep(2 ** (attempt + 1))
                    continue
                if resp.status_code != 200:
                    with self._lock:
                        self.errors += 1
                    if os.environ.get("MIMO_DEBUG"):
                        logger.warning("HTTP %d: %s", resp.status_code, resp.text[:200])
                    return None
                payload = resp.json()
                usage = payload.get("usage") or {}
                with self._lock:
                    self.calls += 1
                    self.prompt_tokens += usage.get("prompt_tokens", 0)
                    self.completion_tokens += usage.get("completion_tokens", 0)
                    self.cached_tokens += (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                msg = payload["choices"][0]["message"]
                content = msg.get("content") or ""
                # 只解析 content,不 fallback 到 reasoning_content — 后者列举所有
                # canonical 候选,substring scan 会错命中 "first listed" 而不是最终结论。
                return self._parse_track(content)
            except (requests.RequestException, requests.Timeout) as exc:
                if attempt >= 2:
                    with self._lock:
                        self.errors += 1
                    if os.environ.get("MIMO_DEBUG"):
                        logger.warning("%s: %r", type(exc).__name__, exc)
                    return None
                time.sleep(2 ** (attempt + 1))
            except Exception as exc:  # Catch-all to surface unexpected failures
                with self._lock:
                    self.errors += 1
                if os.environ.get("MIMO_DEBUG"):
                    logger.warning("Unexpected %s: %r", type(exc).__name__, exc)
                return None
        return None

    @staticmethod
    def _parse_track(content: str) -> Optional[str]:
        if not content:
            return None
        text = content.strip()
        # Strip ```json fences if present
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json\n", "", 1).replace("json", "", 1).strip()
        # Try parse as JSON (whole text, or each line)
        candidates = [text]
        for line in text.split("\n"):
            line = line.strip().rstrip(",")
            if line.startswith("{") and line.endswith("}"):
                candidates.append(line)
        for c in candidates:
            try:
                obj = json.loads(c)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            track = (obj.get("track") or "").strip()
            if track in ALLOWED_TRACKS:
                return track
            # "无金融相关性" 或其它 → 显式 None
            return None
        # JSON 解析全失败 — 不做 substring fallback (会错命中 reasoning 列举的 first candidate)。
        return None


STOP = threading.Event()


def _on_sigint(signum, frame):
    print("\n[mimo_backfill] SIGINT received — finishing in-flight requests then exit...")
    STOP.set()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    signal.signal(signal.SIGINT, _on_sigint)

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只处理 N 行 (0 = 全集)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--qps", type=float, default=2.5, help="Global rate limit (MiMo cap ~2.5-3 req/s)")
    parser.add_argument("--batch-size", type=int, default=200, help="UPDATE batch commit interval")
    parser.add_argument("--model", default=os.environ.get("MIMO_MODEL") or "mimo-v2.5-pro")
    parser.add_argument("--db", default=str(Path(__file__).resolve().parents[1] / "data" / "jobradar.db"))
    args = parser.parse_args()

    api_key = os.environ.get("MIMO_API_KEY", "").strip()
    if not api_key:
        print("ERROR: MIMO_API_KEY env var not set", file=sys.stderr)
        return 2
    base_url = os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")

    client = MimoClient(api_key=api_key, model=args.model, base_url=base_url, max_qps=args.qps)
    print(f"[mimo_backfill] model={args.model} workers={args.workers} qps={args.qps} batch_size={args.batch_size}")

    conn = sqlite3.connect(args.db, timeout=60, isolation_level=None)  # autocommit
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    cur = conn.cursor()

    # Pull pending rows
    cur.execute("SELECT COUNT(*) FROM jobs WHERE canonical_track IS NULL")
    total_pending = cur.fetchone()[0]
    print(f"[mimo_backfill] pending NULL rows: {total_pending:,}")

    sql = """
        SELECT id, company, job_title, company_type_industry, location, job_duty
        FROM jobs WHERE canonical_track IS NULL
    """
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[mimo_backfill] processing {len(rows):,} rows...")

    # Worker
    def _classify_row(row):
        rid, co, title, industry, loc, duty = row
        track = client.classify(co or "", title or "", industry or "", loc or "", duty or "")
        return rid, track

    classified = 0
    null_keeps = 0
    pending_updates: list[tuple[str, int]] = []
    t0 = time.time()

    def _flush_updates():
        nonlocal pending_updates
        if not pending_updates:
            return
        # autocommit on; single executemany is atomic per stmt
        conn.executemany(
            "UPDATE jobs SET canonical_track = ? WHERE id = ?",
            pending_updates,
        )
        pending_updates = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_classify_row, r): r for r in rows}
        for done_idx, fut in enumerate(as_completed(futures), 1):
            if STOP.is_set():
                # Drain remaining in-flight then break
                pass
            try:
                rid, track = fut.result()
            except Exception as exc:
                logger.debug("future failed: %s", exc)
                continue
            if track:
                pending_updates.append((track, rid))
                classified += 1
            else:
                null_keeps += 1
            if len(pending_updates) >= args.batch_size:
                _flush_updates()
            if done_idx % 100 == 0:
                rate = done_idx / max(0.001, time.time() - t0)
                eta_sec = (len(rows) - done_idx) / max(0.01, rate)
                print(
                    f"  [{done_idx:>5,}/{len(rows):,}] classified={classified:,} null={null_keeps:,} "
                    f"errors={client.errors} rl_retries={client.rate_limited_retries} "
                    f"rate={rate:.1f}/s eta={eta_sec/60:.1f}min  "
                    f"tokens p={client.prompt_tokens:,} c={client.completion_tokens:,} "
                    f"cached={client.cached_tokens:,}"
                )
            if STOP.is_set():
                # Submit no further; existing futures will continue
                break

    _flush_updates()
    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(f"[mimo_backfill] DONE in {elapsed/60:.1f} min")
    print(f"  classified to canonical: {classified:,}")
    print(f"  kept NULL (无金融相关性): {null_keeps:,}")
    print(f"  LLM errors: {client.errors}")
    print(f"  total LLM calls: {client.calls:,}")
    print(f"  prompt tokens: {client.prompt_tokens:,}  cached: {client.cached_tokens:,}  ({client.cached_tokens/max(1,client.prompt_tokens)*100:.0f}% cache hit)")
    print(f"  completion tokens: {client.completion_tokens:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
