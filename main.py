main.py

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv
from binance.client import Client
from jose import jwt
from datetime import datetime, timedelta
from collections import defaultdict
from io import BytesIO

import uuid
import os
import httpx
import asyncio
import qrcode
import base64
import random

=========================

LOAD ENV

=========================

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_SECRET")
ALGORITHM = "HS256"

=========================

FASTAPI

=========================

app = FastAPI(
title="Secure Binance Gateway",
default_response_class=ORJSONResponse
)

=========================

CORS

=========================

app.add_middleware(
CORSMiddleware,
allow_origins=[
"https://yourfrontend.com"
],
allow_credentials=True,
allow_methods=["GET", "POST"],
allow_headers=["*"],
)

=========================

DATABASE

=========================

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
DATABASE_URL,
pool_pre_ping=True,
pool_size=20,
max_overflow=30
)

SessionLocal = sessionmaker(
autocommit=False,
autoflush=False,
bind=engine
)

Base = declarative_base()

=========================

BINANCE

=========================

client = Client(
os.getenv("BINANCE_API_KEY"),
os.getenv("BINANCE_API_SECRET"),
requests_params={
"timeout": 5
}
)

=========================

RATE LIMIT

=========================

RATE_LIMIT = defaultdict(list)

=========================

MODEL

=========================

class PaymentOrder(Base):

__tablename__ = "payment_orders"

id = Column(Integer, primary_key=True, index=True)

order_id = Column(String, unique=True, index=True)

amount = Column(Float)

display_amount = Column(Float)

coin = Column(String)

network = Column(String)

wallet_address = Column(String)

status = Column(String, default="pending")

txid = Column(String, nullable=True)

ip_address = Column(String)

secure_token = Column(String)

expires_at = Column(DateTime)

created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

=========================

DB

=========================

def get_db():

db = SessionLocal()

try:
    yield db

finally:
    db.close()

=========================

HELPERS

=========================

def get_ip(request: Request):

forwarded = request.headers.get("x-forwarded-for")

if forwarded:
    return forwarded.split(",")[0]

return request.client.host

def cleanup_rate_limit():

now = datetime.utcnow()

for ip in list(RATE_LIMIT.keys()):

    RATE_LIMIT[ip] = [
        t for t in RATE_LIMIT[ip]
        if (now - t).seconds < 60
    ]

def generate_secure_token(order_id: str):

payload = {
    "order_id": order_id,
    "exp": datetime.utcnow() + timedelta(hours=1)
}

return jwt.encode(
    payload,
    SECRET_KEY,
    algorithm=ALGORITHM
)

async def send_telegram(message: str):

token = os.getenv("TELEGRAM_BOT_TOKEN")

chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    return

try:

    async with httpx.AsyncClient(timeout=5) as http:

        await http.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message
            }
        )

except:
    pass

def generate_qr_base64(data: str):

qr = qrcode.QRCode(
    version=1,
    box_size=10,
    border=5
)

qr.add_data(data)

qr.make(fit=True)

img = qr.make_image(
    fill_color="black",
    back_color="white"
)

buffer = BytesIO()

img.save(buffer, format="PNG")

return base64.b64encode(
    buffer.getvalue()
).decode()

=========================

SECURITY MIDDLEWARE

=========================

@app.middleware("http")
async def security_middleware(request: Request, call_next):

ip = get_ip(request)

cleanup_rate_limit()

RATE_LIMIT[ip].append(datetime.utcnow())

# HARD RATE LIMIT

if len(RATE_LIMIT[ip]) > 20:

    return ORJSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": "Too many requests"
        }
    )

return await call_next(request)

=========================

HOME

=========================

@app.get("/")
async def home():

return {
    "success": True,
    "message": "Secure Binance Gateway Running"
}

=========================

CREATE ORDER

=========================

@app.post("/create-order")
async def create_order(
request: Request,
amount: float,
coin: str = "USDT",
network: str = "BEP20",
db: Session = Depends(get_db)
):

ip = get_ip(request)

# CHECK ACTIVE ORDER

