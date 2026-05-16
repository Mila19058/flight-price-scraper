## Motivation des halbautomatischen Ansatzes

Im Projekt wurde bewusst ein halbautomatischer Ansatz gewählt.
Während der Tests zeigte sich, dass Booking.com empfindlich auf vollständig automatisierte Eingaben reagiert – insbesondere dann, wenn mehrere Abflughäfen gleichzeitig verwendet werden.

Deshalb übernimmt Selenium hauptsächlich die Navigation, Pagination und Extraktion der Resultate, während die eigentliche Suche manuell gestartet wird.

Dadurch bleibt das Scraping stabil und entspricht gleichzeitig der Vorgabe, keine Sicherheitsmechanismen oder Captchas zu umgehen.

Warum Abflughafen manuell, Flugziele vorbereitet?
Mehrere Abflughäfen innerhalb derselben Suchanfrage führten in Tests regelmässig zu Instabilitäten auf Booking.com Flights. Deshalb wird pro Suchdurchlauf nur ein Abflughafen verwendet (z. B. zuerst ZRH, danach BSL).
Beim Zielort funktionieren mehrere Städte stabil. Das Skript zeigt im Terminal eine Standard-Zielliste (London, Berlin, Rom, Barcelona, Paris) und schreibt sie als destination_city in die CSV.
Der Vergleich Zürich vs. Basel passiert später in der Auswertung über die Spalte origin.
Ablauf pro Durchlauf
Selenium öffnet Booking.com Flights, akzeptiert Cookies, aktiviert Nur Hinflug und Nur Direktflüge.
Im Terminal wird eine Standard-Zielliste angezeigt. Im Browser wird ein Abflugort gewählt (z. B. ZRH), danach werden die Ziele und das Datum eingegeben und die Suche gestartet.
Sobald die Trefferliste sichtbar ist, wird die Suche im Terminal bestätigt.
Das Skript fragt:
origin (z. B. ZRH)
destination_city (Enter = Default-Liste)
departure_date (z. B. 2026-06-13)
Selenium liest die aktuelle Ergebnisseite, klickt sich danach über button[aria-label="Weiter"] durch die Pagination (max. 4 Seiten, Duplikate werden über Preis/Carrier/Zeiten/Flughäfen entfernt) und hängt alle Zeilen an die CSV an.
Optional kann ein weiterer Durchlauf gestartet werden (z. B. mit einem anderen Abflughafen wie BSL).
Die CSV wird angehängt, nie überschrieben. Mehrfache Suchdurchläufe können zu Duplikaten führen. Die Bereinigung erfolgt später im Processing-Schritt.

Start
Einmalig das Paket installieren (sonst: No module named flight_scraper):

cd flight-price-scraper
python -m pip install -e ".[dev]"
Mit uv (falls installiert):

cd flight-price-scraper
uv pip install -e ".[dev]"
uv run python -m flight_scraper scrape
Ohne uv, mit normalem venv:

cd flight-price-scraper
python -m pip install -e ".[dev]"
python -m flight_scraper scrape
Kein --headless – der Browser muss sichtbar sein, damit du die Suche manuell machen kannst.

Weitere Befehle
uv run python -m flight_scraper process
uv run pytest
uv run ruff check .
Tests
Die wichtigsten Funktionen werden mit pytest getestet.

Getestet werden unter anderem:

Preis-Parsing bei gültigen, leeren und fehlerhaften Werten
Speichern und Laden von CSV-Dateien
Ergänzung von weekday
Berechnung von booking_lead_days
CSV-Spalten
Die Rohdaten in data/raw/booking_flights_raw.csv enthalten pro Flugtreffer:

Metadaten: scrape_timestamp, source, mode, origin, destination_city,departure_date, one_way, cabin, adults, direct_preference
Flugdaten (aus den data-testid-Feldern von Booking): price_text, carrier, departure_time, departure_airport, destination_time, destination_airport, stops, duration
Exploratory Data Analysis (EDA)
Die gesammelten Daten werden anschliessend analysiert, um Preisunterschiede zwischen Abflughäfen, Zielorten und Reisedaten zu untersuchen.

Zusätzlich werden Verteilungen, häufige Airlines, Preisspannen und Unterschiede zwischen Zürich und Basel ausgewertet.

Dateien
Code: src/flight_scraper/scraper.py
Rohdaten: data/raw/booking_flights_raw.csv
Processed: data/processed/booking_flights_processed.csv
Selektoren-Hinweise: docs/SELECTORS_CHECKLIST.md
Hinweise
Im finalen Projekt wird bewusst ein halbautomatischer Ansatz verwendet.

Immer starten mit python -m flight_scraper, nicht python scraper.py direkt.

Fehler beim Zielort («Es ist ein Fehler aufgetreten …»)
Oft liegt es am Chip «Überall» im Ziel-Feld: erst das X am Chip klicken, dann den Ort eingeben. Alternativ Seite aktualisieren (F5), danach wieder Nur Hinflug und Nur Direktflüge setzen und erneut suchen.

0 Zeilen extrahiert
Booking ändert gelegentlich die data-testid-Werte. In dem Fall im Browser mit F12 eine Flugkarte inspizieren und die Konstanten oben in scraper.py anpassen (SEL_PRICE, SEL_CARRIER, SEL_DEPARTURE_TIME, SEL_DESTINATION_TIME, …).

Pagination überspringt Seiten oder hängt
Standardmässig werden max. 4 Seiten ausgelesen. Wert in run_semi_automatic_scrape() (Aufruf von extract_all_result_pages(driver, max_pages=4)) bei Bedarf erhöhen. Falls Booking den «Weiter»-Button anders
beschriftet (z. B. englische UI), Selektor in SEL_NEXT_PAGE anpassen.
