from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "storage" / "stage2_data_quality"
UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "JPM",
    "BAC",
    "GS",
    "MS",
    "XOM",
    "CVX",
    "NEE",
    "ENPH",
    "AMZN",
    "WMT",
    "COST",
    "PG",
    "JNJ",
    "PFE",
    "UNH",
    "ABT",
]
TRACKS = ["lora", "event", "alpha", "p1", "p2"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_dataset(path: str, split: str) -> dict[str, Any]:
    return {
        "path": path,
        "split": split,
        "rows": 0,
        "sources": [],
        "label_columns": [],
        "target_columns": [],
    }


def build_plan(output_root: Path) -> dict[str, Any]:
    tracks: dict[str, Any] = {}
    for track in TRACKS:
        tracks[track] = {
            "status": "planned",
            "datasets": [
                _empty_dataset(f"storage/stage2_data_quality/datasets/{track}/train.jsonl", "train"),
                _empty_dataset(f"storage/stage2_data_quality/datasets/{track}/val.jsonl", "val"),
                _empty_dataset(f"storage/stage2_data_quality/datasets/{track}/test.jsonl", "test"),
            ],
            "lineage": "planned; real source collection has not started",
            "review": {
                "dual_review_rate": 0.0,
                "cohen_kappa": None,
                "adjudication_log": f"storage/stage2_data_quality/adjudication/{track}.csv",
            },
            "leakage_audit": {"status": "not_run", "notes": "Stage 2 data not collected yet."},
        }

    tasks = [
        {
            "track": "lora",
            "task": "Build source-linked instruction data from ESG reports, RAG evidence chains, and score explanations.",
        },
        {
            "track": "event",
            "task": "Collect real news, filings, announcements, and controversy records with dual-review labels.",
        },
        {
            "track": "alpha",
            "task": "Rebuild point-in-time alpha features with train/val/test split and leakage audit.",
        },
        {
            "track": "p1",
            "task": "Rebuild point-in-time risk targets, regime labels, volatility, and drawdown labels.",
        },
        {
            "track": "p2",
            "task": "Rebuild strategy selector labels with decision rules, provenance, and human spot checks.",
        },
    ]

    return {
        "generated_at": _utc_now(),
        "output_root": str(output_root),
        "stage": "stage2_preparation_only",
        "universe": UNIVERSE,
        "splits": {
            "train": {"start": "2022-01-01", "end": "2023-12-31"},
            "val": {"start": "2024-01-01", "end": "2024-12-31"},
            "test": {"start": "2025-01-01", "end": "2025-12-31"},
        },
        "tasks": tasks,
        "manifest": {
            "version": "stage2-paper-grade-v1",
            "generated_at": _utc_now(),
            "universe": UNIVERSE,
            "splits": {
                "train": {"start": "2022-01-01", "end": "2023-12-31"},
                "val": {"start": "2024-01-01", "end": "2024-12-31"},
                "test": {"start": "2025-01-01", "end": "2025-12-31"},
            },
            "tracks": tracks,
        },
    }


def _write_label_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "record_id",
                "track",
                "symbol",
                "event_date",
                "source_uri",
                "label_field",
                "proposed_label",
                "reviewer_a",
                "reviewer_b",
                "adjudicated_label",
                "notes",
            ]
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Stage 2 paper-grade data task lists and empty manifests.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    output_root = Path(args.output_root)
    for relative in ["datasets", "label_queue", "adjudication", "audit"]:
        (output_root / relative).mkdir(parents=True, exist_ok=True)

    plan = build_plan(output_root)
    (output_root / "stage2_prepare_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "stage2_data_manifest.json").write_text(
        json.dumps(plan["manifest"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for track in TRACKS:
        _write_label_queue(output_root / "label_queue" / f"{track}.csv")
        _write_label_queue(output_root / "adjudication" / f"{track}.csv")

    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
