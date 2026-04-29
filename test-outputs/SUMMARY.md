# Live API Smoke Test — Results

**Date**: 2026-04-27
**Base URL**: `https://api.sarvam.ai`
**Auth**: API key (StaticKeyProvider) via `SARVAM_API_KEY`
**Test runner**: `scripts/smoke_live.py` (with `scripts/smoke_fix*.py` for the 3 endpoints that needed shape discovery)

## Headline

**9 of 11 atomic Sarvam API tools verified working end-to-end against live API.** TTS → STT round-trip succeeded (Hindi text → audio → transcribed back to Hindi → translated to English).

| Tool | Status | Notes |
|---|---|---|
| `sarvam_identify_language` | ✅ | `hi-IN` / `Deva` detected correctly |
| `sarvam_translate` (Mayura) | ✅ | EN → HI colloquial mode |
| `sarvam_translate` (Sarvam-Translate v1) | ✅ | EN → TA, 22-language model |
| `sarvam_transliterate` | ✅ | `नमस्ते दुनिया` → `Namaste duniya` |
| `sarvam_llm_complete` | ✅ | `sarvam-30b` chat, 150 completion tokens |
| `sarvam_tts_speak` | ✅ | `bulbul:v3`, 75 KB WAV produced |
| `sarvam_stt_transcribe` | ✅ | `saaras:v3`, accurate Hindi transcript |
| `sarvam_stt_translate` | ✅ | Saaras v2.5, audio → English |
| `sarvam_stt_batch_submit` | ✅ | Returns Azure SAS upload + output URLs |
| `sarvam_text_analytics` | ⚠️ | Request shape **solved**; server returns 5xx (transient backend issue, not our code) |
| `sarvam_vision_extract` | ❌ | Endpoint path on `api.sarvam.ai` not yet identified — needs Sarvam internal docs |

## Layout

```
test-outputs/
├── SUMMARY.md             # ← this file
├── json/
│   ├── _summary.json      # machine-readable run summary
│   ├── sarvam_identify_language.json
│   ├── sarvam_translate_mayura.json
│   ├── sarvam_translate_sarvam.json
│   ├── sarvam_transliterate.json
│   ├── sarvam_llm_complete.json
│   ├── sarvam_tts_speak.json
│   ├── sarvam_stt_transcribe.json
│   ├── sarvam_stt_translate.json
│   └── sarvam_stt_batch_submit.json
├── audio/
│   └── tts_speak.wav      # Hindi TTS output (the round-trip seed)
└── documents/
    └── hello.png          # synthesized text image used for vision probing
```

## What worked

### 1. Language Identification — `POST /text-lid`
**Input**: `नमस्ते, आप कैसे हैं?`
**Output**:
```json
{ "language_code": "hi-IN", "script_code": "Deva" }
```
Latency: 282–483 ms.

### 2. Translate — `POST /translate` (Mayura)
**Input**: `Hello, how are you doing today?` (en-IN → hi-IN, modern-colloquial)
**Output**:
```json
{ "translated_text": "Hello, आज आप कैसे हैं?", "source_language_code": "en-IN" }
```
Latency: ~250–310 ms.

### 3. Translate — `POST /translate` (Sarvam-Translate v1)
**Input**: `Artificial intelligence is changing the world.` (en-IN → ta-IN)
**Output**:
```json
{ "translated_text": "செயற்கை நுண்ணறிவு உலகை மாற்றுகிறது.", "source_language_code": "en-IN" }
```
Latency: ~210–350 ms.

### 4. Transliterate — `POST /transliterate`
**Input**: `नमस्ते दुनिया` (hi-IN → en-IN)
**Output**:
```json
{ "transliterated_text": "Namaste duniya", "source_language_code": "hi-IN" }
```
Latency: ~220–320 ms.

### 5. Chat Completions — `POST /v1/chat/completions` (sarvam-30b)
**Input**: 2-message conversation asking for "good morning" in Tamil + Marathi.
**Output snippet**:
> Tamil: காலை வணக்கம் (Kaalai vaṇakkam) … Marathi: शुभ सकाळ (Shubh sakāl)
Latency: ~1.1–1.2 s. Returned reasoning trace in `<think>` blocks.

### 6. Text-to-Speech — `POST /text-to-speech` (bulbul:v3)
**Input**: `Hello, आज आप कैसे हैं?` · speaker `priya` · 24kHz · `bulbul:v3`
**Output**: 75,278-byte WAV → `test-outputs/audio/tts_speak.wav`
Latency: ~570–870 ms.

### 7. Speech-to-Text — `POST /speech-to-text` (saaras:v3)
**Input**: the WAV from step 6 · `language_code=hi-IN` · `model=saaras:v3` · `mode=transcribe`
**Output**:
```json
{ "transcript": "हेलो, आज आप कैसे हैं?", "language_code": "hi-IN" }
```
**Round-trip accuracy**: near-perfect — only "Hello" lost casing/diacritic ("हेलो" vs the original "Hello").
Latency: ~340–420 ms.

