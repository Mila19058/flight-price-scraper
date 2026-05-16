from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .parser import (
    parse_currency,
    parse_direct_flight,
    parse_duration_minutes,
    parse_price,
)

# Flughäfen (IATA) → Stadtgruppe für die Auswertung
_DESTINATION_GROUP_AIRPORTS: dict[str, str] = {
    "BER": "Berlin",
    "FCO": "Rom",
    "BCN": "Barcelona",
    "CDG": "Paris",
}
_LONDON_AIRPORTS = frozenset({"LHR", "LGW", "LCY", "LTN", "STN"})

_WEEKDAY_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

_DEDUPE_COLUMNS = (
    "origin",
    "departure_date_clean",
    "price_text",
    "carrier",
    "departure_time",
    "departure_airport",
    "destination_time",
    "destination_airport",
    "duration",
)

# Bekannte Tippfehler in der Raw-CSV (Rohtext vor pd.to_datetime ersetzen).
DATE_CORRECTIONS: dict[str, str] = {
    "2026-24": "2026-07-24",
}


@dataclass
class ProcessingStats:
    """Zähler für die Ausgabe nach dem Processing."""

    raw_rows: int = 0
    corrected_dates: int = 0
    invalid_date_dropped: int = 0
    duplicates_removed: int = 0
    processed_rows: int = 0


def _strip_text_cell(value) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    if isinstance(value, str):
        return value.strip()
    return value


def _empty_strings_to_na(series: pd.Series) -> pd.Series:
    def _cell(x: object) -> object:
        if isinstance(x, str) and x == "":
            return pd.NA
        return x

    return series.map(_cell)


def _destination_group(airport_code: object) -> str:
    if pd.isna(airport_code) or airport_code is None:
        return "Other"
    code = str(airport_code).strip().upper()
    if not code:
        return "Other"
    if code in _LONDON_AIRPORTS:
        return "London"
    return _DESTINATION_GROUP_AIRPORTS.get(code, "Other")


def save_to_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    df = pd.DataFrame(rows)
    if path.exists():
        df.to_csv(path, index=False, mode="a", header=False, encoding="utf-8")
    else:
        df.to_csv(path, index=False, mode="w", header=True, encoding="utf-8")


def load_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8")


