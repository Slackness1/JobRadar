"""Deterministic go/no-go gate for the local Voice Intelligence extractor."""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

from app.services.interview.voice_intelligence import analyze_wav


ROOT = Path(__file__).parents[1] / "tests" / "fixtures" / "voice_turn"


def evaluate() -> dict:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    cases: list[dict] = []
    real_time_factors: list[float] = []

    for expected in manifest["cases"]:
        path = ROOT / expected["file"]
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != expected["sha256"]:
            failures.append(f"{path.name}: checksum mismatch")

        started = time.perf_counter()
        features, flags = analyze_wav(path, transcript_text=expected.get("transcript", ""))
        elapsed = time.perf_counter() - started
        real_time_factor = elapsed / expected["duration_s"]
        real_time_factors.append(real_time_factor)
        speech = features["speech"]
        pauses = features["pauses"]

        if "expected_speech" in expected:
            detected = speech["speech_duration_seconds"] >= 0.5
            if detected != expected["expected_speech"]:
                failures.append(f"{path.name}: expected_speech={expected['expected_speech']}, got {detected}")
        if "speech_duration_s" in expected:
            error = abs(speech["speech_duration_seconds"] - expected["speech_duration_s"])
            if error > 0.10:
                failures.append(f"{path.name}: speech duration error {error:.3f}s")
        if "first_speech_s" in expected:
            first_speech_s = (speech["first_speech_ms"] or 0) / 1000
            error = abs(first_speech_s - expected["first_speech_s"])
            if error > 0.08:
                failures.append(f"{path.name}: first speech error {error:.3f}s")
        if "long_pause_count" in expected and pauses["count"] != expected["long_pause_count"]:
            failures.append(
                f"{path.name}: expected {expected['long_pause_count']} long pauses, got {pauses['count']}"
            )
        if "confidence" in json.dumps(features).lower():
            failures.append(f"{path.name}: uncalibrated confidence field leaked")

        cases.append({
            "file": path.name,
            "speech_duration_seconds": speech["speech_duration_seconds"],
            "first_speech_ms": speech["first_speech_ms"],
            "long_pause_count": pauses["count"],
            "quality_flags": flags,
            "real_time_factor": round(real_time_factor, 4),
        })

    p95_index = max(0, int(len(real_time_factors) * 0.95 + 0.999) - 1)
    p95_rtf = sorted(real_time_factors)[p95_index]
    if p95_rtf >= 0.5:
        failures.append(f"processing p95 real-time factor {p95_rtf:.3f} >= 0.5")

    return {
        "status": "go" if not failures else "no-go",
        "analyzer": "voice-facts-v1",
        "case_count": len(cases),
        "processing_rtf_mean": round(statistics.mean(real_time_factors), 4),
        "processing_rtf_p95": round(p95_rtf, 4),
        "failures": failures,
        "cases": cases,
    }


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "go" else 1)
