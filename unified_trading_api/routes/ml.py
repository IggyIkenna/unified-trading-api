"""ML domain — model families, experiments, training runs, versions, deployments, features, datasets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/model-families")
async def get_model_families(
    request: Request,
) -> dict[str, object]:
    """Get registered model families."""
    if getattr(request.app.state, "mock_mode", True):
        return {"model_families": mock_store.list("model_families")}
    return {"error": "real mode not yet wired"}


@router.get("/experiments")
async def get_experiments(
    request: Request,
    family: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get ML experiments."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("experiments")
        if family:
            records = [r for r in records if r.get("family") == family]
        return {"experiments": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.get("/training-runs")
async def get_training_runs(
    request: Request,
    experiment_id: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """Get training runs."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("training_runs")
        if experiment_id:
            records = [r for r in records if r.get("experiment_id") == experiment_id]
        return {"training_runs": records[:limit]}
    return {"error": "real mode not yet wired"}


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
    return {"error": "real mode not yet wired"}


@router.get("/deployments")
async def get_model_deployments(
    request: Request,
) -> dict[str, object]:
    """Get active model deployments."""
    if getattr(request.app.state, "mock_mode", True):
        return {"deployments": mock_store.list("model_deployments")}
    return {"error": "real mode not yet wired"}


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
    return {"error": "real mode not yet wired"}


@router.get("/datasets")
async def get_datasets(
    request: Request,
    limit: int = Query(50),
) -> dict[str, object]:
    """Get registered datasets."""
    if getattr(request.app.state, "mock_mode", True):
        return {"datasets": mock_store.list("datasets")[:limit]}
    return {"error": "real mode not yet wired"}
