from __future__ import annotations

import re

import pandas as pd

_CURRENCY = r"(?:[A-Z]{3}|CHF|EUR|USD|GBP)"
_AMOUNT = r"\d+(?:[.,]\d+)?"
# Booking zeigt oft «44 CHF»; andere Quellen «CHF 129».
_PRICE_RE = re.compile(
    rf"(?:{_CURRENCY}\s*(?P<amount_after>{_AMOUNT})|(?P<amount_before>{_AMOUNT})\s*{_CURRENCY})",
    re.IGNORECASE,
)

_TIME_RE = re.compile(r"(?P<h>\d{1,2})[:.](?P<m>\d{2})")

_DURATION_RE = re.compile(
    r"(?:(?P<hours>\d+)\s*h)?\s*(?:(?P<minutes>\d+)\s*m)?",
    re.IGNORECASE,
)


def _price_match(text: str):
    return _PRICE_RE.search(text.strip())


def parse_price(text: str | None) -> float | None:
    """Extrahiert den Preis als float, z. B. «44 CHF» oder «CHF 129» -> 129.0."""
    if not text:
        return None

    m = _price_match(text)
    if not m:
        return None

    amount_raw = (m.group("amount_before") or m.group("amount_after") or "").replace(",", ".")
    try:
        return float(amount_raw)
    except ValueError:
        return None


def parse_currency(text: str | None) -> str | None:
    if not text:
        return None
    m = _price_match(text)
    if not m:
        return None
    currency = m.group(0)
    for token in ("CHF", "EUR", "USD", "GBP"):
        if token in currency.upper():
            return token
    code_match = re.search(r"[A-Z]{3}", currency, re.IGNORECASE)
    return code_match.group(0).upper() if code_match else None


def parse_time(text: str | None) -> str | None:
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    h = int(m.group("h"))
    minute = int(m.group("m"))
    if not (0 <= h <= 23 and 0 <= minute <= 59):
        return None
    return f"{h:02d}:{minute:02d}"


def parse_duration_minutes(text: str | None) -> int | None:
    """
    Dauer in Minuten aus Booking-Text, z. B. «1 Std. 55 Min.» oder «55 Min.».
    """
    if text is None or pd.isna(text):
        return None

    s = str(text).strip()
    if not s:
        return None

    h_match = re.search(r"(\d+)\s*Std", s, re.IGNORECASE)
    m_match = re.search(r"(\d+)\s*Min", s, re.IGNORECASE)
    if not h_match and not m_match:
        return None

    total = 0
    if h_match:
        total += int(h_match.group(1)) * 60
    if m_match:
        total += int(m_match.group(1))
    return total


def parse_duration(text: str | None) -> int | None:
    """Alias für das Booking-Format (Std. / Min.). Ältere «2h 30m»-Schreibweise optional."""
    direct = parse_duration_minutes(text)
    if direct is not None:
        return direct

    if not text:
        return None

    m = _DURATION_RE.search(str(text))
    if not m:
        return None

    hours_raw = m.group("hours")
    minutes_raw = m.group("minutes")
    if hours_raw is None and minutes_raw is None:
        return None

    try:
        hours = int(hours_raw) if hours_raw is not None else 0
        minutes = int(minutes_raw) if minutes_raw is not None else 0
    except ValueError:
        return None

    if hours < 0 or minutes < 0:
        return None

    return hours * 60 + minutes


def parse_airline(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split()).strip()
    return cleaned or None


def parse_direct_flight(text: str | None) -> bool | None:
    if not text:
        return None

    t = text.lower()
    if "direct" in t or "direkt" in t or "nonstop" in t or "non-stop" in t:
        return True
    if "1 stop" in t or "1 stopp" in t or "umstieg" in t or "stopover" in t:
        return False
    return None
