"""Tool-registration helpers + shared context plumbed into every tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sarvam_mcp.audio import AudioSink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient

if TYPE_CHECKING:
    from sarvam_mcp.tools.update import UpdateInfo


@dataclass
class ServerContext:
    """The bundle every tool needs. Stashed on the FastMCP lifespan context."""

    config: Config
    client: SarvamClient
    audio_sink: AudioSink
    update_info: UpdateInfo | None = field(default=None)
