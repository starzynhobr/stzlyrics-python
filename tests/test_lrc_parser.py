from app.services.lyrics_sync import LyricsSynchronizer, parse_lrc


def test_parse_lrc_synced_lines_sorted_and_repeated_timestamps():
    raw = """
    [ar:Artist]
    [00:10.00]Line A
    [00:05.00]Line B
    [00:15.00][00:20.00]Line C
    """
    parsed = parse_lrc(raw)
    assert parsed.is_synced is True
    assert [round(line.time_seconds, 2) for line in parsed.lines] == [5.0, 10.0, 15.0, 20.0]
    assert [line.text for line in parsed.lines] == ["Line B", "Line A", "Line C", "Line C"]


def test_parse_lrc_plain_text_fallback():
    raw = "primeira linha\nsegunda linha"
    parsed = parse_lrc(raw)
    assert parsed.is_synced is False
    assert parsed.first_plain_line == "primeira linha"


def test_synchronizer_incremental_and_rewind():
    parsed = parse_lrc("[00:01.00]A\n[00:02.00]B\n[00:03.00]C")
    sync = LyricsSynchronizer()
    sync.load(parsed)

    assert sync.current_line(0.4) == "A"
    assert sync.current_line(1.8) == "A"
    assert sync.current_line(2.1) == "B"
    assert sync.current_line(3.2) == "C"
    assert sync.current_line(1.1) == "A"  # rewind resets cursor

