"""Tested code snippets for the most-used Sarvam APIs.

Each entry is verified against api.sarvam.ai with current models as of
2026-04-27. Update when model defaults shift.

Format: ``SNIPPETS[(api, language)] = code_string``
"""

from __future__ import annotations

# fmt: off

PY_TTS = '''\
"""Generate Indic speech via the current TTS API (bulbul:v3)."""
import base64, os, httpx

API_KEY = os.environ["SARVAM_API_KEY"]

resp = httpx.post(
    "https://api.sarvam.ai/text-to-speech",
    headers={"api-subscription-key": API_KEY},
    json={
        "inputs": ["नमस्ते, आज मौसम कैसा है?"],
        "target_language_code": "hi-IN",
        "speaker": "priya",         # v3 voice; see sarvam_code_speakers
        "model": "bulbul:v3",
        "speech_sample_rate": 24000,
        "enable_preprocessing": True,
    },
    timeout=60.0,
)
resp.raise_for_status()
data = resp.json()
wav_bytes = base64.b64decode(data["audios"][0])
with open("hello.wav", "wb") as fh:
    fh.write(wav_bytes)
print(f"wrote {len(wav_bytes)} bytes — request_id={data.get('request_id')}")
'''

JS_TTS = '''\
// Generate Indic speech (bulbul:v3).
import { writeFileSync } from "node:fs";

const API_KEY = process.env.SARVAM_API_KEY;
const resp = await fetch("https://api.sarvam.ai/text-to-speech", {
  method: "POST",
  headers: {
    "api-subscription-key": API_KEY,
    "content-type": "application/json",
  },
  body: JSON.stringify({
    inputs: ["नमस्ते, आज मौसम कैसा है?"],
    target_language_code: "hi-IN",
    speaker: "priya",          // v3 voice
    model: "bulbul:v3",
    speech_sample_rate: 24000,
    enable_preprocessing: true,
  }),
});
if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
const data = await resp.json();
const wav = Buffer.from(data.audios[0], "base64");
writeFileSync("hello.wav", wav);
console.log(`wrote ${wav.length} bytes — request_id=${data.request_id}`);
'''

CURL_TTS = '''\
# Generate Hindi speech (bulbul:v3).
curl -sS https://api.sarvam.ai/text-to-speech \\
  -H "api-subscription-key: $SARVAM_API_KEY" \\
  -H "content-type: application/json" \\
  -d '{
    "inputs": ["नमस्ते, आज मौसम कैसा है?"],
    "target_language_code": "hi-IN",
    "speaker": "priya",
    "model": "bulbul:v3",
    "speech_sample_rate": 24000
  }' \\
  | jq -r '.audios[0]' | base64 -d > hello.wav
'''

PY_STT = '''\
"""Transcribe Indic audio via Saaras v4."""
import os, httpx

API_KEY = os.environ["SARVAM_API_KEY"]

with open("input.wav", "rb") as fh:
    files = {"file": ("input.wav", fh, "audio/wav")}
    data  = {"model": "saaras:v4", "language_code": "hi-IN", "with_timestamps": "false"}
    resp = httpx.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={"api-subscription-key": API_KEY},
        data=data,
        files=files,
        timeout=120.0,
    )
resp.raise_for_status()
print(resp.json()["transcript"])
'''

JS_STT = '''\
// Transcribe Indic audio via Saaras v4.
import { readFileSync } from "node:fs";

const API_KEY = process.env.SARVAM_API_KEY;
const wav = readFileSync("input.wav");

const form = new FormData();
form.set("file", new Blob([wav], { type: "audio/wav" }), "input.wav");
form.set("model", "saaras:v4");
form.set("language_code", "hi-IN");
form.set("with_timestamps", "false");

const resp = await fetch("https://api.sarvam.ai/speech-to-text", {
  method: "POST",
  headers: { "api-subscription-key": API_KEY },
  body: form,
});
if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
const data = await resp.json();
console.log(data.transcript);
'''

CURL_STT = '''\
curl -sS https://api.sarvam.ai/speech-to-text \\
  -H "api-subscription-key: $SARVAM_API_KEY" \\
  -F "file=@input.wav;type=audio/wav" \\
  -F "model=saaras:v4" \\
  -F "language_code=hi-IN" \\
  -F "with_timestamps=false" \\
  | jq .transcript
'''

