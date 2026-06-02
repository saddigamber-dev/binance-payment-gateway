from sqlalchemy import Column, String, Float, DateTime, Enum, Integer
from datetime import datetime, timedelta
import enum
from app.database import Base

class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    base_amount = Column(Float, nullable=False)
    unique_amount = Column(Float, nullable=False, index=True)
    currency = Column(String, default="USDT")
    network = Column(String, default="TRX")
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    client_ip = Column(String, index=True)
    deposit_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=20))
