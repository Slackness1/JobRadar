"""Privacy-safe storage and deterministic analysis for interview audio.

Raw WAV files are accepted only after explicit per-upload consent, live outside
SQLite, and expire independently of derived measurements. The analyzer exposes
measured acoustic facts only; it does not infer confidence or personality.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import math
import os
import re
import uuid
import wave
from queue import Full, Queue
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from threading import Lock, Thread

import numpy as np
from sqlalchemy.orm import Session

from app import config
from app.database import SessionLocal
from app.models import InterviewAudioArtifact, InterviewTurn
from app.services.interview.voice.asr import run_asr_session


ANALYZER_VERSION = "voice-facts-v1"
CONSENT_VERSION = "voice-analysis-v1"
SUPPORTED_SAMPLE_RATES = {8000, 12000, 16000, 22050, 24000, 32000, 44100, 48000}
_QUEUED_ARTIFACTS: set[str] = set()
_QUEUE_LOCK = Lock()
_ANALYSIS_QUEUE: Queue[tuple[str, Callable[[], Session], str]] = Queue(maxsize=256)
_WORKERS_STARTED = False
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WavMetadata:
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int
    duration_seconds: float


def inspect_wav_bytes(data: bytes) -> WavMetadata:
    """Validate the narrow PCM contract accepted by the analysis worker."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            metadata = WavMetadata(
                sample_rate=wav.getframerate(),
                channels=wav.getnchannels(),
                sample_width=wav.getsampwidth(),
                frame_count=wav.getnframes(),
                duration_seconds=(wav.getnframes() / wav.getframerate())
                if wav.getframerate()
                else 0.0,
            )
            compression = wav.getcomptype()
    except (EOFError, wave.Error) as exc:
        raise ValueError("INVALID_WAV") from exc

    if compression != "NONE" or metadata.sample_width != 2:
        raise ValueError("WAV_MUST_BE_PCM_S16LE")
    if metadata.channels != 1:
        raise ValueError("WAV_MUST_BE_MONO")
    if metadata.sample_rate not in SUPPORTED_SAMPLE_RATES:
        raise ValueError("UNSUPPORTED_WAV_SAMPLE_RATE")
    if metadata.frame_count <= 0 or metadata.duration_seconds <= 0:
        raise ValueError("EMPTY_WAV")
    if metadata.duration_seconds > 10 * 60:
        raise ValueError("WAV_DURATION_LIMIT_EXCEEDED")
    return metadata


