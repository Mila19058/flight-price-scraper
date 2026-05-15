"""
Booking.com Flights: halbautomatischer Ablauf (FHNW LO4).

Hintergrund für die Studienabgabe:
- Booking.com reagiert empfindlich, wenn mehrere Abflughäfen gleichzeitig
  eingegeben werden. Deshalb wird der **Abflugort bewusst manuell** gewählt
  und pro Durchlauf nur EINER (z. B. zuerst ZRH, dann in einem zweiten
  Durchlauf BSL). Der Vergleich Zürich vs. Basel passiert später in der
  Auswertung über die Spalte `origin`.
- Beim **Zielort** funktionieren mehrere Städte gleichzeitig stabil; die
  Standard-Zielliste (London, Berlin, Rom, Barcelona, Paris) wird im
  Terminal angezeigt und automatisch in die CSV-Spalte `destination_city`
  übernommen.

Ablauf pro Durchlauf:
  1) Selenium öffnet Booking.com Flights, akzeptiert Cookies,
     aktiviert «Nur Hinflug» und «Nur Direktflüge».
  2) Im Browser wählt die nutzende Person Abflugort, Ziele und Datum
     und startet die Suche.
  3) Sobald die Trefferliste sichtbar ist: im Terminal Enter drücken.
  4) Das Programm fragt origin, destination_city, departure_date ab.
  5) Selenium liest die Treffer aus (inkl. Pagination «Weiter») und hängt
     die Zeilen an die CSV an.
  6) Frage nach einem weiteren Durchlauf (z. B. zweiter Origin BSL).
"""

from __future__ import annotations

import random
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import CONFIG
from .storage import save_to_csv

BOOKING_FLIGHTS_URL = "https://www.booking.com/flights/index.de.html"

# Nur für die ersten automatischen Klicks (Formular vor manuellen Suche) ---

SEL_COOKIE_ACCEPT_BUTTON = "button#onetrust-accept-btn-handler"

# «Nur Hinflug» – Booking kann data-ui-name ändern; Reihenfolge = Reihenfolge der Versuche.
# Bei Timeout: F12, Element inspizieren, passenden Selektor ergänzen.
SEL_ONE_WAY_CANDIDATES: tuple[str, ...] = (
    '[data-ui-name="input_search_type_oneway"]',
    '[data-ui-name="input_search_type_one_way"]',
    '[data-ui-name*="oneway"]',
)

SEL_DIRECT_FLIGHTS_CANDIDATES: tuple[str, ...] = (
    '[data-ui-name="direct_flights_input"]',
    '[data-ui-name*="direct_flights"]',
)

# --- Ergebnisseite (nach deiner manuellen Suche) ---

# Booking ändert Test-IDs; die Felder werden einzeln gesammelt und per zip() zu Zeilen kombiniert.
SEL_PRICE = '[data-testid="upt_price"]'
SEL_CARRIER = '[data-testid="flight_card_carriers"]'
SEL_DEPARTURE_TIME = '[data-testid="flight_card_segment_departure_time_0"]'
SEL_DEPARTURE_AIRPORT = '[data-testid="flight_card_segment_departure_airport_0"]'
SEL_DESTINATION_TIME = '[data-testid="flight_card_segment_destination_time_0"]'
SEL_DESTINATION_AIRPORT = '[data-testid="flight_card_segment_destination_airport_0"]'
SEL_STOPS = '[data-testid="flight_card_segment_stops_0"]'
SEL_DURATION = '[data-testid="flight_card_segment_duration_0"]'

# Auf eines dieser Felder warten reicht: dann ist die Trefferliste sichtbar.
SEL_RESULT_READY_CANDIDATES: tuple[str, ...] = (SEL_PRICE, SEL_CARRIER)

# Pagination auf der Ergebnisseite (deutsche Booking-Oberfläche).
SEL_NEXT_PAGE = 'button[aria-label="Weiter"]'
SEL_ACTIVE_PAGE = 'button[aria-current="page"]'

