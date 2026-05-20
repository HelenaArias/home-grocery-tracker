import base64
import json
import httpx
from anthropic import AsyncAnthropic
from app.config import settings

client = AsyncAnthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a grocery receipt parser. Extract structured data from receipt images.
Return ONLY valid JSON with this shape:
{
  "store_name": "string or null",
  "purchased_at": "ISO 8601 date string or null",
  "total": number or null,
  "items": [
    {"name": "string", "quantity": number or null, "unit_price": number or null, "total_price": number or null}
  ]
}
If you cannot parse a field, use null. Do not include any text outside the JSON."""


async def parse_receipt_from_url(media_url: str, media_content_type: str) -> dict:
    async with httpx.AsyncClient() as http:
        response = await http.get(
            media_url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
        )
        response.raise_for_status()
        image_data = base64.standard_b64encode(response.content).decode("utf-8")

    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_content_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": "Parse this grocery receipt."},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    print(f"[claude_parser] raw response: {raw}", flush=True)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


async def normalize_item_names(item_names: list[str]) -> dict[str, str]:
    """Returns a mapping of original name -> generic Dutch product name."""
    if not item_names:
        return {}
    items_text = "\n".join(f"- {n}" for n in item_names)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=(
            "You convert brand-specific grocery item names to short generic Dutch product names. "
            "Strip brand names, sizes, and packaging. Return ONLY valid JSON: "
            "{\"original name\": \"generic name\"}. "
            "Examples: 'Jumbo Scharreleieren M/L 6 stuks' -> 'scharreleieren', "
            "'JIMMYS PEANUT BUTTER 350G' -> 'pindakaas', 'Coca-Cola Zero 1.5L' -> 'cola'."
        ),
        messages=[{"role": "user", "content": f"Normalize these items:\n{items_text}"}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return {name: name for name in item_names}


async def answer_query(phone_number: str, question: str, context: str) -> str:
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=(
            "You are a helpful grocery spending assistant. Answer the user's question "
            "based on their purchase history. Be concise — replies go via WhatsApp."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Purchase history:\n{context}\n\nQuestion: {question}",
            }
        ],
    )
    return message.content[0].text
