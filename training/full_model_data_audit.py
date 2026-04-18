from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "storage" / "full-training-runs" / "data_audit"

PAPER_GRADE_TRACKS = {"lora", "alpha", "p1", "event", "p2"}

TRACK_SPECS: dict[str, dict[str, Any]] = {
    "lora": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "train": "data/rag_training_data/train.jsonl",
            "val": "data/rag_training_data/val.jsonl",
        },
        "format": "jsonl",
        "paper_grade_candidate": True,
    },
    "alpha": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "full": "data/alpha_ranker/full_dataset.csv",
            "train": "data/alpha_ranker/train.csv",
            "val": "data/alpha_ranker/val.csv",
        },
        "format": "csv",
        "target_columns": ["forward_return_5d", "target_alpha_score"],
        "paper_grade_candidate": True,
    },
    "p1": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "full": "data/p1_stack/full_dataset.csv",
            "train": "data/p1_stack/train.csv",
            "val": "data/p1_stack/val.csv",
        },
        "format": "csv",
        "target_columns": [
            "forward_return_1d",
            "forward_return_5d",
            "forward_return_20d",
            "future_volatility_10d",
            "future_max_drawdown_20d",
            "regime_label",
        ],
        "paper_grade_candidate": True,
    },
    "sequence": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "train": "data/p1_stack/train.csv",
            "val": "data/p1_stack/val.csv",
        },
        "format": "csv",
        "target_columns": [
            "forward_return_1d",
            "forward_return_5d",
            "future_volatility_10d",
            "future_max_drawdown_20d",
        ],
        "paper_grade_candidate": False,
    },
    "event": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "full": "data/event_classifier/full_dataset.csv",
            "train": "data/event_classifier/train.csv",
            "val": "data/event_classifier/val.csv",
            "manifest": "data/event_classifier/manifest.json",
        },
        "format": "csv",
        "label_columns": [
            "controversy_label",
            "sentiment_label",
            "esg_axis_label",
            "impact_direction",
            "regime_label",
        ],
        "paper_grade_candidate": True,
    },
    "p2": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "signals_train": "data/p2_stack/train_signals.csv",
            "signals_val": "data/p2_stack/val_signals.csv",
            "snapshots_train": "data/p2_stack/train_snapshots.csv",
            "snapshots_val": "data/p2_stack/val_snapshots.csv",
        },
        "format": "csv",
        "label_columns": ["strategy_label"],
        "target_columns": ["selector_priority_target"],
        "required_columns_by_split": {
            "signals_train": ["strategy_label", "selector_priority_target"],
            "signals_val": ["strategy_label", "selector_priority_target"],
            "snapshots_train": ["strategy_label"],
            "snapshots_val": ["strategy_label"],
        },
        "paper_grade_candidate": True,
    },
    "bandit": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "train": "data/advanced_decision/bandit_contexts_train.csv",
            "val": "data/advanced_decision/bandit_contexts_val.csv",
        },
        "format": "csv",
        "label_columns": ["arm"],
        "target_columns": ["reward"],
        "paper_grade_candidate": False,
    },
    "gnn": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "nodes_train": "data/advanced_decision/graph_nodes_train.csv",
            "nodes_val": "data/advanced_decision/graph_nodes_val.csv",
            "edges": "data/advanced_decision/graph_edges.csv",
        },
        "format": "csv",
        "paper_grade_candidate": False,
    },
    "ppo": {
        "role": "stage1_baseline_checkpoint",
        "files": {
            "train": "data/advanced_decision/bandit_contexts_train.csv",
            "val": "data/advanced_decision/bandit_contexts_val.csv",
            "episodes": "data/advanced_decision/ppo_episodes.jsonl",
        },
        "format": "mixed",
        "label_columns": ["arm"],
        "target_columns": ["reward"],
        "paper_grade_candidate": False,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _line_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for count, _ in enumerate(handle, start=1):
            pass
    return count


def _jsonl_count_and_validate(path: Path) -> tuple[int, int]:
    rows = 0
    invalid = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            try:
                json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
    return rows, invalid


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _split_dates(frame: pd.DataFrame) -> dict[str, str] | None:
    if "date" not in frame.columns or frame.empty:
        return None
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return {"min": dates.min().date().isoformat(), "max": dates.max().date().isoformat()}


def _label_counts(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, int]]:
    payload: dict[str, dict[str, int]] = {}
    for column in columns:
        if column not in frame.columns:
            continue
        counts = Counter(str(value) for value in frame[column].dropna().tolist())
        payload[column] = dict(sorted(counts.items()))
    return payload