# Standard-Zielliste für den Vergleich. Mehrere Ziele in einer Booking-Suche sind stabil.
# Diese Liste erscheint im Terminal (Schritt 2) und wird per Enter als
# destination_city in die CSV übernommen.
DEFAULT_DESTINATION_CITIES: tuple[str, ...] = (
    "London",
    "Berlin",
    "Rom",
    "Barcelona",
    "Paris",
)

BLOCK_KEYWORDS = (
    "captcha",
    "are you a robot",
    "unusual traffic",
    "verify you are",
    "access denied",
)


def polite_pause(min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
    import time

    time.sleep(random.uniform(min_seconds, max_seconds))


def setup_driver(headless: bool = False):
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")

    return webdriver.Chrome(options=options)

def _wait(driver, timeout: int = 20) -> WebDriverWait:
    return WebDriverWait(driver, timeout)


def _check_for_block_or_captcha(driver) -> None:
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except WebDriverException:
        return

    if any(k in body_text for k in BLOCK_KEYWORDS):
        raise RuntimeError(
            "Booking.com zeigt vermutlich ein Captcha oder einen Block. "
            "Bitte stoppen (nichts umgehen)."
        )


def open_booking_flights(driver, timeout: int = 30) -> None:
    try:
        driver.get(BOOKING_FLIGHTS_URL)
        _wait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        polite_pause()
        _check_for_block_or_captcha(driver)
    except WebDriverException as e:
        raise RuntimeError(f"Booking Flights konnte nicht geöffnet werden: {e}") from e


def accept_cookies_if_present(driver, timeout: int = 6) -> None:
    try:
        btn = _wait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_COOKIE_ACCEPT_BUTTON))
        )
        btn.click()
        polite_pause()
    except TimeoutException:
        return
    except WebDriverException as e:
        print(f"[WARN] Cookies konnten nicht akzeptiert werden: {e}")


def _click_first_css_candidate(
    driver,
    selectors: tuple[str, ...],
    *,
    description: str,
    timeout_per_selector: int = 12,
) -> None:
    """
    Versucht nacheinander CSS-Selektoren: sichtbar machen, normal klicken,
    sonst JavaScript-Klick (hilft bei Überlagerungen).
    """
    last: Exception | None = None
    for css in selectors:
        try:
            el = WebDriverWait(driver, timeout_per_selector).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                el,
            )
            polite_pause(0.4, 0.9)
            try:
                el.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", el)
            polite_pause()
            return
        except (TimeoutException, WebDriverException) as e:
            last = e
            continue

    raise RuntimeError(
        f"{description}: Kein passendes Element gefunden (nach {len(selectors)} Selektoren). "
        "Seite in Chrome mit F12 inspizieren und `SEL_ONE_WAY_CANDIDATES` bzw. "
        "`SEL_DIRECT_FLIGHTS_CANDIDATES` in scraper.py anpassen."
    ) from last


def select_one_way(driver) -> None:
    _click_first_css_candidate(
        driver,
        SEL_ONE_WAY_CANDIDATES,
        description="«Nur Hinflug»",
    )


def try_remove_destination_everywhere_chip(driver) -> None:
    """
    Entfernt optional den Standard-Chip «Überall» im Ziel-Feld.
    Wenn der Chip bleibt und man trotzdem tippt, meldet Booking oft einen Fehler.
    """
    xpaths = (
        "//span[normalize-space()='Überall']/ancestor::*[self::div or self::span][1]//button",
        "//*[normalize-space()='Überall']/following-sibling::button",
        "//button[contains(@aria-label,'Überall') and contains(@aria-label,'Entfernen')]",
        "//button[contains(@aria-label,'Remove') and contains(@aria-label,'Everywhere')]",
    )
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            polite_pause(0.2, 0.5)
            try:
                btn.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", btn)
            polite_pause(0.5, 1.0)
            return
        except TimeoutException:
            continue


