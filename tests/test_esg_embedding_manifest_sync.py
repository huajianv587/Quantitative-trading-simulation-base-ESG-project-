from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.sync_esg_embedding_manifest import sync_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_chunk_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["local_path", "year", "chunk_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_sync_manifest_aligns_embedding_status_and_chunks(tmp_path: Path):
    corpus = tmp_path / "manifest.json"
    embedding = tmp_path / "embedding_manifest.json"
    chunks = tmp_path / "chunk_manifest.csv"
    report = tmp_path / "report.json"
    records = [
        {
            "ticker": "AAPL",
            "year": 2022,
            "report_type": "E",
            "local_path": "esg_reports/Apple/Apple E 2022.pdf",
            "embedding_status": "pending",
            "chunk_count": 0,
            "valid_pdf": True,
        },
        {
            "ticker": "ABT",
            "year": 2025,
            "report_type": "ESG",
            "local_path": None,
            "embedding_status": "pending",
            "chunk_count": 0,
            "valid_pdf": False,
        },
    ]
    embedded_records = [
        {**records[0], "embedding_status": "embedded", "chunk_count": 2, "checksum_sha256": "abc"},
        {**records[1], "embedding_status": "skipped_no_file", "chunk_count": 0},
    ]
    _write_json(corpus, {"records": records})
    _write_json(embedding, {"records": embedded_records})
    _write_chunk_manifest(
        chunks,
        [
            {"local_path": records[0]["local_path"], "year": 2022, "chunk_id": "c1"},
            {"local_path": records[0]["local_path"], "year": 2022, "chunk_id": "c2"},
        ],
    )

    payload = sync_manifest(
        corpus_manifest_path=corpus,
        embedding_manifest_path=embedding,
        chunk_manifest_path=chunks,
        report_path=report,
        expected_embedded=1,
        expected_skipped=1,
        expected_chunks=2,
    )

    synced = json.loads(corpus.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert synced["records"][0]["embedding_status"] == "embedded"
    assert synced["records"][0]["chunk_count"] == 2
    assert synced["records"][1]["embedding_status"] == "skipped_no_file"


def test_formal_embedding_manifest_excludes_2026_and_non_pdf_audit_files():
    manifest = json.loads((PROJECT_ROOT / "storage/rag/esg_reports_openai_3072/embedding_manifest.json").read_text(encoding="utf-8"))
    chunk_rows = list(csv.DictReader((PROJECT_ROOT / "storage/rag/esg_reports_openai_3072/chunk_manifest.csv").open("r", encoding="utf-8")))

    manifest_paths = [str(record.get("local_path") or "").replace("\\", "/") for record in manifest["records"]]
    chunk_paths = [str(row.get("local_path") or "").replace("\\", "/") for row in chunk_rows]
    all_paths = manifest_paths + chunk_paths

    assert not any("2026" in path for path in all_paths)
    assert not any("_wrong_year_duplicates" in path for path in all_paths)
    assert not any(path.endswith(".csv") for path in all_paths)
    assert {int(record["year"]) for record in manifest["records"]}.issubset({2022, 2023, 2024, 2025})


def test_sync_manifest_fails_when_formal_manifest_contains_2026(tmp_path: Path):
    corpus = tmp_path / "manifest.json"
    embedding = tmp_path / "embedding_manifest.json"
    chunks = tmp_path / "chunk_manifest.csv"
    record = {
        "ticker": "AAPL",
        "year": 2026,
        "report_type": "E",
        "local_path": "esg_reports/Apple/Apple E 2026.pdf",
        "embedding_status": "embedded",
        "chunk_count": 1,
    }
    _write_json(corpus, {"records": [record]})
    _write_json(embedding, {"records": [record]})
    _write_chunk_manifest(chunks, [{"local_path": record["local_path"], "year": 2026, "chunk_id": "bad"}])

    payload = sync_manifest(
        corpus_manifest_path=corpus,
        embedding_manifest_path=embedding,
        chunk_manifest_path=chunks,
        report_path=tmp_path / "report.json",
        expected_embedded=1,
        expected_skipped=0,
        expected_chunks=1,
    )

    assert payload["status"] == "fail"
    assert payload["forbidden_formal_rows"]
