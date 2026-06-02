import hmac
import hashlib
import time
import httpx
from urllib.parse import urlencode
from app.config import settings

class BinanceService:
    BASE_URL = "https://api.binance.com"

    @classmethod
    def _get_signature(cls, query_string: str) -> str:
        return hmac.new(
            settings.BINANCE_API_SECRET.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @classmethod
    async def get_deposit_address(cls, coin: str, network: str) -> str:
        endpoint = "/sapi/v1/capital/deposit/address"
        params = {
            "coin": coin,
            "network": network,
            "timestamp": int(time.time() * 1000)
        }
        query_string = urlencode(params)
        signature = cls._get_signature(query_string)
        
        headers = {"X-MBX-APIKEY": settings.BINANCE_API_KEY}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{cls.BASE_URL}{endpoint}?{query_string}&signature={signature}", headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("address", "")

    @classmethod
    async def check_recent_deposits(cls, coin: str, start_time_ms: int):
        endpoint = "/sapi/v1/capital/deposit/hisrec"
        params = {
            "coin": coin,
            "startTime": start_time_ms,
            "status": 1, # 1 means success/completed in Binance API
            "timestamp": int(time.time() * 1000)
        }
        query_string = urlencode(params)
        signature = cls._get_signature(query_string)
        
        headers = {"X-MBX-APIKEY": settings.BINANCE_API_KEY}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{cls.BASE_URL}{endpoint}?{query_string}&signature={signature}", headers=headers)
            response.raise_for_status()
            return response.json()

class TelegramService:
    @staticmethod
    async def send_message(text: str):
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload)
            except Exception as e:
                print(f"Telegram notification failed: {e}")
              
