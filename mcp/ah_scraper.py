import re
import json
import asyncio
import httpx

BASE = "https://www.ah.nl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "nl-NL,nl;q=0.9",
}


def _extract_slugs(html: str) -> list[str]:
    slugs = re.findall(r'href="(/producten/product/[^"?#]+)"', html)
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
    prices = re.findall(r'"price[^"]*":\s*"?([0-9.]+)', json.dumps(data))
    price = float(prices[0]) if prices else None
    return {
        "store": "Albert Heijn",
        "name": data.get("name", "").replace(" bestellen | Albert Heijn", "").strip(),
        "sku": data.get("sku"),
        "url": data.get("url"),
        "price": price,
        "currency": "EUR",
    }


async def search_bonus_items(item_names: list[str], limit_per_item: int = 3) -> list[dict]:
    """For each item name, search AH with bonus filter and return matching deals."""
    results = []
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        for item in item_names:
            search_url = f"{BASE}/zoeken?query={item}&filter=bonus"
            try:
                resp = await client.get(search_url)
                resp.raise_for_status()
                slugs = _extract_slugs(resp.text)[:limit_per_item]
                if not slugs:
                    continue

                product_resps = await asyncio.gather(
                    *[client.get(f"{BASE}{slug}") for slug in slugs],
                    return_exceptions=True,
                )
                for pr in product_resps:
                    if isinstance(pr, Exception):
                        continue
                    data = _extract_jsonld(pr.text)
                    if data:
                        product = _parse_product(data)
                        product["searched_for"] = item
                        results.append(product)
                        break
            except Exception:
                continue
    return results
