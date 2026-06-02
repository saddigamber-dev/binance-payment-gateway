'''
Binance Payment Gateway v2.0
Production-ready FastAPI application
'''
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.database import engine, Base
from app.routers import orders, demo
from app.services.payment_checker import run_checker_forever

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("binance-gateway")

# Create tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("\U0001F680 Binance Payment Gateway v2.0 starting...")
    
    # Start background payment checker in daemon thread
    checker_thread = threading.Thread(target=run_checker_forever, daemon=True)
    checker_thread.start()
    logger.info("\u2705 Background payment checker thread started")
    
    yield
    
    logger.info("\U0001F44B Shutting down Binance Payment Gateway")


app = FastAPI(
    title="Binance Payment Gateway",
    description="Production crypto payment gateway with real Binance deposit addresses, auto-confirmation, rate limiting and Telegram alerts.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan

)