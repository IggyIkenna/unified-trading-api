"""Tiered help chatbot — auth-gated AI assistant with 3 knowledge scopes.

PUBLIC  (no auth)     → general service descriptions, glossary, capabilities
CLIENT  (external JWT) → + UI navigation, portfolio context, feature guides
INTERNAL (internal JWT) → + backend ops, runbooks, compliance, architecture

Uses Anthropic Claude API with SSE streaming. Falls back to echo responses
in mock mode when no API key is configured.
"""

# SCHEMA_PROVENANCE_EXEMPT: ChatMessage / ChatRequest are the HTTP request body
# for this gateway's chat endpoint. Not a cross-service domain contract — just
# the shape the UI sends to the chatbot.

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from unified_trading_library import UnifiedCloudConfig

from unified_trading_api.middleware.entitlement import (  # noqa: qg-deep-import — self-package
    OrgType,
    get_entitlement_context,
)
from unified_trading_api.services.app_state import (  # noqa: qg-deep-import — self-package
    get_disable_auth,  # noqa: qg-deep-import — self-package
)

logger = logging.getLogger(__name__)

router = APIRouter()
_cloud_cfg = UnifiedCloudConfig()


# ---------------------------------------------------------------------------
# Tier enum + system prompts
# ---------------------------------------------------------------------------


class ChatTier(StrEnum):
    """Knowledge scope tier for the help chatbot."""

    PUBLIC = "public"
    CLIENT = "client"
    INTERNAL = "internal"


_SYSTEM_PROMPTS: dict[ChatTier, str] = {
    ChatTier.PUBLIC: """\
You are the Odum Research help assistant on the public website of the \
Unified Trading System — an institutional-grade quantitative trading platform.

You may answer general questions about:
- What the platform does (backtesting, execution, risk management, ML-driven strategies)
- Service descriptions (instruments, market data, features, strategy, execution, settlement)
- Glossary and domain concepts (venues, shards, adapters, candles, order types)
- Pricing tiers and capabilities at a high level
- How to get started or request a demo

You MUST NOT:
- Reveal any client-specific data, portfolio details, or trade history
- Discuss internal architecture, deployment details, or operational procedures
- Share API keys, credentials, or security configurations
- Provide specific regulatory advice (you may mention FCA registration generally)

If a question requires client access, respond: \
"This question requires a client account. Please sign in or contact us for a demo."

Keep answers concise, professional, and helpful. Under 5 sentences unless \
the topic genuinely requires more detail.
""",
    ChatTier.CLIENT: """\
You are the Odum Research help assistant for authenticated clients of the \
Unified Trading System.

You may answer questions about:
- Everything in the public tier (services, glossary, concepts)
- UI navigation: where to find features, how dashboards work, filter controls
- Portfolio and position views: how to read P&L breakdowns, risk attribution
- Strategy analytics: Sharpe ratios, drawdown charts, regime indicators
- Execution reports: fill quality, slippage analysis, venue routing
- Data exports and reporting features
- Account settings and preferences

You MUST NOT:
- Reveal internal architecture, deployment details, or operational procedures
- Discuss other clients' data or cross-client information
- Share backend runbooks, incident procedures, or compliance internals
- Provide specific regulatory or legal advice

Keep answers concise and actionable. Reference specific UI locations \
(e.g. "Navigate to Services > Execution > Fill Analysis tab").
""",
    ChatTier.INTERNAL: """\
You are the Odum Research internal help assistant for staff of the \
Unified Trading System.

You may answer questions about:
- Everything in the public and client tiers
- Backend architecture: service topology, data pipelines, messaging protocols
- Operational procedures: deployment, rollback, incident response
- Compliance and regulatory: FCA reporting, MiFID II obligations, audit trails
- Infrastructure: Cloud Run, Pub/Sub, BigQuery, GCS patterns
- Quality gates, CI/CD, version management, staging gates
- Troubleshooting: common errors, log analysis, health checks
- Internal tools: admin UI, debug footer, mock mode, demo personas

You are speaking to an internal team member. Be direct and technical. \
Reference specific services, repos, and commands where helpful.
""",
}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):  # CORRECT-LOCAL: API chat request model
    """A single message in the conversation."""

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(description="Message text")


