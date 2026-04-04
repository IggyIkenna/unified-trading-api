"""ML domain — model families, experiments, training, versions, deployments."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/model-families")
async def get_model_families(
    request: Request,
) -> dict[str, object]:
    """Get registered model families."""
    service = get_service(request)
    return single_response(service.list("model_families"))


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
    return paginated_response(records, page, page_size)


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
    return paginated_response(records, page, page_size)


@router.get("/versions")
async def get_model_versions(
    request: Request,
    family: str = Query(None),
) -> dict[str, object]:
    """Get model versions."""
    service = get_service(request)
    records = service.list("model_versions", filters={"family": family})
    return single_response(records)


@router.get("/deployments")
async def get_model_deployments(
    request: Request,
) -> dict[str, object]:
    """Get active model deployments."""
    service = get_service(request)
    return single_response(service.list("model_deployments"))


@router.get("/features")
async def get_features(
    request: Request,
    category: str = Query(None),
) -> dict[str, object]:
    """Get registered ML features."""
    service = get_service(request)
    records = service.list("ml_features", filters={"category": category})
    return single_response(records)


@router.get("/datasets")
async def get_datasets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get registered datasets."""
    service = get_service(request)
    records = service.list("datasets")
    return paginated_response(records, page, page_size)


@router.get("/training-jobs")
async def get_training_jobs(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get ML training jobs."""
    service = get_service(request)
    records = service.list("training_runs", filters={"status": status})
    return paginated_response(records, page, page_size)


@router.post("/training-jobs")
async def create_training_job(
    request: Request,
) -> dict[str, object]:
    """Create a new ML training job."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("training_runs", body)
    return single_response({"job": record, "status": "created"})


@router.get("/validation-results")
async def get_validation_results(
    request: Request,
    model_id: str = Query(None),
) -> dict[str, object]:
    """Get model validation results."""
    service = get_service(request)
    records = service.list("validation_results", filters={"model_id": model_id})
    return single_response(records)


@router.get("/monitoring")
async def get_ml_monitoring(
    request: Request,
    model_id: str = Query(None, description="Filter by model ID"),
    family: str = Query(None, description="Filter by model family"),
) -> dict[str, object]:
    """Get ML model monitoring data — drift metrics, accuracy, prediction distribution.

    Returns per-model monitoring snapshots including feature drift scores,
    prediction accuracy over time, and distribution statistics.
    """
    service = get_service(request)
    records = service.list("ml_monitoring", filters={"model_id": model_id, "family": family})
    if records:
        return single_response(records)
    # Sensible defaults when no seeded data exists
    return single_response(
        [
            {
                "model_id": "sports-match-outcome-v3",
                "family": "sports_match_outcome",
                "drift_score": 0.042,
                "drift_status": "stable",
                "accuracy_7d": 0.681,
                "accuracy_30d": 0.674,
                "predictions_24h": 1247,
                "prediction_distribution": {"home_win": 0.38, "draw": 0.27, "away_win": 0.35},
                "feature_drift": {"form_rating": 0.02, "elo_delta": 0.05, "market_odds": 0.01},
                "last_updated": datetime.now(UTC).isoformat(),
            },
            {
                "model_id": "crypto-alpha-signal-v2",
                "family": "crypto_alpha",
                "drift_score": 0.078,
                "drift_status": "warning",
                "accuracy_7d": 0.543,
                "accuracy_30d": 0.561,
                "predictions_24h": 3842,
                "prediction_distribution": {"long": 0.44, "short": 0.31, "flat": 0.25},
                "feature_drift": {
                    "momentum_12h": 0.09,
                    "volatility_ratio": 0.06,
                    "funding_rate": 0.03,
                },
                "last_updated": datetime.now(UTC).isoformat(),
            },
        ]
    )


@router.get("/governance")
async def get_ml_governance(
    request: Request,
    model_id: str = Query(None, description="Filter by model ID"),
    status: str = Query(None, description="Filter by approval status"),
) -> dict[str, object]:
    """Get ML governance data — approval status, audit trail.

    Returns model approval records with reviewer, timestamp, and decision rationale.
    """
    service = get_service(request)
    records = service.list("ml_governance", filters={"model_id": model_id, "status": status})
    if records:
        return single_response(records)
    return single_response(
        [
            {
                "model_id": "sports-match-outcome-v3",
                "version": "3.1.0",
                "approval_status": "approved",
                "reviewer": "risk-committee",
                "reviewed_at": "2026-03-28T14:00:00Z",
                "rationale": "Passed validation: accuracy 68%, drift stable, backtested 6mo.",
                "audit_trail": [
                    {"action": "submitted", "by": "ml-pipeline", "at": "2026-03-27T10:00:00Z"},
                    {"action": "reviewed", "by": "quant-lead", "at": "2026-03-28T12:00:00Z"},
                    {"action": "approved", "by": "risk-committee", "at": "2026-03-28T14:00:00Z"},
                ],
            },
            {
                "model_id": "crypto-alpha-signal-v2",
                "version": "2.4.1",
                "approval_status": "pending_review",
                "reviewer": None,
                "reviewed_at": None,
                "rationale": None,
                "audit_trail": [
                    {"action": "submitted", "by": "ml-pipeline", "at": "2026-03-30T09:00:00Z"},
                ],
            },
        ]
    )


@router.get("/config")
async def get_ml_config(
    request: Request,
) -> dict[str, object]:
    """Get ML pipeline configuration — feature sets, training schedules, thresholds.

    Returns the current ML pipeline configuration used by training and inference services.
    """
    service = get_service(request)
    records = service.list("ml_config")
    if records:
        return single_response(records[0] if len(records) == 1 else records)
    return single_response(
        {
            "feature_sets": {
                "crypto_alpha": [
                    "momentum_12h",
                    "volatility_ratio",
                    "funding_rate",
                    "orderbook_imbalance",
                ],
                "sports_match_outcome": [
                    "form_rating",
                    "elo_delta",
                    "market_odds",
                    "h2h_record",
                    "injuries",
                ],
            },
            "training_schedule": {
                "crypto_alpha": "daily_04:00_utc",
                "sports_match_outcome": "weekly_monday_06:00_utc",
            },
            "drift_thresholds": {
                "warning": 0.05,
                "critical": 0.15,
                "auto_retrain": 0.20,
            },
            "validation_rules": {
                "min_accuracy": 0.50,
                "max_drawdown_pct": 15.0,
                "min_backtest_months": 3,
            },
        }
    )


@router.post("/models/{model_id}/promote")
async def promote_model(
    request: Request,
    model_id: str,
) -> dict[str, object]:
    """Promote a model version to production."""
    service = get_service(request)

    updated = service.update(
        "model_versions",
        model_id,
        {
            "status": "production",
            "promoted_at": datetime.now(UTC).isoformat(),
        },
    )
    if updated:
        return single_response({"model": updated, "status": "promoted"})
    return {"error": {"code": "NOT_FOUND", "message": f"Model {model_id} not found"}}
