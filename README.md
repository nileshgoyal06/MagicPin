# Neon Bot — magicpin AI Challenge (NightOwlCoders)

## Approach

**Trigger-Kind Dispatch + Gemini LLM Composition + Rule-Based Reply Classification**

### Architecture

```
Evaluation Harness  ─── HTTP/JSON ───►  FastAPI Server (server.py)
                                            │
                       ┌────────────────────┼──────────────────────┐
                       │                    │                      │
                Context Repository     Dialogue Manager      Message Composer
               (version-tracked)    (reply classifier)     (LLM + templates)
                       │                    │                      │
                       └────────────────────┼──────────────────────┘
                                            │
                                       Gemini 2.5 Flash
```

### Key Design Decisions

1. **Trigger-kind dispatch**: Each trigger type (research digest, recall reminder, IPL match, etc.) gets a tailored template with specific composition guidance. This ensures the bot picks the right compulsion levers and voice for each context.

2. **Rule-based reply classification**: Auto-reply detection, hostile handling, and intent transitions are pattern-matched with regex — no LLM call needed. This saves latency (critical for the 30s budget) while handling the most common failure modes.

3. **Post-LLM validation**: Every composed message is checked for taboo words, URLs, and repetition before being sent. This catches the most common penalties.

4. **Deterministic output**: `temperature=0` on all LLM calls ensures the same input always produces the same output.

### Model Choice

- **Gemini 2.5 Flash** — chosen for fast inference (critical for 30s timeout budget), strong instruction following, and cost efficiency for the volume of calls during a 60-minute test window.

### Tradeoffs

- **In-memory storage**: Context is stored in Python dicts. This is simple and fast but doesn't survive restarts. Acceptable since the challenge spec says no restarts during test.
- **Single-file templates**: All prompt templates are in one file for easy iteration. In production, these would be versioned and A/B tested.
- **No RAG/retrieval**: Digest items are passed directly in the prompt context. For a larger digest library, embedding-based retrieval would be better.

### What Additional Context Would Help

1. **Real-time slot availability** — currently using slots from trigger payload; real scheduling would improve specificity
2. **Richer customer visit history** — more granular service records would enable better personalization
3. **Merchant response patterns** — knowing which message styles this specific merchant responds to would improve engagement
4. **Local event calendars** — festival/event triggers with city-specific timing would improve timeliness

## How to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export LLM_API_KEY="your-gemini-api-key"

# Start the bot
python server.py
# or: uvicorn server:app --host 0.0.0.0 --port 8080

# Run the evaluation harness (set LLM_API_KEY in evaluator.py first)
python evaluator.py
```

## File Structure

```
├── server.py               # FastAPI server (5 endpoints)
├── settings.py             # Central configuration
├── store.py                # In-memory context repository with versioning
├── dialogue.py             # Multi-turn conversation state
├── engine.py               # LLM-powered message composer
├── templates.py            # Prompt templates (master + per-trigger-kind)
├── model_client.py         # Multi-provider LLM client
├── requirements.txt        # Python dependencies
├── evaluator.py            # Local test harness with LLM-based scoring
└── README.md               # This file
```

## Team

**NightOwlCoders**
- Niles Sharma

Contact: niles@example.com
