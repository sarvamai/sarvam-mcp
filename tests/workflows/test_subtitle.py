from sarvam_mcp.workflows.subtitle import _format_timestamp, _build_subtitle_blocks

def test_format_timestamp_srt():
    assert _format_timestamp(1.5, fmt="srt") == "00:00:01,500"
    assert _format_timestamp(3661.05, fmt="srt") == "01:01:01,050"

def test_format_timestamp_vtt():
    assert _format_timestamp(1.5, fmt="vtt") == "00:00:01.500"

def test_build_subtitle_blocks_srt():
    timestamps = [
        {"word": "Hello", "start_time_seconds": 0.0, "end_time_seconds": 0.5},
        {"word": "world", "start_time_seconds": 0.6, "end_time_seconds": 1.0},
    ]
    srt = _build_subtitle_blocks(timestamps, fmt="srt")
    assert "1" in srt
    assert "00:00:00,000 --> 00:00:01,000" in srt
    assert "Hello world" in srt