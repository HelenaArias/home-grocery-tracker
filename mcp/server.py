import json
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from mcp.jumbo_scraper import search_products, get_current_deals, match_deals_to_items

app = Server("jumbo-price-checker")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_product",
            description="Search for a product on Jumbo and return current prices.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product name to search for (Dutch or English)"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_current_deals",
            description="Get current promotional deals at Jumbo supermarket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of deals to return", "default": 20},
                },
            },
        ),
        Tool(
            name="match_deals_to_items",
            description="Check which items from a shopping list are currently on deal at Jumbo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of grocery item names to check against current Jumbo deals",
                    },
                },
                "required": ["items"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_product":
        results = await search_products(arguments["query"], arguments.get("limit", 5))
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, indent=2))]

    if name == "get_current_deals":
        deals = await get_current_deals(arguments.get("limit", 20))
        return [TextContent(type="text", text=json.dumps(deals, ensure_ascii=False, indent=2))]

    if name == "match_deals_to_items":
        matches = await match_deals_to_items(arguments["items"])
        if not matches:
            return [TextContent(type="text", text="None of your usual items appear to be on deal at Jumbo right now.")]
        return [TextContent(type="text", text=json.dumps(matches, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
