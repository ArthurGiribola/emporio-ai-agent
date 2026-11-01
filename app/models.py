"""Immutable records; monetary values are Decimal, never float."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True)
class DataWarning:
    code: str
    source: str
    record_id: str
    message: str


@dataclass(frozen=True)
class Category:
    category_id: int
    name: str
    description: str


@dataclass(frozen=True)
class Product:
    product_id: int
    price_brl: Decimal
    name: str
    category_id: int
    description: str
    stock_quantity: int
    status: str
    specs: Mapping[str, str]
    created_at: date

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class Promotion:
    promotion_id: int
    product_id: int
    discount_percent: Decimal
    description: str
    is_active: bool


# These records deliberately suppress personal/free-text values in repr output.
@dataclass(frozen=True, repr=False)
class Customer:
    customer_id: int
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True, repr=False)
class Order:
    order_id: int
    customer_id: int
    order_date: date
    status: str
    total_brl: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None


@dataclass(frozen=True)
class OrderItem:
    order_id: int
    quantity: int
    product_id: int


@dataclass(frozen=True)
class PriceQuote:
    product_id: int
    base_price_brl: Decimal
    final_price_brl: Decimal
    discount_percent: Decimal
    discount_kind: str
    promotion_id: int | None
    payment_method: str
    available: bool
    warnings: tuple[DataWarning, ...] = field(default_factory=tuple)
    source: str = "CSV snapshot; freshness unknown; not a live offer"
