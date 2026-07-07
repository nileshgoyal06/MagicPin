"""
Language model client abstraction for Neon bot.
Supports Gemini (primary), with fallback architecture for additional providers.
"""
import json
import re
import time
import logging
from typing import Optional
from urllib import request as urlrequest, error as urlerror

from settings import (
    LLM_PROVIDER, LLM_API_KEY, LLM_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT
)

logger = logging.getLogger(__name__)


class LanguageModelClient:
    """Unified language model client with JSON parsing capabilities."""

    def __init__(self):
        self.provider    = LLM_PROVIDER
        self.api_key     = LLM_API_KEY
        self.model       = LLM_MODEL or self._get_default_model()
        self.temperature = LLM_TEMPERATURE
        self.max_tokens  = LLM_MAX_TOKENS
        self.timeout     = LLM_TIMEOUT

    def _get_default_model(self) -> str:
        """Returns default model per provider."""
        model_defaults = {
            "gemini": "gemini-2.5-flash",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
            "deepseek": "deepseek-chat",
            "groq": "llama-3.1-70b-versatile",
        }
        return model_defaults.get(self.provider, "gemini-2.5-flash")

    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Send a prompt to the language model and receive raw text response."""
        handler_mapping = {
            "gemini": self._call_gemini,
            "openai": self._call_openai,
            "anthropic": self._call_anthropic,
            "deepseek": self._call_deepseek,
            "groq": self._call_groq,
        }
        handler = handler_mapping.get(self.provider)
        if not handler:
            raise ValueError(f"Unsupported language model provider: {self.provider}")

        # Single retry with exponential backoff
        for attempt_num in range(2):
            try:
                return handler(prompt, system_prompt)
            except Exception as err:
                if attempt_num == 0:
                    logger.warning(f"Language model call failed (attempt 1), retrying: {err}")
                    time.sleep(1)
                else:
                    raise

    def complete_json(self, prompt: str, system_prompt: str = "") -> dict:
        """Send a prompt and parse the response into JSON."""
        raw_text = self.complete(prompt, system_prompt)
        return self._extract_json(raw_text)

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from language model response, handling truncation and code blocks."""
        text = text.strip()

        # Strategy 1: Direct parse
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Strategy 2: Extract from markdown code block
        code_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if code_match:
            try:
                return json.loads(code_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find first { ... } block
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Strategy 4: Attempt to repair truncated JSON
        partial_match = re.search(r'\{[\s\S]*', text)
        if partial_match:
            repaired = self._attempt_json_repair(partial_match.group())
            if repaired:
                return repaired

        logger.error(f"Failed to parse JSON from language model response: {text[:300]}")
        return {}

    def _attempt_json_repair(self, text: str) -> Optional[dict]:
        """Attempt to repair truncated JSON by closing open structures."""
        # Progressive repair attempts
        repair_strategies = [
            text + '"}',           # close string + object
            text + '"}]}',         # close string + array + object
            text + '"}\n}',        # close string + nested object
            text + '" }',          # close string + object with space
            text + '}',            # just close object
        ]

        # Also try truncating to last complete key-value pair
        last_comma_idx = text.rfind('",')
        if last_comma_idx > 0:
            truncated_text = text[:last_comma_idx + 1]  # up to and including the quote
            repair_strategies.extend([
                truncated_text + '}',
                truncated_text + '\n}',
            ])

        # Try truncating to last complete value
        last_quote_idx = text.rfind('"')
        if last_quote_idx > 0:
            # Check if this is the end of a value (not a key)
            remaining = text[last_quote_idx + 1:].strip()
            if not remaining or remaining.startswith(',') or remaining.startswith('}'):
                repair_strategies.append(text[:last_quote_idx + 1] + '}')

        for candidate in repair_strategies:
            try:
                result = json.loads(candidate)
                if isinstance(result, dict) and result.get("body"):
                    logger.info("Successfully repaired truncated JSON")
                    return result
            except json.JSONDecodeError:
                continue

        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Provider implementations
    # ──────────────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, system_prompt: str = "") -> str:
        combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        request_body = json.dumps({
            "contents": [{"parts": [{"text": combined_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            }
        }).encode("utf-8")

        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )
        req = urlrequest.Request(api_url, data=request_body, headers={"Content-Type": "application/json"})
        resp = urlrequest.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_body = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")

        req = urlrequest.Request(
            "https://api.openai.com/v1/chat/completions",
            data=request_body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        resp = urlrequest.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _call_anthropic(self, prompt: str, system_prompt: str = "") -> str:
        request_dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            request_dict["system"] = system_prompt

        req = urlrequest.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(request_dict).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
        )
        resp = urlrequest.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["content"][0]["text"]

    def _call_deepseek(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        req = urlrequest.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        resp = urlrequest.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def _call_groq(self, prompt: str, system_prompt: str = "") -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        req = urlrequest.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps({
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )
        resp = urlrequest.urlopen(req, timeout=self.timeout)
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


# Singleton instance
_client_instance: Optional[LanguageModelClient] = None


def get_model_client() -> LanguageModelClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = LanguageModelClient()
    return _client_instance
