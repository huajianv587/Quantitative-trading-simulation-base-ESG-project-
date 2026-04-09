
import json

from gateway.quant.service import get_quant_system


if __name__ == "__main__":
    payload = {
        "overview": get_quant_system().build_platform_overview(),
        "experiments": get_quant_system().list_experiments(),
        "backtests": get_quant_system().list_backtests(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
