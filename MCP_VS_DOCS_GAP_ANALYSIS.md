# sarvam-mcp v0.2.14 → 0.3.0 vs docs.sarvam.ai — Gap Analysis

**Date:** 2026-11-23 · **Compared:** this repo (`main`, 91287d1) against docs.sarvam.ai (llms.txt index, API reference pages, pricing, models, changelog through 2026-11-22).

**How to read:** ✅ matches docs · ⚠️ present but stale/wrong · ❌ missing from MCP · 🔎 docs are ambiguous — confirm against the live API before changing.

> Method note: docs pages were fetched and read by sub-agents; numbers below are as published on those pages. Items marked 🔎 are places where the docs contradict themselves. Nothing here was tested against the live API. The `sarvam-local` MCP server failed to connect this session (ECONNREFUSED), so I compared source code, not live behaviour.


---

## ✅ Implementation status (updated after the fix pass)

Corrections to the analysis below: (a) STT **already surfaced** `language_probability` — not a gap; (b) there is **no `/v2/embeddings` in the public OpenAPI spec** (only the changelog mentions `embeddinggemma-2`), so it was not implemented; (c) issues #79, #64, #42 and #21 were already fixed on `main`.

**Done:** pricing + rate-limit tables (§3, §4) · Chat V2 routing + all 10 models · `n` capped at 1 · Responses API · `/v2/models` · Dictate (clip, job submit, job status) · Instant Voice Cloning (create, speak, list, get, delete, watermark) · pronunciation update · TTS `output_audio_codec` + `temperature` · transliterate `spoken_form_numerals_language` fix · Prism `clef` · doc-translate `language_specific_guidelines` + tri-state numerals · dubbing `editor_flow` · `od-IN`→`or-IN` for doc translate/dubbing · 402 quota error · README · issues #59/#73/#20/#16, #80, #74, #70, #86, #125, #83, #48.

**Not done (needs a decision or live testing):** Dictate live WebSocket · voice-clone streaming/WebSocket · Chat/Responses streaming · embeddings · Doc AI `capabilities`/`upload_ids`/`config_id` · TTS default changes (`enable_preprocessing`, sample rate) · realtime STT default model · dubbing `mp3` export value · `language_code` vs `target_language_code` on TTS · batch-STT webhook callback · refreshing `sarvam_code_recommend_model` / snippets for the new APIs.


---

## 🔁 Round 2 — compared against `sarvamai/sarvam-fern-config` (docs source repo, PRs + OpenAPI specs)