def persist_private_wav(artifact_id: str, data: bytes, storage_root: Path | None = None) -> Path:
    root = Path(storage_root or config.VOICE_AUDIO_STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    path = root / f"{artifact_id}.wav"
    with path.open("xb") as handle:
        os.chmod(path, 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _read_pcm(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return samples, sample_rate


def _frames(samples: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    if len(samples) < frame_size:
        padded = np.pad(samples, (0, frame_size - len(samples)))
        return padded.reshape(1, -1)
    count = 1 + (len(samples) - frame_size) // hop_size
    shape = (count, frame_size)
    strides = (samples.strides[0] * hop_size, samples.strides[0])
    return np.lib.stride_tricks.as_strided(samples, shape=shape, strides=strides).copy()


def _speech_segments(mask: np.ndarray, hop_seconds: float) -> list[tuple[float, float]]:
    raw: list[tuple[float, float]] = []
    start: int | None = None
    for index, active in enumerate([*mask.tolist(), False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            raw.append((start * hop_seconds, index * hop_seconds))
            start = None

    filtered = [segment for segment in raw if segment[1] - segment[0] >= 0.18]
    merged: list[tuple[float, float]] = []
    for segment in filtered:
        if merged and segment[0] - merged[-1][1] <= 0.20:
            merged[-1] = (merged[-1][0], segment[1])
        else:
            merged.append(segment)
    return merged


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-7))


def _pitch_values(
    samples: np.ndarray,
    sample_rate: int,
    speech_segments: list[tuple[float, float]],
) -> list[float]:
    window_size = max(1, int(sample_rate * 0.04))
    hop_size = max(1, int(sample_rate * 0.02))
    lag_min = max(1, int(sample_rate / 400))
    lag_max = max(lag_min + 1, int(sample_rate / 75))
    values: list[float] = []

    for start_s, end_s in speech_segments:
        start = max(0, int(start_s * sample_rate))
        end = min(len(samples), int(end_s * sample_rate))
        for offset in range(start, max(start, end - window_size + 1), hop_size):
            window = samples[offset:offset + window_size].astype(np.float64)
            window -= np.mean(window)
            energy = float(np.dot(window, window))
            if energy < 1e-5:
                continue
            corr = np.correlate(window, window, mode="full")[window_size - 1:]
            upper = min(lag_max, len(corr) - 1)
            if upper <= lag_min:
                continue
            local = corr[lag_min:upper + 1]
            lag = lag_min + int(np.argmax(local))
            strength = float(corr[lag] / max(corr[0], 1e-12))
            if strength >= 0.35:
                values.append(sample_rate / lag)
    return values


def analyze_wav(
    path: Path,
    *,
    transcript_text: str = "",
) -> tuple[dict, list[str]]:
    """Extract reproducible cadence, energy and raw F0 measurements."""
    samples, sample_rate = _read_pcm(path)
    duration_s = len(samples) / sample_rate
    frame_size = max(1, int(sample_rate * 0.03))
    hop_size = max(1, int(sample_rate * 0.01))
    framed = _frames(samples, frame_size, hop_size)
    rms = np.sqrt(np.mean(np.square(framed), axis=1) + 1e-12)

    noise_floor = float(np.percentile(rms, 20))
    high_energy = float(np.percentile(rms, 90))
    # In ordinary recordings the low percentile approximates room noise. A
    # sustained answer/tone can have no quiet frames, so cap the threshold by a
    # fraction of high energy instead of classifying the whole clip as silence.
    threshold = max(0.006, min(noise_floor * 2.8, high_energy * 0.35))
    speech_mask = rms >= threshold
    segments = _speech_segments(speech_mask, hop_size / sample_rate)
    if high_energy < 0.012:
        segments = []
    measured_speech_mask = np.zeros_like(speech_mask, dtype=bool)
    for start_s, end_s in segments:
        start_frame = max(0, int(start_s * sample_rate / hop_size))
        end_frame = min(len(measured_speech_mask), math.ceil(end_s * sample_rate / hop_size))
        measured_speech_mask[start_frame:end_frame] = True
    speech_duration_s = sum(end - start for start, end in segments)
    pauses = [
        current[0] - previous[1]
        for previous, current in zip(segments, segments[1:])
        if current[0] - previous[1] >= 0.50
    ]

    speech_rms_values = rms[measured_speech_mask]
    if speech_rms_values.size:
        energy_mean_dbfs = _dbfs(float(np.mean(speech_rms_values)))
        energy_p10_dbfs = _dbfs(float(np.percentile(speech_rms_values, 10)))
        energy_p90_dbfs = _dbfs(float(np.percentile(speech_rms_values, 90)))
    else:
        energy_mean_dbfs = energy_p10_dbfs = energy_p90_dbfs = None

    pitch = _pitch_values(samples, sample_rate, segments)
    normalized_chars = len(re.sub(r"\s+", "", transcript_text))
    articulation_cpm = (
        normalized_chars * 60.0 / speech_duration_s
        if normalized_chars and speech_duration_s > 0
        else None
    )
    clipping_ratio = float(np.mean(np.abs(samples) >= 0.995))

    flags: list[str] = []
    if speech_duration_s < 0.50:
        flags.append("insufficient_speech")
    if clipping_ratio >= 0.01:
        flags.append("clipping_detected")
    if energy_mean_dbfs is None or energy_mean_dbfs < -40:
        flags.append("low_input_level")
    if len(pitch) < 5:
        flags.append("pitch_unavailable")

    features = {
        "version": ANALYZER_VERSION,
        "method": "adaptive-energy-vad+autocorrelation-f0",
        "duration_seconds": round(duration_s, 3),
        "speech": {
            "first_speech_ms": round(segments[0][0] * 1000) if segments else None,
            "speech_duration_seconds": round(speech_duration_s, 3),
            "voiced_ratio": round(speech_duration_s / duration_s, 4) if duration_s else None,
            "segment_count": len(segments),
            "segments": [
                {"start_s": round(start, 3), "end_s": round(end, 3)}
                for start, end in segments
            ],
        },
        "pauses": {
            "count": len(pauses),
            "total_seconds": round(sum(pauses), 3),
            "mean_seconds": round(float(np.mean(pauses)), 3) if pauses else None,
            "max_seconds": round(max(pauses), 3) if pauses else None,
        },
        "delivery": {
            "articulation_cpm": round(articulation_cpm) if articulation_cpm else None,
        },
        "energy": {
            "mean_dbfs": round(energy_mean_dbfs, 2) if energy_mean_dbfs is not None else None,
            "dynamic_range_db": (
                round(energy_p90_dbfs - energy_p10_dbfs, 2)
                if energy_p90_dbfs is not None and energy_p10_dbfs is not None
                else None
            ),
            "clipping_ratio": round(clipping_ratio, 6),
        },
        "pitch": {
            "sample_count": len(pitch),
            "median_hz": round(float(np.median(pitch)), 1) if pitch else None,
            "p10_hz": round(float(np.percentile(pitch, 10)), 1) if pitch else None,
            "p90_hz": round(float(np.percentile(pitch, 90)), 1) if pitch else None,
        },
    }
    return features, flags


def normalized_character_error_rate(reference: str, hypothesis: str) -> float | None:
    normalize = lambda value: "".join(re.findall(r"[\w\u4e00-\u9fff]", value.lower()))
    expected = normalize(reference)
    actual = normalize(hypothesis)
    if not expected:
        return None
    previous = list(range(len(actual) + 1))
    for row_index, expected_char in enumerate(expected, start=1):
        current = [row_index]
        for col_index, actual_char in enumerate(actual, start=1):
            current.append(min(
                current[-1] + 1,
                previous[col_index] + 1,
                previous[col_index - 1] + (expected_char != actual_char),
            ))
        previous = current
    return round(previous[-1] / len(expected), 4)


async def _run_shadow_asr(pcm: bytes, sample_rate: int) -> dict:
    events: list[dict] = []

    async def frames():
        frame_bytes = max(2, int(sample_rate * 0.1) * 2)
        for offset in range(0, len(pcm), frame_bytes):
            yield pcm[offset:offset + frame_bytes]

    async def collect(event: dict) -> None:
        events.append(event)

    await run_asr_session(frames(), collect, sample_rate=sample_rate)
    text = "".join(
        str(event.get("text") or "") for event in events if event.get("type") == "final"
    )
    return {"status": "ready", "provider": "dashscope-paraformer", "text": text}


def shadow_asr_for_wav(path: Path, *, reference_text: str) -> dict:
    if not config.VOICE_SHADOW_ASR_ENABLED:
        return {"status": "disabled"}
    try:
        with wave.open(str(path), "rb") as wav:
            sample_rate = wav.getframerate()
            pcm = wav.readframes(wav.getnframes())
        result = asyncio.run(_run_shadow_asr(pcm, sample_rate))
        result["character_error_rate"] = normalized_character_error_rate(
            reference_text, str(result.get("text") or "")
        )
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:300]}


def analyze_audio_artifact(
    artifact_id: str,
    session_factory: Callable[[], Session] = SessionLocal,
    reference_text: str = "",
) -> None:
    """Background-task entry point. It owns its DB session and degrades safely."""
    db = session_factory()
    try:
        row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one_or_none()
        if row is None or row.deleted_at is not None:
            return
        row.status = "analyzing"
        row.updated_at = datetime.utcnow()
        db.commit()

        path = Path(str(row.storage_path))
        turn = db.query(InterviewTurn).filter_by(
            session_id=row.session_id, turn_index=row.turn_index
        ).one_or_none()
        reference_text = reference_text or (str(turn.user_answer or "") if turn else "")
        features, flags = analyze_wav(path, transcript_text=reference_text)
        shadow = shadow_asr_for_wav(path, reference_text=reference_text)

        db.refresh(row)
        if row.deleted_at is not None:
            return
        row.analyzer_version = ANALYZER_VERSION
        row.features_json = json.dumps(features, ensure_ascii=False)
        row.shadow_asr_json = json.dumps(shadow, ensure_ascii=False)
        row.quality_flags_json = json.dumps(flags, ensure_ascii=False)
        row.status = "ready"
        row.error_message = ""
        row.updated_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        db.rollback()
        row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one_or_none()
        if row is not None and row.deleted_at is None:
            row.status = "error"
            row.error_message = str(exc)[:500]
            row.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def enqueue_audio_analysis(
    artifact_id: str,
    session_factory: Callable[[], Session] = SessionLocal,
    reference_text: str = "",
) -> bool:
    """Submit once to bounded daemon workers and return without joining them."""
    _ensure_analysis_workers()
    with _QUEUE_LOCK:
        if artifact_id in _QUEUED_ARTIFACTS:
            return False
        _QUEUED_ARTIFACTS.add(artifact_id)
    try:
        _ANALYSIS_QUEUE.put_nowait((artifact_id, session_factory, reference_text))
    except Full:
        with _QUEUE_LOCK:
            _QUEUED_ARTIFACTS.discard(artifact_id)
        return False
    return True


def _analysis_worker() -> None:
    while True:
        artifact_id, session_factory, reference_text = _ANALYSIS_QUEUE.get()
        try:
            analyze_audio_artifact(artifact_id, session_factory, reference_text)
        except Exception:
            logger.exception("voice analysis worker crashed for artifact %s", artifact_id)
        finally:
            with _QUEUE_LOCK:
                _QUEUED_ARTIFACTS.discard(artifact_id)
            _ANALYSIS_QUEUE.task_done()


def _ensure_analysis_workers() -> None:
    global _WORKERS_STARTED
    with _QUEUE_LOCK:
        if _WORKERS_STARTED:
            return
        for index in range(2):
            Thread(
                target=_analysis_worker,
                name=f"voice-analysis-{index + 1}",
                daemon=True,
            ).start()
        _WORKERS_STARTED = True


def recover_pending_audio_analysis(
    session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    """Requeue non-expired work left behind by a process restart."""
    db = session_factory()
    try:
        rows = db.query(InterviewAudioArtifact).filter(
            InterviewAudioArtifact.status.in_(["uploaded", "analyzing"]),
            InterviewAudioArtifact.deleted_at.is_(None),
            InterviewAudioArtifact.expires_at > datetime.utcnow(),
        ).all()
        ids = [row.id for row in rows if row.storage_path and Path(row.storage_path).is_file()]
    finally:
        db.close()
    return sum(1 for artifact_id in ids if enqueue_audio_analysis(artifact_id, session_factory))


def delete_audio_artifact(row: InterviewAudioArtifact, db: Session, *, status: str = "deleted") -> None:
    path = Path(str(row.storage_path)) if row.storage_path else None
    if path:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # A DB state claiming deletion while the file remains would violate
            # the privacy contract, so let the caller surface the failure.
            raise
    row.storage_path = ""
    row.status = status
    row.features_json = "{}"
    row.shadow_asr_json = "{}"
    row.quality_flags_json = "[]"
    row.error_message = ""
    row.deleted_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()


def cleanup_expired_audio(db: Session, *, now: datetime | None = None) -> int:
    cutoff = now or datetime.utcnow()
    rows = (
        db.query(InterviewAudioArtifact)
        .filter(
            InterviewAudioArtifact.deleted_at.is_(None),
            InterviewAudioArtifact.expires_at <= cutoff,
        )
        .all()
    )
    count = 0
    for row in rows:
        delete_audio_artifact(row, db, status="expired")
        count += 1
    return count


def serialize_audio_artifact(row: InterviewAudioArtifact) -> dict:
    def parse(raw: str, fallback):
        try:
            return json.loads(raw or "")
        except json.JSONDecodeError:
            return fallback

    return {
        "id": row.id,
        "session_id": row.session_id,
        "turn_index": int(row.turn_index),
        "status": row.status,
        "duration_seconds": float(row.duration_seconds or 0),
        "sample_rate": int(row.sample_rate or 0),
        "analyzer_version": row.analyzer_version,
        "features": parse(row.features_json, {}),
        "shadow_asr": parse(row.shadow_asr_json, {}),
        "quality_flags": parse(row.quality_flags_json, []),
        "replay_available": bool(row.storage_path and row.deleted_at is None),
        "expires_at": row.expires_at.isoformat() + "Z" if row.expires_at else "",
        "deleted_at": row.deleted_at.isoformat() + "Z" if row.deleted_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else "",
    }


def new_artifact_id() -> str:
    return uuid.uuid4().hex


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
