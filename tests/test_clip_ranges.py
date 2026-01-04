import pytest

from videoclipper.clipper import ClipperError, parse_clip_ranges, parse_time


def test_parse_time_seconds():
    assert parse_time("120") == 120


def test_parse_time_rejects_non_integer():
    with pytest.raises(ClipperError):
        parse_time("1.5")


def test_parse_time_mm_ss():
    assert parse_time("01:30") == 90


def test_parse_time_hh_mm_ss():
    assert parse_time("1:02:03") == 3723


def test_parse_time_rejects_invalid_components():
    with pytest.raises(ClipperError):
        parse_time("1:60")
    with pytest.raises(ClipperError):
        parse_time("1:02:60")
    with pytest.raises(ClipperError):
        parse_time("1:2:3:4")


def test_parse_clip_ranges_multiple():
    assert parse_clip_ranges("10-30, 40-50") == [(10, 30), (40, 50)]


def test_parse_clip_ranges_rejects_invalid_order():
    with pytest.raises(ClipperError):
        parse_clip_ranges("30-10")
