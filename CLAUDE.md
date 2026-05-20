# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WhatsApp-based grocery receipt tracker. Users send receipt photos via WhatsApp; Claude Haiku parses them and stores structured data in SQLite. Users can also ask natural-language questions about their spending history.

## Commands

### Local development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in env vars
cp .env.example .env

# Run the server (hot reload)
uvicorn app.main:app --reload

# Run with Docker
docker compose up --build

# Run tests (must use Docker — Python 3.14 on the host lacks greenlet support)
make test
```

### Expose webhook locally (Twilio requires a public URL)

```bash
ngrok http 8000
# Set the resulting URL as your Twilio WhatsApp webhook: https://<ngrok-id>.ngrok.io/webhook
```

## Architecture

```
WhatsApp user
    │  (sends photo or text message)
    ▼
Twilio WhatsApp → POST /webhook (FastAPI)
    │
    ├── Image message → claude_parser.parse_receipt_from_url()
    │       Downloads media from Twilio (auth required), encodes as base64,
    │       sends to Claude Haiku with vision, returns structured JSON
    │       → services.save_receipt() → SQLite (receipts + receipt_items tables)
    │
    ├── "summary" / "history" → services.get_spending_summary()
    │
    └── Any other text → claude_parser.answer_query()
            Builds context from last 20 receipts, asks Claude Haiku
    │
    └── whatsapp.send_message() → reply back to user via Twilio
```

### Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, `/webhook` endpoint, `/health` check |
| `app/claude_parser.py` | Claude Haiku calls — receipt image parsing and Q&A |
| `app/services.py` | DB read/write logic (save receipt, build summaries) |
| `app/models.py` | SQLAlchemy ORM models: `Receipt`, `ReceiptItem` |
| `app/database.py` | Async SQLite engine, `get_db` dependency, `init_db` |
| `app/whatsapp.py` | Twilio client wrapper for sending replies |
| `app/config.py` | Pydantic settings loaded from `.env` |

### Data model

- `Receipt` — one row per uploaded receipt (store, total, date, phone number)
- `ReceiptItem` — line items belonging to a receipt (name, qty, unit price, total)

## Environment variables

All required. See `.env.example`:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (used to fetch media) |
| `TWILIO_WHATSAPP_NUMBER` | Sender number in `whatsapp:+1...` format |

## Twilio webhook setup

1. In the Twilio Console, go to Messaging → Senders → WhatsApp Senders (or Sandbox).
2. Set the webhook URL to `https://<your-domain>/webhook` (POST).
3. Twilio sends `From`, `Body`, `NumMedia`, `MediaUrl0`, `MediaContentType0` as form fields.

## SQLite persistence

The database file lives at `data/grocery.db` (created on startup). In Docker it is mounted as a named volume (`grocery_data`) so data survives container restarts.
