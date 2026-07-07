# Neon Bot - Merchant AI Assistant

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> An intelligent WhatsApp chatbot for merchant engagement built for the magicpin AI Challenge by Team **NightOwlCoders**

## 🎯 Overview

Neon Bot is an AI-powered conversational assistant designed to engage merchants over WhatsApp, helping them improve their Google Business Profile, run marketing campaigns, and manage customer relationships. The bot uses LLM-powered composition with trigger-based dispatch to deliver personalized, contextual messages.

## ✨ Key Features

- **🎨 Trigger-Kind Dispatch**: Each trigger type (digest, recall, performance spike) gets tailored template composition
- **🤖 Rule-Based Classification**: Fast auto-reply detection and hostile handling without LLM overhead
- **✅ Post-LLM Validation**: Automatic checking for taboo words, URLs, and message repetition
- **🔄 Multi-Turn Conversations**: State management for natural conversation flow
- **🌐 Multi-Language Support**: Hindi-English code-mix for Indian merchant audiences
- **📊 Context-Aware**: Leverages category, merchant, trigger, and customer contexts for personalization

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│           FastAPI Server (server.py)                │
│  /healthz  /metadata  /context  /tick  /reply      │
└────────────┬────────────┬────────────┬──────────────┘
             │            │            │
    ┌────────▼─────┐  ┌──▼──────┐  ┌──▼──────────────┐
    │   Context    │  │Dialogue │  │    Message      │
    │  Repository  │  │ Manager │  │   Composer      │
    │  (store.py)  │  │(dialogue│  │  (engine.py)    │
    │              │  │  .py)   │  │                 │
    └──────────────┘  └─────────┘  └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  LLM Client     │
                                    │(model_client.py)│
                                    │ Gemini 2.5 Flash│
                                    └─────────────────┘
```

## 📁 Project Structure

```
magicpin/
├── server.py                    # FastAPI server with 5 endpoints
├── engine.py                    # Core message composition logic
├── dialogue.py                  # Multi-turn conversation state manager
├── store.py                     # In-memory context repository
├── templates.py                 # LLM prompt templates
├── model_client.py              # Multi-provider LLM client wrapper
├── settings.py                  # Configuration management
├── evaluator.py                 # Local testing harness
├── requirements.txt             # Python dependencies
├── dataset/                     # Base dataset for challenge
│   ├── categories/              # Category contexts (dentists, salons, etc.)
│   ├── customers_seed.json      # Customer profiles
│   ├── merchants_seed.json      # Merchant profiles
│   └── triggers_seed.json       # Trigger events
├── examples/                    # Documentation and examples
│   ├── api-call-examples.md     # API usage examples
│   └── case-studies.md          # Real conversation patterns
├── challenge-brief.md           # Full challenge specification
└── README.md                    # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/nileshgoyal06/MagicPin.git
   cd MagicPin
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   # Windows Command Prompt
   set LLM_API_KEY=your-gemini-api-key-here
   
   # Windows PowerShell
   $env:LLM_API_KEY="your-gemini-api-key-here"
   
   # Linux/Mac
   export LLM_API_KEY="your-gemini-api-key-here"
   ```

### Running the Bot

**Start the server:**
```bash
python server.py
```

Or using uvicorn directly:
```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

The server will start at `http://localhost:8080`

**Run the evaluation harness:**
```bash
python evaluator.py
```

## 📡 API Endpoints

