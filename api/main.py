import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from settings import get_settings
from adapters.albert import AlbertAdapter, refresh_access_token
from db.models import init_db, get_session, Receipt as DBReceipt, ReceiptItem as DBReceiptItem, StoreToken

app = FastAPI(title="grocery-aggregator")
engine = init_db()


def _get_albert() -> AlbertAdapter:
    s = get_settings()
    # prefer DB tokens (kept up-to-date after rotations) over .env bootstrap values
    with get_session(engine) as session:
        row = session.get(StoreToken, "albert")
        access = row.access_token if row else s.albert_token
        refresh = row.refresh_token if row else s.albert_refresh_token
    if not access:
        raise HTTPException(status_code=503, detail="Albert token not configured")
    return AlbertAdapter(access, refresh_token=refresh)


def _persist_albert_tokens(adapter: AlbertAdapter):
    with get_session(engine) as session:
        row = session.get(StoreToken, "albert") or StoreToken(store="albert")
        row.access_token = adapter.access_token
        row.refresh_token = adapter.refresh_token
        session.merge(row)
        session.commit()


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


@app.post("/sync/albert")
def sync_albert():
    adapter = _get_albert()
    receipts = adapter.get_all_receipts()
    saved = 0
    with get_session(engine) as session:
        for r in receipts:
            pk = f"albert:{r.id}"
            if not session.get(DBReceipt, pk):
                session.add(DBReceipt(id=pk, store="albert", receipt_id=r.id, date=r.date, total_czk=r.total_czk, raw_json=json.dumps(r.raw)))
                for i in adapter.get_receipt_items(r.id):
                    session.add(DBReceiptItem(receipt_pk=pk, name=i.name, quantity=i.quantity, unit_price_czk=i.unit_price_czk, total_price_czk=i.total_price_czk))
                saved += 1
        session.commit()
    _persist_albert_tokens(adapter)
    return {"synced": saved, "total": len(receipts)}


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
    return {"status": "ok", "message": "Albert tokens refreshed and persisted"}
