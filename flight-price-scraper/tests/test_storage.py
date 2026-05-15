from __future__ import annotations

from datetime import datetime

import pandas as pd

from flight_scraper.parser import parse_price
from flight_scraper.storage import (
    ProcessingStats,
    clean_flight_data,
    load_csv,
    save_to_csv,
)


def test_save_and_load_csv(tmp_path) -> None:
    path = tmp_path / "x.csv"
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    save_to_csv(rows, path)
    df = load_csv(path)
    assert len(df) == 2
    assert set(df.columns) >= {"a", "b"}


def test_clean_adds_weekday_and_booking_lead_days() -> None:
    df = pd.DataFrame(
        [
            {
                "departure_date": "2026-06-01",
                "scrape_timestamp": datetime(2026, 5, 1, 12, 0, 0).isoformat(),
                "price": 100.0,
            }
        ]
    )

    out = clean_flight_data(df)
    assert "weekday" in out.columns
    assert out.loc[0, "weekday"] == "Monday"
    assert "booking_lead_days" in out.columns
    assert int(out.loc[0, "booking_lead_days"]) == 31
    assert int(out.loc[0, "weekday_num"]) == 0


def test_clean_parses_price_from_price_text() -> None:
    df = pd.DataFrame([{"price_text": "44 CHF", "departure_date": "2026-06-01"}])
    out = clean_flight_data(df)
    assert out.loc[0, "price"] == parse_price("44 CHF")
    assert out.loc[0, "currency"] == "CHF"


def test_clean_normalizes_origin() -> None:
    df = pd.DataFrame(
        [
            {
                "origin": "bSL",
                "departure_date": "2026-06-01",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "10 CHF",
            }
        ]
    )
    out = clean_flight_data(df)
    assert out.loc[0, "origin"] == "BSL"


def test_clean_invalid_departure_dropped_not_crash() -> None:
    stats = ProcessingStats()
    df = pd.DataFrame(
        [
            {
                "departure_date": "kein-datum",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "10 CHF",
            },
            {
                "departure_date": "2026-06-10",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "20 CHF",
            },
        ]
    )
    out = clean_flight_data(df, stats=stats)
    assert len(out) == 1
    assert stats.invalid_date_dropped == 1
    assert stats.corrected_dates == 0
    assert out.loc[0, "departure_date_clean"] == "2026-06-10"


def test_clean_corrects_known_typo_departure_date() -> None:
    stats = ProcessingStats()
    df = pd.DataFrame(
        [
            {
                "departure_date": "2026-24",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "10 CHF",
            }
        ]
    )
    out = clean_flight_data(df, stats=stats)
    assert len(out) == 1
    assert out.loc[0, "departure_date_clean"] == "2026-07-24"
    assert stats.corrected_dates == 1
    assert stats.invalid_date_dropped == 0


def test_clean_destination_group_lgw() -> None:
    df = pd.DataFrame(
        [
            {
                "destination_airport": "lgw",
                "departure_date": "2026-06-01",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "1 CHF",
            }
        ]
    )
    out = clean_flight_data(df)
    assert out.loc[0, "destination_airport"] == "LGW"
    assert out.loc[0, "destination_group"] == "London"


def test_clean_deduplicates() -> None:
    stats = ProcessingStats()
    row = {
        "departure_date": "2026-06-01",
        "scrape_timestamp": "2026-05-01 12:00:00",
        "origin": "ZRH",
        "price_text": "44 CHF",
        "carrier": "AirX",
        "departure_time": "10:00",
        "departure_airport": "ZRH",
        "destination_time": "12:00",
        "destination_airport": "BCN",
        "duration": "1 Std. 50 Min.",
    }
    df = pd.DataFrame([row, row])
    out = clean_flight_data(df, stats=stats)
    assert len(out) == 1
    assert stats.duplicates_removed == 1


def test_clean_duration_minutes() -> None:
    df = pd.DataFrame(
        [
            {
                "duration": "1 Std. 55 Min.",
                "departure_date": "2026-06-01",
                "scrape_timestamp": "2026-05-01 12:00:00",
                "price_text": "1 CHF",
            }
        ]
    )
    out = clean_flight_data(df)
    assert out.loc[0, "duration_minutes"] == 115
