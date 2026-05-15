from __future__ import annotations

import argparse

from .config import CONFIG
from .scraper import run_semi_automatic_scrape
from .storage import build_processed_csv


def build_processed_from_raw() -> None:
    build_processed_csv(
        CONFIG.paths.raw_results_csv,
        CONFIG.paths.processed_results_csv,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Booking Flights: halbautomatisches Scraping."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    scrape_p = sub.add_parser(
        "scrape",
        help="Browser: Booking, Cookies, Hinflug, Direktfluege, dann manuell suchen, Enter, CSV.",
    )
    scrape_p.add_argument(
        "--headless",
        action="store_true",
        help="Wird abgelehnt (Browser muss sichtbar sein).",
    )

    sub.add_parser("process", help="Processed CSV aus Roh-CSV erzeugen.")

    args = parser.parse_args()

    if args.cmd == "scrape":
        run_semi_automatic_scrape(headless=bool(args.headless))
    elif args.cmd == "process":
        build_processed_from_raw()


if __name__ == "__main__":
    main()
