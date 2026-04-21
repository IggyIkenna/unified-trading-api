"""ML domain — model families, experiments, training, versions, deployments."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from unified_trading_library import FeatureGroupRegistry

from unified_trading_api.middleware.auth import (  # noqa: qg-deep-import — self-package
    verify_api_key,  # noqa: qg-deep-import — self-package
)
from unified_trading_api.models.standard import (  # noqa: qg-deep-import — self-package
    paginated_response,
    single_response,
)
from unified_trading_api.services.factory import get_service  # noqa: qg-deep-import — self-package

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


# ---------------------------------------------------------------------------
# Grid config CRUD — manages TrainingGridConfig objects
# ---------------------------------------------------------------------------


@router.get("/grid-configs")
async def list_grid_configs(
    request: Request,
    category: str = Query(None, description="Filter by category: CEFI, TRADFI, SPORTS"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """List saved ML training grid configurations."""
    service = get_service(request)
    records = service.list("ml_grid_configs", filters={"category": category})
    return paginated_response(records, page, page_size)


@router.get("/grid-configs/{config_name}")
async def get_grid_config(
    request: Request,
    config_name: str,
) -> dict[str, object]:
    """Get a specific grid config by name."""
    service = get_service(request)
    record = service.get("ml_grid_configs", config_name)
    if record:
        return single_response(record)
    return {"error": {"code": "NOT_FOUND", "message": f"Config '{config_name}' not found"}}


@router.post("/grid-configs")
async def create_grid_config(
    request: Request,
) -> dict[str, object]:
    """Create a new grid configuration.

    Body must include ``name`` and at least one of ``instruments`` (CEFI/TRADFI)
    or ``sports_families`` (SPORTS).  Feature groups default to all available
    for the category when omitted.
    """
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    if "created_at" not in body:
        body["created_at"] = datetime.now(UTC).isoformat()
    record = service.create("ml_grid_configs", body)
    return single_response({"config": record, "status": "created"})


@router.put("/grid-configs/{config_name}")
async def update_grid_config(
    request: Request,
    config_name: str,
) -> dict[str, object]:
    """Update an existing grid configuration."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    body["updated_at"] = datetime.now(UTC).isoformat()
    updated = service.update("ml_grid_configs", config_name, body)
    if updated:
        return single_response({"config": updated, "status": "updated"})
    return {"error": {"code": "NOT_FOUND", "message": f"Config '{config_name}' not found"}}


@router.delete("/grid-configs/{config_name}")
async def delete_grid_config(
    request: Request,
    config_name: str,
) -> dict[str, object]:
    """Delete a grid configuration."""
    service = get_service(request)
    deleted = service.delete("ml_grid_configs", config_name)
    if deleted:
        return single_response({"name": config_name, "status": "deleted"})
    return {"error": {"code": "NOT_FOUND", "message": f"Config '{config_name}' not found"}}


@router.get("/feature-groups")
async def get_available_feature_groups(
    request: Request,
    category: str = Query("CEFI", description="Category: CEFI, TRADFI, SPORTS, DEFI"),
) -> dict[str, object]:
    """Get available feature groups for a category.

    Returns the list of feature group names that can be used in grid configs.
    Groups are sourced from the FeatureGroupRegistry (SSOT in UTL).
    """
    upper = category.upper()
    groups = FeatureGroupRegistry.groups_for_domain(upper)
    return single_response({"category": upper, "feature_groups": groups})


# ---------------------------------------------------------------------------
# Training run detail, cancel, queue
# ---------------------------------------------------------------------------


@router.get("/training-runs/{run_id}")
async def get_training_run_detail(
    request: Request,
    run_id: str,
) -> dict[str, object]:
    """Get a specific training run by ID — status, metrics, config."""
    service = get_service(request)
    record = service.get("training_runs", run_id)
    if record:
        return single_response(record)
    return single_response(
        {
            "id": run_id,
            "status": "completed",
            "category": "CEFI",
            "instrument_id": "BINANCE-FUTURES:PERPETUAL:BTC-USDT",
            "timeframe": "1m",
            "target_type": "swing_high",
            "started_at": "2026-04-16T13:00:00Z",
            "completed_at": "2026-04-16T13:49:38Z",
            "metrics": {
                "accuracy": 0.647,
                "precision_macro": 0.512,
                "recall_macro": 0.489,
                "f1_macro": 0.499,
                "num_samples": 42006,
                "num_features": 58,
            },
            "config": {
                "walk_forward_folds": 2,
                "lookback_window": 5,
                "early_stopping_rounds": 50,
            },
        }
    )


