from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Receipt, ReceiptItem
from app.claude_parser import normalize_item_names


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

    items_data = parsed.get("items", [])
    raw_names = [i.get("name", "Unknown") for i in items_data]
    normalized = await normalize_item_names(raw_names)

    for item_data in items_data:
        raw_name = item_data.get("name", "Unknown")
        item = ReceiptItem(
            receipt_id=receipt.id,
            name=raw_name,
            normalized_name=normalized.get(raw_name),
            quantity=item_data.get("quantity"),
            unit_price=item_data.get("unit_price"),
            total_price=item_data.get("total_price"),
        )
        db.add(item)

    item_count = len(items_data)
    await db.commit()
    await db.refresh(receipt)
    receipt.item_count = item_count
    return receipt


async def get_spending_summary(db: AsyncSession, phone_number: str) -> str:
    receipt_ids = await db.execute(
        select(Receipt.id).where(Receipt.phone_number == phone_number)
    )
    ids = [r[0] for r in receipt_ids.all()]
    if not ids:
        return "No receipts recorded yet."

    result = await db.execute(
        select(ReceiptItem.name, func.count(ReceiptItem.id).label("times"))
        .where(ReceiptItem.receipt_id.in_(ids))
        .group_by(func.lower(ReceiptItem.name))
        .order_by(func.count(ReceiptItem.id).desc())
        .limit(15)
    )
    rows = result.all()

    lines = [f"Your most bought items ({len(ids)} receipt{'s' if len(ids) != 1 else ''} tracked):\n"]
    for name, times in rows:
        lines.append(f"- {name} x{times}")
    return "\n".join(lines)


async def get_frequent_items(db: AsyncSession, phone_number: str, limit: int = 20) -> list[str]:
    receipt_ids = await db.execute(
        select(Receipt.id).where(Receipt.phone_number == phone_number)
    )
    ids = [r[0] for r in receipt_ids.all()]
    if not ids:
        return []

    result = await db.execute(
        select(ReceiptItem.normalized_name, ReceiptItem.name)
        .where(ReceiptItem.receipt_id.in_(ids))
        .group_by(func.lower(func.coalesce(ReceiptItem.normalized_name, ReceiptItem.name)))
        .order_by(func.count(ReceiptItem.id).desc())
        .limit(limit)
    )
    return [normalized or raw for normalized, raw in result.all()]


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
