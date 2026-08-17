# JobRadar Voice Agent Acceptance

## Decision model

The release decision has three gates. Gate A is executable in CI and locally.
Gate B requires reviewed Chinese interview recordings. Gate C requires a deployed
LiveKit room and real provider credentials. A production cohort starts only when all
blocking checks in A-C are green; Phase 5 native-speech experiments are not blocking.

## Gate A - automated

Run from `backend/`:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_interview_voice_intelligence.py \
  tests/test_interview_livekit_voice.py \
  tests/test_interview_tts_streaming.py \
  tests/test_interview_asr_websocket.py \
  tests/test_interview_router_turn.py \
  tests/test_voice_metrics.py
PYTHONPATH=. .venv/bin/python scripts/evaluate_voice_intelligence.py
```

Run from `resume-copilot-web/`:

```bash
npx tsc --noEmit
npm run lint
npm run build
```

Blocking checks:

- Explicit consent is required before any WAV is written.
- An artifact is bound to an existing turn and cannot be read by another user key.
- User deletion removes the physical file and derived analysis.
- Expiry cleanup removes only expired artifacts.
- Silence, low background noise and keyboard impulses are not accepted as a valid
  answer; deterministic speech/pause fixtures stay within 100 ms timing error.
- No user-facing or API voice payload contains an uncalibrated confidence label.
- Audio analysis failure never blocks answer submission or report generation.
- The deterministic extractor p95 processing real-time factor is below 0.5.

## Gate B - reviewed speaker set

Collect at least 100 consented turns from at least 20 Mandarin speakers. Include
ordinary answers, intentional 0.5-2.0 second pauses, fillers, quiet/loud input,
finance terms, cough/keyboard noise, overlap and deliberate barge-in. Two reviewers
mark speech boundaries, long pauses, transcript text, interruption intent and whether
the recording is usable. Resolve disagreements before scoring the system.

Blocking targets:

| Area | Target |
| --- | --- |
| final-sentence loss | 0 / 100 stop-finalization trials |
| first/last speech boundary MAE | <= 150 ms |
| long-pause detection F1 | >= 0.90 |
| false endpoint rate | < 2% |
| false barge-in rate | < 1% on the supported noise set |
| finance keyword recall | >= 95% on the reviewed keyword list |
| shadow-ASR regression | CER no more than 2 percentage points worse than realtime ASR |
| deletion verification | 100% of requested files absent from storage |
| unsupported judgments | zero confidence/personality labels |

Voice labels beyond measured facts remain hidden until a reviewed dataset shows label
agreement, calibration and drift behavior. Model consensus alone is a weak label, not
ground truth.

## Gate C - real LiveKit room

Test Chrome desktop, Safari desktop, iOS Safari and Android Chrome on normal Wi-Fi and
a shaped lossy/150 ms RTT profile. Use one 20-minute session per browser plus 30
targeted interruption/reconnect trials.

Blocking targets:

- End of answer to first interviewer audio p95 below 1.5 seconds.
- User barge-in to audible interviewer stop p95 below 300 ms.
- Reconnect completes within 5 seconds without a duplicate question or answer.
- Agent/TTS cancellation leaves no old audio after a new turn starts.
- Transcript, heard-question text and interruption state agree with room events.
- A failed realtime setup reaches the legacy path once, without duplicate first turns.
- Provider credentials never appear in browser traffic, storage or logs.
- Desktop and 390 px mobile layouts have no overlap or horizontal overflow.

## Current status

- Gate A: implemented; deterministic fixture gate reports `go` for seven cases.
- Gate B: protocol ready, reviewed human corpus not yet collected.
- Gate C: browser fallback path verified; real-room measurements are pending LiveKit
  deployment credentials.
- Phase 5: optional A/B research after the cascaded production path passes A-C.
