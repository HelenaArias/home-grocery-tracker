from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str  # e.g. "whatsapp:+14155238886"

    class Config:
        env_file = ".env"


settings = Settings()
