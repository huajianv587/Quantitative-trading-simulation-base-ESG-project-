
from data.ingestion.price_loader import load_dataset as load_price_dataset


def test_price_loader_returns_records():
    result = load_price_dataset()
    assert result["source"] == "price_loader"
    assert result["status"] == "loaded"
    assert result["record_count"] >= 1
    assert "schema" in result
    assert result["records"]
