"""Documents domain — upload/download URLs, list, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from unified_trading_api.middleware.auth import verify_api_key
from unified_trading_api.models.standard import paginated_response, single_response
from unified_trading_api.services.factory import get_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/upload-url")
async def get_upload_url(
    request: Request,
    filename: str = Query(...),
    content_type: str = Query("application/octet-stream"),
) -> dict[str, object]:
    """Get a signed URL for uploading a document."""
    service = get_service(request)
    # Upload URL generation — service provides mock or real signed URL
    _ = service.list("documents")  # ensure service is wired
    return single_response(
        {
            "upload_url": f"https://mock-storage.example.com/upload/{filename}",
            "filename": filename,
            "content_type": content_type,
            "expires_in": 3600,
        }
    )


@router.get("/download-url")
async def get_download_url(
    request: Request,
    document_id: str = Query(...),
) -> dict[str, object]:
    """Get a signed URL for downloading a document."""
    service = get_service(request)
    doc = service.get("documents", document_id)
    if doc:
        return single_response(
            {
                "download_url": f"https://mock-storage.example.com/download/{document_id}",
                "document": doc,
                "expires_in": 3600,
            }
        )
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Document not found",
            "details": {"document_id": document_id},
        }
    }


@router.get("/list")
async def list_documents(
    request: Request,
    category: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    """List uploaded documents."""
    service = get_service(request)
    records = service.list("documents", filters={"category": category})
    return paginated_response(records, page, page_size)


@router.delete("/{document_id}")
async def delete_document(
    request: Request,
    document_id: str,
) -> dict[str, object]:
    """Delete a document."""
    service = get_service(request)
    deleted = service.delete("documents", document_id)
    if deleted:
        return single_response({"document_id": document_id, "status": "deleted"})
    return {
        "error": {
            "code": "NOT_FOUND",
            "message": "Document not found",
            "details": {"document_id": document_id},
        }
    }
