import re
import json
import httpx

BASE = "https://www.dirk.nl"
DEALS_URL = f"{BASE}/aanbiedingen"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9",
}


def _parse_deals_from_html(html: str) -> list[dict]:
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(blob)
            graph = data.get("@graph", [])
            for node in graph:
                if node.get("@type") == "ItemList":
                    results = []
                    for element in node.get("itemListElement", []):
                        item = element.get("item", {})
                        offers = item.get("offers", {})
                        results.append({
                            "store": "Dirk",
                            "name": item.get("name"),
                            "sku": str(item.get("sku", "")),
                            "url": f"{BASE}{item['url']}" if item.get("url", "").startswith("/") else item.get("url"),
                            "price": offers.get("price"),
                            "currency": offers.get("priceCurrency", "EUR"),
                        })
                    return results
        except json.JSONDecodeError:
            continue
    return []


async def get_deals() -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(DEALS_URL)
        resp.raise_for_status()
        return _parse_deals_from_html(resp.text)


async def match_deals_to_items(item_names: list[str]) -> list[dict]:
    deals = await get_deals()
    matches = []
    for item in item_names:
        item_lower = item.lower()
        for deal in deals:
            if deal["name"] and item_lower in deal["name"].lower():
                matches.append({"searched_for": item, **deal})
                break
    return matches
