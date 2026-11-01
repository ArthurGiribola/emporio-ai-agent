"""Read and validate all six CSVs without exposing customer lookup tools."""

import csv
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping

from app.models import Category, Customer, DataWarning, Order, OrderItem, Product, Promotion


class DataValidationError(ValueError):
    """Invalid source data. Messages omit raw values to avoid leaking PII."""


SCHEMAS = {
    "categories": ("category_id", "name", "description"),
    "products": ("product_id", "price_brl", "name", "category_id", "description",
                 "stock_quantity", "status", "specs", "created_at"),
    "promotions": ("promotion_id", "product_id", "discount_percent", "description", "is_active"),
    "customers": ("customer_id", "name", "phone", "email", "city"),
    "orders": ("order_id", "customer_id", "order_date", "status", "total_brl", "payment_method",
               "tracking_code", "estimated_delivery", "notes"),
    "order_items": ("order_id", "quantity", "product_id"),
}
OPTIONAL = {"tracking_code", "estimated_delivery", "notes"}
PRODUCT_STATUSES = {"active", "discontinued", "coming_soon"}
ORDER_STATUSES = {"delivered", "shipped", "confirmed", "pending", "cancelled"}
PAYMENT_METHODS = {"pix", "debit", "boleto"} | {f"credit_{n}x" for n in range(1, 13)}


def _integer(value: str, *, minimum: int = 1) -> int:
    if not re.fullmatch(r"[0-9]{1,12}", value):
        raise ValueError("expected an integer")
    result = int(value)
    if result < minimum:
        raise ValueError("integer outside allowed range")
    return result


def _decimal(value: str, *, maximum: Decimal | None = None, money: bool = False) -> Decimal:
    # Limit input precision so downstream currency calculations remain bounded.
    if not re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,6})?", value):
        raise ValueError("expected a nonnegative decimal")
    result = Decimal(value)
    if not result.is_finite() or (maximum is not None and result > maximum):
        raise ValueError("decimal outside allowed range")
    if money:
        with localcontext() as context:
            context.prec = 40
            cents = result.quantize(Decimal("0.01"))
        if cents != result:
            raise ValueError("money must have cent precision")
        return cents
    return result


def _date(value: str) -> date:
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("expected YYYY-MM-DD")
    return result


def _choice(value: str, choices: set[str]) -> str:
    if value not in choices:
        raise ValueError("unsupported value")
    return value


def _flag(value: str) -> bool:
    return _choice(value, {"0", "1"}) == "1"


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _specs(value: str) -> Mapping[str, str]:
    result = json.loads(value, object_pairs_hook=_unique_object)
    if not isinstance(result, dict) or not all(
        isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
        for k, v in result.items()
    ):
        raise ValueError("expected a JSON object with nonempty string values")
    return MappingProxyType(result)


PARSERS: dict[str, Callable] = {
    **{k: _integer for k in ("category_id", "product_id", "promotion_id", "customer_id", "order_id", "quantity")},
    "stock_quantity": lambda v: _integer(v, minimum=0),
    "price_brl": lambda v: _decimal(v, money=True),
    "total_brl": lambda v: _decimal(v, money=True),
    "discount_percent": lambda v: _decimal(v, maximum=Decimal("100")),
    "created_at": _date, "order_date": _date, "estimated_delivery": _date,
    "is_active": _flag, "specs": _specs,
}


def _read(directory: Path, name: str, record_type: type) -> list:
    path = directory / f"{name}.csv"
    records = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or set(fields) != set(SCHEMAS[name]):
                raise DataValidationError(f"{path.name}: missing, duplicate, or unexpected columns")
            for row in reader:
                location = f"{path.name}: line {reader.line_num}"
                if None in row or any(value is None for value in row.values()):
                    raise DataValidationError(f"{location}: incorrect field count")
                parsed = {}
                for key, raw in row.items():
                    value = raw.strip()
                    if not value:
                        if name == "orders" and key in OPTIONAL:
                            parsed[key] = None
                            continue
                        raise DataValidationError(f"{location}: {key} is required")
                    try:
                        if key == "status":
                            parsed[key] = _choice(value, PRODUCT_STATUSES if name == "products" else ORDER_STATUSES)
                        elif key == "payment_method":
                            parsed[key] = _choice(value, PAYMENT_METHODS)
                        else:
                            parsed[key] = PARSERS.get(key, str)(value)
                    except (ValueError, InvalidOperation, TypeError, OverflowError):
                        raise DataValidationError(f"{location}: invalid {key}") from None
                records.append(record_type(**parsed))
    except (OSError, UnicodeError, csv.Error):
        raise DataValidationError(f"{path.name}: cannot read valid UTF-8 CSV") from None
    return records


