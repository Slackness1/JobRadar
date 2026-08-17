# JobRadar Realtime Voice Agent Spec

- Status: accepted for staged implementation
- Date: 2026-08-16
- Product: Resume Copilot Mock Interview
- Primary audience: Chinese finance and business students preparing for role-specific interviews
- Architecture decision: cascaded interview intelligence over a realtime media runtime

## 1. Product problem

The current mock interview has strong domain logic but a weak realtime boundary:

1. Browser microphone audio is streamed to DashScope ASR, but transport and session
   behavior are implemented as an application WebSocket rather than a realtime media
   session.
2. The backend yields CosyVoice audio chunks, but the browser waits for a complete
   `Blob` before playback. Backend streaming therefore does not reduce first-audio
   latency.
3. Stopping playback does not yet define one cancellation contract across browser
   playback, HTTP streaming, provider synthesis, and pending model generation.
4. End-of-turn and interruption behavior are not modeled as independent decisions.
   Silence, background noise, a filler sound, and an intentional barge-in can be
   confused.
5. There is no complete per-turn latency trace that can prove where a slow or broken
   interaction occurred.

The product must feel like a credible interviewer while preserving JobRadar's core
advantage: role-specific questions, evidence-grounded follow-ups, exact transcripts,
per-turn evaluation, and an auditable final report.

## 2. North-star experience

JobRadar is a structured-duplex AI interviewer:

- The media layer is full duplex: microphone input and interviewer audio output may
  exist at the same time.
- Conversation policy is structured: the interviewer normally lets the candidate
  finish and does not continuously backchannel over an answer.
- The candidate may interrupt the interviewer by speaking or by using an explicit
  control.
- The interviewer may intervene only under an explicit interview policy, such as a
  time limit, persistent repetition, or a pressure-interview mode.
- Every committed turn remains reconstructable from transcript, timing evidence,
  question context, scoring evidence, and playback events.

## 3. Terminology and completion rules

| Term | Definition | Completion rule |
|---|---|---|
| Streaming ASR | Partial and final transcripts arrive while the candidate speaks. | Final text is received after stop without losing the last sentence. |
| Streaming TTS | Audio playback starts before synthesis of the complete utterance finishes. | Browser plays the first PCM frames while the response body is still open. |
| Full-duplex transport | Input and output audio tracks can be active concurrently. | WebRTC session carries both tracks without stopping the microphone for playback. |
| Interruption | A committed action that stops obsolete output and generation. | Playback buffer, TTS stream, pending response, and conversation history agree on the stop point. |
| Barge-in | User speech during interviewer output that requests an interruption. | Sustained target speech interrupts within the latency budget; noise and brief fillers do not. |
| End-of-turn detection | Decision that a candidate has completed the answer. | Uses acoustic and semantic evidence, with explicit manual fallback. |
| False-interruption recovery | Recovery when speech/noise was incorrectly treated as a barge-in. | The interviewer can resume or restart cleanly without corrupting history. |
| Backchannel | Short listener feedback while the other party is speaking. | Disabled by default; enabled only in an evaluated mode. |

The product must not claim "full duplex" merely because a microphone remains open,
or "barge-in" merely because a local audio element can be paused.

## 4. Functional requirements

### 4.1 Realtime speech

- `VOICE-RT-01`: Stream candidate audio and surface partial/final transcripts.
- `VOICE-RT-02`: Stream interviewer PCM to the browser and start playback before
  response completion.
- `VOICE-RT-03`: Preserve a manual stop control in every automatic mode.
- `VOICE-RT-04`: Represent the visible state as one of `connecting`, `speaking`,
  `listening`, `finalizing`, `thinking`, `recovering`, or `error`.
- `VOICE-RT-05`: Survive provider or network failure with a text-mode fallback and
  without losing the committed transcript.

### 4.2 Turn handling and interruption

- `VOICE-TURN-01`: Distinguish speech activity from end of turn.
- `VOICE-TURN-02`: Combine VAD, an audio turn detector, transcript evidence, question
  type, and maximum-duration policy.
- `VOICE-TURN-03`: Candidate barge-in stops audible output within 400 ms at p95 in the
  supported network profile.
- `VOICE-TURN-04`: Cancellation propagates to queued audio, provider TTS, pending LLM
  output, and any speculative work that is no longer useful.
- `VOICE-TURN-05`: Conversation history records only interviewer content that was
  actually played or explicitly re-issued after interruption.
- `VOICE-TURN-06`: Coughs, keyboard noise, echo, and short fillers do not commit a new
  candidate turn.

### 4.3 Interview intelligence

- `VOICE-INT-01`: Questions remain grounded in the selected job, JD, resume, memory,
  and available knowledge-pack context.