Source of truth used: `openapi.json`, `openapi-v2.json`, `fern/asyncapi.yml`, `pricing.mdx`, the Document AI how-to pages and the PRs below (cloned at `c817b5b`, PR #799). Pricing and limits tables in this file were re-checked against `pricing.mdx` on `main` and match.

| Docs PR | State | MCP mismatch found | Action |
|---|---|---|---|
| #759 Split & Classify contract | merged | Classify sent `scope`; Split sent `method`, `pages_per_segment`, `segment_ranges`, `split_on` (all removed from the API) | Rewrote both tools to the new contract |
| #799 / #724 Document AI page limits | merged | Parse said 30 pages, Extract said 20 | Parse 20, Extract 500, Classify 20, Split 500 |
| #741 / #794 Extract `mode` | open / merged | `mode` (basic/advanced) not exposed | Added `mode` |
| #792 TTS overhaul | merged | REST field is `language_code` (MCP sent `target_language_code`); defaults 22050 Hz and preprocessing off | Fixed field + defaults, builder snippets, validator |
| #793 Saaras v4 | merged | Realtime default was `saaras:v3-realtime` (now legacy); `input_audio_codec` enum was 3 of 24 values | Default `saaras:v4`; full enum |
| #781 Sarvam-105B defaults | merged | MCP always sent `temperature=0.7`, `top_p=1.0`; conversations model is reasoning-off only | Omit unless set; `reasoning_effort="none"` sends null on v1; conversations rejects a level |
| #709 / #734 status codes | merged / open | 402 not mapped | `SarvamQuotaError` (done in round 1) |
| #752 / #747 EmbeddingGemma 2 | open / merged | `/v2/embeddings` not exposed | Added `sarvam_tools_embed` |
| Dubbing spec | — | `export_options` documented as video, audio, audio_vocals, srt, vtt; MCP offered `mp3` | Added `audio_vocals`, `vtt`; kept `mp3` as undocumented legacy |
| /transliterate spec | — | Only 11 languages; MCP accepted 23+ | Pre-check |
| #784 pricing rate limits | **open** | New per-plan limits + Business column not yet published | Noted in `RATE_LIMITS_DISCLAIMER`; not applied |
| #771 word-level timestamps | **open**, feature off in prod | — | Not applied (still chunk-level) |
| #761 / #565 STT `prompt` Preview / removal | open | MCP has no `prompt` param | Nothing to do |
| #714, #660, #661 doc-translation MCP guide / global languages / IDML | open | Not shipped yet | Not applied |

**The docs MCP page (`developer-tools/mcp.mdx`, PR #724) lists 36 tools; this server now registers 53.** It needs these rows added: `sarvam_tools_llm_complete` models, `sarvam_tools_responses_create`, `sarvam_tools_list_models`, `sarvam_tools_embed`, `sarvam_tools_dictate_*`, `sarvam_tools_cloned_voice_*`, `sarvam_tools_pronunciation_update`, `sarvam_code_rate_limits`. The page also still says Split/Classify limits "10 documents, 20 categories, 1,000 segments" — the API now allows up to 200 categories.


---

## 🔁 Round 3 — Chat Completion V2 + Provisioned Throughput

Sources: `fern/api-reference-docs/chat-completion/overview.mdx` ("V2 models", "V2 feature support", "V2 behaviour notes"), `models/open-source/overview.mdx` ("Provisioned Throughput"), `fern/overrides-v2.yml` (the effective V2 spec text), `openapi-v2.json`.

- **Provisioned Throughput = contact Sarvam support.** `deepseekv4-pro`, `kimi-k3.1-pro`, `qwen38-27b` (chat/Responses), `clef` (Decisions) and `embeddinggemma-2` (embeddings) are set up per workload and enabled per organisation. Without access `deepseekv4-pro` returns 400 ("…not enabled for your organisation", still listed in `GET /v2/models`); the rest return 404 and are not listed.
- `sarvam-105b-conversations` **is** served on V2 and Responses (reasoning level accepted but ignored). An earlier note in this file that called it V1-only was wrong.
- V2 was reachable only as a side effect of `sarvam_tools_llm_complete` routing; it now has its own tool, `sarvam_tools_chat_v2_complete`.

---

## 0. Top priorities (do these first)

| # | Priority | Item | Why |
|---|---|---|---|
| 1 | 🔴 | **Pricing table has no rupee numbers** and `RATE_LIMITS` is a generic 60/300/5000 | Docs now publish per-plan prices and per-API limits (§3, §4). `sarvam_code_pricing` is the one tool whose answer people will quote. |
| 2 | 🔴 | **Chat V2 (`/v2/chat/completions`) not implemented**; `_data.py` says it needs beta whitelisting | Changelog 2026-10-20/10-22: Chat V2 and Responses are GA. 10 chat models are listed, MCP exposes 2. |
| 3 | 🔴 | **Dictate API missing** (clip, jobs, live WebSocket) | New product, ₹0.50/min. |
| 4 | 🔴 | **Instant Voice Cloning missing** (create/list/get/delete voice, clone, stream, WS, watermark detect) | Beta product with 7+ endpoints. |
| 5 | 🟠 | **TTS defaults differ from the API**: `enable_preprocessing` True (API false), sample rate 24000 (API 22050); missing `output_audio_codec`, `temperature` | Silent behaviour differences. |
| 6 | 🟠 | **Transliterate `spoken_form_numerals_language`** typed as a language code; docs allow only `english` / `native` | Likely a bug: valid inputs rejected. |
| 7 | 🟠 | `n` is exposed on `sarvam_tools_llm_complete`; since 2026-11-07 `n > 1` returns 400 | Remove or cap at 1. |
| 8 | 🟠 | README says "LLM (30B / 105B)" and lists Text Analytics | Sarvam-30B and Sarvam-M are deprecated; `/text-analytics` is retired. |
| 9 | 🟡 | Bulbul V3 EOL on Voice Agents: **Nov 25, 2026** (two days away) | Doc the date; V3 stays on the TTS API. |
| 10 | 🟡 | Introductory pricing on `sarvam-105b`, `sarvam-105b-conversations`, `deepseekv4.1-flash-1017` ends "through the end of 2026" | Pricing answers will change in ~5 weeks. |

---

## 1. API / endpoint coverage

| Docs area | Endpoint(s) | MCP tool | Status |
|---|---|---|---|
| STT REST | `POST /speech-to-text` | `stt_transcribe` | ✅ |
| STT Batch | `/speech-to-text/job/v1…` | `stt_batch_submit/status/download` | ✅ |
| STT Realtime WS | `/speech-to-text/ws` | `stt_realtime` | ⚠️ default model `saaras:v3-realtime`; docs recommend `saaras:v4` |
| TTS REST | `POST /text-to-speech` | `tts_speak` | ⚠️ see §5 |
| TTS HTTP stream / WS | `/text-to-speech/stream`, `/ws` | `tts_stream` | ⚠️ HTTP stream limit 3,500 chars, WS 2,500/message — check handled |
| Pronunciation dict | create/list/get/**update**/delete | list/get/create/delete | ⚠️ **Update missing** |
| **Dictate** | `POST /v2/dictate`, `/v2/dictate/jobs` (create/get/delete), WS | — | ❌ |
| **Instant Voice Cloning** | `/voices/create`, `/voices/clone`, `/clone/stream`, `/clone/ws`, list/get/delete voice, `/voices/watermark/detect` | — | ❌ |
| Translate | `POST /translate` | `translate` | ✅ (minor, §5) |
| Transliterate | `POST /transliterate` | `transliterate` | ⚠️ §5 |
| Language ID | `POST /text-lid` | `identify_language` | ✅ |
| Chat V1 (legacy) | `/v1/chat/completions` | `llm_complete` | ⚠️ only legacy endpoint |
| **Chat V2** | `POST /v2/chat/completions` | — | ❌ |
| **Responses API** | `POST /v2/responses` (+ stream) | — | ❌ |
| **Embeddings** | `POST /v2/embeddings` (`embeddinggemma-2`, provisioned) | — | ❌ |
| Decisions (Prism) | `POST /v2/systemone` | `prism_decide` | ⚠️ `sarvam-prism` hard-coded; docs also accept `clef` (provisioned, images, 65,536 tokens) |
| Models list | `GET` List/Get Models V2 | — | ❌ (would let the MCP self-discover models) |
| Document AI | parse / extract / classify / split / status | `vision_*` | ⚠️ see §6 |
| Doc AI capabilities | `GET /doc-ai/v1/capabilities` | — | ❌ (returns live limits — would fix the stale-limits problem) |
| Doc AI upload URL | `POST /doc-ai/v1/job/upload` (`upload_ids`) | — | ❌ |
| Doc translation | create/start/live-status/export/export-status | `document_translate(_status)` | ⚠️ §6 |
| Dubbing | create/start/live-status/export-status | `dubbing_submit/status` | ⚠️ §7 |
| Text analytics | retired | stub that raises | ⚠️ remove from README; consider dropping the stub |
| Legacy STT-translate, legacy doc-intelligence | marked "Legacy" in docs | — | ✅ intentionally skipped |
| Voice Agents API (deployments, campaigns, analytics, boards, tests, BYOK, webhooks) | many | — | ❌ but see note |

**Voice Agents note:** docs ship a *separate hosted* MCP for Voice Agents (`https://mcp.sarvam.ai/voice-agents`, OAuth, 120 calls/min). It is not a gap in this server by design, but the README / AGENTS.md should point to it so users don't look for those tools here.

---

## 2. Models

### 2.1 Sarvam-built models

| Model | Docs status | In MCP? |
|---|---|---|
| `saaras:v4` | Recommended | ✅ default for REST + batch; ⚠️ realtime default is `saaras:v3-realtime` |
| `saaras:v3` | Legacy | ✅ |
| `saaras:v2.5` | Deprecated | ✅ not offered |
| `bulbul:v4-flash` | Latest, recommended | ✅ (default stays v3) |
| `bulbul:v3` | Active; API default | ✅ |
| Sarvam Instant Voice Cloning | Active (Beta) | ❌ |
| `mayura:v1`, `sarvam-translate:v1` | Active | ✅ |
| Sarvam Vision | Active | ✅ |
| `sarvam-105b`, `sarvam-105b-conversations` | Serverless (intro pricing) | ✅ (v1 only). 2026-11-22: now on Sarvam-105B-1711 weights, no API change |
| `sarvam-prism` | Serverless | ✅ |
| Sarvam-M, Sarvam-30B | **Deprecated** → migrate to Sarvam-105B | ⚠️ README still says "30B" |

### 2.2 Token Factory (open-weight) models — none are reachable from the MCP

| Model ID | Tier | Added/changed |
|---|---|---|
| `glm5.3` | Serverless | GA 2026-10-22 |
| `glm5.3-flash` | Serverless | GA 2026-10-20 |
| `gemma4` (Gemma 4 31B) | Serverless | GA 2026-10-22 |
| `deepseekv4.1-flash-1017` | Serverless (intro pricing) | GA 2026-10-30; price cut 2026-11-07 |
| `deepseekv4.1-flash-1017-interactive` | Serverless | New 2026-11-07, >200 tok/s |
| `deepseekv4-pro` | Provisioned Throughput | 2026-10-20 |
| `kimi-k3.1-pro` | Provisioned Throughput | 2026-11-06 (replaces `kimi-k3`) |
| `qwen38-27b` | Provisioned Throughput | 2026-11-06 |
| `clef` | Provisioned Throughput (decision model) | 2026-11-06 |
| `embeddinggemma-2` | Provisioned Throughput | 2026-11-06 |
| `kimi-k3`, `mimo-v2.6-flash`, `mimo-v2.6-pro` | **No longer offered** | 2026-11-06 |

Provisioned models return 400 (`deepseekv4-pro`) or 404 (the rest) when the org lacks access — the MCP should translate that into a clear "ask Sarvam for access" message.

---

## 3. Pricing (₹, excl. GST) — what `sarvam_code_pricing` should say

Current `PRICING` in `code/_data.py` carries units only, "last reviewed 2026-04-27", says no v4-flash rate is published, and says new users get "Rs. 1000" free credit. **Docs now say ₹100 per verified user on signup; credits never expire.**

### 3.1 Plans
| Plan | Monthly fee | Support |
|---|---|---|
| Pay as you go | — | Community |
| Pro | ₹9,999 | Email |
| Growth | ₹49,999 | Email |
| Business | ₹1,99,999 (includes equal credits; best public rates) | Priority |
| Enterprise | Custom | Dedicated |

Exhausted credits return **402 `insufficient_quota_error`** (separate from 429). `http/errors.py` has no 402 mapping — it will surface as a generic error. Add a `SarvamQuotaError`.

### 3.2 Per-unit prices
| Service | Unit | PAYG | Pro | Growth | Business |
|---|---|---|---|---|---|
| STT (REST, streaming, batch) | /min | 0.49 | 0.45 | 0.41 | — |
| STT + diarization (batch) | /min | 0.59 | 0.54 | 0.50 | — |
| Bulbul v4 Flash | /1k chars | 2.00 | 1.85 | 1.70 | — |
| Bulbul v3 | /1k chars | 3.00 | 2.85 | 2.70 | — |
| Instant Voice Cloning | /1k chars | 2.00 | 2.00 | 2.00 | — |
| Dictate | /min (silence billed) | 0.50 | 0.475 | 0.45 | 0.40 |
| Translate | /1k chars | 2.00 | 1.70 | 1.50 | — |
| Transliterate | /1k chars | 2.00 | 2.00 | 1.80 | — |
| Language ID | /1k chars | 0.35 | 0.35 | 0.31 | — |
| Doc digitization (parse) | /page | 0.50 | 0.50 | 0.50 | — |
| Doc extraction `basic` / `advanced` | /page | 1.00 / 2.50 | same | same | — |
| Doc translation | /1k billable chars /target lang | 5.00 | 5.00 | 4.50 | — |
| Dubbing (`editor_flow:false`) | /min × targets | 40 | 40 | 38 | — |
| Dubbing (`editor_flow:true`) | /min × targets | 80 | 80 | 75 | — |

### 3.3 LLM / Token Factory (₹ per 1M tokens, same on all plans)
| Model | Input | Cached | Output |
|---|---|---|---|
| `sarvam-105b` / `-conversations` | 10 | 0.25 | 25 |
| `sarvam-prism` | 4 | — | 0 |
| `glm5.3` | 126 | 20 | 390 |
| `glm5.3-flash` | 13.5 | 2.5 | 45 |
| `gemma4` | 35 | 10 | 90 |
| `deepseekv4.1-flash-1017` | 14 | 0.25 | 55 |
| `deepseekv4.1-flash-1017-interactive` | 25 | 0.5 | 105 |
| `deepseekv4-pro` | 115 | 4 | 350 |
| `kimi-k3.1-pro` | 200 | 20 | 950 |
| `qwen38-27b` | 18 | 5 | 230 |
| `clef` | 20 | — | input only |
| `embeddinggemma-2` | 2 | — | input only |

Reasoning tokens bill as output. The 2026-11-07 deepseek price cut was ₹25/0.5/105 → ₹14/0.25/55.

**Suggestion:** store these as structured data (`unit`, `by_plan`, `valid_until`) and have `sarvam_code_pricing` return a `plan` argument. Keep the dashboard disclaimer.

---

## 4. Rate limits — replace the generic `RATE_LIMITS`

| API / mode | PAYG | Pro | Growth |
|---|---|---|---|
| STT REST | 60/min | 100/min | 4,000/min |
| STT WebSocket | 20 concurrent | 100 | 100 |
| STT Batch | 20/min | 100/min | 500/min |
| TTS REST + HTTP stream | 60/min | 200/min | 1,000/min |
| TTS WebSocket | 60 concurrent | 200 | 1,000 |
| Dictate clip | 60/min | 100/min | 4,000/min |
| Dictate jobs | 20/min | 100/min | 500/min |
| Dictate live WS | 20 concurrent | 100 | 100 (3 h max session, 60 s idle) |
| Voice cloning (sustained / burst) | 60/min / 100 | 200 / 300 | 1,000 / 1,200 |
| Voice-cloning watermark detect | 5/min (no credits) | | |
| Translate / Transliterate / LID | 60/min | 200/min | 1,000/min |
| Default LLMs (`gemma4`, `glm5.3`, `deepseekv4.1-flash-1017`) | 50/min | 200/min | 1,000/min |
| `sarvam-105b`, `-conversations` | 60/min | 200/min | 300/min |
| Dubbing | 5/min | 50/min | 300/min |
| Doc AI Parse (≤20 pages/req) | 200/min | 300 | 400 |
| Doc AI Extract (≤500 pages) | 30/min | 50 | 60 |
| Doc AI Split (≤500) | 60/min | 120 | 180 |
| Doc AI Classify (≤20) | 100/min | 150 | 200 |
| Doc translation job endpoints (≤500) | 200/min | 500 | 1,000 |

Business has no published limits (Enterprise arrangement). Errors: 429 `rate_limit_exceeded_error`, 503 under load.
🔎 pricing.md says limits are per *account* (shared across keys); the Token Factory page says per *API key*.

Current MCP: `RATE_LIMITS` = 60 / 300 / 5000 req/min. The 300 for `/translate` contradicts the published 60 / 200 / 1,000.

---

## 5. Parameter-level diffs on tools that already exist

### TTS (`sarvam_tools_tts_speak`, `tts_stream`)
| Parameter | Docs | MCP | Action |
|---|---|---|---|
| `enable_preprocessing` | default **false** | default **true** | ⚠️ align or document the deliberate difference |
| `speech_sample_rate` | default 22050; REST: 8000/16000/22050/24000/32000/44100/48000; streaming: ≤24000 | default 24000 | ⚠️ document; check streaming rejects >24000 |
| `output_audio_codec` | mp3, linear16, mulaw, alaw, opus, flac, aac, wav (opus invalid at 22050) | WAV only | ❌ add |
| `temperature` | 0.01–1.0, default 0.6 | not exposed (`_data.py` says ignored on v4-flash) | ❌ / 🔎 |
| `enable_cached_responses` | beta | — | ❌ optional |
| `language_code` | request field is `language_code` | MCP sends `target_language_code` | 🔎 verify against live API (the repo says it live-tested 2026-10-06; docs page differs) |
| `dict_id` | `p_` + 8 hex | ✅ | — |
| text length | REST 2,500; HTTP stream 3,500; WS 2,500/msg | 2,500 stated | ⚠️ stream limit |
| Bulbul v3 speakers | 37 | check `_data.py` roster against the 37 names (docs intro says "30+") | 🔎 |
| Bulbul v4-flash personas | 222 (hi 116, en 62, enhi 13, mr 9, kn/pa/ta/te 4, gu/bn 3) | 222 ✅ | — |

### STT
| Item | Docs | MCP |
|---|---|---|
| Realtime default model | `saaras:v4` | `saaras:v3-realtime` ⚠️ |
| REST audio limit | 30 s; batch 2 h/file, 20 files/job | ✅ in docs text; confirm enforced |
| `keyterms` | v4 only, ≤50 × ≤64 chars | ✅ |
| Batch webhook `callback` (`url`, `auth_token`, 30 s ack) | documented | check `stt_batch_submit` supports it |
| `language_probability` in REST response | returned | not surfaced ❌ |
| Live `config.update` to change keyterms mid-session | documented | not supported ❌ |

### LLM (`sarvam_tools_llm_complete`, v1 endpoint)
| Item | Docs (V2) | MCP |
|---|---|---|
| Models | 10 | 2 |
| `reasoning_effort` | none/low/medium/high/max (model-dependent) | low/medium/high |
| Defaults | temperature 1, top_p 0.95, max_tokens 2048 | 0.7, 1.0, unset |
| `n` | **only 1** (400 otherwise, since 2026-11-07) | exposed, ≥1 ⚠️ |
| Missing params | `top_k`, `repetition_penalty`, `parallel_tool_calls`, `stream_options`, `logprobs`/`top_logprobs`, `developer` role, `x-session-affinity` header, image input (inline `data:` URIs only) | ❌ |
| Request body limit | 10,485,760 bytes | — |
| New errors | 402, 413, 502 `model_call_failed`, 503 `model_overloaded` | 402 unmapped |
| `reasoning_effort` per model | `kimi-k3.1-pro` rejects `none`; `glm5.3` default max | 🔎 Chat V2 page and Responses page disagree on whether literal `"max"` is accepted on `glm5.3` |
| `_data.py` note "`reasoning_effort` default medium" | | stale for V2 |

### Translate / Transliterate
| Item | Docs | MCP |
|---|---|---|
| `spoken_form_numerals_language` | `english` \| `native` | typed as `LanguageCode` ⚠️ **bug** |
| Translate `mode` for `sarvam-translate:v1` | formal only | ✅ ignored |
| Language set for `mayura` vs `sarvam-translate` | Mayura 11; sarvam-translate 22 + `auto` is mayura-only | MCP accepts all codes for both; add a pre-check to give a helpful error |
| Transliterate language set | 11 only (no as/ur/etc.), `auto` source ok | MCP enum accepts 23+; add a pre-check |
| Input limits | translate 1,000 / 2,000; LID 1,000 | ✅ translate; add LID check |
| LID response | adds `script_code` | check surfaced |

### Prism / Decisions
- Add `model` argument (`sarvam-prism` | `clef`); `clef` takes base64 images, 65,536-token limit, 1–255 options.
- Docs: 60 s timeout → 503; temperature/stream rejected with 422.

---

## 6. Document AI + Document Translation

| Item | Docs | MCP |
|---|---|---|
| Parse pages/request | 20 | tool text says **30 pages per PDF**, 30 images per ZIP, 200 MB ⚠️ (MCP doc says 20 for extract; docs table says extract = 500, parse = 20) |
| Extract pages/request | 500 | tool text says **20 pages** ⚠️ |
| Classify | 20 pages/request in the rate-limit table; MCP docs page says 500, 10 docs, 20 categories | 🔎 docs conflict between the limits table (classify 20) and the MCP page (classify/split 500); call `/doc-ai/v1/capabilities` to settle |
| Formats | PDF, PNG, JPEG, ZIP (parse/extract); + TIFF (split/classify) | check TIFF accepted |
| Extract `mode` basic/advanced (₹1 vs ₹2.50/page) | ✅ documented | not exposed? — confirm |
| Extract `config_id` (saved config) / `classification` | documented | ❌ |
| `upload_ids` flow | documented | ❌ |
| Terminal job states | completed, partially_completed, failed, rejected | check `partially_completed` handled |
| Doc translate: `language_specific_guidelines` (per target) | ✅ | ❌ |
| Doc translate: `use_native_numerals` | tri-state (null/false/true), default null | bool default False ⚠️ (forces 0-9) |
| Doc translate: Odia code | `or-IN` in this endpoint | `od-IN` used elsewhere — MCP takes free strings; document the difference 🔎 |
| Doc translate: supported ext | pdf, doc(x), odt, xls(x), ods, ppt(x), odp, html, xhtml, mhtml, md, markdown, txt | check `_guess_doc_mime` covers all |
| Doc translate: "up to 12 target languages" | not stated on the API page | 🔎 MCP enforces 1–12 based on the MCP docs page |

---

## 7. Dubbing

| Item | Docs | MCP |
|---|---|---|
| `export_options` | `video`, `audio`, `srt` (description also mentions `audio_vocals`, `vtt`) | `video, audio, mp3, srt` — **`mp3` is not in the docs** ⚠️ 🔎 |
| `src_lang` | `auto` + 23 Indic + 16 foreign (ar-SA, zh-CN, nl-NL, fr-FR, de-DE, id-ID, it-IT, ja-JP, ko-KR, pl-PL, pt-BR, ru-RU, es-ES, tr-TR, vi-VN) | free string ✅ — mention in tool description |
| `editor_flow` | true = ₹80/min base | hard-coded false; consider exposing |
| `pace_preset`, `register`, `num_speakers`, `voice_id`, `disable_watermark` | ✅ | ✅ |
| `model_tier` in response (plus/lite/auto) | documented | not surfaced |
| Rate limit | 5 / 50 / 300 per min | — |

---

## 8. Voice Cloning — suggested new tools (all ❌ today)
| Tool | Endpoint | Key facts |
|---|---|---|
| `voice_clone_create` | `POST /voices/create` | file ≤50 MB (wav/mp3/flac/opus/aac/mulaw/alaw/linear16), 10–15 s single speaker; `name` 1–100; `language`; `style`, `gender`; `remove_background_noise` default true; 50 voices/org on Starter (403 `TIER_LIMIT_REACHED`); 422 on bad audio |
| `voice_clone_speak` | `POST /voices/clone` (+ `/stream`, WS) | `language_code` optional since 2026-10-26; noise removal default **false** here |
| `voice_list/get/delete` | `/voices`, `/voices/{id}` | `noise_reduction_applied` returned |
| `voice_watermark_detect` | `POST /voices/watermark/detect` | file ≤10 MB, 120 s analysed, verdict `watermarked`/`not_detected`/`inconclusive`, 5/min, free |

## 9. Dictate — suggested new tools (all ❌ today)
| Tool | Endpoint | Key facts |
|---|---|---|
| `dictate_clip` | `POST /v2/dictate` (multipart) | ≤30 s, ≤10,000,000 bytes; `language_code`, `mode`, `style` (preset, rules), `vocabulary[]` (word, sounds_like, description), `context`, `output_rules`, `model` (pin, e.g. `dictate-v1-2026-11-04`); each non-file part ≤1 MiB; empty-string parts → 400; response includes `corrections`, `degraded`, `usage` |
| `dictate_job_*` | `POST /v2/dictate/jobs`, get, delete | up to 1 hour; poll ≥5 s |
| live | WebSocket | 3 h session, 60 s idle timeout |

Billing: per minute incl. silence; failed or degraded calls are not billed.

---

## 10. Changelog items to reflect (newest first)

| Date | Area | Change | MCP impact |
|---|---|---|---|
| 2026-11-22 | Model APIs | `sarvam-105b*` now Sarvam-105B-1711 weights | none |
| 2026-11-18 | Voice Agents | Connect exports to SFTP / S3 | out of scope |
| 2026-11-16 | Voice Agents | Signed public recording URLs; stored webhook configs (HMAC-SHA256) | out of scope |
| 2026-11-11 | Voice Agents | Experiments (beta); **Bulbul V3 EOL on Voice Agents → Nov 25** | 🔎 two docs entries conflict (Nov 10 vs 25) |
| 2026-11-09 | Model APIs | Voice-cloning watermark detection | ❌ §8 |
| 2026-11-07 | Model APIs | deepseek price cut; `-interactive` variant; **`n>1` → 400** | ⚠️ §5, §3 |
| 2026-11-06 | Model APIs | `remove_background_noise`; Serverless vs Provisioned labels; kimi-k3.1-pro, qwen38-27b, clef, embeddinggemma-2; kimi-k3 & mimo removed | ❌ §2 |
| 2026-10-30 | Model APIs | deepseekv4.1-flash GA, 1,048,576 ctx | ❌ |
| 2026-10-26 | Model APIs | voice-clone `language_code` optional | ❌ |
| 2026-10-22 | Model APIs | GLM-5.3, Gemma 4, DeepSeek V4.1 Flash, Responses API GA | ❌ |
| 2026-10-20 | Model APIs | Chat V2 + Responses GA; glm5.3-flash etc. added | ❌ |
| 2026-10-15 | Content Studio | Starter saved-voice limit 5 → 50 | doc only |
| 2026-10-31 | Voice Agents | MCP integrations in agent editor | out of scope |

(Individual changelog entries before 2026-10-28 other than those listed were only seen as index lines; Sep–Oct 2026 entries were not opened.)

---

## 11. MCP-side improvements (beyond doc parity)

1. **Staleness guard.** `_data.py` header says "Last verified 2026-10-06", pricing "2026-04-27". Add a test that fails when these dates are >30 days old, and/or fetch `https://docs.sarvam.ai/openapi.json` in CI and diff model enums, `n`, `reasoning_effort`, etc. Docs publish `openapi.json` and `asyncapi.json`; both are machine-readable.
2. **Use `/doc-ai/v1/capabilities` and `List Models V2` at runtime** to report live limits/models instead of hard-coded text.
3. **Map 402** → `SarvamQuotaError` with a "top up credits at the dashboard" hint; map provisioned-model 400/404 → "ask Sarvam for access".
4. **Retry policy:** `RETRYABLE_STATUS` = 500/502/503/504 ✅; docs recommend exponential backoff on 429 + 503 — confirm 429 uses `Retry-After`.
5. **`sarvam_code_recommend_model`** (documented in the official MCP page) must learn the new LLMs, Dictate, and voice cloning.
6. **`sarvam_code_snippet`** — add snippets for Chat V2, Responses, Dictate, voice cloning; the Python SDK minimum versions cited in docs (`sarvamai>=0.1.45` Py / `>=1.1.18` TS for noise removal; keyterms `>=0.1.33a1`).
7. **README / AGENTS.md:** fix "LLM (30B / 105B)", "Text Analytics", "Exposes every public Sarvam API" (no longer true), free-credit figure, and add a pointer to the hosted Voice Agents MCP.
8. **Dashboard link:** docs now use `indus.sarvam.ai/key-management`; MCP and AGENTS.md use `dashboard.sarvam.ai`. 🔎 confirm which is canonical.
9. **Docs-reported env vars** (`SARVAM_API_BASE_URL`, `SARVAM_MCP_BASE_PATH`, `SARVAM_AUDIO_OUTPUT_MODE`) — verify they match `config.py`.
10. **Docs MCP page lists 35 tools + 1 stub**; the official page should be updated when new tools ship.

## 12. Doc-side inconsistencies worth reporting to the docs team
- Bulbul intro says "30+" v3 speakers; speaker list and API reference say 37.
- Bulbul V3 Voice Agents EOL: Nov 10 vs Nov 25 across changelog entries.
- `glm5.3` `reasoning_effort="max"`: accepted per Chat V2 page, 400 per Responses page.
- Rate limits: per account (pricing page) vs per API key (Token Factory page).
- Dubbing `export_options`: enum lists 3 values, description mentions 5.
- Decision API reference omits `images`; only the Prism page documents it.
- Classify page limits: 20 (limits table) vs 500 (MCP page).
- Several enums not listed on the reference pages: Dictate `language_code`/`mode`, STT `input_audio_codec`, voice-cloning `style`/`gender`, Parse `content_type`, Extract `output_format`.

## 13. Not checked
- Live API behaviour (server wouldn't connect; no tests run).
- Voice Agents API details, Cowork, Content Studio indexes, individual changelog entries before 2026-10-28, per-model pages other than Prism/Mayura/Sarvam-Translate, Sarvam-M/30B deprecation pages, SageMaker self-hosted docs.
- Whether `stt_batch_submit` exposes the webhook callback, whether `vision_extract` exposes `mode`, and whether TIFF is accepted — I read the signatures only partly.
