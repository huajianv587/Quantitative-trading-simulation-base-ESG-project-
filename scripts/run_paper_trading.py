
from gateway.quant.service import get_quant_system


if __name__ == "__main__":
    result = get_quant_system().create_execution_plan()
    print(result["execution_id"])
