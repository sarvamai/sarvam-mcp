"""Get the full bulbul:v3 speaker list by triggering the validation error."""

from __future__ import annotations

import asyncio

from sarvam_mcp.auth import StaticKeyProvider, set_auth
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient


async def main():
    cfg = Config.load()
    set_auth(StaticKeyProvider(cfg.api_key))  # type: ignore[arg-type]
    c = SarvamClient(cfg.base_url)
    try:
        await c.post_json(
            "/text-to-speech",
            json_body={
                "inputs": ["test"],
                "target_language_code": "hi-IN",
                "speaker": "_____invalid_speaker_____",
                "model": "bulbul:v3",
            },
        )
    except Exception as exc:
        print(str(exc))
    await c.aclose()


if __name__ == "__main__":
    asyncio.run(main())