@router.post("/training-runs/{run_id}/cancel")
async def cancel_training_run(
    request: Request,
    run_id: str,
) -> dict[str, object]:
    """Cancel a running training job."""
    service = get_service(request)
    updated = service.update("training_runs", run_id, {"status": "cancelled"})
    if updated:
        return single_response({"id": run_id, "status": "cancelled"})
    return single_response({"id": run_id, "status": "cancelled", "message": "mock cancellation"})


@router.get("/training/queue")
async def get_training_queue(
    request: Request,
) -> dict[str, object]:
    """Get training job queue — queued, running, recently completed."""
    service = get_service(request)
    records = service.list("training_runs", filters={"status": "queued"})
    if records:
        return single_response(records)
    return single_response(
        {
            "queued": [],
            "running": [],
            "recently_completed": [
                {
                    "id": "run-20260416-134938",
                    "category": "CEFI",
                    "instrument": "BTC-USDT",
                    "status": "completed",
                    "started_at": "2026-04-16T13:00:00Z",
                    "completed_at": "2026-04-16T13:49:38Z",
                    "accuracy": 0.647,
                },
            ],
        }
    )


# ---------------------------------------------------------------------------
# Pipeline status, alerts
# ---------------------------------------------------------------------------


@router.get("/pipeline/status")
async def get_pipeline_status(
    request: Request,
) -> dict[str, object]:
    """Get ML pipeline KPIs — models in production, training stats, feature freshness."""
    service = get_service(request)
    records = service.list("ml_pipeline_status")
    if records:
        return single_response(records[0] if len(records) == 1 else records)
    return single_response(
        {
            "models_in_production": 3,
            "models_staging": 2,
            "models_training": 0,
            "total_training_runs": 47,
            "last_training_run": "2026-04-16T13:49:38Z",
            "next_scheduled": "2026-04-17T04:00:00Z",
            "feature_freshness": {
                "technical_indicators": "2026-04-16T23:59:00Z",
                "market_structure": "2026-04-16T23:59:00Z",
                "swing_outcome_targets": "2026-04-16T23:59:00Z",
            },
            "categories": {
                "CEFI": {"models": 2, "last_run": "2026-04-16T13:49:38Z"},
                "TRADFI": {"models": 1, "last_run": "2026-04-15T04:12:00Z"},
                "SPORTS": {"models": 0, "last_run": None},
                "DEFI": {"models": 0, "last_run": None},
            },
        }
    )


@router.get("/alerts")
async def get_ml_alerts(
    request: Request,
    severity: str = Query(None, description="Filter by severity: info, warning, critical"),
) -> dict[str, object]:
    """Get active ML alerts — model drift, training failures, stale predictions."""
    service = get_service(request)
    records = service.list("ml_alerts", filters={"severity": severity})
    if records:
        return single_response(records)
    return single_response(
        [
            {
                "id": "alert-drift-001",
                "type": "model_drift",
                "severity": "warning",
                "model_id": "crypto-alpha-signal-v2",
                "message": "Feature drift score 0.078 exceeds warning threshold 0.05",
                "created_at": "2026-04-16T10:00:00Z",
                "acknowledged": False,
            },
            {
                "id": "alert-stale-001",
                "type": "stale_predictions",
                "severity": "info",
                "model_id": "sports-match-outcome-v3",
                "message": "No predictions generated in last 24h (off-season)",
                "created_at": "2026-04-16T06:00:00Z",
                "acknowledged": True,
            },
        ]
    )


# ---------------------------------------------------------------------------
# Run analysis, comparison, registry
# ---------------------------------------------------------------------------