- `VOICE-INT-02`: The next question may be a planned question, evidence-seeking
  follow-up, clarification, challenge, or interview-policy intervention.
- `VOICE-INT-03`: Content scoring and voice observations are separate outputs.
- `VOICE-INT-04`: Acoustic measurements must not be presented as calibrated confidence
  or personality judgments without an evaluated model.
- `VOICE-INT-05`: The final report links claims to turns and lets the user inspect the
  supporting transcript or replay segment.

### 4.4 Privacy and audit

- `VOICE-PRIV-01`: Raw audio persistence is opt-in and has deletion and expiry paths.
- `VOICE-PRIV-02`: Transcript-only interview mode remains usable.
- `VOICE-PRIV-03`: Each turn emits a trace with endpointing, STT finalization, LLM first
  token, TTS first byte, first audio, completion, interruption, and error events.
- `VOICE-PRIV-04`: Provider credentials never reach the browser.

## 5. Target architecture

```text
Browser
  <-> LiveKit WebRTC room
        <-> JobRadar voice-agent process (Python / LiveKit Agents)
              -> VAD + audio turn detector
              -> DashScope streaming STT adapter
              -> JobRadar Interview Orchestrator
                   -> JD / resume / memory / RAG
                   -> scoring and follow-up policy
              -> DashScope streaming TTS adapter
              -> turn event and latency trace

Committed audio artifact (opt-in)
  -> asynchronous Voice Intelligence Worker
       -> deterministic VAD and pause features
       -> energy and pitch features
       -> shadow ASR and quality evaluation
```

LiveKit owns media transport, realtime session lifecycle, playback, and interruption
coordination. The existing Interview Orchestrator remains the domain brain and source
of persisted interview decisions. Voice analysis runs asynchronously and must not
block the next question.

## 6. Delivery phases

### Phase 0: trustworthy ASR evidence

Status: in progress in the current working tree.

- Preserve provider final-segment timing when available.
- Wait for the provider's final event after the user stops recording.
- Keep missing timing as null instead of fabricating zero-duration evidence.
- Pass a typed ASR transcript contract into turn processing.

### Phase 1: realtime foundations

Goal: prove true streaming playback and cancellation on the current transport before
introducing a new media runtime.

Scope:

1. Add raw signed 16-bit little-endian PCM output to the interview TTS endpoint.
2. Read the response body incrementally in the browser and schedule chunks with Web
   Audio instead of awaiting a complete `Blob`.
3. Abort the HTTP response and stop every scheduled source when the user stops TTS.
4. Signal cancellation to the DashScope producer so an abandoned stream cannot block
   on an unconsumed queue.
5. Expose request-to-headers, request-to-first-byte, and request-to-first-audio
   measurements from the player.
6. Preserve the buffered WAV path as a compatibility fallback.

Non-goals:

- No automatic VAD barge-in.
- No claim of WebRTC/full-duplex transport.
- No LiveKit production deployment.
- No raw-audio persistence or acoustic scoring expansion.
- No simultaneous STT/TTS provider migration.

Acceptance criteria:

- The first PCM chunk is scheduled before the HTTP response completes.
- Stop clears scheduled audio and aborts the active fetch immediately.
- A second `speak()` call cannot play audio from the previous request.
- Odd-byte network chunk boundaries do not corrupt PCM samples.
- WAV fallback continues to work when streaming PCM is unavailable.
- Backend service and route tests pass; Resume Copilot lint and production build pass.
- A real-provider browser smoke test records first-byte and first-audio latency before
  this phase is declared production-ready.

Implementation status on 2026-08-16:

- Implemented in the current working tree.
- Focused backend voice/interview tests: 24 passed.
- Resume Copilot lint: 0 errors, 3 pre-existing unrelated warnings.
- Resume Copilot production build: passed.
- Real CosyVoice provider smoke: first 8,000-byte PCM chunk in 400.5 ms; 111,572
  total bytes, representing 2.53 seconds at 22,050 Hz.
- Through the Next.js `/api` proxy: first response byte in 616.6 ms and complete
  response in 2.32 seconds with chunked transfer. This confirms the proxy does not
  buffer the complete audio body.
- Headless Chromium reached the ready-for-answer state after the real PCM request.
  Headless audio is muted, so a human audible-continuity and stop-latency check is
  still required before production-ready status.

### Phase 2: WebRTC session migration

- Introduce a separate LiveKit Agents Python process.
- Replace browser microphone WebSocket and HTTP TTS playback with WebRTC tracks.
- Wrap current DashScope ASR/TTS and Interview Orchestrator behind agent nodes.
- Add reconnect, room authorization, quotas, and per-turn OpenTelemetry traces.
- Keep push-to-talk as the default turn-commit mechanism during migration.

