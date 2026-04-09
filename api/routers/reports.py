
from fastapi import APIRouter

from gateway.quant.service import get_quant_system

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview")
def reports_overview():
    return {
        "experiments": get_quant_system().list_experiments(),
        "backtests": get_quant_system().list_backtests(),
    }