PY_TRANSLATE = '''\
"""Translate text between Indian languages via Mayura v1."""
import os, httpx

API_KEY = os.environ["SARVAM_API_KEY"]

resp = httpx.post(
    "https://api.sarvam.ai/translate",
    headers={"api-subscription-key": API_KEY},
    json={
        "input": "Hello, how are you doing today?",
        "source_language_code": "en-IN",
        "target_language_code": "hi-IN",
        "model": "mayura:v1",
        "mode": "modern-colloquial",
        "numerals_format": "international",
    },
    timeout=30.0,
)
resp.raise_for_status()
print(resp.json()["translated_text"])
'''

JS_TRANSLATE = '''\
const API_KEY = process.env.SARVAM_API_KEY;
const resp = await fetch("https://api.sarvam.ai/translate", {
  method: "POST",
  headers: {
    "api-subscription-key": API_KEY,
    "content-type": "application/json",
  },
  body: JSON.stringify({
    input: "Hello, how are you doing today?",
    source_language_code: "en-IN",
    target_language_code: "hi-IN",
    model: "mayura:v1",
    mode: "modern-colloquial",
    numerals_format: "international",
  }),
});
if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
const data = await resp.json();
console.log(data.translated_text);
'''

CURL_TRANSLATE = '''\
curl -sS https://api.sarvam.ai/translate \\
  -H "api-subscription-key: $SARVAM_API_KEY" \\
  -H "content-type: application/json" \\
  -d '{
    "input": "Hello, how are you doing today?",
    "source_language_code": "en-IN",
    "target_language_code": "hi-IN",
    "model": "mayura:v1",
    "mode": "modern-colloquial"
  }' | jq .translated_text
'''

PY_LLM = '''\
"""Chat with Sarvam LLM (OpenAI-compatible).

Accepted model id: sarvam-105b (flagship, the sole current chat model).
"""
import os, httpx

API_KEY = os.environ["SARVAM_API_KEY"]
MODEL = "sarvam-105b"

resp = httpx.post(
    "https://api.sarvam.ai/v1/chat/completions",
    headers={"api-subscription-key": API_KEY},
    json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise Indic-language assistant."},
            {"role": "user",   "content": "Translate 'good morning' into Tamil and Marathi."},
        ],
        "temperature": 0.3,
        "max_tokens": 200,
    },
    timeout=60.0,
)
resp.raise_for_status()
print(resp.json()["choices"][0]["message"]["content"])
'''

JS_LLM = '''\
// Accepted model id: sarvam-105b (flagship, the sole current chat model).
const API_KEY = process.env.SARVAM_API_KEY;
const MODEL = "sarvam-105b";
const resp = await fetch("https://api.sarvam.ai/v1/chat/completions", {
  method: "POST",
  headers: {
    "api-subscription-key": API_KEY,
    "content-type": "application/json",
  },
  body: JSON.stringify({
    model: MODEL,
    messages: [
      { role: "system", content: "You are a concise Indic-language assistant." },
      { role: "user",   content: "Translate 'good morning' into Tamil and Marathi." },
    ],
    temperature: 0.3,
    max_tokens: 200,
  }),
});
const data = await resp.json();
console.log(data.choices[0].message.content);
'''

CURL_LLM = '''\
# Accepted model id: sarvam-105b (flagship, the sole current chat model).
curl -sS https://api.sarvam.ai/v1/chat/completions \\
  -H "api-subscription-key: $SARVAM_API_KEY" \\
  -H "content-type: application/json" \\
  -d '{
    "model": "sarvam-105b",
    "messages": [
      {"role": "user", "content": "Translate good morning to Tamil"}
    ],
    "max_tokens": 100
  }' | jq -r '.choices[0].message.content'
'''

# fmt: on


SNIPPETS: dict[tuple[str, str], str] = {
    ("tts", "python"):           PY_TTS,
    ("tts", "javascript"):       JS_TTS,
    ("tts", "typescript"):       JS_TTS,   # same modern Node code works
    ("tts", "curl"):             CURL_TTS,
    ("stt", "python"):           PY_STT,
    ("stt", "javascript"):       JS_STT,
    ("stt", "typescript"):       JS_STT,
    ("stt", "curl"):             CURL_STT,
    ("translate", "python"):     PY_TRANSLATE,
    ("translate", "javascript"): JS_TRANSLATE,
    ("translate", "typescript"): JS_TRANSLATE,
    ("translate", "curl"):       CURL_TRANSLATE,
    ("llm", "python"):           PY_LLM,
    ("llm", "javascript"):       JS_LLM,
    ("llm", "typescript"):       JS_LLM,
    ("llm", "curl"):             CURL_LLM,
}
