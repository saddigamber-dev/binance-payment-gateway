from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from binance.client import Client
import httpx
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64

load_dotenv()

app = FastAPI(title="Binance Payment Gateway - V10 Secure")

client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_API_SECRET"))

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
    status = Column(String, default="pending")
    wallet_address = Column(String)
    txid = Column(String, nullable=True)
    ip_address = Column(String, index=True)
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
                await http.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔥 {message}"})
        except:
            pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================== REAL IP EXTRACTION (Cloudflare Fix) ==================
def get_real_ip(request: Request):
    # Cloudflare real IP
    real_ip = request.headers.get("CF-Connecting-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(',')[0].strip()
    
    return request.client.host

# Auto Cleanup
def cleanup_expired(db):
    db.query(PaymentOrder).filter(
        PaymentOrder.expires_at < datetime.utcnow() - timedelta(hours=2)
    ).delete()
    db.commit()

# ================== STRICT RATE LIMITING ==================
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/create-order":
        ip = get_real_ip(request)
        db = SessionLocal()
        cleanup_expired(db)
        
        active = db.query(PaymentOrder).filter(
            PaymentOrder.ip_address == ip,
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at > datetime.utcnow()
        ).first()
        
        db.close()
        
        if active:
            return JSONResponse(status_code=429, content={
                "error": "You already have one active order. Please wait 20 minutes before creating new one."
            })
    return await call_next(request)

def generate_qr_base64(address: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(address)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# Frontend with good example
@app.get("/", response_class=HTMLResponse)
async def home():
    html = """<html><head><title>Binance Payment</title>
    <style>body{font-family:Arial;background:#0a0a0a;color:#0f0;padding:40px;}</style></head>
    <body>
        <h1>🔥 Binance Payment Gateway</h1>
        <h2>binance.digamber.in</h2>
        
        <h3>Integration Example</h3>
        <pre style="background:#111;padding:15px;border-radius:8px;">
async function createPayment(amount = 10) {
  const res = await fetch(`https://binance.digamber.in/create-order?amount=${amount}&coin=USDT&network=BEP20`);
  const data = await res.json();
  
  if(data.success){
    // Show QR
    document.getElementById('qr').src = data.qr_code;
    
    // Poll for success
    setInterval(async () => {
      const statusRes = await fetch(`https://binance.digamber.in/status/${data.order_id}`);
      const status = await statusRes.json();
      if(status.status === "confirmed"){
        alert("Payment Successful! Product Activated.");
        // Unlock product here
      }
    }, 7000);
  }
}
        </pre>
        
        <form action="/create-order" method="post">
            <input type="number" name="amount" value="10"><br><br>
            <button type="submit">Create Order</button>
        </form>
    </body></html>"""
    return html

@app.post("/create-order")
async def create_order(amount: float, coin: str = "USDT", network: str = "BEP20", request: Request = None, db=Depends(get_db)):
    ip = get_real_ip(request)
    order_id = f"ORDER_{int(datetime.utcnow().timestamp())}"
    expires_at = datetime.utcnow() + timedelta(minutes=20)

    wallet_address = "0xError"
    try:
        api_network = "BSC" if network.upper() == "BEP20" else network
        deposit_info = client.get_deposit_address(coin=coin, network=api_network)
        wallet_address = deposit_info.get('address')
    except:
        pass

    qr_code = generate_qr_base64(wallet_address)

    order = PaymentOrder(
        order_id=order_id,
        amount=amount,
        coin=coin,
        network=network,
        wallet_address=wallet_address,
        ip_address=ip,
        expires_at=expires_at
    )
    
    db.add(order)
    db.commit()
    db.refresh(order)

    await send_telegram(f"New Order: {order_id} | {amount} USDT | IP: {ip}")

    return {
        "success": True,
        "order_id": order_id,
        "wallet_address": wallet_address,
        "qr_code": f"data:image/png;base64,{qr_code}",
        "expires_at": expires_at.isoformat(),
        "status": "pending"
    }

@app.get("/status/{order_id}")
async def get_status(order_id: str, db=Depends(get_db)):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")

    cleanup_expired(db)

    if order.status == "pending" and datetime.utcnow() > order.expires_at:
        order.status = "expired"
        db.commit()

    return order

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
