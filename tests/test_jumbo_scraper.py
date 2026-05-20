import pytest
from unittest.mock import AsyncMock, patch, MagicMock

PRODUCT_HTML = """
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product","name":"Jumbo Scharreleieren M/L 6 Stuks",
"sku":"602648DS","offers":{"@type":"AggregateOffer","lowPrice":2.59,"priceCurrency":"EUR"},
"category":"Zuivel, boter en eieren","url":"https://www.jumbo.com/producten/jumbo-scharreleieren-ml-6-stuks-602648DS"}
</script>
"""

SEARCH_HTML = """
<a href="/producten/jumbo-scharreleieren-ml-6-stuks-602648DS">Eieren</a>
<a href="/producten/jumbo-scharreleieren-ml-12-stuks-602645DS">Eieren 12</a>
"""


def _mock_response(text: str, status: int = 200):
    r = MagicMock()
    r.text = text
    r.status_code = status
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_search_products_returns_parsed_results():
    search_resp = _mock_response(SEARCH_HTML)
    product_resp = _mock_response(PRODUCT_HTML)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [search_resp, product_resp, product_resp]

    with patch("mcp.jumbo_scraper.httpx.AsyncClient", return_value=mock_client):
        from mcp.jumbo_scraper import search_products
        results = await search_products("eieren", limit=2)

    assert len(results) >= 1
    assert results[0]["name"] == "Jumbo Scharreleieren M/L 6 Stuks"
    assert results[0]["price"] == 2.59
    assert results[0]["sku"] == "602648DS"


@pytest.mark.asyncio
async def test_match_deals_finds_matching_item():
    deals_resp = _mock_response(SEARCH_HTML)
    product_resp = _mock_response(PRODUCT_HTML)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [deals_resp, product_resp, product_resp]

    with patch("mcp.jumbo_scraper.httpx.AsyncClient", return_value=mock_client):
        from mcp.jumbo_scraper import match_deals_to_items
        matches = await match_deals_to_items(["scharreleieren", "pasta"])

    assert len(matches) == 1
    assert matches[0]["searched_for"] == "scharreleieren"
    assert matches[0]["price"] == 2.59


@pytest.mark.asyncio
async def test_match_deals_no_match():
    deals_resp = _mock_response(SEARCH_HTML)
    product_resp = _mock_response(PRODUCT_HTML)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [deals_resp, product_resp, product_resp]

    with patch("mcp.jumbo_scraper.httpx.AsyncClient", return_value=mock_client):
        from mcp.jumbo_scraper import match_deals_to_items
        matches = await match_deals_to_items(["pizza", "cola"])

    assert matches == []