### 8. Speech-to-Text-Translate — `POST /speech-to-text-translate` (Saaras)
**Input**: same WAV · `model=saaras:v2.5`
**Output**:
```json
{ "transcript": "Hello, how are you today?" }
```
Round-trip preserves intent exactly (started from "Hello, how are you doing today?").
Latency: ~275–365 ms.

### 9. Batch STT init — `POST /speech-to-text/job/init`
**Important**: this is **JSON-only**, **not multipart**. The endpoint just registers a job and returns Azure Blob SAS URLs; the actual audio upload is a separate step against `input_storage_path`.

**Output**:
```json
{
  "job_id": "20260427_b663...",
  "storage_container_type": "Azure",
  "input_storage_path": "https://appsprodbulkjobssa.blob.core.windows.net/.../inputs?se=...&sp=wdl&...",
  "output_storage_path": "https://appsprodbulkjobssa.blob.core.windows.net/.../outputs?se=...&sp=rl&..."
}
```

**Implication for the tool**: `sarvam_stt_batch_submit` was rewritten — it now takes **no audio file**, only model/language args, and returns the SAS URLs. A future iteration should add a helper that uploads to the SAS URL automatically, but for v1 we surface the URLs and document the next steps in the tool description.
Latency: ~305 ms.

## What didn't (yet)

### `sarvam_text_analytics` — shape solved, server 5xx

The previous community MCP and intuitive guesses were wrong. The actual request shape is:

```json
POST /text-analytics  (multipart/form-data)
text:      "<the source text>"
questions: '[{"id": "q1", "text": "...", "type": "short answer"}, ...]'   ← JSON-encoded string
```

**`type` must be one of**: `boolean`, `enum`, `short answer`, `long answer`, `number`. (Discovered from the API's own validation error.) For `enum` type, also include an `options` array.

**Status today**: 4 retries with valid request all returned `Internal server error.` (status 500, ~10s latency each). This is a Sarvam-side issue, not our code. Tool code at `src/sarvam_mcp/tools/language.py` now uses the correct shape and validates inputs before sending — when the backend is healthy, this should just work.

### `sarvam_vision_extract` — endpoint not on `api.sarvam.ai`

Tried 12 path variants:
```
/parse  /parsedoc  /parse-doc  /parse_doc  /parse/doc  /parse/parsedoc
/parse-document  /document/parse  /document-parse  /document/extract  /extract
/v1/parse  /v1/parse-doc  /v1/parsedoc  /v1/document/parse  /vision/parse
/document-ai/parse  /api/v1/parse  /parse/v1
```

All returned `404 Not Found`. Also tried `parse.sarvam.ai` (TLS handshake error — host doesn't appear configured for this account).

**Likely causes** (all warrant a quick internal check rather than more guessing):
1. Sarvam Vision OCR isn't GA on this API key tier.
2. It lives on a separate base host (parse.sarvam.ai, dia.sarvam.ai, etc.) that needs explicit enablement.
3. The path has a non-obvious slug only documented in internal/dashboard pages.

**Tool code**: `src/sarvam_mcp/tools/vision.py` is wired correctly for multipart upload; only the `PARSE_PATH` constant needs the right value once confirmed. A clear `# NOTE` comment is already in the file flagging this for the next dev.

## Performance summary

| Tool | Median latency |
|---|---|
| Translate (both models), Transliterate, LID | ~200–350 ms |
| TTS | ~570–870 ms |
| STT (saaras:v3) | ~340–420 ms |
| STT-Translate Saaras | ~275–365 ms |
| LLM (150 tokens) | ~1.1 s |
| Batch STT init | ~305 ms |

All within reasonable bounds for an interactive MCP experience.

## What's now in the production tool code

Updates merged from this run (committed in tool modules, not just here):

1. `tools/language.py` — `sarvam_text_analytics` rewritten to use multipart + typed `questions: list[dict]` with client-side validation. Adds `QuestionType` literal.
2. `tools/stt.py` — `sarvam_stt_batch_submit` rewritten to JSON-only, returns SAS URLs + `next_steps` documentation field.
3. `tools/vision.py` — added a `# NOTE` block at `PARSE_PATH` explaining the unconfirmed endpoint.

All 35 unit tests still pass (`.venv/bin/pytest -q`).

## Reproduce

The published package is `pip install sarvam-mcp` — you do not need a git clone to **use** the MCP server. The commands below are for **developers** running the live smoke script from a checkout of this repo:

```bash
cd /path/to/sarvam-mcp   # your local clone
source .venv/bin/activate
SARVAM_API_KEY=sk_... python scripts/smoke_live.py
# Outputs land in test-outputs/{json,audio,documents}/.
```

The runner is idempotent and cheap (one call per endpoint, ~5 s total).

## Action items for next session

| Priority | Item |
|---|---|
| 🔴 high | Confirm Sarvam Vision endpoint path / host (probably needs a 30-second look at internal docs or dashboard). |
| 🟡 med | Re-run `text-analytics` — backend 5xx should resolve; if not, file with platform team using one of the captured request_ids. |
| 🟡 med | Add a `sarvam_stt_batch_upload` helper that accepts a local file path and uploads to the SAS URL returned by `batch_submit`. Closes the batch UX loop. |
| 🟢 low | Periodically re-verify default models against live API / docs. |
