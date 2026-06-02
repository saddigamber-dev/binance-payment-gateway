# Binance Payment Gateway

A production-level personal cryptocurrency payment gateway leveraging FastAPI, PostgreSQL, and Binance API.

## Features
- Strict 20-minute expiry windows with active background cleanup.
- Generates unique floating-point payments to track transactions to static Binance account addresses.
- Auto-extracts actual client IPs behind Cloudflare (`CF-Connecting-IP` / `X-Forwarded-For`).
- Strictly limits users to 1 active pending order per IP to prevent spam and DB bloat.
- Auto-confirms payments via Binance API polling and sends Telegram notifications.

## Environment Variables (.env)
This project is built to accept your exact existing variables.
```text
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
DATABASE_URL=postgres://user:pass@host/db
JWT_SECRET=your_secret
DEBUG=False
HOST=0.0.0.0
PORT=10000
