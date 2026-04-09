
from gateway.quant.service import get_quant_system


def load_dataset(symbols: list[str] | None = None) -> dict:
    universe = get_quant_system().get_default_universe(symbols)
    return {
        "module": "patent_loader",
        "source": "patent_loader",
        "records": [member.model_dump() for member in universe],
    }
