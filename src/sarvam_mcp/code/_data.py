"""Hard-coded reference data for the ``sarvam_code_*`` docs tools.

These tables are the authoritative source for what an agent needs to know
when *generating* Sarvam-using code. They mirror what's encoded as enums
in ``tools/_common.py`` (single source of truth for our runtime tools)
and what's documented at docs.sarvam.ai.

Update cadence: bump these any time Sarvam adds a model/speaker/language
or changes pricing. CI will surface a diff in PR review.

Last verified live against api.sarvam.ai: 2026-10-06.
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
            "target_language_code": "str, required — one of TTS-supported codes",
            "speaker":              "str, required — must be compatible with chosen model",
            "model":                "str — 'bulbul:v3' (default) | 'bulbul:v4-flash'",
            "speech_sample_rate":   "int — 8000|16000|22050|24000|32000|44100|48000",
            "output_audio_codec":   "str (optional) — wav (default) | mp3 | aac | flac | linear16 | mulaw | opus (opus needs 8000/12000/16000/24000/48000 Hz)",
            "pace":                 "float, 0.5 to 2.0 (default 1)",
            "pitch":                "float (optional), -0.5 to 0.5",
            "loudness":             "float (optional), 0.1 to 2.5",
            "enable_preprocessing": "bool — normalize numbers/dates/code-mix",
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
            "`temperature` is silently ignored on v4-flash. Max input length: "
            "2500 characters via `text` (the legacy `inputs` array caps each item at "
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
        "model": "saaras:v3-realtime (default), saaras:v4",
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
            "temperature":       "float, 0.0 to 2.0",
            "top_p":             "float, 0.0 to 1.0",
            "max_tokens":        "int (optional)",
            "reasoning_effort":  "str (optional) — 'low' | 'medium' (default) | 'high'",
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
            "There is also a /v2/chat/completions endpoint (glm5.3, gemma4, "
            "deepseekv4-flash open-weight models) — confirmed to require beta "
            "whitelisting from Sarvam, so most subscription keys can't call it "
            "yet; not implemented here for that reason. Ask Sarvam for beta "
            "access before building against it."
        ),
    },
    "/doc-ai/v1/job/digitise": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":          "binary, required (or upload_ids)",
            "language":      "str — BCP-47, default en-IN. Not language_code.",
            "output_format": "str — html (API default) | md | json. Not 'markdown'.",
            "content_type":  "str — printed | handwritten | mixed",
            "model":         "str — sarvam-vision-v1",
        },
        "response": {
            "job_id": "str",
            "status": "str — pending, then completed | partially_completed | failed | rejected",
        },
        "notes": (
            "Full-document OCR. Poll GET /doc-ai/v1/job/{job_id}/status, then "
            "GET /doc-ai/v1/job/{job_id}/download-url. Max 10 pages."
        ),
    },
    "/doc-ai/v1/job/extract": {
        "method": "POST",
        "model": "sarvam-vision",
        "content_type": "multipart/form-data",
        "request_body": {
            "file":          "binary, required (or upload_ids)",
            "schema":        "JSON string — root type object, each field needs type and description",
            "config_id":     "str — alternative to schema",
            "language":      "str — BCP-47",
            "output_format": "str — json | csv | xlsx",
        },
        "response": {"job_id": "str", "status": "str"},
        "notes": "Schema extraction. Poll status, then GET /doc-ai/v1/job/{job_id}/results.",
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
            "export_options": "list — video | audio | mp3 | srt",
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
# Pricing — point estimate; PER-USER RATES MAY VARY based on plan/contract.
# Always direct end users to https://dashboard.sarvam.ai → Billing for live.
# Last reviewed: 2026-04-27.
# ---------------------------------------------------------------------------

PRICING: dict[str, dict[str, Any]] = {
    "saaras:v4":            {"unit": "per minute of audio",   "tier": "billed by minute (recommended, latest)"},
    "saaras:v3":            {"unit": "per minute of audio",   "tier": "billed by minute"},
    "saaras:v3-realtime":   {"unit": "per minute of audio",   "tier": "billed by minute"},
    "bulbul:v3":            {"unit": "per character",         "tier": "billed by character"},
    "bulbul:v4-flash":      {"unit": "per character",         "tier": "billed by character (assumed same unit as bulbul:v3 — docs.sarvam.ai doesn't publish a v4-flash rate yet; confirm on dashboard.sarvam.ai)"},
    "mayura:v1":            {"unit": "per character",         "tier": "billed by character"},
    "sarvam-translate:v1":  {"unit": "per character",         "tier": "billed by character"},
    "sarvam-105b":          {"unit": "per 1M tokens",         "tier": "billed by tokens (flagship). Hidden reasoning tokens count as completion tokens and are billed the same as visible output."},
    "sarvam-105b-conversations": {"unit": "per 1M tokens",    "tier": "billed by tokens — same rate as sarvam-105b, per docs.sarvam.ai pricing page."},
    "sarvam-vision":        {"unit": "per page",              "tier": "billed by page"},
}

PRICING_DISCLAIMER = (
    "This is a high-level pricing structure; exact per-unit rates depend on "
    "your Sarvam plan and may have changed since last update. ALWAYS confirm "
    "current rates at https://dashboard.sarvam.ai → Billing before quoting "
    "production-bound numbers. New users receive Rs. 1000 in free credits."
)


# ---------------------------------------------------------------------------
# Rate limits — platform defaults (may vary by plan/contract).
# ---------------------------------------------------------------------------

RATE_LIMITS: dict[str, dict[str, Any]] = {
    "general": {
        "requests_per_minute": 60,
        "description": "Default rate limit for most endpoints",
    },
    "translate": {
        "requests_per_minute": 300,
        "description": "Higher limit for /translate endpoint",
    },
    "platform": {
        "requests_per_minute": 5000,
        "description": "Platform-wide aggregate limit",
    },
}

RATE_LIMITS_DISCLAIMER = (
    "These are default rate limits and may vary based on your Sarvam plan. "
    "Check https://dashboard.sarvam.ai for your account-specific limits."
)
