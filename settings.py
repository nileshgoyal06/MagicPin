"""
Central settings for the Neon bot.
Modify these values or override via environment variables.
"""
import os

# ── LLM Settings ──────────────────────────────────────────────────────────────
LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "gemini")
LLM_API_KEY    = os.getenv("LLM_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gemini-2.5-flash")
LLM_TEMPERATURE = 0.0          # deterministic output required by challenge
LLM_MAX_TOKENS  = 2048
LLM_TIMEOUT     = 25           # seconds — leaves 5 s buffer inside 30 s budget

# ── Server Settings ───────────────────────────────────────────────────────────
BOT_PORT = int(os.getenv("PORT", "8080"))
BOT_HOST = "0.0.0.0"

# ── Team Metadata ─────────────────────────────────────────────────────────────
TEAM_NAME      = "NightOwlCoders"
TEAM_MEMBERS   = ["Niles Sharma"]
CONTACT_EMAIL  = "niles@example.com"
BOT_VERSION    = "1.0.0"
APPROACH       = (
    "Trigger-kind dispatch engine with Gemini LLM, "
    "regex-based reply classification, and context-grounded prompting"
)
