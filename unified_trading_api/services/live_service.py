"""Live (real mode) stub for DomainService.

Each method raises NotImplementedError with the service name, making it
clear what needs wiring without breaking the code. As real backend
services are connected, replace these stubs with actual clients.
"""

from __future__ import annotations


class LiveDomainService:
    """Stub real-mode service. All methods raise NotImplementedError."""

    def list(
        self,
        collection: str,
        _filters: dict[str, str | int | float | bool | None] | None = None,
    ) -> list[dict[str, object]]:
        raise NotImplementedError(f"Live mode not wired for collection '{collection}'")

    def get(self, collection: str, _record_id: str) -> dict[str, object] | None:
        raise NotImplementedError(f"Live mode not wired for collection '{collection}'")

    def create(self, collection: str, _data: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError(f"Live mode not wired for collection '{collection}'")

    def update(
        self, collection: str, _record_id: str, _data: dict[str, object]
    ) -> dict[str, object] | None:
        raise NotImplementedError(f"Live mode not wired for collection '{collection}'")

    def delete(self, collection: str, _record_id: str) -> bool:
        raise NotImplementedError(f"Live mode not wired for collection '{collection}'")

    def reset(self) -> None:
        pass  # No-op in live mode
