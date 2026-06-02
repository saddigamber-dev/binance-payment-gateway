import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Order, OrderStatus
from app.services import BinanceService, TelegramService

async def process_orders():
    """Background loop to check Binance deposits, expire old orders, and clean DB."""
    while True:
        try:
            db: Session = SessionLocal()
            now = datetime.utcnow()
            
            # 1. Expire 20-minute old orders (Soft Delete)
            expired_orders = db.query(Order).filter(
                Order.status == OrderStatus.PENDING,
                Order.expires_at <= now
            ).all()
            
            for order in expired_orders:
                order.status = OrderStatus.EXPIRED
            if expired_orders:
                db.commit()

            # 2. Garbage Collection (Hard Delete orders older than 24 hours)
            cleanup_threshold = now - timedelta(hours=24)
            old_orders = db.query(Order).filter(Order.created_at < cleanup_threshold).all()
            for old_order in old_orders:
                db.delete(old_order)
            if old_orders:
                db.commit()

            # 3. Check deposits for active PENDING orders
            active_orders = db.query(Order).filter(Order.status == OrderStatus.PENDING).all()
            if active_orders:
                currencies = {o.currency for o in active_orders}
                for currency in currencies:
                    oldest = min([o for o in active_orders if o.currency == currency], key=lambda x: x.created_at)
                    start_time_ms = int(oldest.created_at.timestamp() * 1000)
                    
                    deposits = await BinanceService.check_recent_deposits(currency, start_time_ms)
                    
                    for deposit in deposits:
                        dep_amount = float(deposit.get("amount", 0))
                        dep_address = deposit.get("address")
                        
                        for order in active_orders:
                            if order.currency == currency and order.deposit_address == dep_address:
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
            
        await asyncio.sleep(30)
