# Quality Gate Bypass Audit — unified-trading-api

## Broad except Exception

**Files:** `routes/reporting.py`, `routes/websocket.py`

**Justification:** Both use `except Exception:` as top-level error handlers for async operations:

- `reporting.py`: PDF generation error handler — logs error and returns HTTP 500
- `websocket.py`: WebSocket connection error handler — logs and closes connection gracefully

These are terminal catch-all handlers at the boundary of async operations where any unhandled
exception would otherwise crash the server. They log the full traceback via `logger.exception()`.
