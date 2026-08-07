"""Hard-coded reference data for the ``sarvam_code_*`` docs tools.

These tables are the authoritative source for what an agent needs to know
when *generating* Sarvam-using code. They mirror what's encoded as enums
in ``tools/_common.py`` (single source of truth for our runtime tools)
and what's documented at docs.sarvam.ai.

Update cadence: bump these any time Sarvam adds a model/speaker/language
or changes pricing. CI will surface a diff in PR review.

Last verified live against api.sarvam.ai: 2026-04-27.
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
    "stt_translate": ALL_LANGUAGES,    # Saaras takes any input; output is always English.
    "tts":           [lang for lang in ALL_LANGUAGES if lang["code"] in _TTS_CODES],
    "translate":     ALL_LANGUAGES,    # sarvam-translate:v1 covers all; mayura:v1 only TTS subset.
    "transliterate": ALL_LANGUAGES,
    "lid":           [lang for lang in ALL_LANGUAGES if lang["code"] in _LID_CODES],
    "llm":           ALL_LANGUAGES,
    "vision":        ALL_LANGUAGES,
}


# ---------------------------------------------------------------------------
# TTS speakers for bulbul:v3.
# ---------------------------------------------------------------------------

V3_SPEAKERS = [
    "aditya", "ritu", "ashutosh", "priya", "neha", "rahul", "pooja", "rohan",
    "simran", "kavya", "amit", "dev", "ishita", "shreya", "ratan", "varun",
    "manan", "sumit", "roopa", "kabir", "aayan", "shubh", "advait", "anand",
    "tanya", "tarun", "sunny", "mani", "gokul", "vijay", "shruti", "suhani",
    "mohit", "kavitha", "rehan", "soham", "rupali", "niharika",
]

SPEAKERS_BY_MODEL: dict[str, list[str]] = {
    "bulbul:v3": V3_SPEAKERS,
}

# Curated tone hints for the most-used voices, so agents can pick sensibly.
SPEAKER_HINTS: dict[str, str] = {
    "priya":    "warm friendly female (default), good for product / IVR",
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
    "niharika": "young energetic female",
}


# ---------------------------------------------------------------------------
# Endpoint reference. Mirrors what the runtime tools use; this is the
# authoritative shape for code-gen tools to consult.
# ---------------------------------------------------------------------------

API_REFERENCE: dict[str, dict[str, Any]] = {
    "/text-to-speech": {
        "method": "POST",
        "model": "bulbul:v3 (latest)",
        "content_type": "application/json",
        "auth_header": "api-subscription-key",
        "request_body": {
            "inputs":               "list[str], required — texts to synthesize",
            "target_language_code": "str, required — one of TTS-supported codes",
            "speaker":              "str, required — must be compatible with chosen model",
            "model":                "str — bulbul:v3 default",
            "speech_sample_rate":   "int — 8000|16000|22050|24000|32000|44100|48000",
            "pitch":                "float, -1.0 to 1.0 (default 0)",
            "pace":                 "float, 0.3 to 3.0 (default 1)",
            "loudness":             "float, 0.1 to 3.0 (default 1)",
            "enable_preprocessing": "bool — normalize numbers/dates/code-mix",
        },
        "response": {
            "audios":     "list[str] — base64-encoded WAV per input",
            "request_id": "str",
        },
        "notes": "Pick a speaker compatible with your model — see sarvam_code_speakers.",
    },
    "/speech-to-text": {
        "method": "POST",
        "model": "saaras:v3 (recommended)",
        "content_type": "multipart/form-data",
        "auth_header": "api-subscription-key",
        "request_body": {
            "file":              "binary, required — audio (wav, mp3, ogg, flac, m4a, webm, aac, opus, amr, wma)",
            "model":             "str — saaras:v3",
            "mode":              "str — transcribe (default) | translate | verbatim | translit | codemix (saaras:v3 only)",
            "language_code":     "str — BCP-47 or 'unknown' for auto-detect",
            "with_timestamps":   "bool",
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
            "Saaras v3 is the recommended model. It supports 5 output modes via the `mode` parameter. "
            "For >30s audio, use /speech-to-text/job/init."
        ),
    },
    "/speech-to-text-translate": {
        "method": "POST",
        "model": "saaras:v2.5 (DEPRECATED — use /speech-to-text with mode=translate instead)",
        "content_type": "multipart/form-data",
        "auth_header": "api-subscription-key",
        "request_body": {
            "file":             "binary, required",
            "model":            "str — saaras:v2.5",
            "with_diarization": "bool",
        },
        "response": {
            "transcript":           "str — always English",
            "language_code":        "str — detected source language",
        },
        "notes": "DEPRECATED. Migrate to /speech-to-text with model=saaras:v3 and mode=translate.",
    },
    "/speech-to-text/job/init": {
        "method": "POST",
        "model": "saaras:v3 (recommended)",
        "content_type": "application/json",
        "request_body": {
            "model":           "str",
            "with_timestamps": "bool",
            "language_code":   "str (optional)",
        },
        "response": {
            "job_id":                  "str",
            "input_storage_path":      "str — Azure Blob SAS URL (PUT audio here)",
            "output_storage_path":     "str — Azure Blob SAS URL (poll for results)",
            "storage_container_type":  "str — 'Azure'",
        },
        "notes": "Async batch flow: init -> upload to SAS -> poll /speech-to-text/job/status?job_id=...",
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
            "enable_preprocessing": "bool",
        },
        "response": {
            "translated_text":      "str",
            "source_language_code": "str",
            "request_id":           "str",
        },
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
        "notes": "Each question MUST have id, text, AND type — common gotcha.",
    },
    "/v1/chat/completions": {
        "method": "POST",
        "model": "sarvam-105b (flagship, sole current model)",
        "content_type": "application/json",
        "request_body": {
            "model":       "str — sarvam-105b",
            "messages":    "list[{role, content}]",
            "temperature": "float, 0.0 to 2.0",
            "top_p":       "float, 0.0 to 1.0",
            "max_tokens":  "int (optional)",
            "stream":      "bool",
        },
        "response_oai_compatible": True,
        "notes": "OpenAI-compatible. sarvam-30b was deprecated by Sarvam; sarvam-105b is the sole current model.",
    },
    "/doc-digitization/job/v1": {
        "method": "POST",
        "model": "Sarvam Vision (3B parameter VLM)",
        "content_type": "application/json",
        "request_body": {
            "job_parameters": "object — {language: BCP-47 code, output_format: 'md'|'html'|'json'}",
            "callback":       "object (optional) — {url: str, auth_token: str} for webhook",
        },
        "response": {
            "job_id":                  "str (UUID)",
            "storage_container_type":  "str",
            "job_parameters":          "object",
            "job_state":               "str — Accepted",
        },
        "notes": (
            "Job-based async pipeline: create job → get upload URLs "
            "(/doc-digitization/job/v1/upload-files) → PUT file to presigned URL → "
            "start (/doc-digitization/job/v1/{job_id}/start) → "
            "poll status (/doc-digitization/job/v1/{job_id}/status). "
            "Max 10 pages per document. Output delivered as ZIP."
        ),
    },
    "/text-to-speech/pronunciation-dictionary": {
        "method": "GET (list), POST (create)",
        "content_type": "application/json",
        "request_body": {
            "entries": "dict[str, str] — word → pronunciation mappings (for create)",
        },
        "response": {
            "dictionary_count": "int",
            "dictionaries":     "list[str] — dictionary IDs",
        },
        "notes": "CRUD for pronunciation dictionaries. Also supports GET /{id}, PUT /{id}, DELETE /{id}.",
    },
}


# ---------------------------------------------------------------------------
# Pricing — point estimate; PER-USER RATES MAY VARY based on plan/contract.
# Always direct end users to https://dashboard.sarvam.ai → Billing for live.
# Last reviewed: 2026-04-27.
# ---------------------------------------------------------------------------

PRICING: dict[str, dict[str, Any]] = {
    "saaras:v3":            {"unit": "per minute of audio",   "tier": "billed by minute (recommended)"},
    "saaras:v3-realtime":   {"unit": "per minute of audio",   "tier": "billed by minute"},
    "saaras:v2.5":          {"unit": "per minute of audio",   "tier": "billed by minute (legacy, deprecated soon)"},
    "bulbul:v3":            {"unit": "per character",         "tier": "billed by character"},
    "mayura:v1":            {"unit": "per character",         "tier": "billed by character"},
    "sarvam-translate:v1":  {"unit": "per character",         "tier": "billed by character"},
    "sarvam-105b":          {"unit": "per 1M tokens",         "tier": "billed by tokens (flagship)"},
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
