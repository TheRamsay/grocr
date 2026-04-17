import requests
import base64
import json
import time
from .base import Receipt, ReceiptItem
from settings import get_settings, load_config


def _jwt_exp(token: str) -> int:
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    return json.loads(base64.b64decode(payload))["exp"]


def refresh_access_token(refresh_token: str) -> tuple[str, str]:
    """Returns (new_access_token, new_refresh_token)."""
    s = get_settings()
    cfg = load_config()["albert"]
    resp = requests.post(
        f"{cfg['auth_url']}/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={
            "Authorization": s.albert_client_credentials,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": f"AlbertApp/{cfg['build_version']} CFNetwork/3860.600.12 Darwin/25.5.0",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["refresh_token"]


class AlbertAdapter:
    def __init__(self, access_token: str, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._cfg = load_config()["albert"]
        self.session = requests.Session()
        self._set_auth(access_token)

    def _set_auth(self, token: str):
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-GB,en;q=0.9",
            "appversion": self._cfg["app_version"],
            "buildversion": self._cfg["build_version"],
            "x-app-build-number": self._cfg["build_version"],
            "User-Agent": json.dumps({
                "buildNumber": int(self._cfg["build_version"]),
                "platform": "ios",
                "platformVersion": "26.5",
                "model": "unknown",
                "brand": "unknown",
                "manufacturer": "unknown",
            }),
            "Connection": "keep-alive",
            "Authorization": f"Bearer {token}",
        })

    def _ensure_valid_token(self) -> bool:
        """Returns True if token was refreshed."""
        if not self.refresh_token:
            return False
        if _jwt_exp(self.access_token) - time.time() < 300:
            self.access_token, self.refresh_token = refresh_access_token(self.refresh_token)
            self._set_auth(self.access_token)
            return True
        return False

    def get_receipts(self, page: int = 1, page_size: int = 20) -> list[Receipt]:
        self._ensure_valid_token()
        resp = self.session.get(
            f"{self._cfg['base_url']}/customer/purchases/v2",
            params={"pageNumber": page, "pageSize": page_size},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            Receipt(
                id=str(r.get("receiptNumber", "")),
                store="albert",
                date=r.get("receiptCreationTime", ""),
                total_czk=float(r.get("receiptSum", 0)),
                raw=r,
            )
            for r in data.get("receipts", [])
        ]

    def get_receipt_items(self, receipt_id: str) -> list[ReceiptItem]:
        self._ensure_valid_token()
        resp = self.session.get(
            f"{self._cfg['base_url']}/customer/purchase/detail",
            params={"receiptNumber": receipt_id},
        )
        resp.raise_for_status()
        return [
            ReceiptItem(
                name=i.get("desc", ""),
                quantity=float(i.get("quantity", 1)),
                unit_price_czk=float(i.get("pricePerItem", 0)),
                total_price_czk=float(i.get("totalPrice", 0)),
            )
            for i in resp.json().get("purchasedItems", [])
        ]

    def get_all_receipts(self) -> list[Receipt]:
        all_receipts, page = [], 1
        while True:
            batch = self.get_receipts(page=page)
            if not batch:
                break
            all_receipts.extend(batch)
            page += 1
        return all_receipts
