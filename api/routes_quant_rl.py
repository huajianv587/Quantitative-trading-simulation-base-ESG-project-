from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.schemas_quant_rl import (
    QuantRLBacktestRequest,
    QuantRLBacktestResponse,
    QuantRLDatasetBuildRequest,
    QuantRLDemoDatasetRequest,
    QuantRLPromoteRequest,
    QuantRLPromoteResponse,
    QuantRLRecipeBuildRequest,
    QuantRLResponse,
    QuantRLSearchRequest,
    QuantRLTrainRequest,
)

router = APIRouter(prefix="/api/v1/quant/rl", tags=["quant-rl"])


class _LazyQuantRLService:
    """Keep the public service handle while deferring the training stack import."""

    def __init__(self) -> None:
        self._instance: Any | None = None

    def _get(self) -> Any:
        if self._instance is None:
            from quant_rl.service.quant_service import QuantRLService

            self._instance = QuantRLService()
        return self._instance

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)

    def reset_for_tests(self) -> None:
        self._instance = None


service = _LazyQuantRLService()


@router.get("/overview")
def overview(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_eligibility: bool = False,
    include_artifacts: bool = True,
    include_output_status: bool = False,
    include_bindings: bool = False,
) -> dict:
    return service.overview(
        limit=limit,
        offset=offset,
        include_eligibility=include_eligibility,
        include_artifacts=include_artifacts,
        include_output_status=include_output_status,
        include_bindings=include_bindings,
    )


@router.get("/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_eligibility: bool = False,
    include_bindings: bool = False,
) -> dict:
    return {
        "runs": service.list_runs(
            limit=limit,
            offset=offset,
            include_eligibility=include_eligibility,
            include_bindings=include_bindings,
        ),
        "pagination": {
            "limit": limit,
            "offset": offset,
            "include_eligibility": include_eligibility,
            "include_bindings": include_bindings,
        },
    }


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


@router.post("/promote", response_model=QuantRLPromoteResponse)
def promote(request: QuantRLPromoteRequest) -> QuantRLPromoteResponse:
    try:
        payload = service.promote_run(
            request.run_id,
            strategy_id=request.strategy_id,
            required_data_tier=request.required_data_tier,
        )
        return QuantRLPromoteResponse(**payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
