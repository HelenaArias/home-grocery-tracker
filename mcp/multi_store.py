import asyncio
from mcp.jumbo_scraper import match_deals_to_items as jumbo_match
from mcp.dirk_scraper import match_deals_to_items as dirk_match
from mcp.ah_scraper import search_bonus_items as ah_match


async def match_deals_across_stores(item_names: list[str]) -> list[dict]:
    """Search all stores in parallel and return combined matches grouped by store."""
    jumbo_results, dirk_results, ah_results = await asyncio.gather(
        jumbo_match(item_names),
        dirk_match(item_names),
        ah_match(item_names),
        return_exceptions=True,
    )

    all_matches = []
    for results in (jumbo_results, dirk_results, ah_results):
        if isinstance(results, Exception):
            continue
        all_matches.extend(results)

    return all_matches


def format_deals_message(matches: list[dict]) -> str:
    if not matches:
        return "None of your usual items are on deal at Jumbo, AH, or Dirk right now."

    by_store: dict[str, list[dict]] = {}
    for m in matches:
        store = m.get("store", "Unknown")
        by_store.setdefault(store, []).append(m)

    lines = ["Your usual items on sale this week:\n"]
    for store, items in by_store.items():
        lines.append(f"*{store}*")
        for item in items:
            price = f"€{item['price']:.2f}" if item.get("price") else "price unknown"
            lines.append(f"  - {item['name']}: {price}")
    return "\n".join(lines)
