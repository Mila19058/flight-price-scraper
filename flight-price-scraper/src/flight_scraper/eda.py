from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .config import CONFIG
from .storage import load_csv


def _save_fig(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def run_eda(processed_csv: str | Path | None = None, figures_dir: str | Path | None = None) -> None:
    if processed_csv is None:
        processed_csv = CONFIG.paths.processed_results_csv
    if figures_dir is None:
        figures_dir = CONFIG.paths.project_root / "reports" / "figures"

    processed_csv = Path(processed_csv)
    figures_dir = Path(figures_dir)

    df = load_csv(processed_csv)
    if df.empty:
        print(f"[INFO] Keine Daten gefunden in {processed_csv}.")
        return

    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    if "destination_city" in df.columns:
        counts = df["destination_city"].value_counts().sort_values(ascending=False)
        counts.plot(kind="bar", title="Anzahl Datensätze pro Zielstadt")
        plt.xlabel("Zielstadt")
        plt.ylabel("Anzahl")
        _save_fig(figures_dir / "count_by_destination.png")

    if {"destination_city", "price"} <= set(df.columns):
        means = df.groupby("destination_city")["price"].mean().sort_values(ascending=False)
        means.plot(kind="bar", title="Durchschnittspreis pro Zielstadt")
        plt.xlabel("Zielstadt")
        plt.ylabel("Ø Preis")
        _save_fig(figures_dir / "mean_price_by_destination.png")

    if {"weekday", "price"} <= set(df.columns):
        means = df.groupby("weekday")["price"].mean()
        means = means.reindex(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
        means.plot(kind="bar", title="Durchschnittspreis pro Wochentag")
        plt.xlabel("Wochentag")
        plt.ylabel("Ø Preis")
        _save_fig(figures_dir / "mean_price_by_weekday.png")

    if {"booking_lead_days", "price"} <= set(df.columns):
        tmp = df.dropna(subset=["booking_lead_days", "price"]).copy()
        tmp["booking_lead_days"] = pd.to_numeric(tmp["booking_lead_days"], errors="coerce")
        tmp = tmp.dropna(subset=["booking_lead_days", "price"])
        plt.scatter(tmp["booking_lead_days"], tmp["price"], alpha=0.25)
        plt.title("Preis vs. Buchungsvorlauf (Tage)")
        plt.xlabel("Buchungsvorlauf (Tage)")
        plt.ylabel("Preis")
        _save_fig(figures_dir / "price_vs_booking_lead.png")

    if {"origin", "price"} <= set(df.columns):
        means = df.groupby("origin")["price"].mean().sort_values(ascending=False)
        means.plot(kind="bar", title="Durchschnittspreis: Basel vs. Zürich")
        plt.xlabel("Abflug (Origin)")
        plt.ylabel("Ø Preis")
        _save_fig(figures_dir / "mean_price_by_origin.png")

    print(f"[OK] Plots gespeichert in {figures_dir}")
