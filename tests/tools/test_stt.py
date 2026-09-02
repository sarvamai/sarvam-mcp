"""sarvam_tools_stt_batch_submit — full job lifecycle including download.

Regression coverage for a bug where the tool polled ``/status`` to
``Completed`` but never called ``POST .../download-files``, so it always
returned an empty transcript: ``/status`` never carries ``transcript``,
``result``, or ``download_urls`` (confirmed against the live OpenAPI spec at
docs.sarvam.ai) — only ``job_details[].outputs[].file_name``, which must be
passed to ``download-files`` to get a signed URL for the actual output file.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastmcp import Client, FastMCP

from sarvam_mcp._registry import ServerContext
from sarvam_mcp.audio.sinks import build_sink
from sarvam_mcp.config import Config
from sarvam_mcp.http import SarvamClient
from sarvam_mcp.tools import stt

BASE = "https://api.sarvam.ai"


@pytest.fixture
async def stt_server(tmp_path):
    client = SarvamClient(BASE)

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield ServerContext(
                config=Config(),
                client=client,
                audio_sink=build_sink("files", tmp_path),
            )
        finally:
            await client.aclose()

    mcp = FastMCP("test", lifespan=lifespan)
    stt.register(mcp)
    return mcp


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "meeting.wav"
    path.write_bytes(b"RIFF....WAVEfmt ")
    return path


def _mock_happy_path(httpx_mock, *, with_diarization=False):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1",
        json={
            "job_id": "job-1",
            "job_state": "Accepted",
            "storage_container_type": "Azure",
            "job_parameters": {},
        },
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1/upload-files",
        json={
            "job_id": "job-1",
            "job_state": "Accepted",
            "storage_container_type": "Azure",
            "upload_urls": {"meeting.wav": {"file_url": "https://blob.example/upload/meeting.wav"}},
        },
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://blob.example/upload/meeting.wav",
        status_code=201,
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1/job-1/start",
        json={"job_id": "job-1", "job_state": "Running"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/speech-to-text/job/v1/job-1/status",
        json={
            "job_id": "job-1",
            "job_state": "Completed",
            "created_at": "2026-07-18T00:00:00Z",
            "updated_at": "2026-07-18T00:01:00Z",
            "storage_container_type": "Azure",
            "total_files": 1,
            "successful_files_count": 1,
            "failed_files_count": 0,
            "job_details": [
                {
                    "inputs": [{"file_name": "meeting.wav", "file_id": "file-1"}],
                    "outputs": [{"file_name": "0.json", "file_id": "file-1-out"}],
                    "state": "Success",
                }
            ],
        },
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1/download-files",
        json={
            "job_id": "job-1",
            "job_state": "Completed",
            "storage_container_type": "Azure",
            "download_urls": {"0.json": {"file_url": "https://blob.example/output/0.json"}},
        },
    )
    output_body: dict[str, Any] = {
        "request_id": "req-1",
        "transcript": "Speaker 1: hello. Speaker 2: hi there.",
        "language_code": "hi-IN",
    }
    if with_diarization:
        output_body["diarized_transcript"] = {
            "entries": [
                {
                    "transcript": "hello",
                    "start_time_seconds": 0.0,
                    "end_time_seconds": 1.0,
                    "speaker_id": "0",
                },
                {
                    "transcript": "hi there",
                    "start_time_seconds": 1.2,
                    "end_time_seconds": 2.5,
                    "speaker_id": "1",
                },
            ]
        }
    httpx_mock.add_response(
        method="GET",
        url="https://blob.example/output/0.json",
        json=output_body,
    )


async def test_batch_submit_downloads_and_returns_transcript(stt_server, httpx_mock, audio_file):
    _mock_happy_path(httpx_mock)

    async with Client(stt_server) as client:
        result = await client.call_tool("sarvam_tools_stt_batch_submit", {"audio_path": str(audio_file)})

    data = result.structured_content
    assert data is not None
    assert data["job_state"] == "Completed"
    assert data["transcript"] == "Speaker 1: hello. Speaker 2: hi there."
    assert data["language_code"] == "hi-IN"


async def test_batch_submit_returns_diarized_entries(stt_server, httpx_mock, audio_file):
    _mock_happy_path(httpx_mock, with_diarization=True)

    async with Client(stt_server) as client:
        result = await client.call_tool(
            "sarvam_tools_stt_batch_submit",
            {"audio_path": str(audio_file), "with_diarization": True, "num_speakers": 2},
        )

    data = result.structured_content
    assert data is not None
    entries = data["diarized_transcript"]["entries"]
    assert [e["speaker_id"] for e in entries] == ["0", "1"]
    assert entries[0]["transcript"] == "hello"


async def test_batch_submit_with_no_successful_outputs_returns_empty_transcript(
    stt_server, httpx_mock, audio_file
):
    # A job that completes with zero successful files should not attempt a
    # download-files call at all, and must not error.
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1",
        json={"job_id": "job-2", "job_state": "Accepted", "storage_container_type": "Azure"},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1/upload-files",
        json={
            "job_id": "job-2",
            "job_state": "Accepted",
            "storage_container_type": "Azure",
            "upload_urls": {"meeting.wav": {"file_url": "https://blob.example/upload/meeting.wav"}},
        },
    )
    httpx_mock.add_response(method="PUT", url="https://blob.example/upload/meeting.wav", status_code=201)
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE}/speech-to-text/job/v1/job-2/start",
        json={"job_id": "job-2", "job_state": "Running"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/speech-to-text/job/v1/job-2/status",
        json={
            "job_id": "job-2",
            "job_state": "Failed",
            "created_at": "2026-07-18T00:00:00Z",
            "updated_at": "2026-07-18T00:01:00Z",
            "storage_container_type": "Azure",
            "total_files": 1,
            "successful_files_count": 0,
            "failed_files_count": 1,
            "job_details": [
                {
                    "inputs": [{"file_name": "meeting.wav", "file_id": "file-1"}],
                    "outputs": [],
                    "state": "API Error",
                    "error_message": "decode failure",
                }
            ],
        },
    )

    async with Client(stt_server) as client:
        result = await client.call_tool("sarvam_tools_stt_batch_submit", {"audio_path": str(audio_file)})

    data = result.structured_content
    assert data is not None
    assert data["job_state"] == "Failed"
    assert data["transcript"] == ""