@router.get("/analysis/runs/{run_id}")
async def get_run_analysis_bundle(
    request: Request,
    run_id: str,
) -> dict[str, object]:
    """Get analysis bundle for a training run — metrics, SHAP, hyperparams, config."""
    service = get_service(request)
    record = service.get("training_runs", run_id)
    if record:
        return single_response(record)
    return single_response(
        {
            "run_id": run_id,
            "metrics": {
                "accuracy": 0.647,
                "precision_macro": 0.512,
                "recall_macro": 0.489,
                "f1_macro": 0.499,
                "average_precision": 0.423,
            },
            "shap_summary": {
                "top_features": [
                    {"name": "rsi_14", "importance": 0.0842},
                    {"name": "macd_histogram", "importance": 0.0713},
                    {"name": "bb_position_20", "importance": 0.0654},
                    {"name": "atr_14", "importance": 0.0598},
                    {"name": "stoch_k_14", "importance": 0.0521},
                ],
                "plot_urls": [],
            },
            "hyperparameters": {
                "num_leaves": 31,
                "max_depth": -1,
                "learning_rate": 0.05,
                "feature_fraction": 0.7,
                "min_child_samples": 20,
            },
            "config": {
                "category": "CEFI",
                "instrument_id": "BINANCE-FUTURES:PERPETUAL:BTC-USDT",
                "timeframe": "1m",
                "target_type": "swing_high",
                "walk_forward_folds": 2,
                "num_features": 58,
                "num_samples": 42006,
            },
            "walk_forward_results": [
                {"fold": 1, "train_rows": 28004, "test_rows": 14002, "accuracy": 0.639},
                {"fold": 2, "train_rows": 33605, "test_rows": 8401, "accuracy": 0.655},
            ],
        }
    )


@router.post("/analysis/compare")
async def compare_runs(
    request: Request,
) -> dict[str, object]:
    """Compare 2-4 training runs side by side — metrics deltas."""
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    raw_ids: object = body.get("run_ids", [])
    run_ids: list[str] = (
        [str(r) for r in list(raw_ids)]  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType]
        if isinstance(raw_ids, list)
        else []
    )
    if len(run_ids) < 2:
        return {"error": {"code": "INVALID_INPUT", "message": "Need at least 2 run_ids"}}

    service = get_service(request)
    runs: list[dict[str, object]] = []
    for rid in run_ids[:4]:
        record = service.get("training_runs", str(rid))
        if record:
            runs.append({"run_id": str(rid), **record})
        else:
            runs.append(
                {
                    "run_id": str(rid),
                    "accuracy": 0.60 + len(runs) * 0.02,
                    "f1_macro": 0.45 + len(runs) * 0.015,
                    "num_features": 58,
                }
            )
    return single_response({"runs": runs, "count": len(runs)})


@router.get("/registry/models")
async def get_registry_models(
    request: Request,
    status: str = Query(None, description="Filter: staging, production, archived"),
    family: str = Query(None, description="Filter by model family"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """List models from the model registry.

    In real mode reads from ml-models-store GCS model_registry/.
    """
    service = get_service(request)
    records = service.list("model_versions", filters={"status": status, "family": family})
    if records:
        return paginated_response(records, page, page_size)
    mock_models: list[dict[str, object]] = [
        {
            "model_id": "CEFI_BTC_swing-high_LIGHTGBM_1m_V20260416134938",
            "family": "swing_high",
            "version": "V20260416134938",
            "category": "CEFI",
            "instrument": "BTC-USDT",
            "timeframe": "1m",
            "training_period": "2026-04",
            "status": "staging",
            "accuracy": 0.647,
            "f1_macro": 0.499,
            "created_at": "2026-04-16T13:49:38Z",
        },
        {
            "model_id": "CEFI_ETH_swing-high_LIGHTGBM_1m_V20260415120000",
            "family": "swing_high",
            "version": "V20260415120000",
            "category": "CEFI",
            "instrument": "ETH-USDT",
            "timeframe": "1m",
            "training_period": "2026-04",
            "status": "production",
            "accuracy": 0.662,
            "f1_macro": 0.523,
            "created_at": "2026-04-15T12:00:00Z",
        },
        {
            "model_id": "TRADFI_SPY_swing-high_LIGHTGBM_5m_V20260414080000",
            "family": "swing_high",
            "version": "V20260414080000",
            "category": "TRADFI",
            "instrument": "SPY-USD",
            "timeframe": "5m",
            "training_period": "2026-04",
            "status": "production",
            "accuracy": 0.614,
            "f1_macro": 0.471,
            "created_at": "2026-04-14T08:00:00Z",
        },
    ]
    return paginated_response(mock_models, page, page_size)


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
