from sarvam_mcp.workflows.subtitle import _build_subtitle_blocks, _format_timestamp


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


def test_build_subtitle_blocks_vtt():
    timestamps = [
        {"word": "Namaste", "start_time_seconds": 0.0, "end_time_seconds": 0.5},
        {"word": "duniya", "start_time_seconds": 0.6, "end_time_seconds": 1.0},
    ]
    vtt = _build_subtitle_blocks(timestamps, fmt="vtt")
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.000" in vtt
    assert "Namaste duniya" in vtt


def test_build_subtitle_blocks_duration_split():
    timestamps = [
        {"word": "Slow", "start_time_seconds": 0.0, "end_time_seconds": 6.0},
        {"word": "speaker", "start_time_seconds": 6.1, "end_time_seconds": 12.0},
    ]
    srt = _build_subtitle_blocks(timestamps, fmt="srt", max_words_per_block=8, max_duration_seconds=5.0)
    assert "1\n00:00:00,000 --> 00:00:06,000\nSlow\n" in srt
    assert "2\n00:00:06,100 --> 00:00:12,000\nspeaker\n" in srt
