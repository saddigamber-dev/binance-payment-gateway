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

app = FastAPI(title="Binance Payment Gateway - V9 Final")

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
                await http.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                    json={"chat_id": chat_id, "text": f"🔥 {message}"})
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

# Auto Cleanup Old Expired Orders
def cleanup_expired_orders(db):
    db.query(PaymentOrder).filter(
        PaymentOrder.status == "expired",
        PaymentOrder.expires_at < datetime.utcnow() - timedelta(hours=1)
    ).delete()
    db.commit()

# Strict Rate Limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/create-order":
        ip = get_client_ip(request)
        db = SessionLocal()
        cleanup_expired_orders(db)
        active = db.query(PaymentOrder).filter(
            PaymentOrder.ip_address == ip,
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at > datetime.utcnow()
        ).first()
        db.close()
        if active:
            return JSONResponse(status_code=429, content={"error": "You have an active order. Wait 20 minutes."})
    return await call_next(request)

def generate_qr_base64(address: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(address)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@app.get("/", response_class=HTMLResponse)
async def home():
    html = """
    <html>
    <head><title>Binance Payment Gateway</title>
    <style>body{font-family:Arial;background:#0a0a0a;color:#0f0;padding:40px;text-align:center;}</style>
    </head>
    <body>
        <h1>🔥 Binance Payment Gateway</h1>
        <h2>binance.digamber.in</h2>

        <h3>Integration Example (Frontend)</h3>
        <pre style="background:#1a1a1a;padding:15px;border-radius:8px;text-align:left;display:inline-block;">
async function createPayment(amount) {
  const res = await fetch("https://binance.digamber.in/create-order?amount=" + amount + "&coin=USDT&network=BEP20");
  const data = await res.json();

  if (data.success) {
    console.log("Order Created:", data.order_id);
    // Show QR Code
    document.getElementById("qr").src = data.qr_code;
    
    // Start Polling for Payment Status
    pollPaymentStatus(data.order_id);
  }
}

async function pollPaymentStatus(order_id) {
  const interval = setInterval(async () => {
    const res = await fetch("https://binance.digamber.in/status/" + order_id);
    const data = await res.json();

    if (data.status === "confirmed") {
      clearInterval(interval);
      alert("🎉 Payment Successful! Product Unlocked.");
      // Yahan apna product activate kar dena (unlock, download, etc.)
      window.location.href = "/success?order=" + order_id;
    } else if (data.status === "expired") {
      clearInterval(interval);
      alert("⏰ Order Expired");
    }
  }, 5000); // Har 5 second mein check
}
        </pre>

        <h3>Test Here</h3>
        <form action="/create-order" method="post">
            <input type="number" name="amount" value="10" required><br><br>
            <button type="submit">Create Order</button>
        </form>
    </body>
    </html>
    """
    return html

@app.post("/create-order")
async def create_order(amount: float, coin: str = "USDT", network: str = "BEP20", request: Request = None, db=Depends(get_db)):
    ip = get_client_ip(request)
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

    await send_telegram(f"New Order: {order_id} | {amount} {coin} | IP: {ip}")

    return {
        "success": True,
        "order_id": order_id,
        "amount": amount,
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

    cleanup_expired_orders(db)

    if order.status == "pending" and datetime.utcnow() > order.expires_at:
        order.status = "expired"
        db.commit()

    # Auto Confirm Check
    if order.status == "pending":
        try:
            deposits = client.get_deposit_history(coin=order.coin, limit=50)
            for dep in deposits:
                if (dep.get('address', '').lower() == order.wallet_address.lower() and 
                    float(dep.get('amount', 0)) >= order.amount and 
                    dep.get('status') == 1):
                    order.status = "confirmed"
                    order.txid = dep.get('txId')
                    db.commit()
                    await send_telegram(f"🎉 Payment Confirmed!\nOrder: {order_id}\nTX: {order.txid}")
                    break
        except:
            pass

    return order

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
