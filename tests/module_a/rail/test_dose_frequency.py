from src.module_a.rail.dose_frequency import parse_doses_per_day


def test_parses_leading_triplet():
    assert parse_doses_per_day("1-0-1 x 5d") == 2
    assert parse_doses_per_day("0-0-1") == 1
    assert parse_doses_per_day("1-1-1 x 3d") == 3


def test_sos_is_unparseable_not_zero():
    assert parse_doses_per_day("SOS") is None


def test_empty_or_none_is_unparseable():
    assert parse_doses_per_day("") is None
    assert parse_doses_per_day(None) is None
