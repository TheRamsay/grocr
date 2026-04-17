import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from adapters.base import StoreAdapter
from db.models import Receipt as DBReceipt, ReceiptItem as DBReceiptItem, SyncLog, get_session

logger = logging.getLogger(__name__)


@dataclass
class StoreSync:
    name: str
    load: Callable[[], StoreAdapter]
    persist: Callable[[StoreAdapter], None] | None = None


@dataclass
class SyncResult:
    store: str
    status: str  # ok | error
    new_receipts: int = 0
    total_receipts: int = 0
    error: str | None = None
    duration_ms: int = 0


class SyncEngine:
    def __init__(self, stores: list[StoreSync], engine):
        self._stores = {s.name: s for s in stores}
        self._engine = engine

    @property
    def store_names(self) -> list[str]:
        return list(self._stores.keys())

    def sync_all(self) -> list[SyncResult]:
        return [self._run(store) for store in self._stores.values()]

    def sync_one(self, store_name: str) -> SyncResult:
        store = self._stores.get(store_name)
        if not store:
            return SyncResult(store=store_name, status="error", error="Store not registered")
        return self._run(store)

    def _run(self, store: StoreSync) -> SyncResult:
        started = datetime.utcnow()
        log = SyncLog(store=store.name, started_at=started, status="running")

        with get_session(self._engine) as session:
            session.add(log)
            session.commit()
            log_id = log.id

        try:
            adapter = store.load()
            receipts = adapter.get_all_receipts()
            new_count = self._upsert(adapter, receipts, store.name)

            if store.persist:
                store.persist(adapter)

            result = SyncResult(
                store=store.name,
                status="ok",
                new_receipts=new_count,
                total_receipts=len(receipts),
                duration_ms=int((datetime.utcnow() - started).total_seconds() * 1000),
            )
        except Exception as exc:
            logger.exception("Sync failed for %s", store.name)
            result = SyncResult(
                store=store.name,
                status="error",
                error=str(exc),
                duration_ms=int((datetime.utcnow() - started).total_seconds() * 1000),
            )

        with get_session(self._engine) as session:
            row = session.get(SyncLog, log_id)
            row.finished_at = datetime.utcnow()
            row.status = result.status
            row.new_receipts = result.new_receipts
            row.error = result.error
            session.commit()

        logger.info("Sync %s: %s", store.name, result)
        return result

    def _upsert(self, adapter: StoreAdapter, receipts, store_name: str) -> int:
        new_count = 0
        with get_session(self._engine) as session:
            for r in receipts:
                pk = f"{store_name}:{r.id}"
                if session.get(DBReceipt, pk):
                    continue
                session.add(DBReceipt(
                    id=pk, store=store_name, receipt_id=r.id,
                    date=r.date, total_czk=r.total_czk, raw_json=json.dumps(r.raw),
                ))
                for item in adapter.get_receipt_items(r.id):
                    session.add(DBReceiptItem(
                        receipt_pk=pk, name=item.name, quantity=item.quantity,
                        unit_price_czk=item.unit_price_czk, total_price_czk=item.total_price_czk,
                    ))
                new_count += 1
            session.commit()
        return new_count
