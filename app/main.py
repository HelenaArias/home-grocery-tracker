import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, Depends, BackgroundTasks
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, init_db, SessionLocal
from app.services import save_receipt, get_spending_summary, build_history_context, get_frequent_items
from app.claude_parser import parse_receipt_from_url, answer_query
from app import whatsapp
from mcp.multi_store import match_deals_across_stores, format_deals_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="Grocery Receipt Tracker", lifespan=lifespan)


async def _check_deals_and_reply(phone_number: str):
    async with SessionLocal() as db:
        items = await get_frequent_items(db, phone_number)
    if not items:
        whatsapp.send_message(to=phone_number, body="No purchase history yet — send me a receipt first and I'll check deals for your usual items.")
        return
    try:
        whatsapp.send_message(to=phone_number, body="Checking deals at Jumbo, AH and Dirk... one moment!")
        matches = await match_deals_across_stores(items)
        reply = format_deals_message(matches)
    except Exception as e:
        reply = f"Couldn't check deals right now. Try again later. ({e})"
    whatsapp.send_message(to=phone_number, body=reply)


@app.post("/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    phone_number = From
    reply = ""

    if NumMedia > 0 and MediaUrl0:
        try:
            parsed = await parse_receipt_from_url(MediaUrl0, MediaContentType0 or "image/jpeg")
            receipt = await save_receipt(db, phone_number, parsed, MediaUrl0)
            store = receipt.store_name or "the store"
            total = f"${receipt.total:.2f}" if receipt.total else "unknown total"
            item_count = receipt.item_count
            reply = (
                f"Got it! Saved your receipt from {store} — {total} "
                f"({item_count} item{'s' if item_count != 1 else ''}). "
                f"Reply 'summary' for your spending overview."
            )
        except Exception as e:
            reply = f"Sorry, I couldn't parse that receipt. Please send a clear photo of a grocery receipt. ({e})"

    elif Body.strip().lower() in ("summary", "spending", "history"):
        reply = await get_spending_summary(db, phone_number)

    elif Body.strip().lower() in ("deals", "aanbiedingen", "sales", "on sale"):
        background_tasks.add_task(_check_deals_and_reply, phone_number)
        return ""

    elif Body.strip():
        context = await build_history_context(db, phone_number)
        reply = await answer_query(phone_number, Body.strip(), context)

    else:
        reply = (
            "Hi! Send me a photo of a grocery receipt and I'll track it for you. "
            "You can also ask questions like 'How much did I spend this month?'"
        )

    whatsapp.send_message(to=phone_number, body=reply)
    return ""


@app.get("/health")
async def health():
    return {"status": "ok"}
