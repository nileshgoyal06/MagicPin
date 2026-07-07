"""
In-memory context store with version tracking for Neon bot.
Handles idempotent context pushes and provides fast keyed lookups.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContextRepository:
    """Thread-safe in-memory repository keyed by (scope, context_id)."""

    def __init__(self):
        # (scope, context_id) -> {"version": int, "payload": dict}
        self._data: dict[tuple[str, str], dict[str, Any]] = {}
        # Suppression keys that have already fired
        self._fired_suppressions: set[str] = set()
        # Conversation IDs that have been closed
        self._closed_conversations: set[str] = set()
        # Merchant IDs that opted out of messaging
        self._opted_out: set[str] = set()

    def push(self, scope: str, context_id: str, version: int, payload: dict) -> dict:
        """
        Push a context update idempotently.
        - Same or older version → no-op (stale_version)
        - Newer version → atomic replace
        """
        key = (scope, context_id)
        existing = self._data.get(key)

        if existing and existing["version"] >= version:
            return {
                "accepted": False,
                "reason": "stale_version",
                "current_version": existing["version"],
            }

        self._data[key] = {"version": version, "payload": payload}
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        logger.info(f"Stored context: {scope}/{context_id} v{version}")
        return {
            "accepted": True,
            "ack_id": f"ack_{context_id}_v{version}",
            "stored_at": now_iso,
        }

    def get(self, scope: str, context_id: str) -> Optional[dict]:
        """Return payload for a context entry, or None if not found."""
        entry = self._data.get((scope, context_id))
        return entry["payload"] if entry else None

    # ── Typed accessors ───────────────────────────────────────────────────────

    def get_category(self, slug: str) -> Optional[dict]:
        return self.get("category", slug)

    def get_merchant(self, merchant_id: str) -> Optional[dict]:
        return self.get("merchant", merchant_id)

    def get_customer(self, customer_id: str) -> Optional[dict]:
        return self.get("customer", customer_id)

    def get_trigger(self, trigger_id: str) -> Optional[dict]:
        return self.get("trigger", trigger_id)

    def get_category_for_merchant(self, merchant_id: str) -> Optional[dict]:
        """Resolve category context for a given merchant."""
        merchant = self.get_merchant(merchant_id)
        if not merchant:
            return None
        category_slug = merchant.get("category_slug", "")
        return self.get_category(category_slug)

    def scope_counts(self) -> dict[str, int]:
        """Return record counts per scope — useful for /healthz."""
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _) in self._data:
            if scope in counts:
                counts[scope] += 1
        return counts

    # ── Suppression helpers ───────────────────────────────────────────────────

    def mark_suppression(self, key: str):
        """Record that a suppression key has been consumed."""
        self._fired_suppressions.add(key)

    def is_suppressed(self, key: str) -> bool:
        """Return True if this suppression key has already fired."""
        return key in self._fired_suppressions

    # ── Conversation lifecycle ────────────────────────────────────────────────

    def close_conversation(self, conversation_id: str):
        """Mark a conversation as closed."""
        self._closed_conversations.add(conversation_id)

    def is_conversation_closed(self, conversation_id: str) -> bool:
        """Return True if this conversation has been closed."""
        return conversation_id in self._closed_conversations

    # ── Opt-out management ────────────────────────────────────────────────────

    def opt_out_merchant(self, merchant_id: str):
        """Record that a merchant has opted out of messaging."""
        self._opted_out.add(merchant_id)

    def is_merchant_opted_out(self, merchant_id: str) -> bool:
        """Return True if this merchant has opted out."""
        return merchant_id in self._opted_out

    # ── Utility ───────────────────────────────────────────────────────────────

    def all_triggers(self) -> list[tuple[str, dict]]:
        """Return all stored triggers as (trigger_id, payload) pairs."""
        result = []
        for (scope, cid), entry in self._data.items():
            if scope == "trigger":
                result.append((cid, entry["payload"]))
        return result