class ChatRequest(BaseModel):  # CORRECT-LOCAL: API chat request model
    """Incoming chat request."""

    message: str = Field(description="User's current message", min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Previous conversation messages (max 20)",
        max_length=20,
    )


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------


def _resolve_tier(request: Request) -> ChatTier:
    """Determine chat tier from auth context.

    - No auth / unauthenticated → PUBLIC
    - External org → CLIENT
    - Internal org → INTERNAL
    """
    disable_auth = get_disable_auth(request)

    # If auth is disabled (mock mode), treat as internal for full access
    if disable_auth:
        return ChatTier.INTERNAL

    # Try to extract entitlement context
    ctx = get_entitlement_context(request)
    if ctx.org_type == OrgType.INTERNAL:
        return ChatTier.INTERNAL
    return ChatTier.CLIENT


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------


async def _stream_anthropic(
    system_prompt: str,
    messages: list[dict[str, str]],
    api_key: str,
) -> AsyncIterator[str]:
    """Stream response from Anthropic Claude API as SSE events."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)

    async with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            # SSE format: data: <json>\n\n
            event_data = json.dumps({"type": "content", "text": text})
            yield f"data: {event_data}\n\n"

    # Send done event
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _stream_mock(message: str) -> AsyncIterator[str]:
    """Mock streaming response when no API key is available."""
    import asyncio

    mock_response = (
        f"[Mock mode — no ANTHROPIC_API_KEY configured]\n\n"
        f'I received your message: "{message[:100]}{"..." if len(message) > 100 else ""}"\n\n'
        f"In production, I would answer based on your access tier. "
        f"Set ANTHROPIC_API_KEY in Secret Manager to enable real responses."
    )

    # Simulate streaming by sending word by word
    words = mock_response.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == 0 else f" {word}"
        event_data = json.dumps({"type": "content", "text": chunk})
        yield f"data: {event_data}\n\n"
        await asyncio.sleep(0.03)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/message")
async def chat_message(request: Request, body: ChatRequest) -> StreamingResponse:
    """Send a message to the tiered help chatbot.

    Returns an SSE stream of content chunks. Each event is:
      data: {"type": "content", "text": "..."} — partial text
      data: {"type": "done"}                   — stream complete

    The knowledge scope is determined by the caller's auth tier:
      - No auth → PUBLIC (general info only)
      - External org JWT → CLIENT (+ UI help, portfolio context)
      - Internal org JWT → INTERNAL (+ backend ops, compliance)
    """
    tier = _resolve_tier(request)
    system_prompt = _SYSTEM_PROMPTS[tier]

    logger.info(
        "Chat request: tier=%s, message_len=%d, history_len=%d",
        tier,
        len(body.message),
        len(body.history),
    )

    # Build messages list for Claude API
    messages: list[dict[str, str]] = []
    for msg in body.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    # Get API key (config-bootstrap: env var for local dev + Secret Manager)
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")  # config-bootstrap:

    stream = _stream_anthropic(system_prompt, messages, api_key) if api_key else _stream_mock(body.message)

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Chat-Tier": tier.value,
        },
    )


@router.get("/tier")
async def chat_tier(request: Request) -> dict[str, str]:
    """Return the caller's resolved chat tier.

    Useful for the UI to show tier-appropriate help text before
    the user sends a message.
    """
    tier = _resolve_tier(request)
    return {
        "tier": tier.value,
        "description": {
            ChatTier.PUBLIC: "General help — sign in for personalised assistance",
            ChatTier.CLIENT: "Client help — ask about your portfolio, UI navigation, and features",
            ChatTier.INTERNAL: "Internal help — full access including backend ops and compliance",
        }[tier],
        "timestamp": datetime.now(UTC).isoformat(),
    }
