from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    project_root: Path
    data_raw_dir: Path
    data_processed_dir: Path
    raw_results_csv: Path
    processed_results_csv: Path


@dataclass(frozen=True)
class AppConfig:
    """Pfade für Roh- und Processed-CSV."""

    paths: Paths


def build_paths(project_root: Path) -> Paths:
    data_raw_dir = project_root / "data" / "raw"
    data_processed_dir = project_root / "data" / "processed"
    return Paths(
        project_root=project_root,
        data_raw_dir=data_raw_dir,
        data_processed_dir=data_processed_dir,
        raw_results_csv=data_raw_dir / "booking_flights_raw.csv",
        processed_results_csv=data_processed_dir / "booking_flights_processed.csv",
    )


def project_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


CONFIG = AppConfig(paths=build_paths(project_root_from_here()))


def make_run_id(ts: datetime | None = None) -> str:
    if ts is None:
        ts = datetime.now()
    return ts.strftime("%Y%m%d_%H%M%S")
