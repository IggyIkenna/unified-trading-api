"""Documents domain — upload/download URLs, list, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.mock_data.state_store import mock_store

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/upload-url")
async def get_upload_url(
    request: Request,
    filename: str = Query(...),
    content_type: str = Query("application/octet-stream"),
) -> dict[str, object]:
    """Get a signed URL for uploading a document."""
    if getattr(request.app.state, "mock_mode", True):
        return {
            "upload_url": f"https://mock-storage.example.com/upload/{filename}",
            "filename": filename,
            "content_type": content_type,
            "expires_in": 3600,
        }
    return {"error": "real mode not yet wired"}


@router.get("/download-url")
async def get_download_url(
    request: Request,
    document_id: str = Query(...),
) -> dict[str, object]:
    """Get a signed URL for downloading a document."""
    if getattr(request.app.state, "mock_mode", True):
        doc = mock_store.get("documents", "document_id", document_id)
        if doc:
            return {
                "download_url": f"https://mock-storage.example.com/download/{document_id}",
                "document": doc,
                "expires_in": 3600,
            }
        return {"error": "document not found", "document_id": document_id}
    return {"error": "real mode not yet wired"}


@router.get("/list")
async def list_documents(
    request: Request,
    category: str = Query(None),
    limit: int = Query(50),
) -> dict[str, object]:
    """List uploaded documents."""
    if getattr(request.app.state, "mock_mode", True):
        records = mock_store.list("documents")
        if category:
            records = [r for r in records if r.get("category") == category]
        return {"documents": records[:limit]}
    return {"error": "real mode not yet wired"}


@router.delete("/{document_id}")
async def delete_document(
    request: Request,
    document_id: str,
) -> dict[str, object]:
    """Delete a document."""
    if getattr(request.app.state, "mock_mode", True):
        deleted = mock_store.delete("documents", "document_id", document_id)
        if deleted:
            return {"status": "deleted", "document_id": document_id}
        return {"status": "not_found", "document_id": document_id}
    return {"error": "real mode not yet wired"}