def _index(records: list, field: str, source: str) -> dict:
    result = {}
    for record in records:
        key = getattr(record, field)
        if key in result:
            raise DataValidationError(f"{source}: duplicate {field}")
        result[key] = record
    return result


class Repository:
    """Immutable snapshot. Private order/customer collections are not agent tools.

    Warnings are diagnostics, not proof that unflagged descriptive fields agree.
    No snapshot timestamp is inferred from file modification or product dates.
    """

    def __init__(self, directory: str | Path):
        directory = Path(directory)
        self.categories = MappingProxyType(_index(_read(directory, "categories", Category), "category_id", "categories.csv"))
        self.products = MappingProxyType(_index(_read(directory, "products", Product), "product_id", "products.csv"))
        self.promotions = MappingProxyType(_index(_read(directory, "promotions", Promotion), "promotion_id", "promotions.csv"))
        self._customers = _index(_read(directory, "customers", Customer), "customer_id", "customers.csv")
        self._orders = _index(_read(directory, "orders", Order), "order_id", "orders.csv")
        self._items = tuple(_read(directory, "order_items", OrderItem))
        self._validate_relationships()
        self.warnings = tuple(self._quality_warnings())

    @property
    def counts(self) -> dict[str, int]:
        return {"categories": len(self.categories), "products": len(self.products),
                "promotions": len(self.promotions), "customers": len(self._customers),
                "orders": len(self._orders), "order_items": len(self._items)}

    def _validate_relationships(self) -> None:
        for records, field, target, source in (
            (self.products.values(), "category_id", self.categories, "products.csv"),
            (self.promotions.values(), "product_id", self.products, "promotions.csv"),
            (self._orders.values(), "customer_id", self._customers, "orders.csv"),
            (self._items, "order_id", self._orders, "order_items.csv"),
            (self._items, "product_id", self.products, "order_items.csv"),
        ):
            if any(getattr(record, field) not in target for record in records):
                raise DataValidationError(f"{source}: unresolved {field} reference")
        keys = [(item.order_id, item.product_id) for item in self._items]
        if len(keys) != len(set(keys)):
            raise DataValidationError("order_items.csv: duplicate order_id/product_id pair")

    def product_warnings(self, product_id: int) -> tuple[DataWarning, ...]:
        return tuple(w for w in self.warnings if w.source == "products.csv" and w.record_id == str(product_id))

    def _quality_warnings(self):
        yield DataWarning("unknown_freshness", "data/", "snapshot", "Snapshot freshness is unknown; no live availability is verified.")
        emails = Counter(c.email.casefold() for c in self._customers.values())
        if any(count > 1 for count in emails.values()):
            yield DataWarning("duplicate_customer_email", "customers.csv", "redacted", "Email addresses are not unique and cannot establish identity.")
        for product in self.products.values():
            if product.status != "active" and product.stock_quantity > 0:
                yield DataWarning("status_stock_conflict", "products.csv", str(product.product_id), "Positive stock does not override a non-active product status.")
            if _description_conflicts(product):
                yield DataWarning("attribute_conflict", "products.csv", str(product.product_id), "Name, description, or specifications disagree; verify disputed attributes before recommending.")
        active = Counter(p.product_id for p in self.promotions.values() if p.is_active)
        for product_id, count in active.items():
            if count > 1:
                yield DataWarning("multiple_active_promotions", "promotions.csv", str(product_id), "Multiple active promotions have no priority; promotional quoting is blocked.")
        for order in self._orders.values():
            items = [item for item in self._items if item.order_id == order.order_id]
            if not items:
                yield DataWarning("missing_order_items", "orders.csv", str(order.order_id), "No line items are supplied for this order.")
            with localcontext() as context:
                context.prec = 40
                total = sum((self.products[i.product_id].price_brl * i.quantity for i in items), Decimal("0"))
            if items and total != order.total_brl:
                yield DataWarning("historical_total_difference", "orders.csv", str(order.order_id), "Recorded total differs from current catalog sum; preserve recorded total, historical unit prices are absent.")


def _description_conflicts(product: Product) -> bool:
    """Conservative checks for explicit brand/key/string-count contradictions.

    This is a limited diagnostic, not semantic validation or automatic correction.
    """
    brands = ("Music Man", "Yamaha", "Fender", "Gibson", "Ibanez", "Pearl", "Tama", "Korg", "Roland", "Nord")
    name = product.name.casefold()
    description = product.description.casefold()
    named = {brand for brand in brands if brand.casefold() in name}
    described = {brand for brand in brands if brand.casefold() in description}
    if named and described and not named.intersection(described):
        return True
    for key, pattern in (("keys", r"\b(\d+)\s+teclas\b"), ("strings", r"\b(\d+)\s+cordas\b")):
        value = product.specs.get(key, "")
        match = re.search(pattern, description)
        if value.isdigit() and match and int(value) != int(match.group(1)):
            return True
    return False
