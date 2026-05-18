"""DashScope text-embedding-v3 client.

Returns 1024-dim float32 vectors. Batch up to 25 strings per request.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import numpy as np

DIMENSION = 1024
MAX_BATCH = 10
URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"


def _get_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY")
    if k:
        return k
    for p in [
        Path(__file__).resolve().parents[3] / "backend/.env.local",
        Path(__file__).resolve().parents[3] / "backend/.env",
        Path(__file__).resolve().parents[4] / ".env.local",
    ]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("DASHSCOPE_API_KEY not found")


def embed_batch(texts: list[str]) -> list[np.ndarray]:
    """Embed up to MAX_BATCH texts in one request. Returns list of 1024-dim float32 arrays."""
    if not texts:
        return []
    if len(texts) > MAX_BATCH:
        raise ValueError(f"Batch too large: {len(texts)} > {MAX_BATCH}")
    body = json.dumps({
        "model": "text-embedding-v3",
        "input": {"texts": texts},
        "parameters": {"dimension": DIMENSION},
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body,
        headers={"Authorization": f"Bearer {_get_key()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope embed HTTP {e.code}: {err_body[:400]}") from e
    items = data.get("output", {}).get("embeddings") or []
    items.sort(key=lambda x: x.get("text_index", 0))
    out = []
    for it in items:
        v = np.asarray(it["embedding"], dtype=np.float32)
        # Normalize to unit length so dot product = cosine similarity
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
        out.append(v)
    return out


def embed_one(text: str) -> np.ndarray:
    return embed_batch([text])[0]


def embed_many(texts: list[str], *, on_progress=None) -> list[np.ndarray]:
    """Embed many texts, batching automatically."""
    out: list[np.ndarray] = []
    for i in range(0, len(texts), MAX_BATCH):
        chunk = texts[i:i + MAX_BATCH]
        out.extend(embed_batch(chunk))
        if on_progress:
            on_progress(len(out), len(texts))
    return out


def to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)
