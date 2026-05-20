import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.database import Base, get_db
from app.main import app

PHONE = "whatsapp:+1234567890"

PARSED_RECEIPT = {
    "store_name": "Costco",
    "purchased_at": "2026-05-20",
    "total": 98.45,
    "items": [
        {"name": "Chicken", "quantity": 1, "unit_price": 12.99, "total_price": 12.99},
    ],
}


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
@patch("app.main.parse_receipt_from_url", new_callable=AsyncMock)
async def test_webhook_image_message(mock_parse, mock_send, client):
    mock_parse.return_value = PARSED_RECEIPT

    response = await client.post("/webhook", data={
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://fake.twilio.com/media/123",
        "MediaContentType0": "image/jpeg",
    })

    assert response.status_code == 200
    mock_send.assert_called_once()
    reply = mock_send.call_args[1]["body"]
    assert "Costco" in reply
    assert "98.45" in reply
    assert "1 item" in reply


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
@patch("app.main.parse_receipt_from_url", new_callable=AsyncMock)
async def test_webhook_summary_command(mock_parse, mock_send, client):
    mock_parse.return_value = PARSED_RECEIPT
    await client.post("/webhook", data={
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://fake.twilio.com/media/123",
        "MediaContentType0": "image/jpeg",
    })
    mock_send.reset_mock()

    response = await client.post("/webhook", data={
        "From": PHONE,
        "Body": "summary",
        "NumMedia": "0",
    })

    assert response.status_code == 200
    reply = mock_send.call_args[1]["body"]
    assert "1 receipt" in reply
    assert "Chicken" in reply


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
async def test_webhook_empty_message_returns_help(mock_send, client):
    response = await client.post("/webhook", data={
        "From": PHONE,
        "Body": "",
        "NumMedia": "0",
    })

    assert response.status_code == 200
    reply = mock_send.call_args[1]["body"]
    assert "Send me a photo" in reply


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
@patch("app.main.parse_receipt_from_url", new_callable=AsyncMock)
@patch("app.main.match_deals_across_stores", new_callable=AsyncMock)
async def test_webhook_deals_with_matches(mock_deals, mock_parse, mock_send, client):
    mock_parse.return_value = PARSED_RECEIPT
    await client.post("/webhook", data={
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://fake.twilio.com/media/123",
        "MediaContentType0": "image/jpeg",
    })
    mock_send.reset_mock()
    mock_deals.return_value = [{"searched_for": "Chicken", "store": "Jumbo", "name": "Jumbo Kipfilet 500g", "price": 3.99}]

    response = await client.post("/webhook", data={
        "From": PHONE,
        "Body": "deals",
        "NumMedia": "0",
    })

    assert response.status_code == 200
    reply = mock_send.call_args[1]["body"]
    assert "Jumbo Kipfilet 500g" in reply
    assert "3.99" in reply


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
@patch("app.main.match_deals_across_stores", new_callable=AsyncMock)
async def test_webhook_deals_no_history(mock_deals, mock_send, client):
    response = await client.post("/webhook", data={
        "From": "whatsapp:+9999999999",
        "Body": "deals",
        "NumMedia": "0",
    })

    assert response.status_code == 200
    reply = mock_send.call_args[1]["body"]
    assert "send me a receipt" in reply.lower()
    mock_deals.assert_not_called()


@pytest.mark.asyncio
@patch("app.main.whatsapp.send_message")
@patch("app.main.answer_query", new_callable=AsyncMock)
async def test_webhook_natural_language_query(mock_answer, mock_send, client):
    mock_answer.return_value = "You spent $98.45 this week."

    response = await client.post("/webhook", data={
        "From": PHONE,
        "Body": "How much did I spend this week?",
        "NumMedia": "0",
    })

    assert response.status_code == 200
    reply = mock_send.call_args[1]["body"]
    assert "98.45" in reply
