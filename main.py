from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.payment import Base, PaymentOrder
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uvicorn
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

settings = get_settings()

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Binance Payment Gateway - Production V10", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_real_ip(request: Request):
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def send_telegram(message: str):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            await http.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": f"🔥 {message}"}
            )
    except:
        pass

def generate_qr_base64(address: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(address)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@app.middleware("http")
async def strict_rate_limit(request: Request, call_next):
    if request.url.path == "/create-order":
        ip = get_real_ip(request)
        db = next(get_db())
        active_order = db.query(PaymentOrder).filter(
            PaymentOrder.ip_address == ip,
            PaymentOrder.status == "pending",
            PaymentOrder.expires_at > datetime.utcnow()
        ).first()
        db.close()
        if active_order:
            return JSONResponse(
                status_code=429,
                content={"error": "You already have one active pending order. Please wait until it expires (20 min) or use existing one."}
            )
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
async def home():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Binance Payment Gateway - Production</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f0f0f; color: #00ff9d; margin: 0; padding: 40px; }
            .container { max-width: 900px; margin: 0 auto; }
            h1 { color: #00ff9d; }
            pre { background: #1a1a1a; padding: 20px; border-radius: 10px; overflow-x: auto; border: 1px solid #00ff9d; }
            .card { background: #1a1a1a; padding: 25px; border-radius: 15px; margin: 20px 0; border: 1px solid #00ff9d; }
            input, button { padding: 12px; margin: 8px 0; border-radius: 8px; border: 1px solid #00ff9d; background: #111; color: #00ff9d; }
            button { cursor: pointer; background: #00ff9d; color: #000; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔥 Binance Payment Gateway</h1>
            <h2>Production Ready • binance.digamber.in</h2>
            
            <div class="card">
                <h3>Integration Example (Copy-Paste Ready)</h3>
                <pre><code>async function createPayment(amount = 10) {
  const res = await fetch(`https://binance.digamber.in/create-order?amount=${amount}&coin=USDT&network=BEP20`);
  const data = await res.json();

  if (data.success) {
    const qrImg = document.getElementById('qr-code');
    qrImg.src = data.qr_code;
    qrImg.style.display = 'block';

    document.getElementById('wallet').innerText = data.wallet_address;

    const pollInterval = setInterval(async () => {
      const statusRes = await fetch(`https://binance.digamber.in/status/${data.order_id}`);
      const statusData = await statusRes.json();

      if (statusData.status === "confirmed") {
        clearInterval(pollInterval);
        alert("🎉 Payment Successful! Your product is now unlocked.");
        window.location.href = `/success?order_id=${data.order_id}`;
      } else if (statusData.status === "expired") {
        clearInterval(pollInterval);
        alert("⏰ Order Expired. Please create a new order.");
      }
    }, 8000);
  }
}</code></pre>
            </div>

            <div class="card">
                <h3>Quick Test</h3>
                <form action="/create-order" method="post">
                    <input type="number" name="amount" value="10" step="0.01" required style="width: 200px;">
                    <button type="submit">Create Payment Order</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/create-order")
async def create_order(amount: float, coin: str = "USDT", network: str = "BEP20", request: Request = None, db: Session = Depends(get_db)):
    ip = get_real_ip(request)
    order_id = f"ORDER_{int(datetime.utcnow().timestamp())}"
    expires_at = datetime.utcnow() + timedelta(minutes=settings.ORDER_EXPIRY_MINUTES)

    wallet_address = "0xError_Fetching_Address"
    try:
        api_network = "BSC" if network.upper() == "BEP20" else network
        deposit_info = client.get_deposit_address(coin=coin, network=api_network)
        wallet_address = deposit_info.get('address', wallet_address)
    except Exception as e:
        await send_telegram(f"Address Fetch Error: {str(e)[:100]}")

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

    await send_telegram(f"New Order Created | ID: {order_id} | Amount: {amount} {coin} | IP: {ip}")

    return {
        "success": True,
        "order_id": order_id,
        "amount": amount,
        "coin": coin,
        "network": network,
        "wallet_address": wallet_address,
        "qr_code": f"data:image/png;base64,{qr_code}",
        "expires_at": expires_at.isoformat(),
        "status": "pending"
    }

@app.get("/status/{order_id}")
async def get_status(order_id: str, db: Session = Depends(get_db)):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == "pending" and datetime.utcnow() > order.expires_at:
        order.status = "expired"
        db.commit()

    if order.status == "pending":
        try:
            deposits = client.get_deposit_history(coin=order.coin, limit=100)
            for dep in deposits:
                if (dep.get("address", "").lower() == order.wallet_address.lower() and
                    float(dep.get("amount", 0)) >= order.amount and
                    dep.get("status") == 1):
                    order.status = "confirmed"
                    order.txid = dep.get("txId")
                    db.commit()
                    await send_telegram(f"🎉 Payment Confirmed! Order: {order_id} | TX: {order.txid}")
                    break
        except:
            pass

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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)