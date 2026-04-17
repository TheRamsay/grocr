from dataclasses import dataclass
from typing import Protocol


@dataclass
class Receipt:
    id: str
    store: str
    date: str
    total_czk: float
    raw: dict


@dataclass
class ReceiptItem:
    name: str
    quantity: float
    unit_price_czk: float
    total_price_czk: float


class StoreAdapter(Protocol):
    def get_receipts(self, page: int = 0) -> list[Receipt]: ...
    def get_receipt_items(self, receipt_id: str) -> list[ReceiptItem]: ...
    def get_all_receipts(self) -> list[Receipt]: ...