### Phase 3: intelligent endpointing and barge-in

- Add Silero VAD plus a Chinese-capable audio turn detector.
- Enable automatic end-of-turn behind a per-session feature flag.
- Add adaptive barge-in with echo/noise protection and false-interruption recovery.
- Propagate interruption through playback, TTS, LLM, and persisted heard-text state.
- Add deterministic audio fixtures for pauses, fillers, coughs, noise, and overlap.

### Phase 4: voice intelligence

- Add explicit audio-consent, retention, and deletion flows.
- Run deterministic VAD, pause, energy, and pitch features asynchronously.
- Run shadow ASR for transcript-quality comparison.
- Calibrate user-facing voice labels against reviewed examples before presenting them
  as confidence or delivery judgments.

Implementation status on 2026-08-16: the product and privacy path is implemented.
Raw WAV capture is off by default and requires explicit per-session consent. Artifacts
are bound to an owned turn, stored outside SQLite with private permissions, analyzed
asynchronously, and deleted on withdrawal or after the configurable seven-day TTL.
The report exposes only versioned timing, pause, energy and raw-F0 facts with per-turn
replay/delete controls. Historical transcript-derived confidence is no longer computed
or returned. Shadow ASR is implemented behind `VOICE_SHADOW_ASR_ENABLED=0` and cannot
replace the realtime transcript. Reviewed-human calibration remains a release gate,
not an implementation claim.

### Phase 5: native speech experiments

- A/B a Chinese native realtime speech model against the cascaded production path.
- Keep shadow STT and the same interview-evaluation contract in both groups.
- Promote only if it improves latency and naturalness without reducing transcript,
  question-control, tool-use, or report auditability.

## 7. Phase 1 API contract

`POST /api/interview/tts?format=pcm`

Request:

```json
{"text": "请介绍一下你在这个项目中的具体贡献。", "voice": null}
```

Response:

- `Content-Type: audio/pcm;rate=22050;channels=1`
- `X-Audio-Sample-Rate: 22050`
- `X-Audio-Sample-Format: s16le`
- `Cache-Control: no-store`
- Body: raw mono signed 16-bit little-endian PCM chunks

The existing request without `format=pcm` continues to return WAV for compatibility.
PCM streaming is initially supported by the CosyVoice WebSocket backend. Unsupported
providers return a clear service error and the browser retries through the WAV path.

## 8. Phase 1 telemetry

The player exposes the latest non-persisted client measurement:

```text
request_to_headers_ms
request_to_first_byte_ms
request_to_first_audio_ms
stream_download_ms
playback_complete_ms
cancelled
fallback_used
```

These measurements are diagnostic evidence, not yet a production SLO. Phase 2 moves
them into a correlated server/client turn trace and reports p50/p95 by provider,
browser, and network profile.

## 9. Quality gates for later phases

- Final-sentence loss: 0 in 100 deterministic stop/finalization trials.
- False endpoint rate: below 2% on the reviewed Chinese interview fixture set.
- False barge-in rate: below 1% on supported noise and echo fixtures.
- End-of-answer to first interviewer audio: p95 below 1.5 seconds in the supported
  network profile.
- Every production error can be assigned to transport, endpointing, STT, interview
  orchestration, TTS, or playback from trace evidence.

These are JobRadar acceptance targets, not guarantees inherited from a framework or
provider.

## 10. Phase 2 implementation status

Status on 2026-08-16: implemented behind feature flags; real-room deployment smoke
is pending LiveKit credentials.

- `POST /api/interview/realtime/session` validates ownership and quota, stores the
  JD and user context server-side, and issues a 10-minute token scoped to one room.
- A room has at most two participants and dispatches only the named JobRadar agent.
- Reissuing the same interview supersedes its previous context. Each user is limited
  to two active realtime sessions by default.
- `livekit_agent.py` is a separate process. It wraps Paraformer streaming STT,
  CosyVoice PCM TTS, and the existing `/api/interview/turn` orchestrator contract.
- The browser uses LiveKit audio tracks, room reconnection, participant
  transcriptions, and RPC controls. A failed realtime setup falls back to the Phase 1
  WebSocket/PCM path.
- Push-to-talk is the default. Stopping the microphone invokes
  `jobradar.commit_user_turn`; pressing the control during interviewer speech invokes
  `jobradar.interrupt` before opening the microphone.
- LiveKit SDK spans can be exported over OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is
  configured. Low-volume state, turn, EOU, overlap, error, and model metrics are also
  stored in `interview_realtime_events` for direct product debugging.

