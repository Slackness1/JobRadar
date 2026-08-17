# Voice Intelligence v1

## Status

- Date: 2026-07-28
- Owner: JobRadar mock-interview
- Current implementation scope: Phase 0 — trustworthy ASR timing and transcript contract
- Explicitly deferred: raw-audio retention, local ML workers, user-facing confidence score

## Problem

The current mock-interview voice path receives real-time ASR text, but drops the
ASR provider's sentence timestamps. The browser then synthesizes contiguous
segments. As a result, `pause_count` and `response_latency_ms` can look valid
while not representing the user's actual speech.

Voice Intelligence v1 separates:

1. **Measured facts** — speech timing, pauses, cadence, audio energy and pitch.
2. **Derived interpretation** — an experimental expression-stability score.
3. **Perceived confidence** — a supervised model that is not shipped until it
   has reliable labels and calibration evidence.

## Target architecture

```text
browser PCM
  ├─ DashScope Paraformer (real-time transcript for the interview UI)
  └─ optional, consented WAV artifact
       └─ async Voice Analysis Worker
            ├─ Silero VAD: speech boundaries and pause timing
            ├─ SenseVoice / FunASR: offline ASR, timestamps, emotion/event hints
            ├─ librosa: energy and volume dynamics
            └─ torchcrepe: F0/pitch dynamics
                 └─ versioned feature record
                      └─ later: calibrated ranker/regressor
```

The real-time ASR path remains the interaction source of truth. Offline analysis
must never block answer submission, next-question generation, or report creation.

## Phase plan

### Phase 0 — trustworthy timing contract (this implementation)

1. Propagate DashScope final-sentence `begin_time` / `end_time` to the browser
   as optional seconds.
2. Make the frontend wait for `final` + `completed` after a stop request;
   never close the socket before the provider's final hypothesis arrives.
3. Send a typed ASR transcript to `POST /turn`, rather than a text string.
4. Preserve real timestamps when available. If unavailable, leave timing-derived
   metrics as `null`; do not invent contiguous timings.
5. Add regression tests for typed payload forwarding and stop/final/completed
   ordering.

### Phase 1 — consented audio artifact and deterministic VAD

1. Authenticate and bind each recording to an existing interview turn.
2. Store raw PCM as a temporary WAV artifact outside SQLite; retain a checksum,
   sample rate, duration, analysis status, expiry and analyzer version in DB.
3. Default to short retention, user deletion, expiry cleanup and deny-by-default
   access checks.
4. Run Silero VAD asynchronously to produce response latency, speech duration,
   pause distribution and articulation CPM.

### Phase 2 — acoustic and offline-ASR features

1. Run librosa RMS/energy features and torchcrepe F0 features only on VAD speech
   spans.
2. Run SenseVoice/FunASR in shadow mode. It may provide comparison text,
   timestamps and emotion/event hints, but cannot overwrite the real-time answer.
3. Version every feature record and expose quality flags such as insufficient
   speech, clipping and timestamp-unavailable.

### Phase 3 — automated quality harness

Use generated TTS audio plus deterministic transformations (known silence,
volume, pitch and noise changes) to test extraction without human annotation.
Track pause-duration error, timing error, ASR character error rate, finance-keyword
recall, truncation rate, processing real-time factor and p95 finalization latency.

### Phase 4 — weak labels and model experiments

Use multi-model audio-judge consensus only as **weak labels** in shadow mode.
Do not call the output an objective confidence score. Train LightGBM/XGBoost only
after feature quality, label agreement, calibration and drift are measured.

## Transcript contract

`POST /api/interview/turn` receives:

```json
{
  "audio_duration_s": 28.4,
  "segments": [
    {
      "start_s": 0.2,
      "end_s": 15.5,
      "text": "嗯，我先介绍一下项目背景。"
    }
  ]
}
```

`start_s` and `end_s` are optional because some ASR events may not supply them.
Timing metrics require valid, monotonic timestamps. Text-only metrics remain
available when timing is absent.

## Metric rules

| Metric | Source | Phase 0 behavior |
| --- | --- | --- |
| filler rate | ASR text / recording duration | available, marked text-derived |
| response CPM | ASR text / recording duration | available; this is not literal English WPM |
| response latency | first valid speech timestamp | `null` without timestamp |
| pause count | valid gap between timestamped segments | `null` without timestamp |
| articulation CPM | VAD speech duration | Phase 1 |
| energy / F0 / tail trend | raw audio | Phase 2 |
| perceived confidence | calibrated supervised model | Phase 4 only |

## Acceptance criteria for Phase 0

1. A backend ASR final event preserves valid provider timing in seconds.
2. A browser stop request can receive `final` then `completed` before close.
3. The backend rejects malformed ASR transcript shapes with HTTP 422.
4. The orchestrator receives the same typed transcript it was sent.
5. Missing timestamps do not turn into fake zero latency or fake zero pauses.
6. Existing text-mode interview requests remain compatible.

## Privacy and product constraints

- Raw audio is not persisted in Phase 0.
- Phase 1 requires a dedicated migration and user deletion/expiry workflow before
  capture is enabled.
- Feature extraction is asynchronous and failure-degrading: no voice analysis
  failure can block an interview answer.
- User-facing language before Phase 4 is “speech/cadence observations”, never
  “objective confidence diagnosis”.
