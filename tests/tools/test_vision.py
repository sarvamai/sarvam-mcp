"""Vision tool tests — download-files call logic, error propagation.

Tests validate that ``DOC_JOB_DOWNLOAD`` is a correctly-formed endpoint
constant and that ``sc.client.post_json`` is called with the right path.
The existing ``test_client.py`` verifies client-level error mapping and auth;
we test the vision-specific constants and endpoint composition here.
"""

from __future__ import annotations

import pytest

from sarvam_mcp.tools.vision import DOC_JOB_BASE, DOC_JOB_DOWNLOAD, DOC_JOB_UPLOAD


def test_endpoint_constants_are_consistent():
    """All endpoint constants must derive from the same base."""
    assert DOC_JOB_BASE == "/doc-digitization/job/v1"
    assert f"{DOC_JOB_BASE}/upload-files" == DOC_JOB_UPLOAD
    assert f"{DOC_JOB_BASE}/{{job_id}}/download-files" == DOC_JOB_DOWNLOAD


def test_download_endpoint_formats_correctly():
    """The download-files endpoint with a concrete job_id must produce a valid path."""
    job_id = "job_doc_1234"
    path = DOC_JOB_DOWNLOAD.format(job_id=job_id)
    assert path == "/doc-digitization/job/v1/job_doc_1234/download-files"


async def test_client_calls_download_for_completed_job(httpx_mock):
    """Verify that post_json(DOC_JOB_DOWNLOAD) is reachable and returns download_urls."""
    from sarvam_mcp.http import SarvamClient

    client = SarvamClient("https://api.sarvam.ai")
    job_id = "job_doc_5678"
    path = DOC_JOB_DOWNLOAD.format(job_id=job_id)

    expected_urls = [
        "https://storage.example.com/outputs/job_doc_5678.zip?sig=abc",
    ]
    httpx_mock.add_response(
        method="POST",
        url=f"https://api.sarvam.ai{path}",
        json={"download_urls": expected_urls},
    )

    resp, _ = await client.post_json(path, json_body={})
    assert resp["download_urls"] == expected_urls


async def test_client_download_endpoint_rejects_missing_body(httpx_mock):
    """The API returns 400 if the body is missing — this tests the error path."""
    from sarvam_mcp.http import SarvamClient
    from sarvam_mcp.http.errors import SarvamBadRequestError

    client = SarvamClient("https://api.sarvam.ai")
    job_id = "job_doc_9999"
    path = DOC_JOB_DOWNLOAD.format(job_id=job_id)

    httpx_mock.add_response(
        method="POST",
        url=f"https://api.sarvam.ai{path}",
        status_code=400,
        json={"error": "missing request body"},
    )

    with pytest.raises(SarvamBadRequestError):
        await client.post_json(path, json_body={})
