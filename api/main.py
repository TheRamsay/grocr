import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scalar_fastapi import get_scalar_api_reference

from adapters.albert import refresh_access_token
from db.models import Receipt as DBReceipt, ReceiptItem as DBReceiptItem, StoreToken, SyncLog, init_db, get_session
from settings import get_settings
from sync.engine import SyncEngine
from sync.registry import STORES

logger = logging.getLogger(__name__)

engine = init_db()
sync_engine = SyncEngine(STORES, engine)
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        lambda: sync_engine.sync_all(),
        CronTrigger(hour=2, minute=0),
        id="nightly_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — nightly sync at 02:00")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="grocr",
    description="Unified API aggregating Czech grocery store receipts, items, and coupons.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/docs", include_in_schema=False)
def scalar_docs():
    return get_scalar_api_reference(openapi_url="/openapi.json", title="grocr")


# --- receipts ---

class ReceiptOut(BaseModel):
    id: str
    store: str
    date: str
    total_czk: float


class ReceiptItemOut(BaseModel):
    name: str
    quantity: float
    unit_price_czk: float
    total_price_czk: float


@app.get("/receipts", response_model=list[ReceiptOut])
def list_receipts(store: str | None = None):
    with get_session(engine) as session:
        q = session.query(DBReceipt)
        if store:
            q = q.filter(DBReceipt.store == store)
        return [ReceiptOut(id=r.id, store=r.store, date=r.date or "", total_czk=r.total_czk or 0) for r in q.all()]


@app.get("/receipts/{receipt_id}/items", response_model=list[ReceiptItemOut])
def get_items(receipt_id: str):
    with get_session(engine) as session:
        items = session.query(DBReceiptItem).filter(DBReceiptItem.receipt_pk == receipt_id).all()
        return [ReceiptItemOut(name=i.name or "", quantity=i.quantity or 0, unit_price_czk=i.unit_price_czk or 0, total_price_czk=i.total_price_czk or 0) for i in items]


# --- sync ---

class SyncResultOut(BaseModel):
    store: str
    status: str
    new_receipts: int = 0
    total_receipts: int = 0
    error: str | None = None
    duration_ms: int = 0


@app.post("/sync", response_model=list[SyncResultOut])
def sync_all():
    return [SyncResultOut(**vars(r)) for r in sync_engine.sync_all()]


@app.post("/sync/{store}", response_model=SyncResultOut)
def sync_store(store: str):
    if store not in sync_engine.store_names:
        raise HTTPException(status_code=404, detail=f"Store '{store}' not registered")
    return SyncResultOut(**vars(sync_engine.sync_one(store)))


@app.get("/sync/logs", response_model=list[dict])
def sync_logs(limit: int = 50):
    with get_session(engine) as session:
        rows = session.query(SyncLog).order_by(SyncLog.started_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id, "store": r.store, "status": r.status,
                "new_receipts": r.new_receipts, "error": r.error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]


# --- auth ---

@app.post("/auth/albert/refresh")
def refresh_albert_token():
    s = get_settings()
    with get_session(engine) as session:
        row = session.get(StoreToken, "albert")
        refresh = row.refresh_token if row else s.albert_refresh_token
    if not refresh:
        raise HTTPException(status_code=503, detail="No Albert refresh token available")
    new_access, new_refresh = refresh_access_token(refresh)
    with get_session(engine) as session:
        row = session.get(StoreToken, "albert") or StoreToken(store="albert")
        row.access_token = new_access
        row.refresh_token = new_refresh
        session.merge(row)
        session.commit()
    return {"status": "ok"}
