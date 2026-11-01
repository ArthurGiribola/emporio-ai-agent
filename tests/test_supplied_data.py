"""Optional integration checks. Restricted resources are never test fixtures in Git."""

import os
import unittest
from decimal import Decimal
from pathlib import Path

from app.repository import Repository, SCHEMAS
from app.services import CatalogService


DATA = Path(os.environ.get("EMPORIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


@unittest.skipUnless(all((DATA / f"{name}.csv").is_file() for name in SCHEMAS),
                     "Authorized original CSVs are not installed; synthetic tests still run")
class SuppliedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Repository(DATA)
        cls.service = CatalogService(cls.repo)

    def test_all_six_files_and_known_counts(self):
        self.assertEqual(self.repo.counts, dict(categories=9, products=65, promotions=25,
                                               customers=50, orders=20, order_items=22))

    def test_budget_search_and_availability_edge_cases(self):
        products = self.service.search_products(category_id=5, max_price_brl=Decimal("1000"))
        self.assertEqual(len(products), 12)
        self.assertEqual({p.product_id for p in products}, {81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 107, 112})
        for product_id in (96, 113, 130, 136):
            self.assertFalse(self.service.get_product(product_id).available)

    def test_four_promotional_prices_without_pix_stacking(self):
        for product_id, expected in [(127, "323.10"), (121, "439.20"), (90, "1967.18"), (94, "5519.08")]:
            with self.subTest(product_id=product_id):
                self.assertEqual(self.service.get_price_quote(product_id, payment_method="pix").final_price_brl, Decimal(expected))
        self.assertEqual(len(self.service.list_promotions()), 4)

    def test_known_quality_issues_and_optional_fields(self):
        codes = {w.code for w in self.repo.warnings}
        self.assertTrue({"duplicate_customer_email", "historical_total_difference", "attribute_conflict", "status_stock_conflict"} <= codes)
        differences = {w.record_id for w in self.repo.warnings if w.code == "historical_total_difference"}
        self.assertEqual(differences, {"3", "20"})
        self.assertEqual(sum(o.tracking_code is None for o in self.repo._orders.values()), 12)
        self.assertEqual(sum(o.estimated_delivery is None for o in self.repo._orders.values()), 12)
        self.assertEqual(self.repo._orders[3].total_brl, Decimal("3450.00"))
        for product_id in (135, 137, 142):
            self.assertIn("attribute_conflict", {w.code for w in self.repo.product_warnings(product_id)})
