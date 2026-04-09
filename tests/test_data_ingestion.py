
from data.ingestion.price_loader import load_dataset as load_price_dataset


def test_price_loader_returns_records():
    result = load_price_dataset()
    assert result["source"] == "price_loader"
    assert result["records"]
