import pytest
from unittest.mock import AsyncMock, patch, MagicMock

JUMBO_MATCH = [{"store": "Jumbo", "searched_for": "melk", "name": "Jumbo Halfvolle Melk 1L", "price": 0.99}]
DIRK_MATCH = [{"store": "Dirk", "searched_for": "melk", "name": "1 de Beste Halfvolle Melk", "price": 0.89}]
AH_MATCH = [{"store": "Albert Heijn", "searched_for": "melk", "name": "AH Halfvolle Melk", "price": 0.95}]


@pytest.mark.asyncio
@patch("mcp.multi_store.jumbo_match", new_callable=AsyncMock)
@patch("mcp.multi_store.dirk_match", new_callable=AsyncMock)
@patch("mcp.multi_store.ah_match", new_callable=AsyncMock)
async def test_match_deals_across_stores_combines_results(mock_ah, mock_dirk, mock_jumbo):
    mock_jumbo.return_value = JUMBO_MATCH
    mock_dirk.return_value = DIRK_MATCH
    mock_ah.return_value = AH_MATCH

    from mcp.multi_store import match_deals_across_stores
    results = await match_deals_across_stores(["melk"])

    assert len(results) == 3
    stores = {r["store"] for r in results}
    assert stores == {"Jumbo", "Dirk", "Albert Heijn"}


@pytest.mark.asyncio
@patch("mcp.multi_store.jumbo_match", new_callable=AsyncMock)
@patch("mcp.multi_store.dirk_match", new_callable=AsyncMock)
@patch("mcp.multi_store.ah_match", new_callable=AsyncMock)
async def test_match_deals_ignores_store_failures(mock_ah, mock_dirk, mock_jumbo):
    mock_jumbo.side_effect = Exception("Jumbo down")
    mock_dirk.return_value = DIRK_MATCH
    mock_ah.return_value = []

    from mcp.multi_store import match_deals_across_stores
    results = await match_deals_across_stores(["melk"])

    assert len(results) == 1
    assert results[0]["store"] == "Dirk"


def test_format_deals_message_groups_by_store():
    from mcp.multi_store import format_deals_message
    matches = JUMBO_MATCH + DIRK_MATCH + AH_MATCH

    msg = format_deals_message(matches)

    assert "Jumbo" in msg
    assert "Dirk" in msg
    assert "Albert Heijn" in msg
    assert "0.99" in msg
    assert "0.89" in msg


def test_format_deals_message_no_matches():
    from mcp.multi_store import format_deals_message
    msg = format_deals_message([])
    assert "None" in msg


@pytest.mark.asyncio
async def test_dirk_scraper_parses_itemlist():
    DIRK_HTML = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[{"@type":"ItemList","itemListElement":[
      {"@type":"ListItem","position":1,"item":{"@type":"Product","name":"Komkommer",
       "sku":12345,"url":"/boodschappen/komkommer/12345",
       "offers":{"@type":"Offer","price":0.49,"priceCurrency":"EUR"}}}
    ]}]}
    </script>
    """
    from mcp.dirk_scraper import _parse_deals_from_html
    results = _parse_deals_from_html(DIRK_HTML)

    assert len(results) == 1
    assert results[0]["name"] == "Komkommer"
    assert results[0]["price"] == 0.49
    assert results[0]["store"] == "Dirk"
