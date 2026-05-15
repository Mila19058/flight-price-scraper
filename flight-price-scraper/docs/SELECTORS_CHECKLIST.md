# Selektoren (nur Halbautomatik)

Alle relevanten CSS-Selektoren stehen in `src/flight_scraper/scraper.py`.

## Vor der manuellen Suche (macht Selenium)

| Konstante | Zweck |
|-----------|--------|
| `SEL_COOKIE_ACCEPT_BUTTON` | Cookies akzeptieren |
| `SEL_ONE_WAY_CANDIDATES` | «Nur Hinflug» (mehrere mögliche Selektoren nacheinander) |
| `SEL_DIRECT_FLIGHTS_CANDIDATES` | «Nur Direktflüge» |

Wenn ein Timeout kommt: **F12 → Element inspizieren** und den passenden Selektor zur Tuple-Liste hinzufügen.

## Nach der manuellen Suche (Resultate)

| Konstante | Zweck |
|-----------|--------|
| `SEL_FLIGHT_CARD_CANDIDATES` | Flight Cards auf der Trefferseite (mehrere Selektoren) |

Abflug, Ziel, Datum und Suche starten erledigst **du im Browser**.

## Backup

Eigene Änderungen mit **Git** committen oder die Datei kopieren.
