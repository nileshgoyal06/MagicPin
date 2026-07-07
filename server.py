"""
Neon Bot — magicpin AI Challenge
FastAPI server exposing all 5 required endpoints.

Run: uvicorn server:app --host 0.0.0.0 --port 8080
"""
import time
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

from settings import TEAM_NAME, TEAM_MEMBERS, CONTACT_EMAIL, BOT_VERSION, APPROACH, LLM_MODEL
from store import ContextRepository
from dialogue import DialogueManager
from engine import MessageComposer

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("neon-bot")

# App
app = FastAPI(title="Neon Bot — NightOwlCoders", version=BOT_VERSION)
START_TIME = time.time()

# Core components
repository = ContextRepository()
dialogue_mgr = DialogueManager()
composer = MessageComposer(repository, dialogue_mgr)


# ============================================================================
# Pydantic Models
# ============================================================================

class ContextPushRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = []


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


# ============================================================================
# GET /v1/healthz — Liveness probe
# ============================================================================

@app.get("/v1/healthz")
async def healthz():
    """Health check endpoint. Returns status and context counts."""
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts_loaded": repository.scope_counts(),
    }


# ============================================================================
# GET /v1/metadata — Bot identity
# ============================================================================

@app.get("/v1/metadata")
async def metadata():
    """Bot identity and team info."""
    return {
        "team_name": TEAM_NAME,
        "team_members": TEAM_MEMBERS,
        "model": LLM_MODEL,
        "approach": APPROACH,
        "contact_email": CONTACT_EMAIL,
        "version": BOT_VERSION,
        "submitted_at": "2026-07-06T15:00:00Z",
    }


# ============================================================================
# POST /v1/context — Receive context push
# ============================================================================

@app.post("/v1/context")
async def push_context(body: ContextPushRequest):
    """
    Receive a context push from the judge.
    Idempotent by (scope, context_id, version).
    """
    valid_scopes = {"category", "merchant", "customer", "trigger"}
    if body.scope not in valid_scopes:
        return {
            "accepted": False,
            "reason": "invalid_scope",
            "details": f"Scope must be one of: {valid_scopes}",
        }

    result = repository.push(body.scope, body.context_id, body.version, body.payload)
    logger.info(
        f"Context push: {body.scope}/{body.context_id} v{body.version} → "
        f"{'accepted' if result.get('accepted') else result.get('reason', 'rejected')}"
    )
    return result


# ============================================================================
# POST /v1/tick — Periodic wake-up
# ============================================================================

@app.post("/v1/tick")
async def tick(body: TickRequest):
    """
    Periodic tick from the judge. Bot evaluates triggers and returns actions.
    """
    actions = []
    processed_merchants = set()  # one action per merchant per tick

    for trigger_id in body.available_triggers:
        # Get trigger to check merchant
        trigger = repository.get_trigger(trigger_id)
        if not trigger:
            continue

        merchant_id = trigger.get("merchant_id", "")

        # Skip if we already have an action for this merchant this tick
        # (But allow customer-scoped triggers for same merchant)
        action_key = f"{merchant_id}:{trigger.get('customer_id', '')}"
        if action_key in processed_merchants:
            continue

        # Compose
        action = composer.compose_for_tick(trigger_id)
        if action:
            actions.append(action)
            processed_merchants.add(action_key)

        # Respect the 20-action cap
        if len(actions) >= 20:
            break

    logger.info(f"Tick at {body.now}: {len(actions)} actions from {len(body.available_triggers)} triggers")
    return {"actions": actions}


# ============================================================================
# POST /v1/reply — Receive a reply from merchant/customer
# ============================================================================

@app.post("/v1/reply")
async def reply(body: ReplyRequest):
    """
    Handle a reply from the simulated merchant/customer.
    Returns: {action: "send"|"wait"|"end", body?: str, cta?: str, rationale: str}
    """
    # Check if conversation was already ended
    if repository.is_conversation_closed(body.conversation_id):
        return {
            "action": "end",
            "rationale": "Conversation was previously ended.",
        }

    result = composer.compose_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id or "",
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
    )

    logger.info(
        f"Reply for conv {body.conversation_id}: "
        f"action={result.get('action', '?')}, "
        f"body={result.get('body', '')[:60] if result.get('body') else 'n/a'}..."
    )
    return result


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from settings import BOT_PORT, BOT_HOST
    uvicorn.run(app, host=BOT_HOST, port=BOT_PORT)
