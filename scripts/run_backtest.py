
from gateway.quant.service import get_quant_system


if __name__ == "__main__":
    result = get_quant_system().run_backtest("ESG Multi-Factor Long-Only")
    print(result["backtest_id"])
