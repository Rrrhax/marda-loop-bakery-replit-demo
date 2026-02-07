"""
Marda Loop Bakery - Production Ready API
FastAPI backend with PostgreSQL/SQLite, Telegram initData validation
"""

import os
import hashlib
import hmac
import json
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

import structlog
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON

from config import Settings, get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Database setup
Base = declarative_base()

class OrderModel(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(String, index=True, nullable=True)
    telegram_username = Column(String, nullable=True)
    items = Column(JSON, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String, default="received")  # received, preparing, ready, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_method = Column(String, default="cash")  # cash, card, telegram_stars
    notes = Column(String, nullable=True)

# Pydantic models
class OrderItem(BaseModel):
    id: int
    name: str
    qty: int = Field(..., ge=1, le=100)
    price: float = Field(..., ge=0)
    
    @validator('price')
    def validate_price(cls, v):
        if v < 0 or v > 1000:
            raise ValueError('Invalid price range')
        return round(v, 2)

class OrderCreate(BaseModel):
    items: List[OrderItem]
    total: float = Field(..., ge=0, le=10000)
    init_data: str  # Telegram WebApp initData for validation
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Order must contain at least one item')
        if len(v) > 50:
            raise ValueError('Too many items in order')
        return v
    
    @validator('notes')
    def validate_notes(cls, v):
        if v and len(v) > 500:
            raise ValueError('Notes too long (max 500 chars)')
        return v.strip() if v else None

class OrderResponse(BaseModel):
    order_id: int
    status: str
    estimated_ready: str
    total: float

class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

# Global database engine
engine = None
async_session = None

async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db(database_url: str):
    """Initialize database tables"""
    global engine, async_session
    
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("database_initialized")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    settings = get_settings()
    await init_db(settings.database_url)
    logger.info("application_startup", version="1.0.0")
    yield
    await engine.dispose()
    logger.info("application_shutdown")

# Create FastAPI app
app = FastAPI(
    title="Marda Loop Bakery API",
    description="Production API for Telegram Mini App",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - restrict to specific origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://web.telegram.org", "https://*.telegram.org"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    max_age=600,
)

# Security middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Rate limiting storage (in production use Redis)
request_counts = {}

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Simple rate limiting per IP"""
    client_ip = request.client.host
    now = datetime.utcnow().timestamp()
    
    # Clean old entries
    for ip in list(request_counts.keys()):
        if now - request_counts[ip]["reset_time"] > 60:
            del request_counts[ip]
    
    # Check limit
    if client_ip in request_counts:
        if request_counts[client_ip]["count"] >= 30:  # 30 requests per minute
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again in a minute."}
            )
        request_counts[client_ip]["count"] += 1
    else:
        request_counts[client_ip] = {"count": 1, "reset_time": now + 60}
    
    return await call_next(request)

def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[TelegramUser]:
    """
    Validate Telegram WebApp initData using HMAC-SHA256
    
    Returns TelegramUser if valid, None if invalid
    """
    try:
        # Parse init_data query string
        params = {}
        for param in init_data.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                params[key] = value
        
        # Extract hash
        received_hash = params.pop('hash', None)
        if not received_hash:
            logger.warning("init_data_missing_hash")
            return None
        
        # Check auth_date is not too old (max 24 hours)
        auth_date = int(params.get('auth_date', 0))
        now = int(datetime.utcnow().timestamp())
        if now - auth_date > 86400:
            logger.warning("init_data_expired", age=now - auth_date)
            return None
        
        # Build data_check_string
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        
        # Calculate HMAC-SHA256
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != received_hash:
            logger.warning("init_data_hash_mismatch")
            return None
        
        # Parse user data
        user_data = json.loads(params.get('user', '{}'))
        return TelegramUser(**user_data)
        
    except Exception as e:
        logger.error("init_data_validation_error", error=str(e))
        return None

# API Routes

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get("/menu.json")
async def get_menu():
    """Get menu items - cached for 5 minutes"""
    return FileResponse("menu.json", headers={
        "Cache-Control": "public, max-age=300",
        "ETag": "menu-v1"
    })

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        async with async_session() as session:
            result = await session.execute(select(func.count()).select_from(OrderModel))
            order_count = result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "orders_count": order_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )

@app.post("/api/order", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Create a new order with Telegram initData validation
    """
    # Validate Telegram initData
    user = validate_telegram_init_data(order.init_data, settings.telegram_token)
    if not user:
        logger.warning("order_rejected_invalid_init_data", ip=request.client.host)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication"
        )
    
    # Validate total matches items
    calculated_total = sum(item.price * item.qty for item in order.items)
    if abs(calculated_total - order.total) > 0.01:  # Allow 1 cent rounding difference
        logger.warning(
            "order_total_mismatch",
            expected=calculated_total,
            received=order.total,
            user_id=user.id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total amount mismatch"
        )
    
    # Create order
    db_order = OrderModel(
        telegram_user_id=str(user.id),
        telegram_username=user.username,
        items=[item.dict() for item in order.items],
        total=order.total,
        notes=order.notes,
        status="received"
    )
    
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)
    
    logger.info(
        "order_created",
        order_id=db_order.id,
        user_id=user.id,
        total=order.total,
        items_count=len(order.items)
    )
    
    # Calculate estimated ready time (15-20 minutes)
    estimated_ready = "15-20 min"
    
    return OrderResponse(
        order_id=db_order.id,
        status="received",
        estimated_ready=estimated_ready,
        total=order.total
    )

@app.get("/api/orders/history")
async def get_order_history(
    user_id: str,
    init_data: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Get order history for authenticated user
    """
    # Validate initData
    user = validate_telegram_init_data(init_data, settings.telegram_token)
    if not user or str(user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    # Fetch orders
    result = await db.execute(
        select(OrderModel)
        .where(OrderModel.telegram_user_id == user_id)
        .order_by(desc(OrderModel.created_at))
        .limit(limit)
    )
    orders = result.scalars().all()
    
    return [
        {
            "id": order.id,
            "status": order.status,
            "total": order.total,
            "items": order.items,
            "created_at": order.created_at.isoformat(),
            "notes": order.notes
        }
        for order in orders
    ]

@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    init_data: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """Get specific order details"""
    user = validate_telegram_init_data(init_data, settings.telegram_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    
    result = await db.execute(
        select(OrderModel).where(OrderModel.id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Users can only see their own orders (or add admin check here)
    if order.telegram_user_id != str(user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": order.id,
        "status": order.status,
        "total": order.total,
        "items": order.items,
        "created_at": order.created_at.isoformat(),
        "notes": order.notes
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error. Please try again later."}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        workers=1,
        reload=False,
        log_level="info"
    )
