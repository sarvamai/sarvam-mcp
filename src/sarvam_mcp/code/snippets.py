"""``sarvam_code_snippet`` / ``sarvam_code_recommend_model`` /
``sarvam_code_validate_request`` — three builder helpers.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.code import _data
from sarvam_mcp.code._snippets import SNIPPETS

SnippetApi = Literal["stt", "tts", "translate", "llm"]
SnippetLanguage = Literal["python", "javascript", "typescript", "curl"]


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_code_snippet",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Return a tested, copy-paste-ready code snippet for calling a "
            "Sarvam API. The agent should use this as the starting point "
            "when adding Sarvam to an existing codebase. Snippets are "
            "verified live against api.sarvam.ai with current model "
            "versions; they assume `SARVAM_API_KEY` is set in the env."
        ),
    )
    async def sarvam_code_snippet(
        ctx: Context,
        api: SnippetApi = Field(description="Which Sarvam API."),
        language: SnippetLanguage = Field(
            default="python",
            description="Programming language for the snippet.",
        ),
    ) -> dict[str, Any]:
        snippet = SNIPPETS.get((api, language))
        if not snippet:
            return {
                "found": False,
                "api": api,
                "language": language,
                "available": sorted({(a, lang) for a, lang in SNIPPETS}),
            }
        return {
            "found": True,
            "api": api,
            "language": language,
            "code": snippet,
            "note": (
                "Set SARVAM_API_KEY in your environment before running. "
                "Get one at https://dashboard.sarvam.ai/login"
            ),
        }

    @mcp.tool(
        name="sarvam_code_recommend_model",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Given a plain-English description of what the dev wants to "
            "build, recommend the right Sarvam model + language code + any "
            "other key params. Useful as the first step when starting a "
            "new Sarvam-using app. Uses heuristics (no LLM call), so it's "
            "fast and works without an API key."
        ),
    )
    async def sarvam_code_recommend_model(
        ctx: Context,
        task_description: str = Field(
            description="What the dev wants to build, e.g. 'transcribe Hindi voicemails'.",
        ),
    ) -> dict[str, Any]:
        return _recommend(task_description)

    @mcp.tool(
        name="sarvam_code_validate_request",
        description=(
            "Build-time tool — helps write code that uses Sarvam. For runtime actions, use sarvam_tools_* instead.\n\n"
            "Validate a draft Sarvam API request body against the canonical "
            "schema BEFORE the dev sends it. Catches: invalid model names, "
            "speaker/model mismatches, deprecated values, unsupported "
            "language codes, missing required fields. Returns a list of "
            "issues with fix suggestions."
        ),
    )
    async def sarvam_code_validate_request(
        ctx: Context,
        endpoint: Literal[
            "/text-to-speech",
            "/speech-to-text",
            "/speech-to-text-translate",
            "/translate",
            "/transliterate",
            "/text-lid",
            "/text-analytics",
            "/v1/chat/completions",
        ] = Field(description="The Sarvam endpoint."),
        body: dict[str, Any] = Field(
            description="The draft request body the agent is about to send.",
        ),
    ) -> dict[str, Any]:
        issues = _validate(endpoint, body)
        return {
            "endpoint": endpoint,
            "body": body,
            "valid": not any(i["severity"] == "error" for i in issues),
            "issues": issues,
            "issue_count": len(issues),
        }


# ---- recommendation heuristics --------------------------------------------

_LANG_PATTERNS = {
    "hi-IN":  r"\b(hindi|हिन्दी|hin)\b",
    "ta-IN":  r"\b(tamil|தமிழ்|tam)\b",
    "te-IN":  r"\b(telugu|తెలుగు|tel)\b",
    "bn-IN":  r"\b(bengali|bangla|বাংলা|ben)\b",
    "mr-IN":  r"\b(marathi|मराठी|mar)\b",
    "gu-IN":  r"\b(gujarati|ગુજરાતી|guj)\b",
    "kn-IN":  r"\b(kannada|ಕನ್ನಡ|kan)\b",
    "ml-IN":  r"\b(malayalam|മലയാളം|mal)\b",
    "pa-IN":  r"\b(punjabi|ਪੰਜਾਬੀ|pan)\b",
    "od-IN":  r"\b(oriya|odia|ଓଡ଼ିଆ|ori)\b",
    "ur-IN":  r"\b(urdu|اردو)\b",
    "as-IN":  r"\b(assamese|asm)\b",
    "ne-IN":  r"\b(nepali|nepalese|nep)\b",
    "en-IN":  r"\b(english|eng)\b",
}


def _detect_language_code(text: str) -> str | None:
    text_lower = text.lower()
    for code, pattern in _LANG_PATTERNS.items():
        if re.search(pattern, text_lower):
            return code
    return None


def _recommend(task: str) -> dict[str, Any]:
    """Heuristic decision tree over the task description."""
    t = task.lower()
    detected_lang = _detect_language_code(t)

    # ---- speech in
    if re.search(r"\b(transcrib\w*|stt|speech.{0,5}to.{0,5}text|voice ?memo|voicemail\w*|recording|audio file)\b", t):
        if "english" in t or re.search(r"into english|to english", t):
            return _result(
                model="saaras:v3",
                endpoint="/speech-to-text",
                why="Audio in any Indic language, output as English text — use Saaras v3 with mode='translate'.",
                language_code=None,
                snippet_key=("stt", "python"),
                extras={"mode": "translate"},
            )
        return _result(
            model="saaras:v3",
            endpoint="/speech-to-text",
            why="Saaras v3 is the recommended STT model (23 languages). Supports transcribe/translate/verbatim/translit/codemix modes.",
            language_code=detected_lang or "unknown",
            snippet_key=("stt", "python"),
            extras={
                "mode": "transcribe",
                "tip_long_audio": "For audio >30s, use /speech-to-text/job/v1 for the async batch flow.",
            },
        )

    # ---- speech out
    if re.search(r"\b(tts|text.{0,5}to.{0,5}speech|speak|synthesi[sz]e|voice|read out|narrate)\b", t):
        return _result(
            model="bulbul:v3",
            endpoint="/text-to-speech",
            why="Indic text → speech. Current TTS stack with 38 voices on v3.",
            language_code=detected_lang or "hi-IN",
            snippet_key=("tts", "python"),
            extras={
                "default_speaker": "priya",
                "tip_speakers":    "Call sarvam_code_speakers('bulbul:v3') for the full voice list with tone hints.",
            },
        )

    # ---- text translation
    if re.search(r"\btransla(te|ting)\b", t):
        # If 22-language coverage signal, pick sarvam-translate.
        if re.search(r"\b(22|all indi(c|an) languages|all indian|kashmiri|sindhi|santali|bodo|maithili|dogri)\b", t):
            return _result(
                model="sarvam-translate:v1",
                endpoint="/translate",
                why="Need broad Indic coverage (22 scheduled languages). Sarvam-Translate v1 is the right choice.",
                language_code=detected_lang,
                snippet_key=("translate", "python"),
            )
        return _result(
            model="mayura:v1",
            endpoint="/translate",
            why="Translation between English and a major Indic language. Mayura v1 supports formal/colloquial/code-mixed modes.",
            language_code=detected_lang,
            snippet_key=("translate", "python"),
            extras={"tip_modes": "mode='modern-colloquial' is usually the best default."},
        )

    # ---- transliteration
    if re.search(r"\btranslitera(te|tion)|romaniz|devanagari to|to devanagari", t):
        return _result(
            model="—",
            endpoint="/transliterate",
            why="Convert script without changing language (e.g. Devanagari ↔ Latin).",
            language_code=detected_lang,
            snippet_key=("translate", "python"),  # closest existing snippet
        )

    # ---- chat / LLM / agent
    if re.search(r"\b(chat|chatbot|llm|agent|generate text|reply|conversation|reasoning|reasoning agent)\b", t):
        # Bigger model when 'reasoning'/'tool use'/'flagship' signals appear.
        if re.search(r"\b(reasoning|complex|flagship|best|highest quality|tool use)\b", t):
            return _result(
                model="sarvam-105b",
                endpoint="/v1/chat/completions",
                why="Highest-quality reasoning + tool use across Indic languages.",
                language_code=detected_lang,
                snippet_key=("llm", "python"),
            )
        return _result(
            model="sarvam-30b",
            endpoint="/v1/chat/completions",
            why="Sarvam-30B — balanced quality + cost, recommended default for chat/agents in Indic languages.",
            language_code=detected_lang,
            snippet_key=("llm", "python"),
        )

    # ---- vision / OCR / document
    if re.search(r"\b(ocr|document|pdf|image|extract text|scan|invoice|receipt)\b", t):
        return _result(
            model="sarvam-vision",
            endpoint="/doc-digitization/job/v1",
            why="Document Intelligence — extracts text, tables, and structure from PDFs/images in 23 languages.",
            language_code=detected_lang,
            snippet_key=None,
            extras={"note": "Job-based async pipeline. Max 10 pages per document."},
        )

    # ---- language detection
    if re.search(r"\b(detect language|what language|language detect|identify language|lid)\b", t):
        return _result(
            model="—",
            endpoint="/text-lid",
            why="Detect language + script of input text.",
            language_code=None,
            snippet_key=None,
        )

    return {
        "matched": False,
        "task": task,
        "suggestion": (
            "Couldn't pick confidently from the task description. "
            "List available endpoints with sarvam_code_api_reference."
        ),
    }


def _result(
    *,
    model: str,
    endpoint: str,
    why: str,
    language_code: str | None,
    snippet_key: tuple[str, str] | None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "matched": True,
        "recommended_model": model,
        "endpoint": endpoint,
        "language_code": language_code,
        "rationale": why,
    }
    if snippet_key:
        out["snippet_hint"] = (
            f"Call sarvam_code_snippet(api='{snippet_key[0]}', language='{snippet_key[1]}') "
            "for a copy-paste starter."
        )
    if extras:
        out.update(extras)
    return out


# ---- request validation ---------------------------------------------------

_VALID_TTS_MODELS = {"bulbul:v3"}
_VALID_LLM_MODELS = {"sarvam-30b", "sarvam-105b"}
_VALID_TRANSLATE_MODELS = {"mayura:v1", "sarvam-translate:v1"}
_VALID_STT_MODELS = {"saaras:v3"}
_VALID_STT_MODES = {"transcribe", "translate", "verbatim", "translit", "codemix"}
_VALID_SAARAS_MODELS = {"saaras:v3", "saaras:v3-realtime", "saaras:v2.5"}
_VALID_LANGUAGE_CODES = {lang["code"] for lang in _data.ALL_LANGUAGES} | {"auto", "unknown"}
_TTS_LANG_CODES = {lang["code"] for lang in _data.LANGUAGES_BY_API["tts"]}


def _err(field: str, message: str, fix: str = "") -> dict[str, Any]:
    return {"severity": "error", "field": field, "message": message, "fix": fix}


def _warn(field: str, message: str, fix: str = "") -> dict[str, Any]:
    return {"severity": "warning", "field": field, "message": message, "fix": fix}


def _validate(endpoint: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    if endpoint == "/text-to-speech":
        if "inputs" not in body or not isinstance(body.get("inputs"), list):
            issues.append(_err("inputs", "Required: list of strings to synthesize."))
        if not body.get("target_language_code"):
            issues.append(_err("target_language_code", "Required."))
        elif body["target_language_code"] not in _TTS_LANG_CODES:
            issues.append(_err(
                "target_language_code",
                f"'{body['target_language_code']}' not supported by TTS.",
                "TTS covers 11 codes; call sarvam_code_languages('tts').",
            ))
        model = body.get("model", "bulbul:v3")
        if model not in _VALID_TTS_MODELS:
            issues.append(_err("model", f"'{model}' invalid for TTS.",
                               f"Use one of: {sorted(_VALID_TTS_MODELS)}"))
        speaker = body.get("speaker")
        if speaker and model in _data.SPEAKERS_BY_MODEL:
            allowed = _data.SPEAKERS_BY_MODEL[model]
            if speaker not in allowed:
                fix = (f"Speakers compatible with {model}: "
                       f"{', '.join(allowed[:8])}, … Call sarvam_code_speakers('{model}').")
                issues.append(_err("speaker", f"'{speaker}' not compatible with {model}.", fix))
        if "speech_sample_rate" in body and body["speech_sample_rate"] not in (
            8000, 16000, 22050, 24000, 32000, 44100, 48000
        ):
            issues.append(_err("speech_sample_rate", "Invalid sample rate."))

    elif endpoint == "/speech-to-text":
        if not body.get("file") and "file" not in body:
            issues.append(_warn("file", "Required (multipart). Pass the audio file separately."))
        model = body.get("model", "saaras:v3")
        if model not in _VALID_STT_MODELS:
            issues.append(_err("model", f"'{model}' invalid for STT.",
                               "Use 'saaras:v3'."))
        mode = body.get("mode")
        if mode and mode not in _VALID_STT_MODES:
            issues.append(_err("mode", f"'{mode}' invalid.",
                               f"Valid modes: {sorted(_VALID_STT_MODES)}"))
        lc = body.get("language_code", "unknown")
        if lc not in _VALID_LANGUAGE_CODES:
            issues.append(_err("language_code", f"Unknown code '{lc}'."))

    elif endpoint == "/speech-to-text-translate":
        model = body.get("model", "saaras:v3")
        if model not in _VALID_SAARAS_MODELS:
            issues.append(_err("model", f"'{model}' invalid.",
                               f"Use one of: {sorted(_VALID_SAARAS_MODELS)}"))

    elif endpoint == "/translate":
        for f in ("input", "source_language_code", "target_language_code"):
            if not body.get(f):
                issues.append(_err(f, f"Required field '{f}' missing."))
        for f in ("source_language_code", "target_language_code"):
            v = body.get(f)
            if v and v not in _VALID_LANGUAGE_CODES:
                issues.append(_err(f, f"Unknown language code '{v}'."))
        model = body.get("model", "mayura:v1")
        if model not in _VALID_TRANSLATE_MODELS:
            issues.append(_err("model", f"'{model}' invalid for translate.",
                               f"Use one of: {sorted(_VALID_TRANSLATE_MODELS)}"))
        if model == "sarvam-translate:v1" and body.get("mode"):
            issues.append(_warn("mode", "Sarvam-Translate v1 ignores `mode` — formal only.",
                                "Drop the field or switch to mayura:v1 if you need modes."))

    elif endpoint == "/v1/chat/completions":
        if not body.get("messages"):
            issues.append(_err("messages", "Required."))
        model = body.get("model", "sarvam-30b")
        if model not in _VALID_LLM_MODELS:
            issues.append(_err("model", f"'{model}' invalid.",
                               f"Valid: {sorted(_VALID_LLM_MODELS)}"))
        t = body.get("temperature")
        if t is not None and not (0.0 <= t <= 2.0):
            issues.append(_err("temperature", "Must be between 0.0 and 2.0."))

    elif endpoint == "/text-analytics":
        if not body.get("text"):
            issues.append(_err("text", "Required."))
        qs = body.get("questions")
        if not isinstance(qs, list) or not qs:
            issues.append(_err("questions", "Required: non-empty list."))
        else:
            valid_types = {"boolean", "enum", "short answer", "long answer", "number"}
            for i, q in enumerate(qs):
                if not isinstance(q, dict):
                    issues.append(_err(f"questions[{i}]", "Must be an object with id/text/type."))
                    continue
                missing = {"id", "text", "type"} - set(q.keys())
                if missing:
                    for mf in sorted(missing):
                        issues.append(_err(
                            f"questions[{i}].{mf}",
                            f"Missing required field '{mf}'.",
                            "Each question needs id, text, type.",
                        ))
                if q.get("type") and q["type"] not in valid_types:
                    issues.append(_err(f"questions[{i}].type",
                                       f"Invalid type '{q['type']}'.",
                                       f"Allowed: {sorted(valid_types)}"))

    elif endpoint == "/text-lid":
        if not body.get("input"):
            issues.append(_err("input", "Required."))

    elif endpoint == "/transliterate":
        for f in ("input", "source_language_code", "target_language_code"):
            if not body.get(f):
                issues.append(_err(f, f"Required field '{f}' missing."))

    return issues
