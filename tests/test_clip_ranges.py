import pytest

from videoclipper.clipper import ClipperError, parse_clip_ranges, parse_time


def test_parse_time_seconds():
    assert parse_time("120") == 120


def test_parse_time_rejects_non_integer():
    with pytest.raises(ClipperError):
        parse_time("1.5")


def test_parse_time_rejects_mm_ss():
    with pytest.raises(ClipperError):
        parse_time("01:30")


def test_parse_clip_ranges_multiple():
    assert parse_clip_ranges("10-30, 40-50") == [(10, 30), (40, 50)]


def test_parse_clip_ranges_rejects_invalid_order():
    with pytest.raises(ClipperError):
        parse_clip_ranges("30-10")