def enable_direct_flights(driver) -> None:
    """Aktiviert «Nur Direktflüge» (Checkbox oder ähnliches Steuerelement)."""
    last: Exception | None = None
    for css in SEL_DIRECT_FLIGHTS_CANDIDATES:
        try:
            el = WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                el,
            )
            polite_pause(0.4, 0.9)
            tag = (el.tag_name or "").lower()
            if tag == "input" and el.get_attribute("type") == "checkbox":
                if not el.is_selected():
                    try:
                        el.click()
                    except WebDriverException:
                        driver.execute_script("arguments[0].click();", el)
            else:
                try:
                    el.click()
                except WebDriverException:
                    driver.execute_script("arguments[0].click();", el)
            polite_pause()
            return
        except (TimeoutException, WebDriverException) as e:
            last = e
            continue

    raise RuntimeError(
        "«Nur Direktflüge» nicht gefunden. `SEL_DIRECT_FLIGHTS_CANDIDATES` in scraper.py prüfen."
    ) from last


def _any_flight_card_displayed(driver) -> bool:
    """True, sobald mindestens ein Preis- oder Carrier-Element sichtbar ist."""
    for css in SEL_RESULT_READY_CANDIDATES:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, css):
                if el.is_displayed():
                    return True
        except WebDriverException:
            continue
    return False


def _texts(driver, css: str) -> list[str | None]:
    """Sammelt den sichtbaren Text aller Elemente zu einem Selektor; bei Fehler None."""
    out: list[str | None] = []
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, css):
            try:
                txt = (el.text or "").strip()
                out.append(txt or None)
            except WebDriverException:
                out.append(None)
    except WebDriverException:
        return out
    return out


def scroll_results(driver, steps: int = 4) -> None:
    for _ in range(steps):
        driver.execute_script("window.scrollBy(0, 900);")
        polite_pause(0.8, 1.8)


def wait_for_manual_search(destinations: tuple[str, ...]) -> None:
    """
    Zeigt die vorbereitete Zielliste und wartet, bis die Trefferliste sichtbar ist.

    Origin bewusst manuell, weil Booking bei mehreren Abflughäfen Fehler wirft.
    Ziele dürfen mehrere sein und werden hier nur als Liste angezeigt, damit die
    nutzende Person sie eintippen kann (kein Auto-Tippen, weil Bookings
    Autocomplete beim Skripting häufig blockt).
    """
    print("Bitte im Browser folgende Schritte ausführen:")
    print("  1) Abflugort eingeben — pro Durchlauf NUR EINEN (z. B. ZRH, später BSL).")
    print("  2) Folgende Ziele eintragen (mehrere Ziele sind bei Booking stabil):")
    for city in destinations:
        print(f"       - {city}")
    print("  3) Datum wählen und die Suche starten (z. B. Entdecken).")
    print(
        "Tipp Zielort: Falls ein Chip «Überall» sichtbar ist, zuerst das X klicken "
        "(sonst kann die Zieleingabe fehlschlagen). Meldet die Seite einen Fehler "
        "beim Tippen: Seite aktualisieren (F5), erneut Nur Hinflug / Nur Direktflüge "
        "setzen und nochmal versuchen."
    )
    input("Wenn die Suchresultate geladen sind, hier Enter drücken… ")


def wait_for_flight_results(driver, timeout: int = 90) -> None:
    driver.execute_script(
        "window.scrollTo(0, Math.min(800, document.body.scrollHeight || 800));"
    )
    polite_pause(0.4, 0.9)
    try:
        _wait(driver, timeout).until(_any_flight_card_displayed)
    except TimeoutException:
        driver.execute_script(
            "window.scrollTo(0, Math.max(0, (document.body.scrollHeight || 0) / 4));"
        )
        polite_pause(0.5, 1.0)
        try:
            _wait(driver, 20).until(_any_flight_card_displayed)
        except TimeoutException as e2:
            raise RuntimeError(
                "Keine sichtbaren Flug-Resultate. Im Browser F12 → eine Karte inspizieren "
                "und die data-testid-Selektoren oben in scraper.py prüfen "
                "(Booking ändert data-testid gelegentlich)."
            ) from e2


