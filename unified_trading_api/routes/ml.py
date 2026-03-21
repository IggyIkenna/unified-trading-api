"""ML domain — model families, experiments, training, versions, deployments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store
from unified_trading_api.models.standard import (
    ErrorDetail,
    StandardErrorResponse,
    paginate,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/model-families")
async def get_model_families(
    request: Request,
) -> dict[str, object]:
    """Get registered model families."""
    if getattr(request.app.state, "mock_mode", True):
        return {"model_families": mock_store.list("model_families")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/experiments")
async def get_experiments(
    request: Request,
    family: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get ML experiments."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("experiments")
        if family:
            records = [r for r in records if r.get("family") == family]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/training-runs")
async def get_training_runs(
    request: Request,
    experiment_id: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get training runs."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("training_runs")
        if experiment_id:
            records = [r for r in records if r.get("experiment_id") == experiment_id]
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/versions")
async def get_model_versions(
    request: Request,
    family: str = Query(None),
) -> dict[str, object]:
    """Get model versions."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("model_versions")
        if family:
            records = [r for r in records if r.get("family") == family]
        return {"versions": records}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/deployments")
async def get_model_deployments(
    request: Request,
) -> dict[str, object]:
    """Get active model deployments."""
    if getattr(request.app.state, "mock_mode", True):
        return {"deployments": mock_store.list("model_deployments")}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/features")
async def get_features(
    request: Request,
    category: str = Query(None),
) -> dict[str, object]:
    """Get registered ML features."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("ml_features")
        if category:
            records = [r for r in records if r.get("category") == category]
        return {"features": records}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()


@router.get("/datasets")
async def get_datasets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get registered datasets."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("datasets")
        data, pagination = paginate(records, page, page_size)
        return {"data": data, "pagination": pagination.model_dump()}
    return StandardErrorResponse(
        error=ErrorDetail(code="NOT_IMPLEMENTED", message="Real mode not yet wired")
    ).model_dump()
