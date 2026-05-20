import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


SAMPLE_PARSED = {
    "store_name": "Whole Foods",
    "purchased_at": "2026-05-20",
    "total": 42.57,
    "items": [
        {"name": "Organic Milk", "quantity": 1, "unit_price": 4.99, "total_price": 4.99},
        {"name": "Sourdough Bread", "quantity": 1, "unit_price": 6.49, "total_price": 6.49},
    ],
}


def _make_claude_response(text: str):
    content = MagicMock()
    content.text = text
    response = MagicMock()
    response.content = [content]
    return response


@pytest.mark.asyncio
@patch("app.claude_parser.client")
@patch("httpx.AsyncClient")
async def test_parse_plain_json(mock_http_cls, mock_client):
    mock_http = AsyncMock()
    mock_http_cls.return_value.__aenter__.return_value = mock_http
    mock_http.get.return_value = MagicMock(content=b"fake-image", raise_for_status=MagicMock())

    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response(json.dumps(SAMPLE_PARSED))
    )

    from app.claude_parser import parse_receipt_from_url
    result = await parse_receipt_from_url("https://fake.url/media", "image/jpeg")

    assert result["store_name"] == "Whole Foods"
    assert result["total"] == 42.57
    assert len(result["items"]) == 2


@pytest.mark.asyncio
@patch("app.claude_parser.client")
@patch("httpx.AsyncClient")
async def test_parse_strips_markdown_code_block(mock_http_cls, mock_client):
    mock_http = AsyncMock()
    mock_http_cls.return_value.__aenter__.return_value = mock_http
    mock_http.get.return_value = MagicMock(content=b"fake-image", raise_for_status=MagicMock())

    wrapped = f"```json\n{json.dumps(SAMPLE_PARSED)}\n```"
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response(wrapped)
    )

    from app.claude_parser import parse_receipt_from_url
    result = await parse_receipt_from_url("https://fake.url/media", "image/jpeg")

    assert result["store_name"] == "Whole Foods"


@pytest.mark.asyncio
@patch("app.claude_parser.client")
async def test_answer_query_returns_string(mock_client):
    mock_client.messages.create = AsyncMock(
        return_value=_make_claude_response("You spent $42.57 last week.")
    )

    from app.claude_parser import answer_query
    result = await answer_query("whatsapp:+1234", "How much did I spend?", "context here")

    assert "42.57" in result