def extract_flight_cards(driver, timeout: int = 20) -> list[dict]:
    """
    Sammelt die Felder einzeln über ihre data-testid-Selektoren und kombiniert sie
    per zip() zu einer Zeile pro Flug. Fehlt ein Feld, wird None gespeichert.
    """
    try:
        _wait(driver, timeout).until(_any_flight_card_displayed)
    except TimeoutException:
        return []

    try:
        prices = _texts(driver, SEL_PRICE)
        carriers = _texts(driver, SEL_CARRIER)
        dep_times = _texts(driver, SEL_DEPARTURE_TIME)
        dep_airports = _texts(driver, SEL_DEPARTURE_AIRPORT)
        dst_times = _texts(driver, SEL_DESTINATION_TIME)
        dst_airports = _texts(driver, SEL_DESTINATION_AIRPORT)
        stops = _texts(driver, SEL_STOPS)
        durations = _texts(driver, SEL_DURATION)
    except WebDriverException:
        return []

    columns = [
        prices,
        carriers,
        dep_times,
        dep_airports,
        dst_times,
        dst_airports,
        stops,
        durations,
    ]
    # Längste Spalte bestimmt die Zeilenanzahl; kürzere werden mit None aufgefüllt.
    n_rows = max((len(c) for c in columns), default=0)
    padded = [c + [None] * (n_rows - len(c)) for c in columns]

    rows: list[dict] = []
    for (
        price_text,
        carrier,
        departure_time,
        departure_airport,
        destination_time,
        destination_airport,
        stops_text,
        duration,
    ) in zip(*padded):
        rows.append(
            {
                "price_text": price_text,
                "carrier": carrier,
                "departure_time": departure_time,
                "departure_airport": departure_airport,
                "destination_time": destination_time,
                "destination_airport": destination_airport,
                "stops": stops_text,
                "duration": duration,
            }
        )
    return rows


def _flight_dedupe_key(row: dict) -> tuple:
    """Schlüssel für Duplikat-Erkennung über die wichtigsten Flugattribute."""
    return (
        row.get("price_text"),
        row.get("carrier"),
        row.get("departure_time"),
        row.get("destination_time"),
        row.get("departure_airport"),
        row.get("destination_airport"),
    )


def extract_all_result_pages(driver, max_pages: int = 4) -> list[dict]:
    """
    Liest alle sichtbaren Ergebnisseiten nacheinander aus (Pagination).

    Ablauf pro Seite: Treffer extrahieren, Duplikate weglassen, dann optional
    auf «Weiter» klicken und warten, bis die nächste Seite geladen ist.
    Stoppt, wenn «Weiter» fehlt/nicht klickbar ist oder max_pages erreicht ist.
    """
    seen: set[tuple] = set()
    all_rows: list[dict] = []

    for page_index in range(max_pages):
        try:
            scroll_results(driver)
        except WebDriverException:
            pass

        try:
            page_rows = extract_flight_cards(driver, timeout=20)
        except WebDriverException:
            page_rows = []

        for row in page_rows:
            key = _flight_dedupe_key(row)
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

        # Letzte erlaubte Seite: nicht noch auf «Weiter» klicken.
        if page_index >= max_pages - 1:
            break

        try:
            next_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_NEXT_PAGE))
            )
        except (TimeoutException, WebDriverException):
            break

        # Referenz auf die aktive Seiten-Nummer: nach Klick auf «Weiter» wird
        # das DOM oft neu gerendert → Staleness signalisiert «nächste Seite da».
        old_page_btn = None
        try:
            old_page_btn = driver.find_element(By.CSS_SELECTOR, SEL_ACTIVE_PAGE)
        except WebDriverException:
            pass

        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                next_btn,
            )
            polite_pause(0.3, 0.7)
            try:
                next_btn.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", next_btn)
        except WebDriverException:
            break

        polite_pause()

        if old_page_btn is not None:
            try:
                WebDriverWait(driver, 15).until(EC.staleness_of(old_page_btn))
            except TimeoutException:
                pass

        try:
            WebDriverWait(driver, 15).until(_any_flight_card_displayed)
        except TimeoutException:
            break

    return all_rows


