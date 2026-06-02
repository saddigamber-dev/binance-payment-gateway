from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv
from binance.client import Client
import httpx
from datetime import datetime, timedelta
import logging
from fastapi.responses import JSONResponse

load_dotenv()

app = FastAPI(title="Binance Payment Gateway - Production V2")

# ====================== BINANCE CLIENT ======================
client = Client(
    os.getenv("BINANCE_API_KEY"), 
    os.getenv("BINANCE_API_SECRET")
)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
    amount = Column(Float)
    coin = Column(String)
    network = Column(String)
    status = Column(String, default="pending")  # pending, confirmed, expired
    wallet_address = Column(String)
    txid = Column(String, nullable=True)
    ip_address = Column(String)
    expires_at = Column(DateTime)
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

def get_client_ip(request: Request):
    return request.headers.get("X-Forwarded-For") or request.client.host

# Rate Limiting (5 orders per IP per 10 minutes)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = get_client_ip(request)
    if request.url.path == "/create-order":
        db = SessionLocal()
        ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
        count = db.query(PaymentOrder).filter(
            PaymentOrder.ip_address == ip,
            PaymentOrder.created_at >= ten_min_ago
        ).count()
        db.close()
        if count >= 5:
            return JSONResponse(status_code=429, content={"error": "Rate limit exceeded. Try after some time."})
    return await call_next(request)

@app.post("/create-order")
async def create_order(amount: float, coin: str = "USDT", network: str = "BEP20", request: Request = None, db=Depends(get_db)):
    try:
        ip = get_client_ip(request)
        
        # Real Deposit Address Generate (Binance)
        try:
            deposit_info = client.get_deposit_address(coin=coin, network=network)
            wallet_address = deposit_info.get('address')
            memo = deposit_info.get('tag') or deposit_info.get('memo')
        except:
            wallet_address = "Error_fetching_address"
            memo = None

        order_id = f"ORDER_{int(datetime.utcnow().timestamp())}"
        expires_at = datetime.utcnow() + timedelta(minutes=20)

        order = PaymentOrder(
            order_id=order_id,
            amount=amount,
            coin=coin,
            network=network,
            wallet_address=wallet_address,
            status="pending",
            ip_address=ip,
            expires_at=expires_at
        )
        
        db.add(order)
        db.commit()
        db.refresh(order)

        await send_telegram(
            f"✅ New Order\n"
            f"OrderID: {order_id}\n"
            f"Amount: {amount} {coin}\n"
            f"Network: {network}\n"
            f"Address: {wallet_address}\n"
            f"Expires: 20 min"
        )

        return {
            "success": True,
            "order_id": order_id,
            "amount": amount,
            "coin": coin,
            "network": network,
            "wallet_address": wallet_address,
            "memo": memo,
            "expires_at": expires_at.isoformat(),
            "status": "pending"
        }
    except Exception as e:
        await send_telegram(f"❌ Create Order Error: {str(e)}")
        raise HTTPException(500, str(e))

@app.get("/status/{order_id}")
async def get_status(order_id: str, db=Depends(get_db)):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Auto expire check
    if order.status == "pending" and datetime.utcnow() > order.expires_at:
        order.status = "expired"
        db.commit()
        await send_telegram(f"⏰ Order Expired: {order_id}")
    
    return {
        "order_id": order.order_id,
        "amount": order.amount,
        "coin": order.coin,
        "network": order.network,
        "wallet_address": order.wallet_address,
        "status": order.status,
        "txid": order.txid,
        "expires_at": order.expires_at.isoformat()
    }

@app.get("/")
async def home():
    return {"message": "Binance Payment Gateway V2 Live 🔥 | Real Addresses + Auto Expiry"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
