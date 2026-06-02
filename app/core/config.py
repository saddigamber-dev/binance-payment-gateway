from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str
    DATABASE_URL: str
    JWT_SECRET: str
    DEBUG: bool = False
    RATE_LIMIT_PER_IP: int = 1
    ORDER_EXPIRY_MINUTES: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()