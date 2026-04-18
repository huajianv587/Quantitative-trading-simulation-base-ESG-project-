from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gateway.quant.esg_house_score import compute_calibrated_house_score, compute_house_score
from quant_rl.data.split import time_split
from quant_rl.service.quant_service import QuantRLService
from scripts.esg_corpus_pipeline import build_manifest, coverage_summary, rag_quality, score_records


def test_house_score_v2_outputs_research_fields():
    score = compute_house_score(
        company_name="Apple",
        sector="Technology",
        industry="Technology Hardware",
        e_score=74,
        s_score=71,
        g_score=82,
        data_sources=["apple-environmental-report"],
        data_lineage=["rag:chunk:1", "rag:chunk:2"],
        metric_coverage_ratio=0.9,
        esg_delta=0.03,
        evidence_count=12,
        effective_date="2025-04-02",
        staleness_days=90,
    ).as_dict()

    assert score["formula_version"] == "JHJ_HOUSE_SCORE_V2"
    assert 0 <= score["house_score"] <= 100
    assert set(["E", "S", "G"]).issubset(score["pillar_breakdown"])
    assert score["materiality_weights"]
    assert score["evidence_count"] == 12
    assert score["score_delta"] == 0.03


def test_house_score_v2_1_calibrates_without_return_leakage():
    calibrated = compute_calibrated_house_score(
        base_score=72,
        sector_year_mean=65,
        sector_year_std=5,
        global_year_mean=66,
        global_year_std=7,
        percentile_rank=0.8,
        confidence=0.82,
        evidence_strength=0.9,
        staleness_days=120,
    )

    assert calibrated["formula_version_v2_1"] == "JHJ_HOUSE_SCORE_V2_1_CALIBRATED"
    assert calibrated["house_score_v2_1"] > 72
    assert -1 <= calibrated["sector_relative_esg"] <= 1


def test_esg_corpus_manifest_has_20_company_universe():
    records = build_manifest(download=False, force=False, limit=None, timeout=1)
    summary = coverage_summary(records)

    assert summary["companies_total"] == 20
    assert "AAPL" in summary["by_ticker"]
    assert "MSFT" in summary["by_ticker"]
    assert summary["files_total"] >= 1


def test_score_records_writes_distribution_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.esg_corpus_pipeline.STORAGE_ROOT", tmp_path)
    records = build_manifest(download=False, force=False, limit=None, timeout=1)
    summary = score_records(records)

    assert summary["rows"] == 80
    assert summary["score_max"] > summary["score_min"]
    assert Path(summary["json_path"]).exists()
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert payload[0]["formula_version"] == "JHJ_HOUSE_SCORE_V2"
    missing = next(row for row in payload if row["coverage"] == 0)
    assert missing["house_score_v2"] == 50.0
    assert missing["house_score_v2_1"] == 50.0
    assert missing["score_available"] is False
    assert missing["esg_missing_flag"] == 1
    assert missing["confidence"] == 0.0
    evidence_only = json.loads((tmp_path / "score_distribution_evidence_only.json").read_text(encoding="utf-8"))
    assert evidence_only["rows"] == summary["score_available_rows"]
    assert evidence_only["excluded_missing_rows"] == summary["missing_rows"]
    assert "v2_1" in evidence_only


