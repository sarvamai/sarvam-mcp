"""Hard-coded reference data for the ``sarvam_code_*`` docs tools.

These tables are the authoritative source for what an agent needs to know
when *generating* Sarvam-using code. They mirror what's encoded as enums
in ``tools/_common.py`` (single source of truth for our runtime tools)
and what's documented at docs.sarvam.ai.

Update cadence: bump these any time Sarvam adds a model/speaker/language
or changes pricing. CI will surface a diff in PR review.

Last verified live against api.sarvam.ai: 2026-10-06.
Docs-synced (not live-tested): 2026-11-23 — pricing, rate limits, Chat V2, Responses, Dictate, voice cloning.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Languages per API. STT covers all 22 scheduled Indian languages + English;
# TTS covers a smaller set. Translate matches based on model.
# ---------------------------------------------------------------------------

ALL_LANGUAGES: list[dict[str, str]] = [
    {"code": "en-IN", "name": "English (India)", "script": "Latin"},
    {"code": "hi-IN", "name": "Hindi", "script": "Devanagari"},
    {"code": "bn-IN", "name": "Bengali", "script": "Bengali"},
    {"code": "ta-IN", "name": "Tamil", "script": "Tamil"},
    {"code": "te-IN", "name": "Telugu", "script": "Telugu"},
    {"code": "gu-IN", "name": "Gujarati", "script": "Gujarati"},
    {"code": "kn-IN", "name": "Kannada", "script": "Kannada"},
    {"code": "ml-IN", "name": "Malayalam", "script": "Malayalam"},
    {"code": "mr-IN", "name": "Marathi", "script": "Devanagari"},
    {"code": "pa-IN", "name": "Punjabi", "script": "Gurmukhi"},
    {"code": "od-IN", "name": "Odia", "script": "Odia"},
    {"code": "as-IN", "name": "Assamese", "script": "Bengali"},
    {"code": "ur-IN", "name": "Urdu", "script": "Perso-Arabic"},
    {"code": "ne-IN", "name": "Nepali", "script": "Devanagari"},
    {"code": "kok-IN", "name": "Konkani", "script": "Devanagari"},
    {"code": "ks-IN", "name": "Kashmiri", "script": "Perso-Arabic"},
    {"code": "sd-IN", "name": "Sindhi", "script": "Perso-Arabic"},
    {"code": "sa-IN", "name": "Sanskrit", "script": "Devanagari"},
    {"code": "sat-IN", "name": "Santali", "script": "Ol Chiki"},
    {"code": "mni-IN", "name": "Manipuri", "script": "Meitei"},
    {"code": "brx-IN", "name": "Bodo", "script": "Devanagari"},
    {"code": "mai-IN", "name": "Maithili", "script": "Devanagari"},
    {"code": "doi-IN", "name": "Dogri", "script": "Devanagari"},
]

_TTS_CODES = {
    "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
    "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN",
}

# LID only supports 11 languages per the /text-lid OpenAPI spec.
_LID_CODES = {
    "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
    "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN",
}

# Per-API language coverage. Keys match what the agent might pass.
LANGUAGES_BY_API: dict[str, list[dict[str, str]]] = {
    "stt":           ALL_LANGUAGES,
    "tts":           [lang for lang in ALL_LANGUAGES if lang["code"] in _TTS_CODES],
    "translate":     ALL_LANGUAGES,    # sarvam-translate:v1 covers all; mayura:v1 only TTS subset.
    "transliterate": ALL_LANGUAGES,
    "lid":           [lang for lang in ALL_LANGUAGES if lang["code"] in _LID_CODES],
    "llm":           ALL_LANGUAGES,
    "vision":        ALL_LANGUAGES,
}


# ---------------------------------------------------------------------------
# TTS speakers per model. Speaker IDs are model-specific: the API rejects a
# v3 name on v4-flash (and vice versa) with a 400 that lists the valid set.
# ---------------------------------------------------------------------------

V3_SPEAKERS = [
    "aditya", "ritu", "ashutosh", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun",
    "manan", "sumit", "roopa", "kabir", "aayan", "shubh", "advait", "anand",
    "tanya", "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani",
    "mohit", "kavitha", "rehan", "soham", "rupali",
]

# bulbul:v4-flash persona IDs, `<voice>_<lang>_<style>` (222 IDs, matching
# docs.sarvam.ai; re-verified against the live API on 2026-10-06 after Sarvam
# renamed bappa_bn_conversation -> arnab_bn_conversation and vetri_ta_* ->
# aravind_ta_*). The live API also lists 2 Assamese (`as`) personas; they
# are intentionally left out — Assamese voices require contacting Sarvam.
V4_FLASH_SPEAKERS = [
    "aayan_hi_conversational", "amit_hi_conversational",
    "ashutosh_hi_conversational", "kabir_hi_conversational",
    "kavya_hi_conversational", "manan_hi_conversational",
    "rahul_hi_conversational", "sumit_hi_conversational",
    "arnab_bn_conversation", "roopa_bn_conversational", "aditi_en_stories",
    "aparna_en_companion", "aparna_en_edtech", "ashwin_en_sports",
    "ashwin_en_sports_energetic", "chandrika_en_stories", "dev_en_recovery",
    "dev_en_conversational", "deven_en_conversation", "ishita_en_customer",
    "ishita_en_medical", "ishita_en_numbers", "ishita_en_social",
    "ishita_en_stories", "kalpit_en_edtech", "nachiket_en_ads",
    "neha_en_customer", "neha_en_latenight", "nupur_en_kids", "ojas_en_social",
    "ritu_en_edtech", "ritu_en_latenight", "ritu_en_medical", "ritu_en_reels",
    "rohan_en_recovery", "roopa_en_conversational", "rustom_en_suspense",
    "sanchita_en_companion", "sanchita_en_insurance", "sanchita_en_recovery",
    "sanchita_en_market", "sanchita_en_social", "shabana_en_edtech",
    "shalini_en_companion", "shalini_en_customer", "shubh_en_narration",
    "shubh_en_numbers", "shubh_en_ads", "shubh_en_recovery",
    "shubh_en_audiobook", "shubh_en_narration_gentle", "shubh_en_sports",
    "simran_en_narration", "simran_en_automobile", "simran_en_conversation",
    "simran_en_customer", "simran_en_edtech", "simran_en_edtech_bot",
    "simran_en_sales", "simran_en_recovery", "simran_en_ads",
    "simran_en_therapist", "sunny_en_social", "varun_en_ads",
    "varun_en_suspense", "zarina_en_conversation", "ishita_enhi_companion",
    "ishita_enhi_customer", "ishita_enhi_customer_expressive",
    "sanchita_enhi_companion", "shalini_enhi_companion",
    "shalini_enhi_customer", "shubh_enhi_companion", "shubh_enhi_ads",
    "shubh_enhi_banking", "simran_enhi_companion", "simran_enhi_customer",
    "simran_enhi_banking_expressive", "sunny_enhi_customer",
    "bhavik_gu_conversation", "pooja_gu_conversational", "pooja_gu_customer",
    "aditya_hi_conversational", "aditya_hi_sales", "anand_hi_documentary",
    "anand_hi_news", "aparna_hi_customer", "aparna_hi_kyc",
    "ashok_hi_character", "ashok_hi_news", "chhavi_hi_kids", "ishita_hi_ads",
    "ishita_hi_edtech", "ishita_hi_banking", "ishita_hi_ads_informal",
    "ishita_hi_devotional", "ishita_hi_numbers", "ishita_hi_social",
    "kunal_hi_kids", "mahesh_hi_documentary", "mani_hi_devotional",
    "mani_hi_conversational", "mohit_hi_conversational",
    "nachiket_hi_devotional", "priya_hi_recovery", "ratan_hi_latenight",
    "ratan_hi_customer_expressive", "ratan_hi_documentary",
    "ratan_hi_devotional", "ratan_hi_recovery", "ratan_hi_social",
    "ratan_hi_sports", "ratan_hi_latenight_warm", "rehan_hi_social",
    "ritu_hi_customer_utility", "ritu_hi_kids", "ritu_hi_conversation",
    "ritu_hi_customer", "ritu_hi_edtech", "ritu_hi_ads_formal",
    "ritu_hi_banking", "ritu_hi_ads_informal", "ritu_hi_insurance",
    "ritu_hi_edtech_bot", "ritu_hi_medical", "ritu_hi_sales", "ritu_hi_reels",
    "ritu_hi_social", "ritu_hi_customer_warm", "ritu_hi_social_lively",
    "roopa_hi_companion", "roopa_hi_narration", "roopa_hi_recovery",
    "roopa_hi_market", "roopa_hi_conversational", "sanchita_hi_assistant",
    "sanchita_hi_edtech", "sanchita_hi_banking", "sanchita_hi_feedback",
    "sanchita_hi_ads_formal", "sanchita_hi_ads_informal",
    "sanchita_hi_interview", "sanchita_hi_romantic", "sanchita_hi_market",
    "sanchita_hi_social", "sanchita_hi_kyc", "sarika_hi_conversation",
    "shalini_hi_companion", "shalini_hi_social", "shreya_hi_conversational",
    "shreya_hi_news", "shruti_hi_edtech", "shubh_hi_customer", "shubh_hi_ecomm",
    "shubh_hi_stories_mixed", "shubh_hi_devotional", "shubh_hi_ads",
    "shubh_hi_recovery", "shubh_hi_stories_dramatic", "simran_hi_assistant",
    "simran_hi_narration", "simran_hi_automobile", "simran_hi_conversation",
    "simran_hi_news_breaking", "simran_hi_social_energetic",
    "simran_hi_social_excited", "simran_hi_latenight", "simran_hi_news",
    "simran_hi_recovery", "simran_hi_sales", "suchitra_hi_ecomm",
    "suhani_hi_social", "sunny_hi_ads", "sunny_hi_reels",
    "tarun_hi_conversational", "tarun_hi_sales", "chaitra_hi_customer",
    "shilpa_hi_narration", "tanya_hi_narration", "chaitra_kn_conversation",
    "chaitra_kn_narration", "chetan_kn_conversation", "suchitra_kn_narration",
    "ishita_mr_conversational", "mrunal_mr_narration", "neha_mr_narration",
    "nilesh_mr_conversation", "ritu_mr_insurance", "ritu_mr_narration",
    "rupali_mr_stories", "soham_mr_narration", "anand_pa_conversation",
    "anand_pa_customer", "harpreet_pa_narration", "jaspal_pa_banking",
    "gokul_ta_narration", "aravind_ta_ads", "aravind_ta_suspense",
    "vijay_ta_narration", "kavitha_te_conversation", "kavitha_te_narration",
    "pooja_te_conversation", "tarun_te_narration", "amelia_en_conversational",
    "sophia_en_conversational", "bimal_bn_suspense", "girish_en_documentary",
    "girish_en_devotional", "payal_en_edtech", "sarang_en_narration",
    "aarti_hi_customer", "advait_hi_character", "aryaman_hi_ads",
    "chirag_hi_social", "girish_hi_devotional", "mukul_hi_ads",
    "mukul_hi_suspense", "suman_hi_companion", "vaibhav_hi_social",
    "vandana_hi_ecomm", "vipul_hi_social", "mukul_mr_stories",
]

SPEAKERS_BY_MODEL: dict[str, list[str]] = {
    "bulbul:v3": V3_SPEAKERS,
    "bulbul:v4-flash": V4_FLASH_SPEAKERS,
}

# Curated tone hints for the most-used voices, so agents can pick sensibly.
SPEAKER_HINTS: dict[str, str] = {
    "shubh":    "bulbul:v3 default voice (per docs.sarvam.ai)",
    "priya":    "warm friendly female, good for product / IVR",
    "neha":     "warm female, conversational",
    "pooja":    "warm female, friendly",
    "shreya":   "calm female, news-anchor / narration",
    "kavya":    "calm female, professional",
    "ritu":     "calm female, professional",
    "aditya":   "professional male, news-anchor",
    "rahul":    "professional male, conversational",
    "kabir":    "professional male, warm",
    "vijay":    "mature male, authoritative",
    "gokul":    "mature male, narration",
    "anand":    "mature male, professional",
    "tanya":    "young energetic female",
    "suhani":   "young energetic female",
    # bulbul:v4-flash personas — the style suffix is the tone.
    "shubh_enhi_ads":     "bulbul:v4-flash default; English-Hindi code-mixed, ad-read style",
    "simran_en_customer": "English (en-IN) customer-care female",
    "simran_en_sales":    "English (en-IN) sales female",
    "aparna_hi_customer": "Hindi customer-care female",
    "shubh_hi_customer":  "Hindi customer-care male",
    "ritu_hi_customer":   "Hindi customer-care female",
    "aparna_en_edtech":   "English (en-IN) edtech female",
    "sunny_en_social":    "English (en-IN) social-media male",
}


# ---------------------------------------------------------------------------
# Endpoint reference. Mirrors what the runtime tools use; this is the
# authoritative shape for code-gen tools to consult.
# ---------------------------------------------------------------------------

API_REFERENCE: dict[str, dict[str, Any]] = {
    "/text-to-speech": {
        "method": "POST",
        "model": "bulbul:v3 (default) | bulbul:v4-flash (low-latency, persona speakers)",
        "content_type": "application/json",
        "auth_header": "api-subscription-key",
        "request_body": {
            "text":                 "str, required — text to synthesize, max 2500 characters",
            "inputs":               "list[str] (legacy alternative to `text`) — each item max 500 characters; prefer `text`",
            "language_code":        "str, required — one of the 11 TTS codes (documented field name; the older `target_language_code` spelling appears in existing code)",
            "speaker":              "str, required — must be compatible with chosen model",
            "model":                "str — 'bulbul:v3' (default) | 'bulbul:v4-flash'",
            "speech_sample_rate":   "int, default 22050 — REST: 8000|16000|22050|24000|32000|44100|48000; streaming: 8000|16000|22050|24000 only",
            "output_audio_codec":   "str (optional) — wav (default) | mp3 | aac | flac | linear16 | mulaw | alaw | opus (opus needs 8000/16000/24000/48000 Hz; 22050 -> 400). HTTP stream default is mp3",
            "temperature":          "float 0.01-1.0, default 0.6 — randomness/expressiveness",
            "enable_cached_responses": "bool (beta, default false) — behaviour not guaranteed",
            "pace":                 "float, 0.5 to 2.0 (default 1)",
            "pitch":                "float (optional), -0.5 to 0.5",
            "loudness":             "float (optional), 0.1 to 2.5",
            "enable_preprocessing": "bool, default false — normalize English words and numeric entities (accepted on both models)",
            "dict_id":              "str (optional) — pronunciation dictionary ID to apply",
        },
        "response": {
            "audios":     "list[str] — base64-encoded WAV per input",
            "request_id": "str",
        },
        "notes": (
            "Pick a speaker compatible with your model — see sarvam_code_speakers. "
            "bulbul:v3 uses short names ('shubh', 'priya'); bulbul:v4-flash uses "
            "persona IDs ('simran_en_customer', default 'shubh_enhi_ads') and "
            "rejects v3 names. Both models accept `pitch`, `loudness` and `pace` "
            "(live-confirmed 2026-10-06; the earlier 'v3 rejects pitch/loudness' "
            "behavior is gone) and out-of-range values return 400. "
            "`temperature` (0.01-1.0, default 0.6) is documented for both models (an earlier live check "
            "found it ignored on v4-flash — verify). Max input length: "
            "2500 characters via `text` (REST), 3500 per HTTP-stream request, 2500 per WebSocket message "
            "(the legacy `inputs` array caps each item at "
            "500 — live-confirmed 2026-10-06). v4-flash: no SSML, native-script text recommended "
            "(romanised Indic degrades quality); also served by HTTP streaming "
            "(POST /text-to-speech/stream) and the WebSocket below."
        ),
    },
    "/speech-to-text": {
        "method": "POST",
        "model": "saaras:v4 (recommended, latest)",
        "content_type": "multipart/form-data",
        "auth_header": "api-subscription-key",
        "request_body": {
            "file":              "binary, required — audio (wav, mp3, ogg, flac, m4a, webm, aac, opus, amr, wma)",
            "model":             "str — saaras:v4 (latest) | saaras:v3",
            "mode":              "str — transcribe (default) | translate | verbatim | translit | codemix (saaras:v3/v4 only)",
            "language_code":     "str — BCP-47 or 'unknown' for auto-detect",
            "with_timestamps":   "bool",
            "keyterms":          "JSON list, saaras:v4 only, up to 50 terms of 64 chars",
            "input_audio_codec": "str (optional) — pcm_s16le | pcm_l16 | pcm_raw (required for PCM files, 16kHz only)",
        },
        "response": {
            "transcript":           "str",
            "language_code":        "str — detected if input was 'unknown'",
            "language_probability": "float — confidence of detected language",
            "diarized_transcript":  "list[turn] | null",
            "timestamps":           "list[word_ts] | null",
        },
        "notes": (
            "Saaras v4 is the latest, recommended model (22 Indic languages + Global/Indian English). "
            "It supports 5 output modes via the `mode` parameter, same as v3. "
            "`keyterms` (v4 only): up to 50 domain terms, JSON-encoded array form field, "
            "64 chars max each. Speech-to-English is mode=translate on this endpoint. "
            "For >30s audio, use /speech-to-text/job/v1. "
            "Live audio uses GET /speech-to-text-realtime/ws."
        ),
    },
    "/speech-to-text/job/v1": {
        "method": "POST",
        "model": "saaras:v4 (recommended, latest)",
        "content_type": "application/json",
        "request_body": {
            "job_parameters": (
                "object, required — {model, mode, language_code, with_timestamps, "
                "with_diarization, num_speakers, input_audio_codec, keyterms}"
            ),
            "callback": "object (optional) — {url, auth_token} webhook, notified on completion",
        },
        "response": {
            "job_id":    "str",
            "job_state": "str — e.g. 'Accepted'",
        },
        "notes": (
            "Steps 1, 2, 5 below live-confirmed 2026-09-28 against Sarvam's own "
            "reference pages (initiate/upload/status/download). Step 4 (/start) is "
            "carried over from this repo's own prior working implementation — "
            "Sarvam's public docs describe it only via their SDK's job.start() "
            "abstraction, without publishing the raw REST path, so it wasn't "
            "independently re-confirmed against docs text on 2026-09-28. "
            "Full async pipeline, 5 calls: "
            "1) POST /speech-to-text/job/v1 with {\"job_parameters\": {...}} -> job_id. "
            "2) POST /speech-to-text/job/v1/upload-files with {job_id, files: [name, ...]} "
            "-> presigned upload URL(s). "
            "3) PUT the raw audio bytes to that presigned URL. "
            "4) POST /speech-to-text/job/v1/{job_id}/start with {job_id, job_parameters}. "
            "5) Poll GET /speech-to-text/job/v1/{job_id}/status until job_state is terminal "
            "('Completed'/'PartiallyCompleted'/'Failed'), or fetch fresh presigned output "
            "URLs any time via POST /speech-to-text/job/v1/download-files with "
            "{job_id, files: [filename, ...]} — files must be exact output filenames "
            "(e.g. '0.json'), not just the job_id. "
            "Up to 20 files per job, audio up to 2 hours; PCM must be 16kHz "
            "(set job_parameters.input_audio_codec)."
        ),
    },
    "/speech-to-text-realtime/ws": {
        "method": "GET",
        "model": "saaras:v4 (default, recommended), saaras:v3-realtime (legacy)",
        "content_type": "websocket",
        "request_body": {
            "query":       "language_code (or auto), model, mode, encoding, sample_rate, stream_type",
            "audio_input": "base64 linear16 PCM",
            "flush":       "finalize buffered audio",
            "end":         "close the session",
        },
        "response": {
            "transcript.partial": "interim text",
            "transcript.final":   "final text for the utterance",
        },
        "notes": "Mono 16-bit WAV only, 8000 or 16000 Hz. keyterms require saaras:v4.",
    },
    "/translate": {
        "method": "POST",
        "model": "mayura:v1 (11 langs, modes), sarvam-translate:v1 (22 langs)",
        "content_type": "application/json",
        "request_body": {
            "input":                "str, required",
            "source_language_code": "str — BCP-47 or 'auto' for auto-detect",
            "target_language_code": "str — BCP-47",
            "model":                "str",
            "mode":                 "str — formal | modern-colloquial | classic-colloquial | code-mixed (Mayura only)",
            "output_script":        "str — roman | fully-native | spoken-form-in-native (Mayura only)",
            "numerals_format":      "str — international | native",
            "speaker_gender":       "str — Male | Female (gendered languages)",
        },
        "response": {
            "translated_text":      "str",
            "source_language_code": "str",
            "request_id":           "str",
        },
        "notes": (
            "max input length: 1000 chars for mayura:v1, 2000 chars for "
            "sarvam-translate:v1 (live-confirmed 2026-08-14). "
            "`enable_preprocessing` was removed from this endpoint's schema "
            "and is no longer a valid parameter — don't send it."
        ),
    },
    "/transliterate": {
        "method": "POST",
        "content_type": "application/json",
        "request_body": {
            "input":                         "str",
            "source_language_code":          "str",
            "target_language_code":          "str",
            "numerals_format":               "str",
            "spoken_form":                   "bool",
            "spoken_form_numerals_language": "str (optional)",
        },
        "response": {
            "transliterated_text":  "str",
            "source_language_code": "str",
        },
    },
    "/text-lid": {
        "method": "POST",
        "content_type": "application/json",
        "request_body": {"input": "str (max 1000 characters)"},
        "response": {
            "language_code": "str — one of 11 supported codes (en-IN, hi-IN, bn-IN, gu-IN, kn-IN, ml-IN, mr-IN, od-IN, pa-IN, ta-IN, te-IN)",
            "script_code": "str — Latn, Deva, Beng, Gujr, Knda, Mlym, Orya, Guru, Taml, Telu",
        },
        "notes": "Only supports 11 languages (not all 23). Max input 1000 characters.",
    },
    "/text-analytics": {
        "method": "POST",
        "content_type": "multipart/form-data",
        "request_body": {
            "text":      "str (form field)",
            "questions": 'JSON-stringified list of {id, text, type} where type is "boolean" | "enum" | "short answer" | "long answer" | "number". For "enum", also include "options".',
        },
        "response": {"answers": "list[answer]"},
        "notes": (
            "PERMANENTLY REMOVED (404 since 2026-08-13, confirmed deliberate via "
            "Sarvam's own SDK notes, not an outage) — this shape is kept only for "
            "historical reference. sarvam_tools_text_analytics raises immediately "
            "rather than calling this. Check 'SarvamParse' (new lightweight beta "
            "endpoint) on docs.sarvam.ai for a possible replacement."
        ),
    },
    "/v1/chat/completions": {
        "method": "POST",
        "model": "sarvam-105b (flagship, 128K ctx) | sarvam-105b-conversations (32K ctx, voice/chat-tuned)",
        "content_type": "application/json",
        "request_body": {
            "model":             "str — 'sarvam-105b' | 'sarvam-105b-conversations'",
            "messages":          "list[{role, content}]",
            "temperature":       "float, 0.0 to 2.0 — omit to use the model default: sarvam-105b 1.0 (reasoning on) / 0.6 (reasoning off); sarvam-105b-conversations 0.6",
            "top_p":             "float >0 to 1.0, default 1.0",
            "max_tokens":        "int (optional), API default 2048",
            "reasoning_effort":  "str (optional) — 'low' | 'medium' (default) | 'high'; explicit null turns reasoning OFF. sarvam-105b-conversations runs with reasoning off only — do not set a level",
            "stream":            "bool",
            "stop":              "list[str] (optional) — up to 4 sequences",
            "frequency_penalty": "float (optional), -2.0 to 2.0",
            "presence_penalty":  "float (optional), -2.0 to 2.0",
            "seed":              "int (optional) — beta, best-effort determinism",
            "n":                 "int (optional) — number of completions",
            "tools":             "list[object] (optional) — OpenAI-style function-calling defs",
            "tool_choice":       "str | object (optional)",
            "response_format":   "object (optional) — {'type': 'json_object'} or json_schema",
        },
        "response_oai_compatible": True,
        "notes": (
            "OpenAI-compatible. Two models live on this v1 endpoint: sarvam-105b (default, "
            "complex reasoning/coding/agentic tool use) and "
            "sarvam-105b-conversations (post-trained for real-time dialogue and "
            "voice agents — same price, smaller 32K context). "
            "GOTCHA (live-confirmed 2026-08-14): sarvam-105b reasons by "
            "default even without reasoning_effort set, and reasoning tokens "
            "count against max_tokens. A small max_tokens (e.g. 20-100) can "
            "come back with finish_reason='length' and EMPTY content — the "
            "whole budget was consumed by hidden reasoning. Give it real "
            "headroom (300+) or omit max_tokens; reasoning_effort='low' "
            "reduces but does not eliminate this. "
            "For the open-weight models (glm5.3, glm5.3-flash, gemma4, deepseekv4.1-flash-1017[-interactive], "
            "deepseekv4-pro, kimi-k3.1-pro, qwen38-27b) use /v2/chat/completions, which is GA since "
            "2026-10-20 — sarvam_tools_llm_complete routes to it automatically. n>1 returns 400 on both "
            "endpoints since 2026-11-07. Sarvam-M and Sarvam-30B are deprecated; use sarvam-105b."
        ),
    },
    "/v2/systemone": {
        "method": "POST",
        "model": "sarvam-prism | clef",
        "content_type": "application/json",
        "request_body": {
            "model":     "str, required — 'sarvam-prism' (serverless) or 'clef' (Provisioned Throughput; also reads base64 images, up to 65,536 tokens/request, 1-255 options, 1-10 levels). Case-sensitive",
            "state":     "str | object | array, required — the input; objects/arrays are sent as compact JSON. Never truncated",
            "questions": "object, required (>=1) — your question id -> {type, instructions, criteria}. No other keys",
            "questions.*.type":         "str — noul (yes/no) | choice (pick one) | score (ordered scale), lowercase",
            "questions.*.instructions": "str | object | array — the question text",
            "questions.*.criteria":     "noul: optional {true, false}; choice: required {option_id: description}, 2-255 options; score: required list of 2-10 level descriptions, lowest first",
        },
        "response": {
            "model": "str — sarvam-prism",
            "answers": "object — one entry per question id, each with its `type`",
            "answers.noul": "noul: float 0-1, probability of yes",
            "answers.choice": "choice: top option id, plus confidence and probabilities keyed by your option ids",
            "answers.score": "score: expected level (0-based float), plus confidence, legend and probabilities keyed '0', '1', ...",
            "usage": "{input_tokens, output_tokens} — output_tokens is always 0",
        },
        "notes": (
            "Decision model (System-1) built on Sarvam 105B: scores options, generates no text. "
            "Synchronous, no streaming; 60 s timeout (503 model_overloaded beyond that — split big batches). "
            "Auth: api-subscription-key or Authorization: Bearer. "
            "Not accepted (422): temperature, max_tokens, stream, images; an image URL is a 400. "
            "Limit: 32,768 tokens per question (state + question + options), checked per question — "
            "one oversized question fails the whole request. No cap on the number of questions. "
            "For score questions option order defines the scale; for choice it does not. "
            "Ask every question about one state in a single call: the state is billed once. "
            "Probabilities can vary slightly between identical requests; the top answer is stable, "
            "so leave a margin around thresholds. Calibration refers to the top probability "
            "(noul, or probabilities[choice]), not the rescaled `confidence`. Indian-language "
            "answers clear a 0.9 threshold far less often than English (~38% vs ~69%). "
            "Languages: English, 10 Indian languages, Hinglish. SDKs: Python sarvamai>=0.1.43, "
            "JavaScript sarvamai>=1.1.15. Retry 429/502/503 with backoff; other 4xx are not retryable."
        ),
    },
    "/doc-ai/v1/job/parse": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":          "binary — or upload_ids (comma-separated ids from POST /doc-ai/v1/job/upload); exactly one",
            "language":      "str — BCP-47, e.g. en-IN, hi-IN. Default `indic` (Indic OCR); send en-IN for English. Not language_code.",
            "output_format": "str — html (default) | md | json. Not 'markdown' (400).",
            "content_type":  "str — printed (default) | handwritten | mixed",
            "model":         "str — sarvam-vision-v1 (default; other values 400 MODEL_INVALID)",
        },
        "response": {
            "job_id": "str",
            "status": "str — pending, running, then completed | partially_completed | failed | rejected",
        },
        "notes": (
            "Full-document parse (OCR). Poll GET /doc-ai/v1/job/{job_id}/status (the `pipeline` field "
            "uses the API's internal name for Parse, not 'parse'). Then GET /doc-ai/v1/job/{job_id}/results for JSON text blocks per page "
            "(text, layout_tag, reading_order, coordinates; works for every output_format), or "
            "GET /doc-ai/v1/job/{job_id}/download-url for a ZIP with the output file and manifest. "
            "Limits: 20 pages per request, 100 MiB per file. Formats: PDF, PNG, JPEG, TIFF, DOCX, or a flat "
            "ZIP of JPG/PNG pages. GET /doc-ai/v1/capabilities returns the live limits."
        ),
    },
    "/doc-ai/v1/job/extract": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":          "binary — or upload_ids; exactly one. Several files in one request are read as ONE document (one merged result)",
            "schema":        "JSON string — root type object with non-empty properties; every field needs a type, a description is recommended; optional enum; max depth 4",
            "config_id":     "str — saved config (UUID) instead of schema; exactly one of schema / config_id (400 otherwise)",
            "language":      "str — BCP-47. Default `indic` (Indic OCR); send en-IN for English",
            "output_format": "str — json (default) | csv | xlsx",
            "mode":          "str — basic (default) | advanced (second whole-document pass; slower, ₹2.50 vs ₹1.00 per page)",
            "model":         "str — sarvam-vision-v1 (default)",
        },
        "response": {"job_id": "str", "status": "str — pending, running, then a terminal state"},
        "notes": (
            "Schema extraction. Poll status, then GET /doc-ai/v1/job/{job_id}/results: `result` (field "
            "values) and `annotations` (per field: confidence and sources with page and bbox). /results "
            "is JSON for every output_format; for the CSV/XLSX file call GET /doc-ai/v1/job/{job_id}/download-url. "
            "Do not send `classification`: it returns 400 CLASSIFICATION_NOT_SUPPORTED — use /classify. "
            "Limits: 500 pages per request, 100 MiB per file. Formats: PDF, PNG, JPEG, TIFF, DOCX, or a flat ZIP of JPG/PNG pages."
        ),
    },
    "/doc-ai/v1/job/classify": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":        "binary (or upload_ids). PDF, PNG, JPEG, TIFF or DOCX; repeat for up to 10 documents",
            "request":     "JSON part (application/json). Must contain `config` ({} for defaults); request={} returns 400",
            "request.config.categories": "list of {type (required, <=200 chars), description (optional, <=2,000 chars)}, up to 20. Omit to let the API read types from instructions or suggest one",
            "request.config.instructions": "str, up to 8,000 chars",
            "request.config.page_ranges": "str '1-3,5' or list of {start,end}. Mutually exclusive with request.max_pages (422 PAGE_SELECTION_CONFLICT)",
            "request.config.unmatched_behavior": "str — suggest_type (default) | other",
            "request.config.review_policy.min_class_confidence": "0-1, default 0.9",
            "request.max_pages":          "int >= 1 — read the first N pages. Default: first 2 pages and the last",
            "request.language":           "str — BCP-47, e.g. en-IN",
            "request.context":            "str, up to 4,000 chars",
            "request.output.include_evidence": "bool, default false",
        },
        "response": {"job_id": "str", "status": "str — accepted", "status_url": "str", "results_url": "str"},
        "notes": (
            "ONE decision per document — there is no `scope` (use Split with categories for a result "
            "per document). Poll GET /doc-ai/v1/job/{job_id}/status (accepted, running, then completed | "
            "partially_completed | failed | cancelled), then GET /doc-ai/v1/job/{job_id}/results (add "
            "?include=details for evidence). Check review_required; confidence can be null. A bundle of "
            "several documents returns classification_status 'mixed' — split it first. "
            "Limits: 20 pages per request, 20 categories, 512 MiB per file (send files over ~100 MiB "
            "with upload_ids; 422 INPUT_TOO_LARGE above 512 MiB). Add an Idempotency-Key header to retry "
            "a submission safely."
        ),
    },
    "/doc-ai/v1/job/split": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":    "binary (or upload_ids). PDF, PNG, JPEG, TIFF or DOCX (no ZIP); repeat for up to 10 documents",
            "request": "JSON part (application/json). Must contain `config` ({} for defaults)",
            "request.config.classify_segments": "bool, default true. Send categories when true, omit them when false",
            "request.config.categories":        "list of {type (required), description, identifier_key (fills each document's identifier)}, up to 20",
            "request.config.instructions":      "str, up to 8,000 chars",
            "request.config.page_ranges":       "str '1-3,5' or list of {start,end}. Default: every page",
            "request.config.constraints.must_split_before":  "list of pages (2 or later) that always start a new document; page 1 returns 400",
            "request.config.review_policy.min_segment_confidence / min_class_confidence": "0-1, default 0.9",
            "request.context / language": "as classify",
        },
        "response": {"job_id": "str", "status": "str — accepted", "status_url": "str", "results_url": "str"},
        "notes": (
            "The model always finds the boundaries — there is NO `method`, `pages_per_segment`, "
            "`segment_ranges`, `split_on` or `remainder` (sending them is rejected). "
            "`constraints.must_keep_together` returns 422 UNSUPPORTED_CAPABILITY unless "
            "GET /doc-ai/v1/capabilities lists it as enabled. Splits a bundle into child documents, each with "
            "original page numbers and a document_ref. Poll status, then GET /doc-ai/v1/job/{job_id}/results. "
            "'completed' does not mean every segment passed review — check each segment's review_required. "
            "Limits: 500 pages per request, 20 categories, 512 MiB per file (over ~100 MiB use upload_ids)."
        ),
    },
    "/doc-ai/v1/job/upload": {
        "method": "POST",
        "content_type": "application/json",
        "request_body": {
            "content_type": "str, optional — e.g. application/pdf",
        },
        "response": {
            "upload_id": "str",
            "method": "str — usually PUT",
            "url": "str — presigned URL",
            "headers": "dict, optional — send with the upload",
            "expires_at": "str — about an hour after creation",
        },
        "notes": (
            "Upload a file first, then pass `upload_ids` instead of `file` on Parse, Extract, Split or "
            "Classify (comma-separated for several). Needed for Split/Classify files over ~100 MiB (up to "
            "512 MiB). Each upload_id works once (reuse: 404 UPLOAD_NOT_FOUND); using it before the PUT "
            "finishes returns 400 UPLOAD_NOT_COMPLETED. Up to 300 uploaded files can wait unused "
            "(429 UPLOAD_LIMIT_EXCEEDED, Retry-After)."
        ),
    },
    "/translate/document/jobs": {
        "method": "POST",
        "content_type": "application/json",
        "request_body": {
            "source_language_code":  "str, required",
            "target_language_codes": "list[str], 1 to 12",
            "original_filename":     "str, required",
            "genre":                 "str — NON_FICTION | ADULT_FICTION | CHILDREN_FICTION | RELIGIOUS | LEGAL | ACADEMIC",
        },
        "response": {
            "job_id":     "str",
            "upload_url": "str — PUT the file here with x-ms-blob-type: BlockBlob",
        },
        "notes": (
            "Then POST /translate/document/jobs/{job_id}/start, "
            "GET .../live-status, POST .../export?lang=, GET .../export/status."
        ),
    },
    "/dubbing/jobs": {
        "method": "POST",
        "content_type": "application/json",
        "request_body": {
            "src_lang":       "str, required — REST field name, not source_language_code",
            "target_langs":   "list[str], required",
            "export_options": "list — video | audio | audio_vocals | srt | vtt (omit = dubbed MP4 only). editor_flow=true suppresses auto-export and bills 2x",
            "voice_cloning":  "bool, default true",
            "editor_flow":    "bool — keep false for API integrations",
        },
        "response": {
            "data.job_id":     "str",
            "data.upload_url": "str",
        },
        "notes": (
            "PUT the media, POST /dubbing/jobs/{job_id}/start, "
            "GET .../live-status and GET .../export-status?limit=100. "
            "This is the dubbing product, separate from the short-audio dub workflow."
        ),
    },
    "/text-to-speech/pronunciation-dictionary": {
        "method": "GET (list), POST (create), GET /{id} (get), DELETE ?dict_id= (delete)",
        "content_type": "application/json",
        "request_body": {
            "entries": "dict[str, str] — word → pronunciation mappings (for create)",
        },
        "response": {
            "dictionary_count": "int",
            "dictionaries":     "list[str] — dictionary IDs",
        },
        "notes": (
            "CRUD for pronunciation dictionaries (all live-confirmed 2026-08-14). "
            "GET a specific dictionary via a path segment (.../{dictionary_id}); "
            "DELETE instead takes the id as a query param "
            "(.../pronunciation-dictionary?dict_id={id}), not a path segment — "
            "easy to get backwards."
        ),
    },
    "/text-to-speech/ws": {
        "method": "WebSocket",
        "model": "bulbul:v3 | bulbul:v4-flash",
        "notes": (
            "Live-confirmed 2026-08-14. Connect to "
            "wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3 (or bulbul:v4-flash) with header "
            "api-subscription-key: <key>. model is a URL query param, not a "
            "body/config field. Message sequence: send "
            '{"type":"config","data":{"speaker","language_code","pace",'
            '"pitch","loudness","output_audio_codec","output_audio_bitrate","min_buffer_size",'
            '"max_chunk_length"}} first, then one or more '
            '{"type":"text","data":{"text":...}}, then {"type":"flush"} to force '
            "processing. Audio arrives as TEXT (JSON) frames, not binary: "
            '{"type":"audio","data":{"content_type":...,"audio":"<base64>"}}. '
            "There is no reliable end-of-stream event in practice — treat a "
            "short idle period with no new frames as completion. Only the "
            "first audio chunk carries a WAV header; concatenating chunks "
            "in order produces a valid file, but the header's RIFF/data size "
            "fields are streaming placeholders (0xFFFFFFFF) that must be "
            "patched with the true length once the stream ends, or strict WAV "
            "parsers will misread the duration."
        ),
    },
}


# ---------------------------------------------------------------------------
# Endpoints added after the 2026-10 docs sync (Chat V2, Responses, models,
# Dictate, Instant Voice Cloning). Source: docs.sarvam.ai/api-reference/*,
# reviewed 2026-11-23. Not yet live-tested against api.sarvam.ai.
# ---------------------------------------------------------------------------

API_REFERENCE.update({
    "/v2/chat/completions": {
        "method": "POST",
        "model": "sarvam-105b | sarvam-105b-conversations | glm5.3 | glm5.3-flash | gemma4 | deepseekv4.1-flash-1017 | deepseekv4.1-flash-1017-interactive | deepseekv4-pro (provisioned) | kimi-k3.1-pro (provisioned) | qwen38-27b (provisioned)",
        "content_type": "application/json",
        "request_body": {
            "model":              "str, required, case-sensitive (GET /v2/models lists what your key can use)",
            "messages":           "list, required — roles system|developer|user|assistant|tool. Images only as inline data:image URIs",
            "temperature":        "float 0-2, default 1",
            "top_p":              "float >0..1, default 0.95",
            "max_tokens":         "int, default 2048 (includes reasoning tokens)",
            "reasoning_effort":   "none|low|medium|high|max — low/high/max on every reasoning model; medium on sarvam-105b, deepseek*, kimi-k3.1-pro (runs as high), qwen38-27b; none only on deepseek* and qwen38-27b (kimi-k3.1-pro 400s; glm5.3/glm5.3-flash keep thinking). Default max on glm5.3/kimi-k3.1-pro, high on glm5.3-flash/deepseek*, off on gemma4; sarvam-105b-conversations ignores it",
            "n":                  "must be 1 (n>1 -> 400 invalid_request_error)",
            "stop":               "str | list[str] (up to 4)",
            "tools / tool_choice / parallel_tool_calls": "function tools only; tool_choice none|auto|required|{function}",
            "response_format":    "json_object | json_schema (strict defaults false)",
            "top_k":              "-1 or >=1 (0 rejected); not on glm5.3",
            "repetition_penalty": ">0 and <=2",
            "logprobs / top_logprobs": "not supported on glm5.3 or kimi-k3.1-pro",
            "stream / stream_options": "stream_options.include_usage only with stream:true",
        },
        "headers": "api-subscription-key (required); optional x-session-affinity for multi-turn routing",
        "notes": (
            "Body limit 10,485,760 bytes. Errors: 400, 402 (credits), 403 (invalid keys appear as 403), "
            "404 (unknown model / no provisioned access), 413, 429, 502 model_call_failed, 503 model_overloaded. "
            "PROVISIONED THROUGHPUT models (deepseekv4-pro, kimi-k3.1-pro, qwen38-27b; also clef and "
            "embeddinggemma-2 on other endpoints) are enabled per organisation — contact Sarvam support "
            "(support@sarvam.ai, https://docs.sarvam.ai/api/getting-started/help) with the model and your expected volume. "
            "Without access deepseekv4-pro returns 400 invalid_request_error ('…runs on Provisioned Throughput and is not "
            "enabled for your organisation') and is still listed by GET /v2/models; the others return 404 not_found_error "
            "and are NOT listed. "
            "Per-model rules: reasoning_effort none only on deepseekv4.1-flash-1017[-interactive]/deepseekv4-pro/qwen38-27b "
            "(glm5.3, glm5.3-flash, kimi-k3.1-pro always think; gemma4 off unless set); logprobs 400 on glm5.3 and "
            "kimi-k3.1-pro; image input (inline data: URIs only) on glm5.3-flash, gemma4, deepseekv4.1-flash-1017*, "
            "kimi-k3.1-pro (also video), qwen38-27b; stop: sarvam-105b/glm5.3/gemma4 max 4 (400), others accept more; "
            "only gemma4 honours x-session-affinity; qwen38-27b structured output needs reasoning_effort none; "
            "max_tokens default 2048 on glm5.3 only (set it explicitly — reasoning counts against it); "
            "body limit 10 MiB (32 MiB deepseekv4.1-flash-1017); auth failures are 403 not 401. "
            "Context: sarvam-105b 128K; glm5.3/glm5.3-flash/deepseek/kimi 1M; gemma4/qwen38-27b 256K."
        ),
    },
    "/v2/responses": {
        "method": "POST",
        "model": "sarvam-105b | sarvam-105b-conversations | glm5.3 | glm5.3-flash | gemma4 | deepseekv4.1-flash-1017 | deepseekv4.1-flash-1017-interactive | deepseekv4-pro | kimi-k3.1-pro | qwen38-27b (provisioned models need org access — contact Sarvam support)",
        "content_type": "application/json",
        "request_body": {
            "model":             "str, required",
            "input":             "str | list of items, required",
            "instructions":      "str",
            "max_output_tokens": "int — no default cap; always set it",
            "reasoning":         "{effort: none|low|medium|high|max (per model), summary: auto|detailed}",
            "tools":             "FLAT shape {type:'function', name, description, parameters, strict}; the nested chat shape -> 400",
            "text":              "{format: {type: text|json_object|json_schema}}",
            "stream":            "bool; ends on response.completed|incomplete|failed (no [DONE])",
        },
        "notes": (
            "Stateless: store must be false/omitted; previous_response_id, conversation, background:true, "
            "max_tool_calls, prompt, item_reference -> 400; GET /v2/responses/{id} always 404. "
            "n and seed are ignored (open-weight models return 400 for n, even n=1) and open-weight models reject stop. "
            "glm5.3 / glm5.3-flash accept only low|high. top_k unsupported on glm5.3. Logprobs: send top_logprobs with "
            "include=['message.output_text.logprobs'] (400 on glm5.3, gemma4, kimi-k3.1-pro). GET /v2/responses and "
            "DELETE /v2/responses/{id} return 405."
        ),
    },
    "/v2/embeddings": {
        "method": "POST",
        "model": "embeddinggemma-2 (Provisioned Throughput)",
        "content_type": "application/json",
        "request_body": {
            "model":           "str, required — 'embeddinggemma-2'",
            "input":           "str | list[str], required — each up to 8,192 tokens; an empty list -> 400",
            "encoding_format": "float (default) | base64 (768 little-endian float32). bytes / bytes_only / int8 -> 400",
            "dimensions":      "NOT supported — any value -> 400. Truncate to the first N values and re-normalise yourself",
        },
        "response": {
            "data": "list of {object:'embedding', index, embedding:[768 floats]} in input order",
            "usage": "{prompt_tokens, total_tokens, completion_tokens:0}",
        },
        "notes": (
            "OpenAI-compatible. The API adds NO task prefix — prepend one yourself: "
            "'task: search result | query: ' (queries), 'title: none | text: ' (documents), "
            "'task: question answering | query: ', 'task: fact checking | query: ', "
            "'task: classification | query: ', 'task: clustering | query: ', "
            "'task: sentence similarity | query: ', 'task: code retrieval | query: '. "
            "Billed INR 2 per 1M input tokens. The path is documented on the model page but is not yet in the public OpenAPI spec."
        ),
    },
    "/v2/models": {
        "method": "GET",
        "content_type": "-",
        "response": {"data": "list of {id, created, owned_by, access: standard|provisioned}"},
        "notes": (
            "Also GET /v2/models/{model_id}. deepseekv4-pro is listed for every key (400 without access); "
            "kimi-k3.1-pro, qwen38-27b, clef and embeddinggemma-2 appear only once Sarvam has enabled "
            "Provisioned Throughput for your org (contact support)."
        ),
    },
    "/v2/dictate": {
        "method": "POST",
        "model": "dictate-v1 (alias of dictate-v1-2026-11-04; also dictate-v1-2026-11-05)",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":          "file, required — <=30 s, <=10,000,000 bytes (WAV, MP3, AAC, AIFF, OGG, Opus, FLAC, MP4/M4A, AMR, WMA, WebM)",
            "language_code": "auto (default) | hi-IN, bn-IN, kn-IN, ml-IN, mr-IN, or-IN (Odia), pa-IN, ta-IN, te-IN, en-IN, gu-IN, as-IN, ur-IN, ne-IN, kok-IN, ks-IN, sd-IN, sa-IN, sat-IN, mni-IN, brx-IN, mai-IN, doi-IN",
            "mode":          "transcribe (default) | verbatim | translit | codemix",
            "style":         "JSON {preset: none|light|clean, rules: str<=2000}; prefix/suffix -> 400",
            "vocabulary":    "JSON list (<=1000) of {word 1-64, sounds_like[<=5], description<=200}",
            "context":       "JSON {text<=2000, reference<=50000}",
            "output_rules":  "str<=4000 — derive an extra `output` from the whole recording",
            "model":         "str — pin a snapshot",
        },
        "response": {"text": "finished text", "transcript": "raw", "corrections": "[{heard, wrote, source}]", "degraded": "llm_timeout|llm_error|llm_guard_failed|llm_context_limit|asr_error|asr_timeout|null", "usage": "{audio_duration_s, words, llm_input_tokens, llm_output_tokens}", "output": "only with output_rules"},
        "notes": (
            "Send options as multipart FORM PARTS holding JSON text — query params are ignored and empty-string "
            "parts return 400. Each non-file part <=1 MiB; body <=12,097,152 bytes; no trailing slash. "
            "Billed per minute incl. silence. Long audio: POST /v2/dictate/jobs (<=1 h)."
        ),
    },
    "/v2/dictate/jobs": {
        "method": "POST (create) | GET /v2/dictate/jobs/{job_id} (poll)",
        "content_type": "multipart/form-data (Content-Length required)",
        "request_body": {
            "file | audio_url": "exactly one. file: gateway 413 at ~100 MB; audio_url: https, port 443/8443, no private addresses, <=3 redirects",
            "language_code / mode / style / vocabulary / context / output_rules / model": "as /v2/dictate",
            "callback":         "JSON {url (https, 443/8443, no redirects), auth_token (1-4096 printable ASCII; sent as X-SARVAM-JOB-CALLBACK-TOKEN)}",
        },
        "response": {"create": "202 {job_id, job_state}", "poll": "{job_state Accepted|Pending|Running|Completed|Failed, created_at, completed_at, expires_at (7 days after completion, then 404), error{code,message}, result{...as /v2/dictate plus segments, sections}}"},
        "notes": "Each POST creates a new billed job (no idempotency key). A Failed job still returns HTTP 200. Poll every 5 s or slower. Live WebSocket sessions last up to 3 hours, 60 s idle timeout.",
    },
    "/voices/create": {
        "method": "POST",
        "model": "Sarvam Instant Voice Cloning (beta)",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":     "file, required — WAV/MP3/FLAC/OPUS/AAC/MULAW/ALAW/LINEAR16, <=50 MB, ideally 10-15 s single speaker",
            "name":     "str 1-100, required",
            "language": "BCP-47 of the reference audio, required",
            "style / gender": "optional labels",
            "remove_background_noise": "bool, default true",
        },
        "response": {"data": "{voice_id (svc-<uuid>), status, reference_text, background_noise_removed}"},
        "notes": "Rejected Studio-only fields (400): consent, passage_id, noise_reduction, enable_noise_reduction, accent, ref_text. 403 TIER_LIMIT_REACHED at the org voice cap (50 on Starter); 422 if audio fails quality/ASR checks. Also: GET /voices (list: search, gender, accent, limit<=200, offset), GET /voices/{id}, DELETE /voices/delete/{id} (204).",
    },
    "/voices/clone": {
        "method": "POST",
        "model": "Sarvam Instant Voice Cloning (beta)",
        "content_type": "multipart/form-data",
        "request_body": {
            "voice_id | ref_audio": "exactly one (400 otherwise). ref_audio <=10 MB, <=15 s",
            "text":                 "str, required, <=1000 chars",
            "language_code":        "as/bn/en/gu/hi/kn/ml/mr/od/pa/ta/te -IN; optional (auto-detected from text)",
            "pace":                 "0.5-2.0; mutually exclusive with max_audio_duration",
            "output_audio_codec":   "wav (default) | mp3 | flac | opus | aac | linear16 | mulaw | alaw",
            "speech_sample_rate":   "8000..48000, default 24000; opus needs 8000/16000/24000/48000",
            "enable_qc / enable_vad / remove_background_noise / enable_text_normalization": "bools (vad default true; noise removal only with ref_audio, API default false here)",
            "min_audio_duration / max_audio_duration": "seconds; max >= min",
        },
        "response": {"audio_b64": "base64 audio", "audio_duration": "seconds", "request_id": "str"},
        "notes": "Also /voices/clone/stream (HTTP) and a WebSocket variant. language_code became optional 2026-10-26. 1000-char text limit (400 above).",
    },
    "/voices/watermark/detect": {
        "method": "POST",
        "content_type": "multipart/form-data",
        "request_body": {"file": "WAV/MP3/FLAC/OGG/M4A/WebM, <=10 MB, first 120 s analysed"},
        "response": {"data": "{verdict: watermarked|not_detected|inconclusive, z_score, n_pairs_scored, analysed_seconds, algorithm_version, inconclusive, probability, p_value}"},
        "notes": "5 requests/minute; free. Clips under ~5 s are usually inconclusive; z_score above ~3.5 is typically watermarked.",
    },
})


# ---------------------------------------------------------------------------
# Pricing — INR, excluding GST. Source: docs.sarvam.ai/api/getting-started/pricing
# Last reviewed against the docs: 2026-11-23.
# Per-plan keys: payg (Pay as you go) | pro | growth | business (only where the
# docs publish one). Token models are priced per 1M tokens and are identical on
# every plan. Always direct end users to the dashboard for their live rate.
# ---------------------------------------------------------------------------

PLANS: dict[str, dict[str, Any]] = {
    "payg":       {"name": "Pay as you go", "monthly_fee_inr": 0,        "support": "Community"},
    "pro":        {"name": "Pro",           "monthly_fee_inr": 9999,     "support": "Email"},
    "growth":     {"name": "Growth",        "monthly_fee_inr": 49999,    "support": "Email"},
    "business":   {"name": "Business",      "monthly_fee_inr": 199999,   "support": "Priority",
                   "note": "Includes INR 1,99,999 of credits and the best public API rates. No public rate limits."},
    "enterprise": {"name": "Enterprise",    "monthly_fee_inr": None,     "support": "Dedicated"},
}


def _per_plan(payg: float, pro: float, growth: float, business: float | None = None) -> dict[str, float]:
    rates = {"payg": payg, "pro": pro, "growth": growth}
    if business is not None:
        rates["business"] = business
    return rates


def _tokens(inp: float, cached: float | None, out: float | None, note: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "unit": "per 1M tokens",
        "rates_inr": {"input": inp, "cached_input": cached, "output": out},
        "same_on_all_plans": True,
        "access": "provisioned" if note.startswith("Provisioned Throughput") else "serverless",
        "tier": note,
    }
    if entry["access"] == "provisioned":
        entry["how_to_get_access"] = (
            "Enabled per organisation — contact Sarvam support (support@sarvam.ai, "
            "https://docs.sarvam.ai/api/getting-started/help) with the model and your expected volume."
        )
    return entry


PRICING: dict[str, dict[str, Any]] = {
    # Speech
    "saaras:v4":            {"unit": "per minute of audio", "rates_inr_by_plan": _per_plan(0.49, 0.45, 0.41),
                             "tier": "recommended, latest. Same rate for REST, streaming and batch"},
    "saaras:v3":            {"unit": "per minute of audio", "rates_inr_by_plan": _per_plan(0.49, 0.45, 0.41), "tier": "legacy"},
    "saaras:v3-realtime":   {"unit": "per minute of audio", "rates_inr_by_plan": _per_plan(0.49, 0.45, 0.41), "tier": "streaming"},
    "saaras:v4+diarization": {"unit": "per minute of audio", "rates_inr_by_plan": _per_plan(0.59, 0.54, 0.50),
                             "tier": "batch STT with with_diarization=true"},
    "bulbul:v3":            {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(3.00, 2.85, 2.70),
                             "tier": "API default model. Bulbul V3 reaches end of life on Voice Agents on 2026-11-25 but stays on the TTS API"},
    "bulbul:v4-flash":      {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(2.00, 1.85, 1.70), "tier": "latest"},
    "instant-voice-cloning": {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(2.00, 2.00, 2.00),
                             "tier": "beta. /voices/watermark/detect is free"},
    "dictate":              {"unit": "per minute of audio (silence included)",
                             "rates_inr_by_plan": _per_plan(0.50, 0.475, 0.45, 0.40),
                             "tier": "clip, job and live socket. Failed calls and degraded results are not billed"},
    # Text
    "mayura:v1":            {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(2.00, 1.70, 1.50),
                             "tier": "Translate, formal and colloquial"},
    "sarvam-translate:v1":  {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(2.00, 1.70, 1.50),
                             "tier": "Translate (same published Translate rate)"},
    "transliterate":        {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(2.00, 2.00, 1.80), "tier": "/transliterate"},
    "language-identification": {"unit": "per 1,000 characters", "rates_inr_by_plan": _per_plan(0.35, 0.35, 0.31), "tier": "/text-lid"},
    # Document AI
    "sarvam-vision":        {"unit": "per page", "rates_inr_by_plan": _per_plan(0.50, 0.50, 0.50),
                             "tier": "Document AI: Parse"},
    "doc-extract-basic":    {"unit": "per page", "rates_inr_by_plan": _per_plan(1.00, 1.00, 1.00), "tier": "extract mode=basic"},
    "doc-extract-advanced": {"unit": "per page", "rates_inr_by_plan": _per_plan(2.50, 2.50, 2.50), "tier": "extract mode=advanced"},
    "document-translation": {"unit": "per 1,000 billable characters, per target language",
                             "rates_inr_by_plan": _per_plan(5.00, 5.00, 4.50),
                             "tier": "rounded up to the nearest rupee, minimum INR 1"},
    "dubbing":              {"unit": "per minute of source media x target languages",
                             "rates_inr_by_plan": _per_plan(40, 40, 38), "tier": "editor_flow=false"},
    "dubbing-editor-flow":  {"unit": "per minute of source media x target languages",
                             "rates_inr_by_plan": _per_plan(80, 80, 75), "tier": "editor_flow=true"},
    # LLMs (INR per 1M tokens; reasoning tokens bill as output)
    "sarvam-105b":          _tokens(10, 0.25, 25, "serverless. Introductory pricing through the end of 2026"),
    "sarvam-105b-conversations": _tokens(10, 0.25, 25, "serverless. Same rate as sarvam-105b; introductory pricing through the end of 2026"),
    "sarvam-prism":         _tokens(4, None, 0, "serverless. Input tokens only; the state is billed once per request however many questions you ask"),
    "glm5.3":               _tokens(126, 20, 390, "serverless"),
    "glm5.3-flash":         _tokens(13.5, 2.5, 45, "serverless"),
    "gemma4":               _tokens(35, 10, 90, "serverless (Gemma 4 31B)"),
    "deepseekv4.1-flash-1017": _tokens(14, 0.25, 55, "serverless. Cut from 25/0.5/105 on 2026-11-07; introductory pricing through the end of 2026"),
    "deepseekv4.1-flash-1017-interactive": _tokens(25, 0.5, 105, "serverless. >200 tokens/s (about 80 on the standard model)"),
    "deepseekv4-pro":       _tokens(115, 4, 350, "Provisioned Throughput — enabled per org (contact support)"),
    "kimi-k3.1-pro":        _tokens(200, 20, 950, "Provisioned Throughput — enabled per org (contact support)"),
    "qwen38-27b":           _tokens(18, 5, 230, "Provisioned Throughput — enabled per org (contact support)"),
    "clef":                 _tokens(20, None, None, "Provisioned Throughput decision model (contact support), billed on input only"),
    "embeddinggemma-2":     _tokens(2, None, None, "Provisioned Throughput (contact support), billed on input only, POST /v2/embeddings"),
}

PROVISIONED_THROUGHPUT_NOTE = (
    "Provisioned Throughput models (deepseekv4-pro, kimi-k3.1-pro, qwen38-27b, clef, embeddinggemma-2) "
    "are NOT self-serve: capacity is set up for your workload and enabled per organisation. Contact "
    "Sarvam support (support@sarvam.ai, https://docs.sarvam.ai/api/getting-started/help) with the model "
    "you need and your expected volume. Without access deepseekv4-pro returns 400 and the others 404."
)

PRICING_DISCLAIMER = (
    "Prices are in INR, exclude GST, and mirror docs.sarvam.ai/api/getting-started/pricing "
    "as of 2026-11-23. Introductory pricing on sarvam-105b, sarvam-105b-conversations and "
    "deepseekv4.1-flash-1017 runs through the end of 2026. Credits never expire; new verified "
    "users receive INR 100 of free credits. Exhausted credits return HTTP 402 "
    "(insufficient_quota_error), which is separate from 429. Confirm live rates at "
    "https://dashboard.sarvam.ai (billing) before quoting production numbers."
)

# Deprecated / removed — do not recommend.
DEPRECATED_MODELS: dict[str, str] = {
    "sarvam-m": "Deprecated and no longer served — use sarvam-105b.",
    "sarvam-30b": "Deprecated — use sarvam-105b.",
    "saaras:v2.5": "Deprecated — use saaras:v4.",
    "kimi-k3": "No longer offered (2026-11-06) — use kimi-k3.1-pro or glm5.3-flash.",
    "mimo-v2.6-flash": "No longer offered (2026-11-06) — use glm5.3-flash for the lowest price.",
    "mimo-v2.6-pro": "No longer offered (2026-11-06).",
}


# ---------------------------------------------------------------------------
# Rate limits — per plan, per API. Source: docs.sarvam.ai/api/getting-started/pricing#rate-limits
# Last reviewed against the docs: 2026-11-23. Business has no published limits
# (limits above Growth need an Enterprise arrangement).
# Units: "req/min" requests per minute; "concurrent" open connections.
# ---------------------------------------------------------------------------

def _limit(payg: int, pro: int, growth: int, unit: str = "req/min", **extra: Any) -> dict[str, Any]:
    return {"unit": unit, "payg": payg, "pro": pro, "growth": growth, **extra}


# Document AI limits are per organisation and shared by Parse, Extract, Split and
# Classify — not per plan or per operation (docs: languages-formats-limits#rate-limits).
_DOC_AI_SHARED: dict[str, Any] = {
    "unit": "req/min",
    "all_plans": {
        "submit_and_upload": 300,
        "status_results_download": 6000,
        "uploaded_files_waiting": 300,
    },
    "note": (
        "Organisation-wide and shared by Parse, Extract, Split and Classify. Over a limit returns 429 "
        "(retryable: true, Retry-After). Contracted limits apply instead; contact Sarvam for more."
    ),
}

RATE_LIMITS: dict[str, dict[str, Any]] = {
    "stt_rest":            _limit(60, 100, 4000),
    "stt_websocket":       _limit(20, 100, 100, "concurrent"),
    "stt_batch":           _limit(20, 100, 500, note="Poll no faster than your plan allows (SDK default 5 s)."),
    "tts_rest_and_http_stream": _limit(60, 200, 1000, note="bulbul:v3 and bulbul:v4-flash"),
    "tts_websocket":       _limit(60, 200, 1000, "concurrent"),
    "dictate_clip":        _limit(60, 100, 4000, note="POST /v2/dictate"),
    "dictate_jobs":        _limit(20, 100, 500, note="create, read, delete. Poll every 5 s or slower."),
    "dictate_live_websocket": _limit(20, 100, 100, "concurrent", note="Session lasts up to 3 hours; closes after 60 s with no client message."),
    "voice_cloning":       {"unit": "req/min (burst)", "payg": "60 (burst 100)", "pro": "200 (burst 300)", "growth": "1000 (burst 1200)"},
    "voice_watermark_detect": {"unit": "req/min", "all_plans": 5, "note": "Free, consumes no credits."},
    "translate_transliterate_lid": _limit(60, 200, 1000, note="POST /translate, /transliterate, /text-lid"),
    "llm_default":         _limit(50, 200, 1000, note="gemma4, glm5.3, deepseekv4.1-flash-1017"),
    "llm_sarvam_105b":     _limit(60, 200, 300, note="sarvam-105b and sarvam-105b-conversations"),
    "dubbing":             _limit(5, 50, 300),
    "doc_ai": _DOC_AI_SHARED,
    "doc_ai_parse":        {**_DOC_AI_SHARED, "pages_per_request": 20, "max_file_mib": 100},
    "doc_ai_extract":      {**_DOC_AI_SHARED, "pages_per_request": 500, "max_file_mib": 100},
    "doc_ai_split":        {**_DOC_AI_SHARED, "pages_per_request": 500, "max_file_mib": 512},
    "doc_ai_classify":     {**_DOC_AI_SHARED, "pages_per_request": 20, "max_file_mib": 512},
    "document_translation": _limit(200, 500, 1000, pages_per_request=500, note="Document Translation job endpoints. Poll live-status every 10-15 s."),
}

RATE_LIMITS_DISCLAIMER = (
    "Limits are the published per-plan defaults (docs.sarvam.ai, reviewed 2026-11-23). Exceeding "
    "them returns 429 rate_limit_exceeded_error; 503 means load shedding — retry both with "
    "exponential backoff. The docs disagree on scope (per account in the pricing page, per API key "
    "on the Token Factory page); treat them as per account to be safe. Business has no published "
    "limits. Document AI page limits are authoritative via GET /doc-ai/v1/capabilities. "
    "PENDING DOCS CHANGE: sarvamai/sarvam-fern-config PR #784 (open, unmerged as of 2026-11-23) "
    "proposes new limits — STT/TTS REST+WebSocket 150/200/1,000/4,000 req/min (PAYG/Pro/Growth/Business), "
    "Sarvam-105B Growth 1,000, Voice Cloning 60/200/300/1,000, Prism/Clef/EmbeddingGemma 120/500/1,200/2,000, "
    "and a Business column everywhere. Until it merges the table above is what docs.sarvam.ai publishes."
)
