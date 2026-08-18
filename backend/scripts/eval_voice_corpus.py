"""Gate 2 scorer: how well do we measure a real Mandarin answer?

Four numbers, each with a fixed definition, computed against human labels:

  tail_loss_rate     did the last sentence survive stop-finalization
  boundary_mae_ms    |our first/last speech time - the labelled one|
  pause_f1           long pauses we found vs the ones a human marked
  term_recall        finance vocabulary the ASR actually transcribed

Deliberately *not* here: false-endpoint and false-barge-in rates. Those need the
system to act, not to measure, so they come from automatic-mode shadow logging
(record when it *would* have committed, compare against the human's click) rather
than from this corpus. See docs/voice-acceptance-runbook-2026-08.md.

Corpus layout (everything lives under one directory, kept in eval-runs/):

    manifest.json          one entry per clip, see CLIP_TEMPLATE below
    wav/<clip_id>.wav      16 kHz mono PCM, one answer per file
    labels/<clip_id>.tsv   Audacity label track: start_s <TAB> end_s <TAB> speech|pause
    asr/<clip_id>.json     what our realtime ASR returned (AsrTranscript shape)

Usage:

    # 1. scaffold manifest + label templates from a folder of wavs
    PYTHONPATH=. .venv/bin/python scripts/eval_voice_corpus.py --make-template <dir>

    # 2. after the human fills in labels/, transcripts and term lists
    PYTHONPATH=. .venv/bin/python scripts/eval_voice_corpus.py --corpus <dir> [--report out.json]

Exit code is 0 only when every gate below passes, so this can be wired into CI
once a corpus exists.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path

from app.services.interview.voice_intelligence import analyze_wav

# Gate 2 first-round thresholds (docs/voice-acceptance-runbook-2026-08.md).
# Deliberately wider than the original spec: 150 ms is a read-speech number, and
# a gate nobody can pass gets ignored rather than fixed. Tighten after round one.
GATES = {
    "tail_loss_rate": 0.0,        # max
    "boundary_mae_ms": 250.0,     # max
    "pause_f1": 0.85,             # min
    "term_recall": 0.90,          # min
}

# A system pause must overlap a labelled pause by at least this much of their
# union to count as the same event. Loose enough to tolerate edge jitter, strict
# enough that "one long pause" cannot be scored as three.
PAUSE_IOU = 0.5

CLIP_TEMPLATE = {
    "clip_id": "",
    "speaker": "",                 # s1 / s2 / s3 — no names in the corpus
    "device": "",                  # macbook_builtin | bluetooth_earbuds | phone
    "scenario": "",                # normal | pause_05 | pause_15 | terms | noise | barge_in
    "reference_text": "",          # what was actually said, typed by the human
    "tail_phrase": "",             # last 4-8 characters; used for stop-finalization loss
    "terms": [],                   # finance terms expected in this clip
}


def _normalize(text: str) -> str:
    """Keep CJK, letters and digits — punctuation and spacing are not evidence."""
    return "".join(re.findall(r"[0-9A-Za-z一-鿿]", (text or "").lower()))


@dataclass
class Clip:
    clip_id: str
    wav: Path
    meta: dict
    labels: list[tuple[float, float, str]] = field(default_factory=list)
    asr: dict | None = None

    @property
    def speech_labels(self) -> list[tuple[float, float]]:
        return [(s, e) for s, e, kind in self.labels if kind == "speech"]

    @property
    def pause_labels(self) -> list[tuple[float, float]]:
        return [(s, e) for s, e, kind in self.labels if kind == "pause"]

    @property
    def asr_text(self) -> str:
        if not self.asr:
            return ""
        return "".join(str(seg.get("text") or "") for seg in self.asr.get("segments", []))


def load_corpus(root: Path) -> list[Clip]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    clips: list[Clip] = []
    for entry in manifest["clips"]:
        clip_id = entry["clip_id"]
        wav_path = root / "wav" / f"{clip_id}.wav"
        if not wav_path.exists():
            raise FileNotFoundError(f"missing audio for {clip_id}: {wav_path}")
        clip = Clip(clip_id=clip_id, wav=wav_path, meta=entry)

        label_path = root / "labels" / f"{clip_id}.tsv"
        if label_path.exists():
            for line in label_path.read_text(encoding="utf-8").splitlines():
                parts = line.split("\t")
                if len(parts) < 3 or not parts[0].strip():
                    continue
                try:
                    clip.labels.append((float(parts[0]), float(parts[1]), parts[2].strip()))
                except ValueError:
                    continue

        asr_path = root / "asr" / f"{clip_id}.json"
        if asr_path.exists():
            clip.asr = json.loads(asr_path.read_text(encoding="utf-8"))
        clips.append(clip)
    return clips


def _iou(a: tuple[float, float], b: tuple[float, float]) -> float:
    overlap = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return overlap / union if union > 0 else 0.0


def score_clip(clip: Clip) -> dict:
    """One clip → per-metric contributions, or a reason it was skipped."""
    features, flags = analyze_wav(clip.wav, transcript_text=clip.asr_text or clip.meta.get("reference_text", ""))
    speech = features["speech"]
    system_segments = [(seg["start_s"], seg["end_s"]) for seg in speech.get("segments", [])]
    result: dict = {
        "clip_id": clip.clip_id,
        "speaker": clip.meta.get("speaker", ""),
        "device": clip.meta.get("device", ""),
        "scenario": clip.meta.get("scenario", ""),
        "quality_flags": flags,
        "boundary_errors_ms": [],
        "pause_match": None,
        "tail": None,
        "terms": None,
        "skipped": [],
    }

    # ── boundaries ────────────────────────────────────────────────────────
    if clip.speech_labels and system_segments:
        label_first = min(s for s, _ in clip.speech_labels)
        label_last = max(e for _, e in clip.speech_labels)
        system_first = system_segments[0][0]
        system_last = system_segments[-1][1]
        result["boundary_errors_ms"] = [
            abs(system_first - label_first) * 1000,
            abs(system_last - label_last) * 1000,
        ]
    else:
        result["skipped"].append("boundary: no speech labels or no detected speech")

    # ── long pauses ───────────────────────────────────────────────────────
    if clip.labels:
        floor_s = 0.5  # matches the acoustic analyzer's long-pause floor
        truth = [(s, e) for s, e in clip.pause_labels if e - s >= floor_s]
        system: list[tuple[float, float]] = []
        for (_, prev_end), (next_start, _) in zip(system_segments, system_segments[1:]):
            if next_start - prev_end >= floor_s:
                system.append((prev_end, next_start))
        matched = 0
        remaining = list(system)
        for gold in truth:
            hit = next((cand for cand in remaining if _iou(gold, cand) >= PAUSE_IOU), None)
            if hit is not None:
                remaining.remove(hit)
                matched += 1
        result["pause_match"] = {
            "truth": len(truth), "system": len(system), "matched": matched,
        }
    else:
        result["skipped"].append("pause: no label track")

    # ── stop-finalization tail ────────────────────────────────────────────
    tail = _normalize(clip.meta.get("tail_phrase", ""))
    if tail and clip.asr is not None:
        result["tail"] = {"phrase": clip.meta["tail_phrase"], "kept": tail in _normalize(clip.asr_text)}
    else:
        result["skipped"].append("tail: needs tail_phrase + asr/<clip>.json")

    # ── finance vocabulary ────────────────────────────────────────────────
    terms = [t for t in clip.meta.get("terms", []) if t.strip()]
    if terms and clip.asr is not None:
        heard = _normalize(clip.asr_text)
        missed = [t for t in terms if _normalize(t) not in heard]
        result["terms"] = {"expected": len(terms), "missed": missed}
    elif terms:
        result["skipped"].append("terms: needs asr/<clip>.json")

    return result


def aggregate(per_clip: list[dict]) -> dict:
    boundary_errors = [err for clip in per_clip for err in clip["boundary_errors_ms"]]
    truth = sum(clip["pause_match"]["truth"] for clip in per_clip if clip["pause_match"])
    system = sum(clip["pause_match"]["system"] for clip in per_clip if clip["pause_match"])
    matched = sum(clip["pause_match"]["matched"] for clip in per_clip if clip["pause_match"])
    precision = matched / system if system else 0.0
    recall = matched / truth if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    tails = [clip["tail"] for clip in per_clip if clip["tail"]]
    lost = [clip["clip_id"] for clip in per_clip if clip["tail"] and not clip["tail"]["kept"]]
    expected_terms = sum(clip["terms"]["expected"] for clip in per_clip if clip["terms"])
    missed_terms = [t for clip in per_clip if clip["terms"] for t in clip["terms"]["missed"]]

    metrics = {
        "tail_loss_rate": round(len(lost) / len(tails), 4) if tails else None,
        "boundary_mae_ms": round(sum(boundary_errors) / len(boundary_errors), 1) if boundary_errors else None,
        "pause_f1": round(f1, 4) if truth or system else None,
        "term_recall": round(1 - len(missed_terms) / expected_terms, 4) if expected_terms else None,
    }
    coverage = {
        "clips": len(per_clip),
        "clips_with_boundaries": sum(1 for c in per_clip if c["boundary_errors_ms"]),
        "clips_with_pause_labels": sum(1 for c in per_clip if c["pause_match"]),
        "clips_with_asr": len(tails),
        "expected_terms": expected_terms,
        "speakers": sorted({c["speaker"] for c in per_clip if c["speaker"]}),
        "devices": sorted({c["device"] for c in per_clip if c["device"]}),
    }

    failures = []
    for name, value in metrics.items():
        if value is None:
            failures.append(f"{name}: not measurable — corpus is missing the inputs for it")
            continue
        gate = GATES[name]
        if name in {"tail_loss_rate", "boundary_mae_ms"}:
            if value > gate:
                failures.append(f"{name}={value} exceeds {gate}")
        elif value < gate:
            failures.append(f"{name}={value} below {gate}")

    # A corpus that cannot fail is not a gate: refuse to sign off on a sample
    # thinner than the runbook asks for.
    if coverage["clips"] < 30:
        failures.append(f"corpus has {coverage['clips']} clips, runbook asks for 30")
    if len(coverage["speakers"]) < 3:
        failures.append(f"corpus has {len(coverage['speakers'])} speakers, runbook asks for 3")
    if len(coverage["devices"]) < 3:
        failures.append(f"corpus covers {len(coverage['devices'])} devices, runbook asks for 3")

    return {
        "gate": "voice-corpus-gate2",
        "status": "go" if not failures else "no-go",
        "metrics": metrics,
        "thresholds": GATES,
        "coverage": coverage,
        "lost_tails": lost,
        "missed_terms": sorted(set(missed_terms)),
        "failures": failures,
        "clips": per_clip,
    }


def make_template(root: Path) -> None:
    """Scaffold manifest + empty label tracks from whatever wavs are present."""
    wav_dir = root / "wav"
    if not wav_dir.is_dir():
        raise SystemExit(f"put the recordings in {wav_dir} first")
    (root / "labels").mkdir(exist_ok=True)
    (root / "asr").mkdir(exist_ok=True)

    clips = []
    for wav_path in sorted(wav_dir.glob("*.wav")):
        clip_id = wav_path.stem
        entry = dict(CLIP_TEMPLATE, clip_id=clip_id, terms=[])
        clips.append(entry)
        label_path = root / "labels" / f"{clip_id}.tsv"
        if not label_path.exists():
            with wave.open(str(wav_path), "rb") as handle:
                duration = handle.getnframes() / float(handle.getframerate() or 1)
            label_path.write_text(
                "# start_s\tend_s\tspeech|pause  (Audacity label track export)\n"
                f"# clip duration: {duration:.2f}s — replace these two example rows\n"
                "0.000\t0.000\tspeech\n0.000\t0.000\tpause\n",
                encoding="utf-8",
            )
    manifest = root / "manifest.json"
    if manifest.exists():
        raise SystemExit(f"{manifest} already exists; not overwriting")
    manifest.write_text(
        json.dumps({"clips": clips}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"scaffolded {len(clips)} clips in {root}")
    print("next: fill speaker/device/scenario/reference_text/tail_phrase/terms in manifest.json,")
    print("      export Audacity label tracks into labels/, drop realtime ASR output into asr/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, help="corpus directory to score")
    parser.add_argument("--make-template", type=Path, dest="template", help="scaffold a corpus directory")
    parser.add_argument("--report", type=Path, help="write the JSON report here as well as stdout")
    args = parser.parse_args()

    if args.template:
        make_template(args.template)
        return 0
    if not args.corpus:
        parser.error("pass --corpus <dir> or --make-template <dir>")

    clips = load_corpus(args.corpus)
    report = aggregate([score_clip(clip) for clip in clips])
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0 if report["status"] == "go" else 1


if __name__ == "__main__":
    sys.exit(main())
