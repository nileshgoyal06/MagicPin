"""
Dialogue manager for multi-turn conversation handling in Neon bot.
Tracks conversation state, classifies merchant/customer replies, and manages flow.
"""
import re
import logging
from typing import Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Auto-reply detection patterns ─────────────────────────────────────────────
AUTOREPLY_PATTERNS = [
    r"thank you for contacting",
    r"thanks for reaching out",
    r"our team will respond",
    r"we will get back to you",
    r"your message has been received",
    r"automated (?:reply|response|message)",
    r"i am an automated assistant",
    r"(?:currently|we are) (?:unavailable|busy|away)",
    r"working hours",
    r"will revert (?:shortly|soon|back)",
    r"aapki jaankari.*shukriya",
    r"team tak pahuncha",
    r"shukriya.*message",
]

# ── Hostile / opt-out patterns ────────────────────────────────────────────────
HOSTILE_PATTERNS = [
    r"stop\b",
    r"(?:don'?t|do not) (?:message|contact|bother|disturb)",
    r"not interested",
    r"spam",
    r"useless",
    r"stop messaging",
    r"unsubscribe",
    r"leave me alone",
    r"go away",
    r"(?:fuck|shit|damn|hell)\b",
    r"bakwas",
    r"band karo",
    r"pareshan mat karo",
]

# ── Intent commitment patterns ────────────────────────────────────────────────
INTENT_PATTERNS = [
    r"\byes\b",
    r"\bhaan\b",
    r"\bha\b",
    r"\bok\b",
    r"\bokay\b",
    r"let'?s do it",
    r"go ahead",
    r"proceed",
    r"confirm",
    r"kar do",
    r"chalo",
    r"theek hai",
    r"done",
    r"what'?s next",
    r"kya karna hai",
    r"start (?:karo|kar do|it)",
    r"send (?:it|them|me|karo|kar do)",
    r"please (?:send|draft|do|start|share)",
]

# ── Off-topic detection patterns ──────────────────────────────────────────────
OFFTOPIC_PATTERNS = [
    r"gst\b",
    r"income tax",
    r"(?:file|filing|return)\b.*(?:tax|gst)",
    r"loan\b",
    r"(?:personal|home|car)\s+loan",
    r"insurance",
    r"passport",
    r"visa\b",
    r"flight",
    r"train ticket",
    r"weather\b",
    r"cricket score",
]


class ConversationRecord:
    """State for a single conversation with merchant or customer."""

    def __init__(self, conversation_id: str, merchant_id: str,
                 customer_id: Optional[str], trigger_id: str):
        self.conversation_id = conversation_id
        self.merchant_id = merchant_id
        self.customer_id = customer_id
        self.trigger_id = trigger_id
        self.turns: list[dict[str, Any]] = []
        self.status: str = "active"  # active | waiting | ended
        self.autoreply_counter: int = 0
        self.sent_messages: set[str] = set()
        self.created_at = datetime.now(timezone.utc).isoformat()

    def add_turn(self, from_role: str, body: str, ts: Optional[str] = None):
        self.turns.append({
            "from": from_role,
            "body": body,
            "ts": ts or datetime.now(timezone.utc).isoformat(),
        })

    def get_summary(self) -> str:
        """Build a summary of the conversation so far for LLM context."""
        if not self.turns:
            return "No prior messages in this conversation."
        lines = []
        for turn in self.turns[-6:]:  # last 6 turns max
            role_name = "Bot" if turn["from"] in ("bot", "assistant") else "Merchant"
            lines.append(f"[{role_name}]: {turn['body']}")
        return "\n".join(lines)

    def has_sent_message(self, body: str) -> bool:
        """Check if this exact body was already sent in this conversation."""
        normalized = body.strip().lower()
        return normalized in self.sent_messages

    def record_sent_message(self, body: str):
        """Record a sent message body to prevent repetition."""
        self.sent_messages.add(body.strip().lower())


