import re
import json
import asyncio
import httpx

BASE = "https://www.jumbo.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9",
}


def _extract_slugs(html: str) -> list[str]:
    slugs = re.findall(r'href="(/producten/[a-z0-9\-]+-[A-Z0-9]+)"', html)
    seen = set()
    unique = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def _extract_jsonld(html: str) -> dict | None:
    for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(blob)
            if data.get("@type") == "Product":
                return data
        except json.JSONDecodeError:
            continue
    return None


def _parse_product(data: dict) -> dict:
    offers = data.get("offers", {})
    return {
        "store": "Jumbo",
        "name": data.get("name"),
        "sku": data.get("sku"),
        "url": data.get("url") or f"{BASE}/producten/{data.get('sku')}",
        "price": offers.get("lowPrice"),
        "currency": offers.get("priceCurrency", "EUR"),
    }


async def search_products(query: str, limit: int = 5) -> list[dict]:
    url = f"{BASE}/producten/?searchType=keyword&searchTerms={query}&offSet=0"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        slugs = _extract_slugs(resp.text)[:limit]

        tasks = [client.get(f"{BASE}{slug}") for slug in slugs]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for r in responses:
        if isinstance(r, Exception):
            continue
        data = _extract_jsonld(r.text)
        if data:
            results.append(_parse_product(data))
    return results


async def get_current_deals(limit: int = 20) -> list[dict]:
    url = f"{BASE}/producten/alle-aanbiedingen/"
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        slugs = _extract_slugs(resp.text)[:limit]

        tasks = [client.get(f"{BASE}{slug}") for slug in slugs]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for r in responses:
        if isinstance(r, Exception):
            continue
        data = _extract_jsonld(r.text)
        if data:
            results.append(_parse_product(data))
    return results


async def match_deals_to_items(item_names: list[str]) -> list[dict]:
    deals = await get_current_deals(limit=40)
    matches = []
    for item in item_names:
        item_lower = item.lower()
        for deal in deals:
            if deal["name"] and item_lower in deal["name"].lower():
                matches.append({"searched_for": item, **deal})
                break
    return matches