def test_rag_evidence_chain_reports_missing_embedding(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.esg_corpus_pipeline.STORAGE_ROOT", tmp_path / "corpus")
    monkeypatch.setattr("scripts.esg_corpus_pipeline.EMBED_ROOT", tmp_path / "missing_embedding")
    records = build_manifest(download=False, force=False, limit=None, timeout=1)

    report = rag_quality(records, evidence_chain=True)

    chain_path = Path(report["evidence_chain"]["json_path"])
    assert chain_path.exists()
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain["summary"]["rows"] == 20 * 4 * 3
    assert chain["summary"]["quality_flag_counts"]["embedding_missing"] == 20 * 4 * 3


def test_rag_evidence_chain_supports_pillar_chunks(tmp_path, monkeypatch):
    esg_root = tmp_path / "ESG报告"
    year_dir = esg_root / "MSFT" / "2024"
    year_dir.mkdir(parents=True)
    pdf = year_dir / "MSFT_ESG_2024.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"x" * 12000)
    embed_root = tmp_path / "embed"
    embed_root.mkdir()
    embedding = {
        "id": "chunk-msft-2024-e",
        "metadata": {
            "ticker": "MSFT",
            "company": "Microsoft",
            "sector": "Technology",
            "year": 2024,
            "local_path": "ESG报告/MSFT/2024/MSFT_ESG_2024.pdf",
            "chunk_index": 0,
            "extract_status": "ok",
        },
        "text": "Microsoft climate carbon emission renewable energy water waste environmental progress.",
        "embedding": [0.0, 0.1],
    }
    (embed_root / "embeddings.jsonl").write_text(json.dumps(embedding, ensure_ascii=False) + "\n", encoding="utf-8")

    monkeypatch.setattr("scripts.esg_corpus_pipeline.ESG_ROOT", esg_root)
    monkeypatch.setattr("scripts.esg_corpus_pipeline.DOWNLOADER_PATH", esg_root / "missing.py")
    monkeypatch.setattr("scripts.esg_corpus_pipeline.STORAGE_ROOT", tmp_path / "corpus")
    monkeypatch.setattr("scripts.esg_corpus_pipeline.EMBED_ROOT", embed_root)
    records = build_manifest(download=False, force=False, limit=None, timeout=1)

    report = rag_quality(records, evidence_chain=True)
    chain = json.loads(Path(report["evidence_chain"]["json_path"]).read_text(encoding="utf-8"))
    msft_e = next(item for item in chain["chains"] if item["ticker"] == "MSFT" and item["year"] == 2024 and item["pillar"] == "E")

    assert msft_e["support_level"] == "supported"
    assert msft_e["top_chunks"][0]["chunk_id"] == "chunk-msft-2024-e"


def test_manual_ticker_year_folder_and_source_metadata(tmp_path, monkeypatch):
    esg_root = tmp_path / "ESG报告"
    year_dir = esg_root / "MSFT" / "2024"
    year_dir.mkdir(parents=True)
    (year_dir / "source_url.txt").write_text(
        "source_url=https://example.com/msft-2024-esg.pdf\npublished_date=2025-03-15\n",
        encoding="utf-8",
    )
    pdf = year_dir / "MSFT_ESG_2024.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + b"x" * 12000)

    monkeypatch.setattr("scripts.esg_corpus_pipeline.ESG_ROOT", esg_root)
    monkeypatch.setattr("scripts.esg_corpus_pipeline.DOWNLOADER_PATH", esg_root / "missing.py")

    records = build_manifest(download=False, force=False, limit=None, timeout=1)
    msft = [record for record in records if record.ticker == "MSFT" and record.year == 2024]

    assert msft
    assert msft[0].download_status == "exists"
    assert msft[0].source_url == "https://example.com/msft-2024-esg.pdf"
    assert msft[0].published_date == "2025-03-15"


def test_flat_esg_reports_root_maps_apple_to_aapl(tmp_path, monkeypatch):
    esg_root = tmp_path / "esg_reports"
    apple_dir = esg_root / "Apple"
    msft_dir = esg_root / "MSFT"
    apple_dir.mkdir(parents=True)
    msft_dir.mkdir(parents=True)
    (apple_dir / "Apple_2022_ESG_Report.pdf").write_bytes(b"%PDF-1.7\n" + b"apple" * 3000)
    (msft_dir / "MSFT_2024_Sustainability_Report.pdf").write_bytes(b"%PDF-1.7\n" + b"msft" * 3000)
    (esg_root / "download_check.csv").write_text(
        "Ticker,Year,SourceUrl,Note\nAAPL,2022,https://example.com/apple.pdf,valid\nMSFT,2024,https://example.com/msft.pdf,valid\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("scripts.esg_corpus_pipeline.ESG_ROOT", esg_root)
    monkeypatch.setattr("scripts.esg_corpus_pipeline.DOWNLOADER_PATH", esg_root / "missing.py")

    records = build_manifest(download=False, force=False, limit=None, timeout=1)

    assert any(record.ticker == "AAPL" and record.year == 2022 and record.local_path for record in records)
    assert any(record.ticker == "MSFT" and record.year == 2024 and record.local_path for record in records)


def test_calendar_split_uses_2022_2025_protocol():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2022-01-03", "2023-06-01", "2024-02-01", "2025-03-03"], utc=True),
            "close": [1, 2, 3, 4],
        }
    )

    train, val, test = time_split(df)

    assert len(train) == 2
    assert len(val) == 1
    assert len(test) == 1


def test_esg_timeline_does_not_leak_before_effective_date():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-12-31", "2025-04-02", "2025-04-03"], utc=True),
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 100, 100],
        }
    )
    profile = {
        "house_score_v2": 50,
        "house_score_v2_1": 50,
        "e_score": 50,
        "s_score": 50,
        "g_score": 50,
        "score_timeseries": [
            {
                "effective_date": "2025-04-03",
                "house_score": 80,
                "house_score_v2_1": 84,
                "pillar_breakdown": {"E": 78, "S": 79, "G": 82},
                "disclosure_confidence": 0.9,
                "score_delta": 0.12,
                "score_delta_v2_1": 0.16,
                "sector_relative_esg": 0.5,
            }
        ],
    }

    enriched = QuantRLService._enrich_market_frame(frame, symbol="MSFT", profile=profile)

    assert enriched.loc[0, "esg_missing_flag"] == 1.0
    assert enriched.loc[1, "esg_missing_flag"] == 1.0
    assert float(enriched.loc[1, "house_score_v2"]) == 0.5
    assert enriched.loc[2, "esg_missing_flag"] == 0.0
    assert round(float(enriched.loc[2, "house_score_v2"]), 2) == 0.8
    assert round(float(enriched.loc[2, "house_score_v2_1"]), 2) == 0.84
    assert round(float(enriched.loc[2, "sector_relative_esg"]), 2) == 0.5
    assert enriched.loc[2, "esg_effective_date"] == "2025-04-03"
