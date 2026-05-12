#!/usr/bin/env python3
"""Export OpenAPI spec from the unified-trading-api FastAPI application.

Imports the app directly (no server startup required) and extracts
the OpenAPI JSON schema.

Usage:
    python scripts/export_openapi.py                     # write to stdout
    python scripts/export_openapi.py --output spec.json  # write to file
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure unified-trading-api is importable
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

# Set mock mode so the app can be constructed without cloud credentials
import os

os.environ.setdefault("CLOUD_PROVIDER", "local")  # config-bootstrap:
os.environ.setdefault("CLOUD_MOCK_MODE", "true")  # config-bootstrap:
os.environ.setdefault("DISABLE_AUTH", "true")  # config-bootstrap:
os.environ.setdefault("MOCK_STATE_MODE", "deterministic")  # config-bootstrap:


def get_openapi_spec() -> dict[str, object]:
    """Get the OpenAPI spec dict directly from the FastAPI app (no server needed)."""
    from unified_trading_api.main import create_app

    app = create_app()
    spec = app.openapi()
    return spec


def main() -> int:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Export OpenAPI spec from unified-trading-api")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    args = parser.parse_args()

    spec = get_openapi_spec()
    json_str = json.dumps(spec, indent=2, sort_keys=False, default=str) + "\n"

    if args.output:
        output_path: Path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_str)
        route_count = 0
        paths = spec.get("paths")
        if isinstance(paths, dict):
            route_count = len(paths)
        print(f"Wrote OpenAPI spec to {output_path} ({route_count} paths)")
    else:
        sys.stdout.write(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
