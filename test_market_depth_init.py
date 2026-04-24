
from gateway.quant.market_depth import MarketDepthGateway
from pathlib import Path

gateway = MarketDepthGateway(storage_root=Path("storage"))
status = gateway.status(symbols=["AAPL"], require_l2=False)
print(json.dumps({
    "provider": status.get("selected_provider"),
    "data_tier": status.get("data_tier"),
    "available": status.get("available"),
    "eligibility_status": status.get("eligibility_status")
}, indent=2))