def clean_flight_data(
    df: pd.DataFrame, stats: ProcessingStats | None = None
) -> pd.DataFrame:
    """
    Bereinigt Rohdaten: Text, Datums- und Preisfelder, Dauer, 
    Zielgruppe, entfernt ungültige Datumszeilen und Duplikate.
    """
    if stats is not None:
        stats.raw_rows = int(len(df))

    if df.empty:
        return df.copy()

    out = df.copy()
    out = out.dropna(how="all")

    # --- 1) Text: Whitespace, leere Strings → NaN ---
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].map(_strip_text_cell)
            out[col] = _empty_strings_to_na(out[col])

    if "origin" in out.columns:
        out["origin"] = out["origin"].map(
            lambda x: str(x).strip().upper() if pd.notna(x) else x
        )
    for col in ("departure_airport", "destination_airport"):
        if col in out.columns:
            out[col] = out[col].map(
                lambda x: str(x).strip().upper() if pd.notna(x) else x
            )

    # --- 2) Abflugdatum (datetime + abgeleitete Spalten) ---
    if "departure_date" not in out.columns:
        out["departure_date"] = pd.NaT

    if DATE_CORRECTIONS:
        keys = out["departure_date"].map(
            lambda x: str(x).strip() if pd.notna(x) else None
        )
        replacement = keys.map(
            lambda k: DATE_CORRECTIONS[k]
            if k is not None and k in DATE_CORRECTIONS
            else pd.NA
        )
        fix_mask = replacement.notna()
        if stats is not None:
            stats.corrected_dates = int(fix_mask.sum())
        if fix_mask.any():
            out.loc[fix_mask, "departure_date"] = replacement.loc[fix_mask].values
        elif stats is not None:
            stats.corrected_dates = 0

    n_before_dates = len(out)
    dep = pd.to_datetime(out["departure_date"], errors="coerce")
    invalid_mask = dep.isna()
    out = out.loc[~invalid_mask].copy()
    dep = dep.loc[out.index]

    if stats is not None:
        stats.invalid_date_dropped = n_before_dates - len(out)

    if len(out) == 0:
        if stats is not None:
            stats.processed_rows = 0
            stats.duplicates_removed = 0
        return out.reset_index(drop=True)

    out["departure_date"] = dep
    out["departure_date_clean"] = dep.dt.strftime("%Y-%m-%d")
    wd = dep.dt.weekday
    out["weekday_num"] = wd.astype("Int64")
    out["weekday"] = wd.map(lambda i: _WEEKDAY_EN[int(i)])

    # --- 3) Scrape-Zeitpunkt & Buchungsvorlauf ---
    if "scrape_timestamp" not in out.columns:
        out["scrape_timestamp"] = pd.NaT

    scrape_dt = pd.to_datetime(out["scrape_timestamp"], errors="coerce")
    out["scrape_timestamp"] = scrape_dt

    dep_day = dep.dt.normalize()
    scrape_day = scrape_dt.dt.normalize()
    out["booking_lead_days"] = (dep_day - scrape_day).dt.days
    missing = dep_day.isna() | scrape_day.isna()
    out.loc[missing, "booking_lead_days"] = pd.NA

    # --- 4) Preis & Währung ---
    if "price_text" in out.columns:
        out["price"] = out["price_text"].map(parse_price)
        out["currency"] = out["price_text"].map(parse_currency)

    # --- 5) Dauer (Minuten), Direktflug aus stops ---
    if "duration" in out.columns:
        out["duration_minutes"] = out["duration"].map(parse_duration_minutes)

    if "stops" in out.columns:
        out["is_direct"] = out["stops"].map(parse_direct_flight)

    # --- 6) destination_group ---
    if "destination_airport" in out.columns:
        out["destination_group"] = out["destination_airport"].map(_destination_group)
    else:
        out["destination_group"] = pd.Series("Other", index=out.index)

    # --- 7) Duplikate ---
    subset = [c for c in _DEDUPE_COLUMNS if c in out.columns]
    if subset:
        n_before_dup = len(out)
        out = out.drop_duplicates(subset=subset, keep="first")
        if stats is not None:
            stats.duplicates_removed = n_before_dup - len(out)

    if stats is not None:
        stats.processed_rows = len(out)

    return out.reset_index(drop=True)


def print_processing_summary(stats: ProcessingStats, df: pd.DataFrame) -> None:
    """Gibt Kennzahlen und einfache Plausibilitätsprüfungen im Terminal aus."""
    print()
    print("=== Processing-Zusammenfassung ===")
    print(f"Raw-Zeilen:                  {stats.raw_rows}")
    print(f"Korrigierte Abflugdaten:     {stats.corrected_dates}")
    print(f"Entfernt (Datumsfehler):     {stats.invalid_date_dropped}")
    print(f"Entfernt (Duplikate):        {stats.duplicates_removed}")
    print(f"Processed-Zeilen:            {stats.processed_rows}")

    if df.empty:
        print("(Keine Zeilen nach der Bereinigung.)")
        return

    if "origin" in df.columns:
        print()
        print("Zeilen pro origin:")
        for name, cnt in df["origin"].value_counts().sort_index().items():
            print(f"  {name}: {int(cnt)}")

    if "departure_date_clean" in df.columns:
        dates = pd.to_datetime(df["departure_date_clean"], errors="coerce")
        dates = dates.dropna()
        if len(dates):
            print()
            print(
                "Datumsbereich (Abflug): "
                f"{dates.min().date()} … {dates.max().date()}"
            )

    if "destination_group" in df.columns:
        print()
        print("Flüge pro destination_group:")
        for name, cnt in df["destination_group"].value_counts().sort_index().items():
            print(f"  {name}: {int(cnt)}")

    print()


def build_processed_csv(raw_path: Path | str, output_path: Path | str) -> pd.DataFrame:
    """Lädt Roh-CSV, bereinigt, speichert Processed-CSV und druckt die Zusammenfassung."""
    raw_path = Path(raw_path)
    output_path = Path(output_path)

    raw = load_csv(raw_path)
    if raw.empty:
        print(f"[INFO] Keine Rohdaten: {raw_path}")
        return raw

    stats = ProcessingStats()
    cleaned = clean_flight_data(raw, stats=stats)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False, encoding="utf-8")

    print_processing_summary(stats, cleaned)
    print(f"[OK] Processed CSV geschrieben: {output_path}")

    return cleaned
