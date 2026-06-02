import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import BinanceService, TelegramService

async def process_orders():
    """Background loop to check Binance deposits and expire old orders."""
    while True:
        try:
            db: Session = SessionLocal()
            now = datetime.utcnow()
            
            # 1. Expire old orders
            expired_orders = db.query(Order).filter(
                Order.status == OrderStatus.PENDING,
                Order.expires_at <= now
            ).all()
            
            for order in expired_orders:
                order.status = OrderStatus.EXPIRED
            if expired_orders:
                db.commit()

            # 2. Check deposits for active orders
            active_orders = db.query(Order).filter(Order.status == OrderStatus.PENDING).all()
            if active_orders:
                # Group by currency to minimize API calls
                currencies = {o.currency for o in active_orders}
                for currency in currencies:
                    # Find the oldest active order to set Binance search window
                    oldest = min([o for o in active_orders if o.currency == currency], key=lambda x: x.created_at)
                    start_time_ms = int(oldest.created_at.timestamp() * 1000)
                    
                    deposits = await BinanceService.check_recent_deposits(currency, start_time_ms)
                    
                    for deposit in deposits:
                        dep_amount = float(deposit.get("amount", 0))
                        dep_address = deposit.get("address")
                        
                        # Match unique exact amount and address
                        for order in active_orders:
                            if order.currency == currency and order.deposit_address == dep_address:
                                # Float comparison tolerance
                                if abs(order.unique_amount - dep_amount) < 0.00001:
                                    order.status = OrderStatus.CONFIRMED
                                    db.commit()
                                    await TelegramService.send_message(
                                        f"✅ <b>Payment Received!</b>\n\n"
                                        f"<b>Order ID:</b> {order.id}\n"
                                        f"<b>Amount:</b> {order.unique_amount} {order.currency}\n"
                                        f"<b>Status:</b> CONFIRMED"
                                    )
        except Exception as e:
            print(f"Background task error: {e}")
        finally:
            db.close()
            
        await asyncio.sleep(30) # Poll every 30 seconds
