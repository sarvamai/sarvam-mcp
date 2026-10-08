"""Headers for presigned storage uploads (Azure Blob by default)."""

from __future__ import annotations

from typing import Any


def presigned_put_headers(
    content_type: str,
    *,
    storage: str | None = None,
    file_metadata: dict[str, Any] | None = None,
    azure: bool = False,
) -> dict[str, str]:
    """Build PUT headers for a Sarvam-issued upload URL.

    Azure jobs need ``x-ms-blob-type: BlockBlob``. ``file_metadata`` from the
    upload-files response overrides anything we guessed.
    """
    headers = {"Content-Type": content_type}
    use_azure = azure or storage in (None, "Azure", "Azure_V1")
    if use_azure:
        headers["x-ms-blob-type"] = "BlockBlob"
    for key, value in (file_metadata or {}).items():
        if isinstance(value, str):
            headers[str(key)] = value
    return headers
