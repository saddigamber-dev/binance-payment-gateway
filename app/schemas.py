from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models import OrderStatus

class OrderCreate(BaseModel):
    amount: float
    currency: str = "USDT"
    network: str = "TRX" # e.g., TRX for Tron TRC20

class OrderResponse(BaseModel):
    id: str
    unique_amount: float
    currency: str
    network: str
    status: OrderStatus
    deposit_address: str
    qr_code_base64: str
    expires_at: datetime
    
    class Config:
        from_attributes = True
