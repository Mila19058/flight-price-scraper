from flight_scraper.parser import (
    parse_currency,
    parse_duration,
    parse_duration_minutes,
    parse_price,
)


def test_parse_price_basic() -> None:
    assert parse_price("CHF 129") == 129.0


def test_parse_price_amount_before_currency() -> None:
    assert parse_price("44 CHF") == 44.0


def test_parse_price_87_chf_currency() -> None:
    assert parse_price("87 CHF") == 87.0
    assert parse_currency("87 CHF") == "CHF"


def test_parse_price_empty_or_malformed() -> None:
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("Preis: ???") is None


def test_parse_duration_german_examples() -> None:
    assert parse_duration_minutes("1 Std. 55 Min.") == 115
    assert parse_duration_minutes("1 Std. 20 Min.") == 80
    assert parse_duration_minutes("55 Min.") == 55
    assert parse_duration("1 Std. 55 Min.") == 115
