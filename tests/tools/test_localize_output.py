"""Output naming and overwrite behavior through the MCP tool."""

from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from sarvam_mcp.workflows import localize


@pytest.fixture
async def localize_tool(monkeypatch):
    translate = AsyncMock(return_value="Namaste")
    monkeypatch.setattr(localize, "ready_ctx", AsyncMock())
    monkeypatch.setattr(localize, "translate_text", translate)
    server = FastMCP("test-localize-output")
    localize.register(server)
    async with Client(server) as client:
        yield client, translate


@pytest.mark.parametrize(
    ("source_name", "output_name"),
    [
        ("checkout.buttons.json", "checkout.buttons.hi-IN.json"),
        ("checkout.errors.json", "checkout.errors.hi-IN.json"),
        ("messages.en.json", "messages.hi-IN.json"),
        ("messages.en-IN.json", "messages.hi-IN.json"),
    ],
)
async def test_default_output_keeps_non_language_suffixes(tmp_path, localize_tool, source_name, output_name):
    client, _ = localize_tool
    src = tmp_path / source_name
    src.write_text('{"hello": "Hello"}')

    result = await client.call_tool(
        "sarvam_tools_localize", {"source_path": str(src), "target_language_code": "hi-IN"}
    )

    assert result.data["output_path"] == str(tmp_path / output_name)
    assert (tmp_path / output_name).is_file()


@pytest.mark.parametrize("source_name", ["messages.hi-IN.json", "messages.en-IN.json"])
async def test_existing_default_output_is_rejected_before_translation(tmp_path, localize_tool, source_name):
    client, translate = localize_tool
    src = tmp_path / source_name
    dst = tmp_path / "messages.hi-IN.json"
    original = '{"hello": "Keep me"}'
    src.write_text(original)
    dst.write_text(original)

    with pytest.raises(ToolError, match="already exists.*output_path"):
        await client.call_tool(
            "sarvam_tools_localize", {"source_path": str(src), "target_language_code": "hi-IN"}
        )

    assert src.read_text() == original
    assert dst.read_text() == original
    translate.assert_not_awaited()


async def test_default_output_created_during_translation_is_preserved(tmp_path, localize_tool):
    client, translate = localize_tool
    src = tmp_path / "messages.en.txt"
    dst = tmp_path / "messages.hi-IN.txt"
    src.write_text("hello=Hello\n")

    async def translate_and_create_output(*args, **kwargs):
        dst.write_text("other writer's content")
        return "Namaste"

    translate.side_effect = translate_and_create_output

    with pytest.raises(ToolError, match="File exists"):
        await client.call_tool(
            "sarvam_tools_localize", {"source_path": str(src), "target_language_code": "hi-IN"}
        )

    assert dst.read_text() == "other writer's content"


async def test_explicit_output_can_replace_an_existing_text_file(tmp_path, localize_tool):
    client, _ = localize_tool
    src = tmp_path / "messages.en.txt"
    dst = tmp_path / "chosen.txt"
    src.write_text("hello=Hello\n")
    dst.write_text("old content")

    await client.call_tool(
        "sarvam_tools_localize",
        {"source_path": str(src), "target_language_code": "hi-IN", "output_path": str(dst)},
    )

    assert src.read_text() == "hello=Hello\n"
    assert dst.read_text() == "hello= Namaste\n"
