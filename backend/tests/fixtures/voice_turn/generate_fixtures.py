"""Generate deterministic mono 16 kHz PCM fixtures for turn-handling tests."""
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 16000
ROOT = Path(__file__).resolve().parent


def _write(name: str, samples: list[int]) -> dict:
    path = ROOT / name
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    return {
        "file": name,
        "duration_s": round(len(samples) / SAMPLE_RATE, 3),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _silence(seconds: float) -> list[int]:
    return [0] * int(seconds * SAMPLE_RATE)


def _noise(seconds: float, amplitude: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.randint(-amplitude, amplitude) for _ in range(int(seconds * SAMPLE_RATE))]


def _speech_like(seconds: float, amplitude: int = 7800) -> list[int]:
    samples: list[int] = []
    for index in range(int(seconds * SAMPLE_RATE)):
        t = index / SAMPLE_RATE
        envelope = min(1.0, t / 0.04, max(0.0, (seconds - t) / 0.08))
        syllable = 0.55 + 0.45 * math.sin(2 * math.pi * 4.2 * t) ** 2
        carrier = (
            math.sin(2 * math.pi * 185 * t)
            + 0.45 * math.sin(2 * math.pi * 370 * t)
            + 0.22 * math.sin(2 * math.pi * 555 * t)
        )
        samples.append(int(amplitude * envelope * syllable * carrier / 1.67))
    return samples


def _keyboard_impulses(seconds: float) -> list[int]:
    samples = _noise(seconds, 120, 71)
    for start_s in (0.18, 0.43, 0.82, 1.05):
        start = int(start_s * SAMPLE_RATE)
        for offset in range(120):
            decay = math.exp(-offset / 22)
            samples[start + offset] += int(9500 * decay * (1 if offset % 2 else -1))
    return [max(-32768, min(32767, value)) for value in samples]


def _cough_like() -> list[int]:
    rng = random.Random(103)
    samples = _silence(0.8)
    start = int(0.22 * SAMPLE_RATE)
    length = int(0.19 * SAMPLE_RATE)
    for offset in range(length):
        position = offset / length
        envelope = math.sin(math.pi * position) ** 2
        samples[start + offset] = int(rng.randint(-13000, 13000) * envelope)
    return samples


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    cases = []

    item = _write("silence_pause.wav", _silence(1.4))
    cases.append({**item, "transcript": "", "expected_speech": False, "expected_interruption": False})

    item = _write("background_noise.wav", _noise(1.4, 380, 29))
    cases.append({**item, "transcript": "", "expected_speech": False, "expected_interruption": False})

    item = _write("keyboard_impulses.wav", _keyboard_impulses(1.4))
    cases.append({**item, "transcript": "", "expected_speech": False, "expected_interruption": False})

    short_filler = _silence(0.2) + _speech_like(0.18, 5200) + _silence(0.32)
    item = _write("short_filler.wav", short_filler)
    cases.append(
        {
            **item,
            "speech_duration_s": 0.18,
            "transcript": "嗯",
            "expected_speech": False,
            "expected_interruption": False,
        }
    )

    item = _write("cough_like.wav", _cough_like())
    cases.append(
        {
            **item,
            "speech_duration_s": 0.19,
            "transcript": "",
            "expected_speech": False,
            "expected_interruption": False,
        }
    )

    overlap = _silence(0.1) + _speech_like(0.9) + _silence(0.2)
    item = _write("sustained_overlap.wav", overlap)
    cases.append(
        {
            **item,
            "speech_duration_s": 0.9,
            "first_speech_s": 0.1,
            "transcript": "等一下，我想补充一点",
            "expected_speech": True,
            "expected_interruption": True,
        }
    )

    paused_answer = (
        _silence(0.2)
        + _speech_like(0.65)
        + _silence(0.85)
        + _speech_like(0.55)
        + _silence(0.2)
    )
    item = _write("two_phrases_pause.wav", paused_answer)
    cases.append(
        {
            **item,
            "speech_duration_s": 1.2,
            "first_speech_s": 0.2,
            "long_pause_count": 1,
            "transcript": "我先介绍项目背景，然后说明我的具体贡献",
            "expected_speech": True,
            "expected_interruption": True,
        }
    )

    manifest = {
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "sample_width_bytes": 2,
        "cases": cases,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