class DialogueManager:
    """Manages all active conversations and reply classification."""

    def __init__(self):
        self._conversations: dict[str, ConversationRecord] = {}

    def get_or_create(self, conversation_id: str, merchant_id: str,
                      customer_id: Optional[str] = None,
                      trigger_id: str = "") -> ConversationRecord:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = ConversationRecord(
                conversation_id, merchant_id, customer_id, trigger_id
            )
        return self._conversations[conversation_id]

    def get(self, conversation_id: str) -> Optional[ConversationRecord]:
        return self._conversations.get(conversation_id)

    def classify_reply(self, message: str, conversation: ConversationRecord) -> str:
        """
        Classify a merchant/customer reply into:
        - auto_reply: Canned WhatsApp Business auto-reply
        - hostile: Opt-out or hostile message
        - intent_commit: Merchant commits to an action
        - off_topic: Off-topic question
        - engaged: Normal engaged response
        """
        msg_normalized = message.lower().strip()

        # 1. Check for auto-reply
        if self._matches_auto_reply(msg_normalized):
            conversation.autoreply_counter += 1
            if conversation.autoreply_counter >= 3:
                return "auto_reply_persistent"
            elif conversation.autoreply_counter >= 2:
                return "auto_reply_repeat"
            return "auto_reply_first"

        # Reset auto-reply count on real message
        conversation.autoreply_counter = 0

        # 2. Check for hostile / opt-out
        if self._matches_any_pattern(msg_normalized, HOSTILE_PATTERNS):
            return "hostile"

        # 3. Check for off-topic
        if self._matches_any_pattern(msg_normalized, OFFTOPIC_PATTERNS):
            return "off_topic"

        # 4. Check for intent commitment
        if self._matches_any_pattern(msg_normalized, INTENT_PATTERNS):
            return "intent_commit"

        # 5. Default: engaged
        return "engaged"

    def _matches_auto_reply(self, msg: str) -> bool:
        """Check if message matches auto-reply patterns."""
        return self._matches_any_pattern(msg, AUTOREPLY_PATTERNS)

    def _matches_any_pattern(self, msg: str, patterns: list[str]) -> bool:
        """Check if message matches any pattern in the list."""
        for pattern in patterns:
            if re.search(pattern, msg, re.IGNORECASE):
                return True
        return False

    def build_rule_based_response(self, classification: str, message: str,
                                   conversation: ConversationRecord) -> Optional[dict]:
        """
        Build a rule-based response for non-engaged classifications.
        Returns None for 'engaged' and 'intent_commit' — those need LLM composition.
        """
        if classification == "auto_reply_first":
            return {
                "action": "send",
                "body": "Looks like an auto-reply 😊 Jab owner dekhe, toh bas 'Yes' reply kar dena for what I shared above.",
                "cta": "binary_yes_no",
                "rationale": "Detected auto-reply (canned greeting). One nudge to surface the message for the owner.",
            }

        if classification == "auto_reply_repeat":
            return {
                "action": "wait",
                "wait_seconds": 86400,
                "rationale": "Same auto-reply received twice. Owner likely not at phone. Waiting 24h before retry.",
            }

        if classification == "auto_reply_persistent":
            return {
                "action": "end",
                "rationale": "Auto-reply received 3+ times. No real engagement signal. Closing conversation.",
            }

        if classification == "hostile":
            return {
                "action": "end",
                "rationale": "Merchant explicitly opted out or expressed frustration. Closing conversation; suppressing future triggers for this merchant.",
            }

        # off_topic, engaged, intent_commit → need LLM composition
        return None

    def get_active_conversation_ids(self, merchant_id: str) -> list[str]:
        """Get all active conversation IDs for a merchant."""
        return [
            conv.conversation_id
            for conv in self._conversations.values()
            if conv.merchant_id == merchant_id and conv.status == "active"
        ]
