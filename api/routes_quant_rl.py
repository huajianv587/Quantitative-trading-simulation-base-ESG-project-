from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas_quant_rl import (
    QuantRLBacktestRequest,
    QuantRLBacktestResponse,
    QuantRLDatasetBuildRequest,
    QuantRLDemoDatasetRequest,
    QuantRLRecipeBuildRequest,
    QuantRLResponse,
    QuantRLSearchRequest,
    QuantRLTrainRequest,
)
from quant_rl.service.quant_service import QuantRLService

router = APIRouter(prefix="/api/v1/quant/rl", tags=["quant-rl"])
service = QuantRLService()


@router.get("/overview")
def overview() -> dict:
    return service.overview()


@router.get("/runs")
def list_runs() -> dict:
    return {"runs": service.list_runs()}


@router.post("/datasets/build")
def build_dataset(request: QuantRLDatasetBuildRequest) -> dict:
    try:
        return service.build_market_dataset(
            request.symbols,
            dataset_name=request.dataset_name,
            limit=request.limit,
            force_refresh=request.force_refresh,
            include_esg=request.include_esg,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/recipes/build")
def build_recipe_dataset(request: QuantRLRecipeBuildRequest) -> dict:
    try:
        return service.build_recipe_dataset(
            request.recipe_key,
            dataset_name=request.dataset_name,
            limit=request.limit,
            force_refresh=request.force_refresh,
            symbols=request.symbols or None,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search")
def search_recipe(request: QuantRLSearchRequest) -> dict:
    try:
        return service.search_recipe(
            request.recipe_key,
            dataset_path=request.dataset_path,
            trials=request.trials,
            quick_steps=request.quick_steps,
            action_type=request.action_type,
            seed=request.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/datasets/demo")
def build_demo_dataset(request: QuantRLDemoDatasetRequest) -> dict:
    return service.generate_demo_dataset(
        target_path=request.target_path,
        seed=request.seed,
        length=request.length,
    )


@router.post("/train", response_model=QuantRLResponse)
def train(request: QuantRLTrainRequest) -> QuantRLResponse:
    try:
        payload = service.train(
            request.algorithm,
            request.dataset_path,
            request.action_type,
            request.episodes,
            request.total_steps,
            request.use_demo_if_missing,
            experiment_group=request.experiment_group,
            seed=request.seed,
            notes=request.notes,
            trainer_hparams=request.trainer_hparams,
        )
        return QuantRLResponse(**payload)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backtest", response_model=QuantRLBacktestResponse)
def backtest(request: QuantRLBacktestRequest) -> QuantRLBacktestResponse:
    try:
        payload = service.backtest(
            request.algorithm,
            request.dataset_path,
            request.checkpoint_path,
            request.action_type,
            experiment_group=request.experiment_group,
            seed=request.seed,
            notes=request.notes,
        )
        return QuantRLBacktestResponse(**payload)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