def prompt_run_metadata(
    default_destinations: tuple[str, ...],
) -> tuple[str, str, str]:
    """
    Fragt die Metadaten zum aktuellen Durchlauf ab und gibt sie zurück.

    - origin: vom Nutzenden eingegeben (z. B. ZRH oder BSL).
    - destination_city: Enter übernimmt die Default-Zielliste; eigene Eingabe
      wird 1:1 in die CSV geschrieben (z. B. nur «London»).
    - departure_date: vom Nutzenden im Format YYYY-MM-DD.
    """
    print("\nSuch-Metadaten (werden für alle Zeilen dieses Durchlaufs verwendet):")
    default_dest = ", ".join(default_destinations)

    while True:
        origin = input("origin (z. B. ZRH): ").strip()
        if origin:
            break
        print("  origin darf nicht leer sein.")

    while True:
        dest_input = input(f"destination_city (Enter = {default_dest}): ").strip()
        destination_city = dest_input or default_dest
        if destination_city:
            break
        print("  destination_city darf nicht leer sein.")

    while True:
        departure_date = input("departure_date (z. B. 2026-06-13): ").strip()
        if departure_date:
            break
        print("  departure_date darf nicht leer sein.")

    return origin, destination_city, departure_date


def ask_for_another_run() -> bool:
    """Fragt nach einem weiteren Durchlauf (z. B. zweiter Origin BSL)."""
    answer = input("Weitere Suche erfassen? [j/N]: ").strip().lower()
    return answer in ("j", "ja", "y", "yes")


def _prepare_search_form(driver) -> None:
    """
    Bereitet das Suchformular für einen Durchlauf vor:
    Booking öffnen, Cookies, Nur Hinflug, Nur Direktflüge, «Überall»-Chip weg.
    Wird beim ersten Durchlauf und bei jeder Wiederholung neu aufgerufen.
    """
    open_booking_flights(driver)
    accept_cookies_if_present(driver)
    polite_pause(1.0, 2.0)
    select_one_way(driver)
    enable_direct_flights(driver)
    polite_pause(2.0, 3.5)
    try_remove_destination_everywhere_chip(driver)


def run_semi_automatic_scrape(headless: bool = False) -> None:
    """
    Halbautomatik in einer Schleife:
      pro Durchlauf 1× Origin manuell, Ziele aus der Default-Liste,
      Metadaten abfragen, Treffer über mehrere Ergebnisseiten («Weiter»)
      auslesen und an die CSV ANHÄNGEN.

    Nutzung für die Studienabgabe:
      - Durchlauf 1: manuell ZRH wählen, Ziele wie unten, Datum, Suche starten.
      - Nach «Weitere Suche erfassen? [j/N]»: j → Durchlauf 2 mit BSL.
    """
    if headless:
        raise ValueError("Halbautomatik braucht einen sichtbaren Browser (kein --headless).")

    driver = setup_driver(headless=False)
    total_rows = 0
    runs = 0
    try:
        while True:
            runs += 1
            print(f"\n=== Durchlauf {runs} ===")

            _prepare_search_form(driver)

            wait_for_manual_search(DEFAULT_DESTINATION_CITIES)

            _check_for_block_or_captcha(driver)
            wait_for_flight_results(driver)
            scroll_results(driver)

            origin, destination_city, departure_date = prompt_run_metadata(
                DEFAULT_DESTINATION_CITIES
            )

            rows = extract_all_result_pages(driver, max_pages=4)
            scrape_ts = datetime.now().isoformat(timespec="seconds")
            enriched = [
                {
                    "scrape_timestamp": scrape_ts,
                    "source": "booking.com",
                    "mode": "semi_automatic",
                    "origin": origin,
                    "destination_city": destination_city,
                    "departure_date": departure_date,
                    "one_way": True,
                    "cabin": "Economy",
                    "adults": 1,
                    "direct_preference": True,
                    **r,
                }
                for r in rows
            ]

            save_to_csv(enriched, CONFIG.paths.raw_results_csv)
            total_rows += len(enriched)
            print(
                f"[OK] Durchlauf {runs}: {len(enriched)} Zeilen angehängt "
                f"(gesamt: {total_rows}). Datei: {CONFIG.paths.raw_results_csv}"
            )

            if not ask_for_another_run():
                break
    finally:
        driver.quit()
