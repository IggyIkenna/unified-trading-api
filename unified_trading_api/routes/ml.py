"""ML domain — model families, experiments, training, versions, deployments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/model-families")
async def get_model_families(
    request: Request,
) -> dict[str, object]:
    """Get registered model families."""
    service = get_service(request)
    return {"model_families": service.list("model_families")}


@router.get("/experiments")
async def get_experiments(
    request: Request,
    family: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get ML experiments."""
    service = get_service(request)
    records = service.list("experiments", filters={"family": family})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/training-runs")
async def get_training_runs(
    request: Request,
    experiment_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get training runs."""
    service = get_service(request)
    records = service.list("training_runs", filters={"experiment_id": experiment_id})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/versions")
async def get_model_versions(
    request: Request,
    family: str = Query(None),
) -> dict[str, object]:
    """Get model versions."""
    service = get_service(request)
    records = service.list("model_versions", filters={"family": family})
    return {"versions": records}


@router.get("/deployments")
async def get_model_deployments(
    request: Request,
) -> dict[str, object]:
    """Get active model deployments."""
    service = get_service(request)
    return {"deployments": service.list("model_deployments")}


@router.get("/features")
async def get_features(
    request: Request,
    category: str = Query(None),
) -> dict[str, object]:
    """Get registered ML features."""
    service = get_service(request)
    records = service.list("ml_features", filters={"category": category})
    return {"features": records}


@router.get("/datasets")
async def get_datasets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get registered datasets."""
    service = get_service(request)
    records = service.list("datasets")
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}
