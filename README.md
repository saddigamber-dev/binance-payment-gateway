# Binance Payment Gateway - Full Production Level

Complete production-ready Binance Crypto Payment Gateway with:

- Strict IP rate limiting (Cloudflare + Proxy support)
- QR Code generation
- Auto payment confirmation via Binance API
- Telegram notifications
- Clean folder structure
- Frontend with integration example

## Folder Structure

binance-payment-gateway/
├── main.py
├── requirements.txt
├── .env
├── alembic/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── security.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── payment.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── payment.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── binance_service.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
└── README.md

## Setup

1. Copy .env.example to .env and fill your keys
2. pip install -r requirements.txt
3. uvicorn main:app --reload

## Endpoints

- POST /create-order
- GET /status/{order_id}

## Website Integration

See the frontend example in main.py or use the JS code provided separately.