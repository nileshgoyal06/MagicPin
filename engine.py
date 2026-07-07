"""
Message composition engine — the core of the Neon bot.
Takes 4 contexts (category, merchant, trigger, customer?) and produces a composed message.
Handles both tick-based proactive sends and reply-based follow-ups.
"""
import json
import logging
from typing import Optional

from model_client import get_model_client
from templates import (
    MASTER_SYSTEM_PROMPT,
    format_category_context,
    format_merchant_context,
    format_trigger_context,
    format_customer_context,
    build_trigger_instruction,
    build_reply_prompt,
)
from store import ContextRepository
from dialogue import DialogueManager, ConversationRecord

logger = logging.getLogger(__name__)


class MessageComposer:
    """Composes messages using LLM with trigger-kind dispatch."""

    def __init__(self, store: ContextRepository, conv_manager: DialogueManager):
        self.store = store
        self.conv_manager = conv_manager
        self.llm = get_model_client()

    def compose_for_tick(self, trigger_id: str) -> Optional[dict]:
        """
        Compose a proactive message for a trigger.
        Returns an action dict ready for the /v1/tick response, or None if skipped.
        """
        trigger = self.store.get_trigger(trigger_id)
        if not trigger:
            logger.warning(f"Trigger not found: {trigger_id}")
            return None

        # Check suppression
        suppression_key = trigger.get("suppression_key", "")
        if suppression_key and self.store.is_suppressed(suppression_key):
            logger.info(f"Trigger suppressed: {trigger_id} (key: {suppression_key})")
            return None

        # Get merchant
        merchant_id = trigger.get("merchant_id", "")
        if not merchant_id:
            logger.warning(f"Trigger has no merchant_id: {trigger_id}")
            return None

        # Check if merchant opted out
        if self.store.is_merchant_opted_out(merchant_id):
            logger.info(f"Merchant opted out, skipping: {merchant_id}")
            return None

        merchant = self.store.get_merchant(merchant_id)
        if not merchant:
            logger.warning(f"Merchant not found: {merchant_id}")
            return None

        # Get category
        category_slug = merchant.get("category_slug", "")
        category = self.store.get_category(category_slug)
        if not category:
            logger.warning(f"Category not found: {category_slug}")
            return None

        # Get customer (if customer-scoped trigger)
        customer = None
        customer_id = trigger.get("customer_id")
        if customer_id:
            customer = self.store.get_customer(customer_id)

        # Determine send_as
        is_customer_facing = customer is not None and trigger.get("scope") == "customer"
        send_as = "merchant_on_behalf" if is_customer_facing else "neon_bot"

        # Build the prompt
        kind = trigger.get("kind", "generic")
        system = MASTER_SYSTEM_PROMPT
        user_prompt = self._build_composition_prompt(
            category, merchant, trigger, customer, kind
        )

        # Call LLM
        try:
            result = self.llm.complete_json(user_prompt, system)
        except Exception as e:
            logger.error(f"LLM call failed for trigger {trigger_id}: {e}")
            return None

        if not result or not result.get("body"):
            logger.warning(f"Empty LLM result for trigger {trigger_id}")
            return None

        # Post-validate
        result = self._post_validate(result, category, merchant, send_as)

        # Build conversation ID
        conv_id = f"session_{merchant_id}_{trigger_id}"
        if customer_id:
            conv_id = f"session_{customer_id}_{trigger_id}"

        # Create conversation state
        conv = self.conv_manager.get_or_create(
            conv_id, merchant_id, customer_id, trigger_id
        )
        conv.add_turn("bot", result["body"])
        conv.record_sent_message(result["body"])

        # Mark suppression
        if suppression_key:
            self.store.mark_suppression(suppression_key)

        # Build action
        identity = merchant.get("identity", {})
        owner = identity.get("owner_first_name", identity.get("name", ""))

        action = {
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": send_as,
            "trigger_id": trigger_id,
            "template_name": result.get("template_name", f"vera_{kind}_v1"),
            "template_params": result.get("template_params", [owner]),
            "body": result["body"],
            "cta": result.get("cta", "open_ended"),
            "suppression_key": suppression_key,
            "rationale": result.get("rationale", f"Composed for {kind} trigger"),
        }

        logger.info(f"Composed message for {trigger_id}: {result['body'][:80]}...")
        return action

    def compose_reply(self, conversation_id: str, merchant_id: str,
                      customer_id: Optional[str], from_role: str,
                      message: str, turn_number: int) -> dict:
        """
        Compose a reply to a merchant/customer message.
        Returns a reply action dict.
        """
        # Get or create conversation
        conv = self.conv_manager.get(conversation_id)
        if not conv:
            conv = self.conv_manager.get_or_create(
                conversation_id, merchant_id, customer_id, ""
            )

        # Record the incoming message
        conv.add_turn(from_role, message)

        # Classify the reply
        classification = self.conv_manager.classify_reply(message, conv)
        logger.info(f"Reply classified as: {classification} for conv {conversation_id}")

        # Check for rule-based response (auto-reply, hostile)
        rule_response = self.conv_manager.build_rule_based_response(
            classification, message, conv
        )
        if rule_response:
            if rule_response["action"] == "end":
                conv.status = "ended"
                self.store.close_conversation(conversation_id)
                if classification == "hostile":
                    self.store.opt_out_merchant(merchant_id)
            elif rule_response["action"] == "wait":
                conv.status = "waiting"
            return rule_response

        # Need LLM composition for engaged / intent_commit / off_topic
        merchant = self.store.get_merchant(merchant_id) or {}
        category_slug = merchant.get("category_slug", "")
        category = self.store.get_category(category_slug) or {}

        # Get trigger context
        trigger = {}
        if conv.trigger_id:
            trigger = self.store.get_trigger(conv.trigger_id) or {}

        customer = None
        if customer_id:
            customer = self.store.get_customer(customer_id)

        # Build reply prompt
        conversation_summary = conv.get_summary()
        reply_prompt = build_reply_prompt(
            classification, message, conversation_summary,
            merchant, category, trigger, customer
        )

        # Build context block
        context_block = self._build_context_block(category, merchant, trigger, customer)
        full_prompt = f"{context_block}\n\n{reply_prompt}"

        # Call LLM
        try:
            result = self.llm.complete_json(full_prompt, MASTER_SYSTEM_PROMPT)
        except Exception as e:
            logger.error(f"LLM reply failed for conv {conversation_id}: {e}")
            return {
                "action": "send",
                "body": "Noted — let me check and get back to you shortly.",
                "cta": "none",
                "rationale": "LLM error fallback — acknowledged and promised follow-up",
            }

        if not result:
            return {
                "action": "send",
                "body": "Got it, let me look into this for you.",
                "cta": "none",
                "rationale": "Empty LLM result fallback",
            }

        action = result.get("action", "send")

        # Handle different actions
        if action == "end":
            conv.status = "ended"
            self.store.close_conversation(conversation_id)
            return {
                "action": "end",
                "rationale": result.get("rationale", "Conversation ended naturally"),
            }

        if action == "wait":
            conv.status = "waiting"
            return {
                "action": "wait",
                "wait_seconds": result.get("wait_seconds", 1800),
                "rationale": result.get("rationale", "Merchant needs time"),
            }

        # action == "send"
        body = result.get("body", "")
        if not body:
            return {
                "action": "send",
                "body": "Understood. Let me work on this and follow up shortly.",
                "cta": "none",
                "rationale": "Empty body fallback",
            }

        # Anti-repetition check
        if conv.has_sent_message(body):
            # Re-prompt with anti-repetition constraint
            body = body + " (Let me know your thoughts.)"

        # Post-validate
        send_as = "merchant_on_behalf" if customer_id else "neon_bot"
        validated = self._post_validate(
            {"body": body, "cta": result.get("cta", "open_ended")},
            category, merchant, send_as
        )

        conv.add_turn("bot", validated["body"])
        conv.record_sent_message(validated["body"])

        return {
            "action": "send",
            "body": validated["body"],
            "cta": validated.get("cta", "open_ended"),
            "rationale": result.get("rationale", "Composed reply"),
        }

    def _build_composition_prompt(self, category: dict, merchant: dict,
                                   trigger: dict, customer: Optional[dict],
                                   kind: str) -> str:
        """Build the full user prompt for message composition."""
        context_block = self._build_context_block(category, merchant, trigger, customer)
        trigger_instruction = build_trigger_instruction(
            kind, trigger, merchant, category, customer
        )

        return f"""{context_block}

=== COMPOSITION INSTRUCTIONS ===
{trigger_instruction}

Compose the message now. Return ONLY the JSON object."""

    def _build_context_block(self, category: dict, merchant: dict,
                              trigger: dict, customer: Optional[dict]) -> str:
        """Build the context block section of the prompt."""
        parts = [
            "=== CATEGORY CONTEXT ===",
            format_category_context(category),
            "",
            "=== MERCHANT CONTEXT ===",
            format_merchant_context(merchant),
            "",
            "=== TRIGGER CONTEXT ===",
            format_trigger_context(trigger),
        ]

        if customer:
            parts.extend([
                "",
                "=== CUSTOMER CONTEXT ===",
                format_customer_context(customer),
            ])

        return "\n".join(parts)

    def _post_validate(self, result: dict, category: dict, merchant: dict,
                        send_as: str) -> dict:
        """Post-LLM validation: check taboos, URLs, etc."""
        body = result.get("body", "")
        voice = category.get("voice", {})
        taboos = voice.get("vocab_taboo", [])

        # Check for taboo words
        body_lower = body.lower()
        for taboo in taboos:
            taboo_lower = taboo.lower().split("(")[0].strip()  # Remove annotations
            if taboo_lower in body_lower:
                logger.warning(f"Taboo word found: '{taboo_lower}' — removing")
                body = body.replace(taboo_lower, "")
                body = body.replace(taboo_lower.capitalize(), "")

        # Check for URLs (penalty: -3 per URL)
        import re
        url_pattern = r'https?://\S+'
        if re.search(url_pattern, body):
            logger.warning("URL found in body — removing")
            body = re.sub(url_pattern, '', body).strip()

        # Ensure send_as is correct
        result["body"] = body.strip()
        result["send_as"] = send_as

        return result
