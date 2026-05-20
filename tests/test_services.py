import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base
from app.services import save_receipt, get_spending_summary, build_history_context

PARSED_RECEIPT = {
    "store_name": "Trader Joe's",
    "purchased_at": "2026-05-20",
    "total": 35.80,
    "items": [
        {"name": "Eggs", "quantity": 1, "unit_price": 3.99, "total_price": 3.99},
        {"name": "Pasta", "quantity": 2, "unit_price": 1.49, "total_price": 2.98},
    ],
}

PHONE = "whatsapp:+1234567890"


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_save_receipt_stores_data(db):
    receipt = await save_receipt(db, PHONE, PARSED_RECEIPT, None)

    assert receipt.store_name == "Trader Joe's"
    assert receipt.total == 35.80
    assert receipt.phone_number == PHONE
    assert receipt.item_count == 2


@pytest.mark.asyncio
async def test_save_receipt_handles_missing_fields(db):
    receipt = await save_receipt(db, PHONE, {"items": []}, None)

    assert receipt.store_name is None
    assert receipt.total is None
    assert receipt.item_count == 0


@pytest.mark.asyncio
async def test_get_spending_summary_no_receipts(db):
    result = await get_spending_summary(db, "whatsapp:+0000000000")
    assert result == "No receipts recorded yet."


@pytest.mark.asyncio
async def test_get_spending_summary_with_receipts(db):
    await save_receipt(db, PHONE, PARSED_RECEIPT, None)
    await save_receipt(db, PHONE, {**PARSED_RECEIPT, "total": 20.00}, None)

    result = await get_spending_summary(db, PHONE)

    assert "2 receipts" in result
    assert "Eggs" in result
    assert "Pasta" in result
    assert "x2" in result


@pytest.mark.asyncio
async def test_build_history_context_no_receipts(db):
    result = await build_history_context(db, "whatsapp:+0000000000")
    assert result == "No purchase history."


@pytest.mark.asyncio
async def test_build_history_context_with_receipts(db):
    await save_receipt(db, PHONE, PARSED_RECEIPT, None)

    result = await build_history_context(db, PHONE)

    assert "Trader Joe's" in result
    assert "35.80" in result
