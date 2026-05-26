"""One-off catch-up: internet + state_owned + bank, all need Playwright (just installed today)."""
import sys, time, traceback
sys.path.insert(0, "/home/chuanbo/projects/JobRadar/backend")

from app.database import SessionLocal

def ts():
    return time.strftime("%H:%M:%S")

print(f"[{ts()}] === CATCHUP START ===", flush=True)

# 1. internet
print(f"[{ts()}] internet...", flush=True)
t0 = time.time()
db = SessionLocal()
try:
    from app.services.internet_crawler import (
        build_internet_targets, crawl_internet_targets, select_primary_targets,
    )
    primary = select_primary_targets(build_internet_targets())
    results = crawl_internet_targets(db, primary)
    new_total = sum(getattr(r, "new_count", 0) or 0 for r in results)
    print(f"  internet done: {new_total} new across {len(results)} targets, {time.time()-t0:.0f}s", flush=True)
except Exception as e:
    print(f"  internet FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
finally:
    db.close()

# 2. state_owned
print(f"[{ts()}] state_owned...", flush=True)
t0 = time.time()
db = SessionLocal()
try:
    from app.services.state_owned_crawler import (
        build_state_owned_targets, crawl_state_owned_targets,
    )
    targets = build_state_owned_targets()
    results = crawl_state_owned_targets(db, targets)
    new_total = sum(getattr(r, "new_count", 0) or 0 for r in results)
    print(f"  state_owned done: {new_total} new across {len(results)} targets, {time.time()-t0:.0f}s", flush=True)
except Exception as e:
    print(f"  state_owned FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
finally:
    db.close()

# 3. bank
print(f"[{ts()}] bank...", flush=True)
t0 = time.time()
db = SessionLocal()
try:
    from app.services.bank_tier_crawler import crawl_banks
    new = crawl_banks(db)
    print(f"  bank done: {new} new, {time.time()-t0:.0f}s", flush=True)
except Exception as e:
    print(f"  bank FAILED: {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
finally:
    db.close()

print(f"[{ts()}] === CATCHUP DONE ===", flush=True)