## 11. Phase 3 implementation status

Status on 2026-08-16: policy and runtime implemented behind server flags; reviewed
real-speaker calibration remains pending.

- Silero VAD runs at 16 kHz with browser echo cancellation, noise suppression, and
  automatic gain control.
- Automatic end-of-turn uses LiveKit's Chinese-capable audio turn detector with local
  fallback only when `VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED=1` and the session asks
  for automatic mode.
- Preemptive generation stays disabled because `/api/interview/turn` persists domain
  state; speculative or retried calls must not create duplicate interview turns.
- Interruption requires at least 550 ms of speech and one transcript unit by default.
  A 1-second AEC warmup prevents immediate speaker echo from interrupting the agent.
- Adaptive interruption is used only when
  `VOICE_LIVEKIT_ADAPTIVE_INTERRUPTION_ENABLED=1`; otherwise interruption uses the
  portable VAD strategy. False interruptions resume after the configured timeout.
- Interruption cancellation reaches LiveKit playback, the TTS iterator, the pending
  orchestrator HTTP stream, and the generated reply task through the AgentSession
  cancellation lifecycle.
- `question_heard_text`, `question_interrupted`, and `realtime_transport` record what
  was actually delivered, separately from the complete intended question.
- Deterministic 16 kHz WAV fixtures cover silence, background noise, keyboard
  impulses, short filler, cough-like energy, and sustained overlap. Silero is run in
  tests against the nuisance fixtures; the manifest also checks the duration plus
  transcript interruption guard.

The generated fixtures are useful regression inputs, not a claim that synthetic
waveforms represent Chinese speakers. Promotion still requires reviewed recordings
from multiple speakers, microphones, rooms, and network conditions.

## 12. Realtime session API

`POST /api/interview/realtime/session`

Request:

```json
{
  "session_id": "browser-session-uuid",
  "target_job": "投行分析师",
  "jd_content": "负责行业研究、估值建模和交易材料准备",
  "turn_mode": "manual"
}
```

Required header: `X-Resume-User-Key`.

Response fields include `url`, `token`, `room_name`, `expires_at`, effective
`turn_mode`, `automatic_turns_available`, and effective `interruption_mode`. Provider
credentials, user context, and JD content are never returned in the room token.

## 13. Runtime configuration

```bash
VOICE_LIVEKIT_ENABLED=1
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
VOICE_LIVEKIT_AGENT_NAME=jobradar-interviewer
VOICE_LIVEKIT_BACKEND_URL=http://127.0.0.1:8002

# Phase 3 rollout flags: both remain off for the first production cohort.
VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED=0
VOICE_LIVEKIT_ADAPTIVE_INTERRUPTION_ENABLED=0

# Browser build-time flag.
NEXT_PUBLIC_VOICE_LIVEKIT_ENABLED=1
NEXT_PUBLIC_VOICE_LIVEKIT_TURN_MODE=manual

# Optional observability.
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_SERVICE_NAME=jobradar-voice-agent
```

Prepare and run the worker from `backend/`:

```bash
PYTHONPATH=. .venv/bin/python -m livekit.agents download-files
PYTHONPATH=. .venv/bin/python scripts/run_interview_voice_agent.py dev
```

The API process and agent process must use the same database and LiveKit credentials.
`DASHSCOPE_TTS_MODEL` must be a CosyVoice model while the adapter requires raw PCM.

## 14. Current verification

- Focused backend voice/interview suite: 34 passed.
- LiveKit worker module compilation and CLI discovery: passed.
- Alembic upgrade to `f8b1d4c6e2a9`: passed on the development database.
- Resume Copilot TypeScript check: passed.
- Resume Copilot lint: 0 errors and 3 pre-existing unrelated warnings.
- Resume Copilot production build: passed.
- Desktop and 390 px mobile browser smoke: passed without page errors or horizontal
  overflow. The feature-enabled/no-credentials path returned 503 and automatically
  reached the legacy first question without a duplicate request.
- A real LiveKit room smoke, measured WebRTC barge-in latency, reconnect test, and
  adaptive-interruption calibration remain blocked until a LiveKit deployment and
  credentials are configured.
- Phase 4 privacy/API tests cover explicit consent, ownership isolation, physical
  deletion, expiry cleanup, deterministic extraction and migration idempotence.
- `scripts/evaluate_voice_intelligence.py` is the executable acoustic gate. It passes
  seven checksum-pinned fixtures, including silence, low noise, keyboard impulses,
  short filler, cough, sustained speech and a known long pause.
- The full production go/no-go protocol, including reviewed-speaker and real-room
  targets, is in `docs/voice-agent-acceptance-2026-08-16.md`.
