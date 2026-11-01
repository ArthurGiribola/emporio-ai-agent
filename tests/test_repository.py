import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.repository import DataValidationError, Repository
from tests.helpers import fixture_rows, write_fixture


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.rows = fixture_rows()

    def load(self):
        write_fixture(self.path, self.rows)
        return Repository(self.path)

    def test_typed_loading_and_optional_nulls(self):
        repo = self.load()
        self.assertEqual(repo.counts, dict(categories=2, products=5, promotions=3, customers=1, orders=1, order_items=1))
        self.assertEqual(repo.products[1].price_brl, Decimal("100.10"))
        self.assertEqual(repo.products[1].created_at, date(2025, 1, 1))
        self.assertEqual(repo.products[1].specs["strings"], "nylon")
        self.assertIs(repo.promotions[2].is_active, False)
        self.assertIsNone(repo._orders[1].tracking_code)
        self.assertIsNone(repo._orders[1].estimated_delivery)
        self.assertIsNone(repo._orders[1].notes)

    def test_catalog_mappings_are_read_only(self):
        repo = self.load()
        with self.assertRaises(TypeError):
            repo.products[9] = repo.products[1]
        with self.assertRaises(TypeError):
            repo.products[1].specs["strings"] = "steel"

    def test_required_blank_values_fail_without_echoing_values(self):
        self.rows["customers"][0]["email"] = " "
        with self.assertRaisesRegex(DataValidationError, "email is required") as error:
            self.load()
        self.assertNotIn("Synthetic Person", str(error.exception))

    def test_invalid_types_and_ranges(self):
        cases = [
            ("products", "product_id", "0"), ("products", "stock_quantity", "-1"),
            ("products", "stock_quantity", "2.5"), ("products", "price_brl", "NaN"),
            ("products", "price_brl", "Infinity"), ("products", "price_brl", "-0.01"),
            ("products", "price_brl", "1.001"), ("products", "price_brl", "1,99"),
            ("products", "created_at", "2025-02-30"), ("products", "created_at", "20250101"),
            ("products", "status", "unknown"), ("products", "specs", "not json"),
            ("products", "specs", "[]"), ("products", "specs", '{"keys":61}'),
            ("products", "specs", '{"keys":"61","keys":"88"}'),
            ("promotions", "discount_percent", "101"), ("promotions", "discount_percent", "-5"),
            ("promotions", "is_active", "true"), ("orders", "status", "lost"),
            ("orders", "payment_method", "crypto"), ("orders", "estimated_delivery", "tomorrow"),
            ("order_items", "quantity", "0"), ("order_items", "quantity", "1000000000000"),
        ]
        for table, field, value in cases:
            with self.subTest(table=table, field=field, value=value):
                self.rows = fixture_rows()
                self.rows[table][0][field] = value
                with self.assertRaises(DataValidationError):
                    self.load()

    def test_duplicate_primary_keys(self):
        for table in ("products", "categories", "promotions", "customers", "orders"):
            with self.subTest(table=table):
                self.rows = fixture_rows()
                self.rows[table].append(self.rows[table][0].copy())
                with self.assertRaisesRegex(DataValidationError, "duplicate"):
                    self.load()

    def test_each_foreign_key_is_checked(self):
        for table, field in [("products", "category_id"), ("promotions", "product_id"),
                             ("orders", "customer_id"), ("order_items", "order_id"),
                             ("order_items", "product_id")]:
            with self.subTest(table=table, field=field):
                self.rows = fixture_rows()
                self.rows[table][0][field] = "999"
                with self.assertRaisesRegex(DataValidationError, "unresolved"):
                    self.load()

    def test_duplicate_line_item_rejected(self):
        self.rows["order_items"].append(self.rows["order_items"][0].copy())
        with self.assertRaisesRegex(DataValidationError, "duplicate order_id/product_id"):
            self.load()

    def test_missing_and_bad_headers(self):
        write_fixture(self.path, self.rows)
        path = self.path / "products.csv"
        for content in ("product_id,name\n1,Test\n", "product_id,product_id\n1,1\n"):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(DataValidationError, "columns"):
                    Repository(self.path)

    def test_wrong_row_width(self):
        for suffix in (",extra", ","):
            with self.subTest(suffix=suffix):
                write_fixture(self.path, self.rows)
                path = self.path / "categories.csv"
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("3,Example,Description" + suffix + "\n")
                with self.assertRaisesRegex(DataValidationError, "field count"):
                    Repository(self.path)

    def test_missing_file_and_invalid_encoding(self):
        write_fixture(self.path, self.rows)
        path = self.path / "customers.csv"
        path.unlink()
        with self.assertRaisesRegex(DataValidationError, "customers.csv: cannot read"):
            Repository(self.path)
        path.write_bytes(b"\xff\xfe")
        with self.assertRaises(DataValidationError):
            Repository(self.path)

    def test_optional_whitespace_becomes_none(self):
        self.rows["orders"][0]["notes"] = "   "
        self.assertIsNone(self.load()._orders[1].notes)

    def test_duplicate_email_warning_is_redacted(self):
        duplicate = self.rows["customers"][0].copy()
        duplicate.update(customer_id="2", email="TEST@EXAMPLE.INVALID")
        self.rows["customers"].append(duplicate)
        repo = self.load()
        self.assertIn("duplicate_customer_email", {w.code for w in repo.warnings})
        self.assertNotIn("example.invalid", repr(repo.warnings).lower())
        self.assertNotIn("Synthetic Person", repr(repo._customers[1]))

    def test_source_inconsistencies_are_warnings_not_corrections(self):
        repo = self.load()
        codes = {w.code for w in repo.warnings}
        self.assertTrue({"status_stock_conflict", "historical_total_difference", "unknown_freshness"} <= codes)
        self.assertEqual(repo._orders[1].total_brl, Decimal("99.00"))
        self.assertFalse(repo.products[3].available)

    def test_explicit_brand_and_numeric_conflicts_are_flagged(self):
        for name, description, specs in [
            ("Yamaha Test", "An Ibanez instrument", '{"strings":"4"}'),
            ("Test", "Instrumento com 5 cordas", '{"strings":"4"}'),
            ("Test", "Instrumento com 88 teclas", '{"keys":"61"}'),
        ]:
            with self.subTest(name=name, description=description):
                self.rows = fixture_rows()
                self.rows["products"][0].update(name=name, description=description, specs=specs)
                self.assertIn("attribute_conflict", {w.code for w in self.load().product_warnings(1)})

    def test_empty_optional_tables_are_supported(self):
        for table in ("promotions", "orders", "order_items", "customers"):
            self.rows[table] = []
        self.assertEqual(self.load().counts["promotions"], 0)
