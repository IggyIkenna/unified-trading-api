"""Reporting domain — reports, settlements, reconciliation.

In mock mode: serves from MockStateStore.
In real mode: proxies to client-reporting-api (port 8014).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginate
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])

# Unauthenticated health sub-router — mounted by main.py at /reporting prefix
health_router = APIRouter()

logger = logging.getLogger(__name__)

_CLIENT_REPORTING_URL = "http://localhost:8014"


@health_router.get("/health")
async def reporting_health(request: Request) -> JSONResponse:
    """Health probe for client-reporting-api domain.

    Mock mode: returns synthetic OK (no downstream service needed).
    Real mode: proxies to client-reporting-api at port 8014.
    Returns HTTP 503 when downstream is unreachable so the UI correctly detects "down".
    """
    mock_mode: bool = getattr(request.app.state, "mock_mode", True)  # pyright: ignore[reportAny]
    if mock_mode:
        return JSONResponse(
            {
                "status": "ok",
                "service": "client-reporting-api",
                "mode": "mock",
                "detail": "served by unified-trading-api gateway (mock mode)",
            }
        )
    try:
        async with httpx.AsyncClient(base_url=_CLIENT_REPORTING_URL, timeout=5.0) as client:
            resp = await client.get("/health")
            if resp.status_code == 200:
                result: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
                return JSONResponse(result)
            return JSONResponse(
                {
                    "status": "down",
                    "service": "client-reporting-api",
                    "detail": f"HTTP {resp.status_code}",
                },
                status_code=503,
            )
    except Exception as exc:
        logger.warning("client-reporting-api health check failed: %s", exc)
        return JSONResponse(
            {
                "status": "down",
                "service": "client-reporting-api",
                "detail": str(exc),
            },
            status_code=503,
        )


async def _proxy_or_mock(
    request: Request,
    path: str,
    params: dict[str, str | int | None] | None = None,
) -> dict[str, object] | None:
    """In real mode, proxy to client-reporting-api. Returns None if mock mode."""
    mock_mode: bool = getattr(request.app.state, "mock_mode", True)  # pyright: ignore[reportAny]
    if mock_mode:
        return None
    try:
        async with httpx.AsyncClient(base_url=_CLIENT_REPORTING_URL, timeout=10.0) as client:
            effective_params: dict[str, str | int | None] = params if params is not None else {}
            cleaned = {k: v for k, v in effective_params.items() if v is not None}
            resp = await client.get(f"/api{path}", params=cleaned)
            result: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
            return result
    except Exception:
        logger.exception("Failed to proxy to client-reporting-api")
        return None


@router.get("/reports")
async def get_reports(
    request: Request,
    report_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get generated reports."""
    proxied = await _proxy_or_mock(request, "/reports", {"report_type": report_type})
    if proxied is not None:
        return proxied
    service = get_service(request)
    records = service.list("reports", filters={"report_type": report_type})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/settlements")
async def get_settlements(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get settlement reports."""
    service = get_service(request)
    records = service.list("reporting_settlements", filters={"status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/reconciliation")
async def get_reconciliation(
    request: Request,
    date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get reconciliation results."""
    service = get_service(request)
    records = service.list("reconciliation", filters={"date": date})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.get("/regulatory")
async def get_regulatory_reports(
    request: Request,
    report_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get regulatory report records (MiFID II, FCA, EMIR)."""
    service = get_service(request)
    records = service.list("regulatory_reports", filters={"report_type": report_type})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}


@router.post("/generate")
async def generate_report(
    request: Request,
) -> dict[str, object]:
    """Generate a report + auto-create invoice if applicable.

    Mock mode: creates report record, optionally creates invoice
    and settlement records as side effects.
    """
    import random
    import uuid

    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    now = datetime.now(UTC).isoformat()
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    report_type = str(body.get("type", "pnl"))
    client_name = str(body.get("client", "All Clients"))

    report = service.create(
        "generated_reports",
        {
            "id": report_id,
            "name": str(body.get("name", f"{report_type.upper()} Report")),
            "type": report_type,
            "client": client_name,
            "format": str(body.get("format", "PDF")),
            "status": "ready",
            "generated_at": now,
            **body,
        },
    )

    # Auto-generate invoice for fee-related reports
    invoice = None
    if report_type in ("fees", "pnl", "nav", "performance"):
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        amount = round(random.uniform(500, 25000), 2)
        invoice = service.create(
            "invoices",
            {
                "id": invoice_id,
                "report_id": report_id,
                "client": client_name,
                "type": f"{report_type}_fee",
                "amount": amount,
                "currency": "USD",
                "status": "pending",
                "issued_at": now,
                "due_date": datetime(2026, 4, 30, tzinfo=UTC).isoformat(),
                "line_items": [
                    {"description": f"Management fee — {client_name}", "amount": round(amount * 0.6, 2)},
                    {"description": f"Performance fee — {client_name}", "amount": round(amount * 0.3, 2)},
                    {"description": "Admin & custody", "amount": round(amount * 0.1, 2)},
                ],
            },
        )

    return {"status": "ready", "report": report, "invoice": invoice}


@router.get("/download/{report_id}")
async def download_report(
    request: Request,
    report_id: str,
) -> object:
    """Download a generated report. In mock mode serves a sample PDF."""
    service = get_service(request)
    report = service.get("generated_reports", report_id)
    if not report:
        return {"error": {"code": "NOT_FOUND", "message": "Report not found"}}

    # In mock mode, serve sample PDF
    sample_pdf = (
        Path(__file__).parent.parent / "mock_data" / "sample_reports" / "sample_pnl_report.pdf"
    )
    if sample_pdf.exists():
        return FileResponse(
            sample_pdf,
            media_type="application/pdf",
            filename=f"{report_id}.pdf",
        )
    return {
        "report": report,
        "download_url": f"https://mock-reports.example.com/{report_id}.pdf",
    }


@router.post("/schedules")
async def create_report_schedule(
    request: Request,
) -> dict[str, object]:
    """Create a scheduled report configuration."""
    service = get_service(request)
    body: dict[str, object] = await request.json()  # pyright: ignore[reportAny]
    record = service.create("scheduled_reports", body)
    return {"status": "created", "schedule": record}


@router.get("/schedules")
async def get_report_schedules(
    request: Request,
) -> dict[str, object]:
    """Get scheduled report configurations."""
    service = get_service(request)
    return {"schedules": service.list("scheduled_reports")}


@router.get("/pnl-attribution")
async def get_pnl_attribution(
    request: Request,
    period: str = Query("1d"),
) -> dict[str, object]:
    """Get PnL attribution breakdown by strategy/venue/asset class."""
    service = get_service(request)
    records = service.list("pnl_attribution", filters={"period": period})
    return {"period": period, "attribution": records}


@router.get("/executive-summary")
async def get_executive_summary(
    request: Request,
    period: str = Query("1d"),
) -> dict[str, object]:
    """Get executive summary for reporting dashboard."""
    service = get_service(request)
    records = service.list("executive_summary", filters={"period": period})
    return {"period": period, "summary": records[0] if records else {}}


@router.get("/invoices")
async def get_invoices(
    request: Request,
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """Get invoice list."""
    service = get_service(request)
    records = service.list("invoices", filters={"status": status})
    data, pagination = paginate(records, page, page_size)
    return {"data": data, "pagination": pagination.model_dump()}