### `GET /v1/healthz`
Health check endpoint that returns server status and context counts.

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 1234,
  "contexts_loaded": {
    "categories": 5,
    "merchants": 50,
    "customers": 200,
    "triggers": 100
  }
}
```

### `GET /v1/metadata`
Returns bot identity and team information.

**Response:**
```json
{
  "team_name": "NightOwlCoders",
  "team_members": ["Niles Sharma"],
  "model": "gemini-2.5-flash",
  "approach": "Trigger-Kind Dispatch + LLM Composition + Rule-Based Classification",
  "contact_email": "niles@example.com",
  "version": "1.0.0"
}
```

### `POST /v1/context`
Receive context updates (categories, merchants, customers, triggers).

**Request:**
```json
{
  "scope": "merchant",
  "context_id": "m_001",
  "version": 1,
  "payload": { /* merchant data */ },
  "delivered_at": "2026-07-06T12:00:00Z"
}
```

### `POST /v1/tick`
Periodic wake-up call to evaluate triggers and compose messages.

**Request:**
```json
{
  "now": "2026-07-06T12:00:00Z",
  "available_triggers": ["trg_001", "trg_002"]
}
```

**Response:**
```json
{
  "actions": [
    {
      "conversation_id": "session_m001_trg001",
      "merchant_id": "m_001",
      "send_as": "neon_bot",
      "body": "Hi Dr. Meera...",
      "cta": "open_ended",
      "rationale": "Research digest engagement"
    }
  ]
}
```

### `POST /v1/reply`
Handle merchant/customer replies in ongoing conversations.

**Request:**
```json
{
  "conversation_id": "session_m001_trg001",
  "merchant_id": "m_001",
  "from_role": "merchant",
  "message": "Yes, interested",
  "received_at": "2026-07-06T12:05:00Z",
  "turn_number": 2
}
```

## 🧠 Core Design Decisions

### 1. **Trigger-Kind Dispatch**
Each trigger type receives a specialized composition template:
- `research_digest` → Curiosity-driven, source-cited
- `recall_reminder` → Service-specific, low-friction
- `perf_spike` → Social proof, loss aversion
- `festival_upcoming` → Timely, offer-centric

### 2. **Rule-Based Reply Classification**
Fast pattern matching for common scenarios:
- Auto-reply detection (regex patterns)
- Hostile/abusive language handling
- Intent commitment recognition ("yes", "let's do it")

### 3. **Deterministic Output**
- `temperature=0` on all LLM calls
- Same input → same output (reproducible results)
- Critical for A/B testing and debugging

### 4. **Post-LLM Validation**
Every composed message is validated for:
- ❌ Taboo words (category-specific)
- ❌ URLs (penalty avoidance)
- ❌ Repetition (conversation history check)
- ✅ Language preference matching

## 🎨 Message Composition Strategy

### Compulsion Levers
The bot uses proven engagement techniques:

1. **Specificity** - Concrete numbers, dates, sources
   - ✅ "6,777 missed searches in Sector 14"
   - ❌ "Many people searching for you"

2. **Loss Aversion** - Highlight missed opportunities
   - ✅ "Before this window closes..."
   - ✅ "You're missing 38% potential patients"

3. **Social Proof** - Peer comparison
   - ✅ "3 dentists in your area did this"
   - ✅ "Above peer median CTR"

4. **Effort Externalization** - Do work for them
   - ✅ "I've drafted this for you - just say go"
   - ✅ "5-min setup, I'll handle it"

5. **Curiosity** - Open loops
   - ✅ "Want to see who?"
   - ✅ "Want the full list?"

## 🔧 Configuration

Edit `settings.py` to customize:

```python
# Team Info
TEAM_NAME = "NightOwlCoders"
TEAM_MEMBERS = ["Niles Sharma"]
CONTACT_EMAIL = "niles@example.com"

# LLM Configuration
LLM_PROVIDER = "gemini"  # or "openai", "anthropic"
LLM_MODEL = "gemini-2.5-flash"
LLM_TEMPERATURE = 0

# Server Configuration
BOT_HOST = "0.0.0.0"
BOT_PORT = 8080
```

## 📊 Model Choice

**Gemini 2.5 Flash** was selected for:
- ⚡ Fast inference (critical for 30s timeout budget)
- 🎯 Strong instruction following
- 💰 Cost efficiency for high-volume testing
- 🌐 Multi-language support (Hindi-English mix)

## 🧪 Testing

The project includes a comprehensive evaluation harness:

```bash
python evaluator.py
```

Evaluation dimensions (0-10 each):
1. **Specificity** - Concrete, verifiable facts
2. **Category Fit** - Voice, vocabulary, offer format
3. **Merchant Fit** - Personalization to specific merchant
4. **Trigger Relevance** - Clear "why now" communication
5. **Engagement Compulsion** - Would merchant reply?

## 🚧 Known Limitations & Tradeoffs

### Accepted Tradeoffs

1. **In-Memory Storage**
   - ✅ Simple and fast
   - ❌ Doesn't survive restarts
   - ✔️ Acceptable per challenge spec (no restarts during test)

2. **Single-File Templates**
   - ✅ Easy iteration during development
   - ❌ Not production-ready for A/B testing
   - ✔️ Would version externally in production

3. **No RAG/Retrieval**
   - ✅ Direct context passing is simpler
   - ❌ Won't scale to large digest libraries
   - ✔️ Embedding-based retrieval needed for production scale

### Opportunities for Improvement

Given more context, the bot could improve with:
- 📅 Real-time slot availability APIs
- 📊 Richer customer visit history
- 🎯 Merchant-specific response patterns
- 📍 Local event calendars and festival triggers

## 🤝 Contributing

This project was built for the magicpin AI Challenge. For questions or collaboration:

**Team NightOwlCoders**
- Niles Sharma - [Contact](mailto:niles@example.com)

## 📄 License

MIT License - feel free to use this code for learning and development.

## 🙏 Acknowledgments

- magicpin team for organizing the AI Challenge
- Google Gemini for the LLM API
- FastAPI community for the excellent framework

## 📚 Additional Resources

- [Challenge Brief](challenge-brief.md) - Full challenge specification
- [Challenge Testing Brief](challenge-testing-brief.md) - Testing guidelines
- [API Call Examples](examples/api-call-examples.md) - Sample requests/responses
- [Case Studies](examples/case-studies.md) - Real conversation patterns
- [Engagement Research](engagement-research.md) - Behavioral insights

---

**Built with ❤️ by Team NightOwlCoders for the magicpin AI Challenge**
