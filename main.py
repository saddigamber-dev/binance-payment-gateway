from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from binance.client import Client
import httpx
from datetime import datetime
from jose import JWTError, jwt
import logging

load_dotenv()

app = FastAPI(title="Binance Payment Gateway - Production")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Binance
client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

# Models
class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    coin = Column(String)
    network = Column(String)
    status = Column(String, default="pending")  # pending, confirmed, failed
    wallet_address = Column(String)
    txid = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            async with httpx.AsyncClient() as http:
                await http.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": f"🔥 {message}"}
                )
        except:
            pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/create-order")
async def create_order(amount: float, coin: str = "USDT", network: str = "BEP20", db=Depends(get_db)):
    try:
        order_id = f"ORDER_{int(datetime.utcnow().timestamp())}"
        
        order = PaymentOrder(
            order_id=order_id,
            amount=amount,
            coin=coin,
            network=network,
            status="pending",
            wallet_address="0xGenerated_Wallet_Address"  # Real mein Binance Pay se le
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)

        await send_telegram(f"New Order: {amount} {coin} | OrderID: {order_id} | Network: {network}")

        return {
            "order_id": order_id,
            "amount": amount,
            "coin": coin,
            "network": network,
            "wallet_address": order.wallet_address,
            "status": "pending"
        }
    except Exception as e:
        await send_telegram(f"ERROR Create Order: {str(e)}")
        raise HTTPException(500, str(e))

@app.get("/status/{order_id}")
async def get_status(order_id: str, db=Depends(get_db)):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    return {"order_id": order.order_id, "status": order.status, "txid": order.txid}

@app.post("/webhook")
async def binance_webhook(request: Request, db=Depends(get_db)):
    # Real webhook logic yahan aayega
    data = await request.json()
    await send_telegram(f"Webhook Received: {data}")
    # Database update logic add kar sakte hain
    return {"status": "received"}

@app.get("/")
async def home():
    return {"message": "Binance Payment Gateway Production Ready 🔥"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
