from twilio.rest import Client
from app.config import settings

_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_message(to: str, body: str) -> None:
    _client.messages.create(
        from_=settings.twilio_whatsapp_number,
        to=to,
        body=body,
    )
