from adapters.albert import AlbertAdapter, refresh_access_token
from db.models import StoreToken, get_session
from settings import get_settings
from .engine import StoreSync


def _load_albert() -> AlbertAdapter:
    s = get_settings()
    with get_session() as session:
        row = session.get(StoreToken, "albert")
        access = row.access_token if row else s.albert_token
        refresh = row.refresh_token if row else s.albert_refresh_token
    if not access:
        raise RuntimeError("Albert token not configured")
    return AlbertAdapter(access, refresh_token=refresh)


def _persist_albert(adapter: AlbertAdapter):
    with get_session() as session:
        row = session.get(StoreToken, "albert") or StoreToken(store="albert")
        row.access_token = adapter.access_token
        row.refresh_token = adapter.refresh_token
        session.merge(row)
        session.commit()


STORES: list[StoreSync] = [
    StoreSync(name="albert", load=_load_albert, persist=_persist_albert),
    # StoreSync(name="lidl", load=_load_lidl, persist=_persist_lidl),
    # StoreSync(name="penny", load=_load_penny),
]
