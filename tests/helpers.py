"""Entirely synthetic fixtures: no copied customer records or policy text."""

import csv
from pathlib import Path

from app.repository import SCHEMAS


def fixture_rows() -> dict[str, list[dict[str, str]]]:
    return {
        "categories": [dict(category_id="1", name="Violões", description="Acoustic instruments"),
                       dict(category_id="2", name="Ukuleles", description="Small instruments")],
        "products": [
            dict(product_id=str(i), price_brl=price, name=name, category_id="1",
                 description="Synthetic instrument for tests", stock_quantity=stock,
                 status=status, specs='{"strings":"nylon"}', created_at="2025-01-01")
            for i, price, name, stock, status in [
                (1, "100.10", "Test Nylon", "2", "active"),
                (2, "200", "Test Folk", "0", "active"),
                (3, "300", "Test Vintage", "4", "discontinued"),
                (4, "400", "Test Future", "1", "coming_soon"),
                (5, "100.05", "Test Round", "3", "active"),
            ]
        ],
        "promotions": [
            dict(promotion_id="1", product_id="1", discount_percent="10", description="Synthetic offer", is_active="1"),
            dict(promotion_id="2", product_id="1", discount_percent="90", description="Old offer", is_active="0"),
            dict(promotion_id="3", product_id="2", discount_percent="20", description="Stockout offer", is_active="1"),
        ],
        "customers": [dict(customer_id="1", name="Synthetic Person", phone="TEST-ONLY",
                           email="test@example.invalid", city="Test City")],
        "orders": [dict(order_id="1", customer_id="1", order_date="2025-01-02", status="confirmed",
                        total_brl="99", payment_method="pix", tracking_code="", estimated_delivery="", notes="")],
        "order_items": [dict(order_id="1", quantity="1", product_id="1")],
    }


def write_fixture(directory: Path, rows: dict) -> None:
    for name, records in rows.items():
        with (directory / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SCHEMAS[name])
            writer.writeheader()
            writer.writerows(records)


def mock_shop_scope(case):
    """Isolate existing business/transport tests; real scope is tested in test_scope."""
    from unittest.mock import patch
    scope = patch("app.agent.assess_scope", return_value=("shop", "en"))
    decision = scope.start()
    case.addCleanup(scope.stop)
    return decision