active = db.query(PaymentOrder).filter(
    PaymentOrder.ip_address == ip,
    PaymentOrder.status == "pending",
    PaymentOrder.expires_at > datetime.utcnow()
).first()

if active:

    raise HTTPException(
        status_code=429,
        detail="You already have a pending order"
    )

# RANDOMIZE AMOUNT

randomized_amount = round(
    amount + random.uniform(0.001, 0.009),
    3
)

# UNIQUE ORDER ID

order_id = f"ORD-{uuid.uuid4().hex[:16]}"

expires_at = datetime.utcnow() + timedelta(minutes=20)

wallet_address = "UNAVAILABLE"

try:

    api_network = (
        "BSC"
        if network.upper() == "BEP20"
        else network
    )

    deposit_info = client.get_deposit_address(
        coin=coin,
        network=api_network
    )

    wallet_address = deposit_info["address"]

except Exception as e:

    print(e)

# GENERATE QR

qr_code = generate_qr_base64(wallet_address)

# JWT TOKEN

secure_token = generate_secure_token(order_id)

# SAVE ORDER

order = PaymentOrder(
    order_id=order_id,
    amount=randomized_amount,
    display_amount=amount,
    coin=coin,
    network=network,
    wallet_address=wallet_address,
    ip_address=ip,
    secure_token=secure_token,
    expires_at=expires_at
)

db.add(order)

db.commit()

db.refresh(order)

asyncio.create_task(

    send_telegram(
        f"🔥 NEW ORDER\n\n"
        f"Order: {order_id}\n"
        f"Amount: {randomized_amount} {coin}\n"
        f"IP: {ip}"
    )

)

return {

    "success": True,

    "order_id": order_id,

    "amount": randomized_amount,

    "display_amount": amount,

    "coin": coin,

    "network": network,

    "wallet_address": wallet_address,

    "qr_code": f"data:image/png;base64,{qr_code}",

    "expires_at": expires_at.isoformat(),

    "status": "pending"
}

=========================

PAYMENT STATUS

=========================

@app.get("/status/{order_id}")
async def payment_status(
order_id: str,
db: Session = Depends(get_db)
):

order = db.query(PaymentOrder).filter(
    PaymentOrder.order_id == order_id
).first()

if not order:

    raise HTTPException(
        status_code=404,
        detail="Order not found"
    )

# EXPIRE ORDER

if (
    order.status == "pending"
    and datetime.utcnow() > order.expires_at
):

    order.status = "expired"

    db.commit()

# VERIFY PAYMENT FROM BINANCE

if order.status == "pending":

    try:

        deposits = client.get_deposit_history(
            coin=order.coin,
            limit=50
        )

        for dep in deposits:

            address_match = (
                dep.get("address", "").lower()
                ==
                order.wallet_address.lower()
            )

            amount_match = (
                float(dep.get("amount", 0))
                >= order.amount
            )

            confirmed = dep.get("status") == 1

            if (
                address_match
                and amount_match
                and confirmed
            ):

                order.status = "confirmed"

                order.txid = dep.get("txId")

                db.commit()

                asyncio.create_task(

                    send_telegram(
                        f"🎉 PAYMENT CONFIRMED\n\n"
                        f"Order: {order.order_id}\n"
                        f"Amount: {order.amount}\n"
                        f"TXID: {order.txid}"
                    )

                )

                break

    except Exception as e:

        print(e)

return {

    "success": True,

    "order_id": order.order_id,

    "status": order.status,

    "verified": (
        order.status == "confirmed"
    ),

    "secure_token": (
        order.secure_token
        if order.status == "confirmed"
        else None
    ),

    "txid": order.txid
}

=========================

VERIFY TOKEN

=========================

@app.get("/verify-token")
async def verify_token(token: str):

try:

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    return {

        "success": True,

        "valid": True,

        "order_id": payload["order_id"]
    }

except:

    raise HTTPException(
        status_code=401,
        detail="Invalid token"
    )

=========================

START

=========================

if name == "main":

import uvicorn

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=int(os.getenv("PORT", 8000))
)
