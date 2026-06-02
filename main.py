from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import asyncio
import uuid
import random
from datetime import datetime

from app.config import settings
from app.database import engine, Base, get_db
from app.models import Order, OrderStatus
from app.schemas import OrderCreate, OrderResponse
from app.utils import get_real_ip, generate_qr_base64
from app.services import BinanceService, TelegramService
from app.tasks import process_orders

# Initialize DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Binance Payment Gateway API", debug=settings.DEBUG)
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    # Start the background worker
    asyncio.create_task(process_orders())

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    #changes is here
    return templates.TemplateResponse(request=request, name="index.html")
    

@app.post("/api/orders", response_model=OrderResponse)
async def create_order(order_req: OrderCreate, request: Request, db: Session = Depends(get_db)):
    client_ip = get_real_ip(request)
    now = datetime.utcnow()
    
    # 1. Strict IP Rate Limiting (1 PENDING order per 20 mins)
    existing_order = db.query(Order).filter(
        Order.client_ip == client_ip,
        Order.status == OrderStatus.PENDING,
        Order.expires_at > now
    ).first()
    
    if existing_order:
        raise HTTPException(
            status_code=429, 
            detail=f"You already have a pending order ({existing_order.id}). Please complete or wait for it to expire."
        )

    # 2. Generate unique tracking amount (adds between 0.001 and 0.999)
    # This is CRITICAL because standard Binance accounts have 1 static address.
    fraction = random.randint(1, 999) / 1000.0
    unique_amount = round(order_req.amount + fraction, 3)

    # 3. Fetch Real Deposit Address from Binance
    try:
        deposit_address = await BinanceService.get_deposit_address(order_req.currency, order_req.network)
        if not deposit_address:
            raise ValueError("Empty address returned")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Payment gateway temporarily unavailable. (Binance API Error)")

    # 4. Create Order
    order_id = str(uuid.uuid4())[:8].upper()
    new_order = Order(
        id=order_id,
        base_amount=order_req.amount,
        unique_amount=unique_amount,
        currency=order_req.currency,
        network=order_req.network,
        client_ip=client_ip,
        deposit_address=deposit_address
    )
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 5. Notify Admin via Telegram
    await TelegramService.send_message(
        f"📝 <b>New Order Created</b>\n\n"
        f"<b>ID:</b> {new_order.id}\n"
        f"<b>Amount Requested:</b> {new_order.unique_amount} {new_order.currency}\n"
        f"<b>IP:</b> {client_ip}"
    )

    qr_base64 = generate_qr_base64(deposit_address)
    
    return OrderResponse(
        id=new_order.id,
        unique_amount=new_order.unique_amount,
        currency=new_order.currency,
        network=new_order.network,
        status=new_order.status,
        deposit_address=new_order.deposit_address,
        qr_code_base64=qr_base64,
        expires_at=new_order.expires_at
    )

@app.get("/api/orders/{order_id}")
async def get_order_status(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"id": order.id, "status": order.status}
