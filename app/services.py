from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Receipt, ReceiptItem


async def save_receipt(db: AsyncSession, phone_number: str, parsed: dict, media_url: str | None) -> Receipt:
    purchased_at = None
    if parsed.get("purchased_at"):
        try:
            purchased_at = datetime.fromisoformat(parsed["purchased_at"])
        except ValueError:
            pass

    receipt = Receipt(
        phone_number=phone_number,
        store_name=parsed.get("store_name"),
        total=parsed.get("total"),
        purchased_at=purchased_at,
        raw_media_url=media_url,
    )
    db.add(receipt)
    await db.flush()

    for item_data in parsed.get("items", []):
        item = ReceiptItem(
            receipt_id=receipt.id,
            name=item_data.get("name", "Unknown"),
            quantity=item_data.get("quantity"),
            unit_price=item_data.get("unit_price"),
            total_price=item_data.get("total_price"),
        )
        db.add(item)

    item_count = len(parsed.get("items", []))
    await db.commit()
    await db.refresh(receipt)
    receipt.item_count = item_count
    return receipt


async def get_spending_summary(db: AsyncSession, phone_number: str) -> str:
    result = await db.execute(
        select(func.count(Receipt.id), func.sum(Receipt.total))
        .where(Receipt.phone_number == phone_number)
    )
    count, total = result.one()
    if not count:
        return "No receipts recorded yet."

    receipts = await db.execute(
        select(Receipt).where(Receipt.phone_number == phone_number).order_by(Receipt.created_at.desc()).limit(5)
    )
    recent = receipts.scalars().all()
    lines = [f"Total receipts: {count}, Total spent: ${total or 0:.2f}\n\nRecent purchases:"]
    for r in recent:
        store = r.store_name or "Unknown store"
        amount = f"${r.total:.2f}" if r.total else "unknown amount"
        date = r.purchased_at.strftime("%Y-%m-%d") if r.purchased_at else r.created_at.strftime("%Y-%m-%d")
        lines.append(f"- {date}: {store} — {amount}")
    return "\n".join(lines)


async def build_history_context(db: AsyncSession, phone_number: str) -> str:
    receipts = await db.execute(
        select(Receipt).where(Receipt.phone_number == phone_number).order_by(Receipt.created_at.desc()).limit(20)
    )
    rows = receipts.scalars().all()
    if not rows:
        return "No purchase history."
    parts = []
    for r in rows:
        store = r.store_name or "Unknown store"
        date = r.purchased_at.strftime("%Y-%m-%d") if r.purchased_at else r.created_at.strftime("%Y-%m-%d")
        parts.append(f"{date} at {store}: ${r.total or 0:.2f}")
    return "\n".join(parts)