def _column_missing_rates(frame: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    payload: dict[str, float] = {}
    for column in columns:
        if column in frame.columns:
            payload[column] = round(float(frame[column].isna().mean()), 6)
    return payload


def _audit_file(path: Path, kind: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists():
        payload["status"] = "missing"
        return payload
    payload["size_bytes"] = path.stat().st_size
    if path.suffix.lower() == ".jsonl":
        rows, invalid = _jsonl_count_and_validate(path)
        payload.update({"rows": rows, "invalid_json_rows": invalid, "status": "ok" if invalid == 0 else "invalid"})
        return payload
    if path.suffix.lower() == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            payload.update({"rows": 1, "status": "ok"})
        except json.JSONDecodeError:
            payload.update({"rows": 0, "status": "invalid"})
        return payload
    if path.suffix.lower() == ".csv":
        frame = _read_csv(path)
        payload.update(
            {
                "rows": int(len(frame)),
                "columns": list(frame.columns),
                "date_range": _split_dates(frame),
                "duplicate_rows": int(frame.duplicated().sum()),
                "status": "ok",
            }
        )
        return payload
    payload.update({"rows": _line_count(path), "kind": kind, "status": "ok"})
    return payload


def _add_issue(issues: list[dict[str, str]], severity: str, track: str, rule: str, message: str) -> None:
    issues.append({"severity": severity, "track": track, "rule": rule, "message": message})


def audit_project(
    *,
    project_root: Path = PROJECT_ROOT,
    require_paper_grade: bool = False,
    jobs: list[str] | None = None,
) -> dict[str, Any]:
    selected = jobs or list(TRACK_SPECS)
    tracks: dict[str, Any] = {}
    issues: list[dict[str, str]] = []

    for track in selected:
        spec = TRACK_SPECS[track]
        track_payload: dict[str, Any] = {
            "role": spec["role"],
            "paper_grade_candidate": bool(spec.get("paper_grade_candidate")),
            "files": {},
            "label_counts": {},
            "missing_rates": {},
            "split_quality": "stage1_baseline",
        }
        loaded_frames: dict[str, pd.DataFrame] = {}
        for split, relative_path in spec["files"].items():
            path = project_root / relative_path
            file_payload = _audit_file(path, split)
            track_payload["files"][split] = file_payload
            if not file_payload.get("exists"):
                _add_issue(issues, "fail", track, "missing_file", f"{relative_path} is missing.")
                continue
            if file_payload.get("status") == "invalid":
                _add_issue(issues, "fail", track, "invalid_file", f"{relative_path} is invalid.")
            if int(file_payload.get("rows") or 0) == 0:
                _add_issue(issues, "fail", track, "empty_file", f"{relative_path} has no rows.")
            if path.suffix.lower() == ".csv":
                loaded_frames[split] = _read_csv(path)

        if "test" not in spec["files"]:
            severity = "fail" if require_paper_grade and track in PAPER_GRADE_TRACKS else "warn"
            _add_issue(issues, severity, track, "missing_independent_test", f"{track} has no independent test split.")

        label_columns = list(spec.get("label_columns", []))
        target_columns = list(spec.get("target_columns", []))
        for split, frame in loaded_frames.items():
            if label_columns:
                track_payload["label_counts"][split] = _label_counts(frame, label_columns)
            if label_columns or target_columns:
                track_payload["missing_rates"][split] = _column_missing_rates(frame, label_columns + target_columns)
            required_columns = list(spec.get("required_columns_by_split", {}).get(split, label_columns + target_columns))
            for column in required_columns:
                if column not in frame.columns:
                    _add_issue(issues, "fail", track, "missing_column", f"{split} is missing required column {column}.")

        if label_columns and "train" in loaded_frames:
            for column, counts in track_payload["label_counts"].get("train", {}).items():
                if len(counts) < 2:
                    _add_issue(issues, "fail", track, "single_class_label", f"{track}.{column} has fewer than 2 classes.")
                    continue
                total = sum(counts.values())
                smallest = min(counts.values()) if counts else 0
                if total and smallest / total < 0.03:
                    _add_issue(
                        issues,
                        "warn",
                        track,
                        "label_imbalance",
                        f"{track}.{column} smallest class has {smallest}/{total} rows.",
                    )

        tracks[track] = track_payload

    status = "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass"
    return {
        "generated_at": _utc_now(),
        "project_root": str(project_root),
        "require_paper_grade": bool(require_paper_grade),
        "status": status,
        "tracks": tracks,
        "issues": issues,
        "stage1_note": "Non-paper model lines are trainable baseline checkpoints until Stage 2 upgrades their data.",
    }


def _write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "full_model_data_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "full_model_data_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["severity", "track", "rule", "message"])
        writer.writeheader()
        for issue in report["issues"]:
            writer.writerow(issue)
    markdown = [
        "# Full Model Data Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at']}`",
        f"- Require paper grade: `{report['require_paper_grade']}`",
        "",
        "## Issues",
        "",
    ]
    if report["issues"]:
        for issue in report["issues"]:
            markdown.append(f"- `{issue['severity']}` `{issue['track']}` `{issue['rule']}`: {issue['message']}")
    else:
        markdown.append("- No issues.")
    markdown.extend(["", "## Track Rows", ""])
    for track, payload in report["tracks"].items():
        split_rows = {
            split: info.get("rows")
            for split, info in payload["files"].items()
            if info.get("exists")
        }
        markdown.append(f"- `{track}`: {split_rows}")
    (output_dir / "full_model_data_audit.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")

    limitation_lines = [
        "# Stage 1 Baseline Limitations",
        "",
        "These notes are intended for the paper appendix and rebuttal material.",
        "",
        "- Stage 1 full-suite checkpoints are marked `stage1_baseline_checkpoint`; they prove the project training lines are runnable and resumable, but they are not the ESG/RL paper's primary evidence.",
        "- LoRA/Event/Alpha/P1/P2 require Stage 2 paper-grade data upgrades before their metrics can be used as main research conclusions.",
        "- Independent 2025 test splits are missing for several non-paper tracks in Stage 1; those warnings are expected and must not be presented as paper-grade validation.",
        "- Event classifier labels may be sparse or synthetic in Stage 1, especially minority ESG axes such as environmental controversy; Stage 2 must add source-linked event labels and double-check label quality.",
        "- Alpha/P1/P2 Stage 1 labels are useful for baseline checkpoint training, but Stage 2 must add leakage audits, walk-forward manifests, and independent test splits before publication claims.",
        "",
        "## Audit Warnings",
        "",
    ]
    warning_issues = [issue for issue in report["issues"] if issue["severity"] == "warn"]
    if warning_issues:
        for issue in warning_issues:
            limitation_lines.append(f"- `{issue['track']}` `{issue['rule']}`: {issue['message']}")
    else:
        limitation_lines.append("- No Stage 1 warnings were reported.")
    (output_dir / "stage1_baseline_limitations.md").write_text("\n".join(limitation_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit full-suite training data before 5090 runs.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--jobs", default="all", help="Comma-separated track subset, or all.")
    parser.add_argument("--require-paper-grade", action="store_true")
    args = parser.parse_args()

    jobs = None if args.jobs.strip().lower() == "all" else [item.strip() for item in args.jobs.split(",") if item.strip()]
    unknown = sorted(set(jobs or []) - set(TRACK_SPECS))
    if unknown:
        raise SystemExit(f"Unknown audit track(s): {', '.join(unknown)}")
    report = audit_project(
        project_root=Path(args.project_root),
        require_paper_grade=args.require_paper_grade,
        jobs=jobs,
    )
    _write_outputs(report, Path(args.output_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
