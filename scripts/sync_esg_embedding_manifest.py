from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_MANIFEST = ROOT / "storage" / "esg_corpus" / "manifest.json"
DEFAULT_EMBEDDING_MANIFEST = ROOT / "storage" / "rag" / "esg_reports_openai_3072" / "embedding_manifest.json"
DEFAULT_CHUNK_MANIFEST = ROOT / "storage" / "rag" / "esg_reports_openai_3072" / "chunk_manifest.csv"
DEFAULT_REPORT = ROOT / "storage" / "esg_corpus" / "embedding_manifest_sync_report.json"
FORMAL_YEARS = {2022, 2023, 2024, 2025}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normal_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip().lower()


def _record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("ticker") or "").upper(),
        str(record.get("year") or ""),
        str(record.get("report_type") or "").upper(),
    )


def _index_embedding_records(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    by_path: dict[str, dict[str, Any]] = {}
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        local_path = _normal_path(record.get("local_path"))
        if local_path:
            by_path[local_path] = record
        by_key[_record_key(record)] = record
    return by_path, by_key


def _read_chunk_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _forbidden_formal_rows(records: list[dict[str, Any]], chunk_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forbidden: list[dict[str, Any]] = []
    for record in records:
        local_path = _normal_path(record.get("local_path"))
        year = int(record.get("year") or 0)
        if year not in FORMAL_YEARS:
            forbidden.append({"kind": "manifest_record", "year": year, "local_path": record.get("local_path")})
        if "2026" in local_path or "_wrong_year_duplicates" in local_path or local_path.endswith(".csv"):
            forbidden.append({"kind": "manifest_record_path", "year": year, "local_path": record.get("local_path")})
    for row in chunk_rows:
        local_path = _normal_path(row.get("local_path"))
        year = int(float(row.get("year") or 0))
        if year not in FORMAL_YEARS:
            forbidden.append({"kind": "chunk_manifest_row", "year": year, "local_path": row.get("local_path")})
        if "2026" in local_path or "_wrong_year_duplicates" in local_path or local_path.endswith(".csv"):
            forbidden.append({"kind": "chunk_manifest_path", "year": year, "local_path": row.get("local_path")})
    return forbidden


def sync_manifest(
    *,
    corpus_manifest_path: Path = DEFAULT_CORPUS_MANIFEST,
    embedding_manifest_path: Path = DEFAULT_EMBEDDING_MANIFEST,
    chunk_manifest_path: Path = DEFAULT_CHUNK_MANIFEST,
    report_path: Path = DEFAULT_REPORT,
    write: bool = True,
    expected_embedded: int | None = 84,
    expected_skipped: int | None = 10,
    expected_chunks: int | None = 1905,
) -> dict[str, Any]:
    corpus_manifest = _read_json(corpus_manifest_path)
    embedding_manifest = _read_json(embedding_manifest_path)
    embedding_records = list(embedding_manifest.get("records") or [])
    chunk_rows = _read_chunk_rows(chunk_manifest_path)
    by_path, by_key = _index_embedding_records(embedding_records)

    updated_records: list[dict[str, Any]] = []
    changed = 0
    unmatched: list[dict[str, Any]] = []
    for record in corpus_manifest.get("records") or []:
        before = dict(record)
        local_path = _normal_path(record.get("local_path"))
        match = by_path.get(local_path) if local_path else None
        if match is None:
            match = by_key.get(_record_key(record))
        if match is not None:
            for field in (
                "embedding_status",
                "chunk_count",
                "valid_pdf",
                "pages",
                "title",
                "checksum_sha256",
                "size_bytes",
                "source_note",
            ):
                if field in match:
                    record[field] = match.get(field)
        elif not record.get("local_path"):
            record["embedding_status"] = "skipped_no_file"
            record["chunk_count"] = 0
            record["valid_pdf"] = False
        else:
            unmatched.append(
                {
                    "ticker": record.get("ticker"),
                    "year": record.get("year"),
                    "report_type": record.get("report_type"),
                    "local_path": record.get("local_path"),
                }
            )
        if before != record:
            changed += 1
        updated_records.append(record)

    corpus_manifest["records"] = updated_records
    status_counts = Counter(str(record.get("embedding_status") or "missing") for record in updated_records)
    embedded_records = [record for record in updated_records if record.get("embedding_status") == "embedded"]
    skipped_records = [record for record in updated_records if record.get("embedding_status") == "skipped_no_file"]
    chunk_count_sum = sum(int(record.get("chunk_count") or 0) for record in updated_records)
    forbidden = _forbidden_formal_rows(embedding_records, chunk_rows)

    failures: list[str] = []
    if unmatched:
        failures.append("corpus records with local_path were not found in embedding manifest")
    if expected_embedded is not None and len(embedded_records) != expected_embedded:
        failures.append(f"embedded record count mismatch: expected {expected_embedded}, got {len(embedded_records)}")
    if expected_skipped is not None and len(skipped_records) != expected_skipped:
        failures.append(f"skipped record count mismatch: expected {expected_skipped}, got {len(skipped_records)}")
    if expected_chunks is not None and chunk_count_sum != expected_chunks:
        failures.append(f"chunk count mismatch: expected {expected_chunks}, got {chunk_count_sum}")
    if expected_chunks is not None and len(chunk_rows) != expected_chunks:
        failures.append(f"chunk manifest row count mismatch: expected {expected_chunks}, got {len(chunk_rows)}")
    if forbidden:
        failures.append("formal embedding manifest contains a forbidden year/path")

    report = {
        "generated_at": _utc_now(),
        "status": "fail" if failures else "pass",
        "write": bool(write),
        "corpus_manifest_path": str(corpus_manifest_path),
        "embedding_manifest_path": str(embedding_manifest_path),
        "chunk_manifest_path": str(chunk_manifest_path),
        "records": len(updated_records),
        "changed_records": changed,
        "embedding_status_counts": dict(sorted(status_counts.items())),
        "embedded_records": len(embedded_records),
        "skipped_no_file_records": len(skipped_records),
        "chunk_count_sum": chunk_count_sum,
        "chunk_manifest_rows": len(chunk_rows),
        "unmatched_records": unmatched,
        "forbidden_formal_rows": forbidden,
        "failures": failures,
    }

    if write:
        _write_json(corpus_manifest_path, corpus_manifest)
    _write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize ESG corpus manifest embedding fields from the frozen embedding manifest.")
    parser.add_argument("--corpus-manifest", default=str(DEFAULT_CORPUS_MANIFEST))
    parser.add_argument("--embedding-manifest", default=str(DEFAULT_EMBEDDING_MANIFEST))
    parser.add_argument("--chunk-manifest", default=str(DEFAULT_CHUNK_MANIFEST))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT))
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--expected-embedded", type=int, default=84)
    parser.add_argument("--expected-skipped", type=int, default=10)
    parser.add_argument("--expected-chunks", type=int, default=1905)
    args = parser.parse_args()

    report = sync_manifest(
        corpus_manifest_path=Path(args.corpus_manifest),
        embedding_manifest_path=Path(args.embedding_manifest),
        chunk_manifest_path=Path(args.chunk_manifest),
        report_path=Path(args.report_path),
        write=not args.check_only,
        expected_embedded=args.expected_embedded,
        expected_skipped=args.expected_skipped,
        expected_chunks=args.expected_chunks,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
