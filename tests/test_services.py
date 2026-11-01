import unittest
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from app.repository import Repository
from app.services import CatalogService, PricingConflictError
from tests.helpers import fixture_rows, write_fixture


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.rows = fixture_rows()

    def service(self):
        write_fixture(self.path, self.rows)
        return CatalogService(Repository(self.path))

    def test_only_active_positive_stock_is_available(self):
        service = self.service()
        self.assertEqual({p.product_id for p in service.search_products()}, {1, 5})
        self.assertEqual(len(service.search_products(available_only=False)), 5)
        self.assertFalse(service.get_product(2).available)
        self.assertFalse(service.get_product(3).available)
        self.assertFalse(service.get_product(4).available)

    def test_search_is_case_and_accent_insensitive_and_matches_all_terms(self):
        service = self.service()
        self.assertEqual([p.product_id for p in service.search_products("VIOLAO nylon")], [1])
        self.assertEqual(service.search_products("nylon nonexistent"), ())

    def test_price_bounds_are_inclusive_and_use_list_price(self):
        service = self.service()
        self.assertEqual([p.product_id for p in service.search_products(min_price_brl=Decimal("100.10"), max_price_brl=Decimal("100.10"))], [1])
        self.assertEqual(service.search_products(max_price_brl=Decimal("95")), ())
        self.assertEqual(service.search_products(category_id=2), ())
        self.assertEqual(service.search_products(category_id=999), ())

    def test_stable_sort_by_price_then_id(self):
        self.rows["products"][4]["price_brl"] = "100.10"
        self.assertEqual([p.product_id for p in self.service().search_products()], [1, 5])

    def test_invalid_search_arguments(self):
        service = self.service()
        for kwargs in [dict(max_price_brl=1.5), dict(max_price_brl=Decimal("NaN")),
                       dict(min_price_brl=Decimal("Infinity")), dict(min_price_brl=Decimal("-1")),
                       dict(min_price_brl=Decimal("2"), max_price_brl=Decimal("1")),
                       dict(category_id=True), dict(query=None), dict(available_only="false")]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                service.search_products(**kwargs)

    def test_missing_and_invalid_product_ids(self):
        service = self.service()
        with self.assertRaises(KeyError):
            service.get_price_quote(999)
        for value in (True, "1", -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                service.get_product(value)

    def test_active_promotion_ignores_inactive_history_and_never_stacks_pix(self):
        service = self.service()
        for method in ("list", "pix", "debit", "credit", "boleto"):
            with self.subTest(method=method):
                quote = service.get_price_quote(1, payment_method=method)
                self.assertEqual(quote.final_price_brl, Decimal("90.09"))
                self.assertEqual(quote.base_price_brl, Decimal("100.10"))
                self.assertEqual(quote.discount_percent, Decimal("10"))
                self.assertEqual(quote.promotion_id, 1)
                self.assertEqual(quote.discount_kind, "promotion")
                self.assertIn("unknown_freshness", {w.code for w in quote.warnings})

    def test_pix_and_half_up_rounding(self):
        service = self.service()
        self.assertEqual(service.get_price_quote(5, payment_method="pix").final_price_brl, Decimal("95.05"))
        self.assertEqual(service.get_price_quote(5).final_price_brl, Decimal("100.05"))
        self.rows["products"][4]["price_brl"] = "0.10"
        self.assertEqual(self.service().get_price_quote(5, payment_method="pix").final_price_brl, Decimal("0.10"))

    def test_decimal_context_does_not_change_quote(self):
        service = self.service()
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(service.get_price_quote(1).final_price_brl, Decimal("90.09"))

    def test_unavailable_quote_is_explicitly_nonbinding(self):
        quote = self.service().get_price_quote(2)
        self.assertFalse(quote.available)
        self.assertIn("not a live offer", quote.source)

    def test_promotion_listing_filters_stock_and_inactive_records(self):
        service = self.service()
        self.assertEqual([p.promotion_id for p in service.list_promotions()], [1])
        self.assertEqual([p.promotion_id for p in service.list_promotions(available_only=False)], [1, 3])

    def test_multiple_active_promotions_block_quote(self):
        self.rows["promotions"][1]["is_active"] = "1"
        service = self.service()
        self.assertIn("multiple_active_promotions", {w.code for w in service.repository.warnings})
        with self.assertRaises(PricingConflictError):
            service.get_price_quote(1)

    def test_zero_and_full_discounts(self):
        for percent, expected in [("0", "100.10"), ("100", "0.00")]:
            with self.subTest(percent=percent):
                self.rows["promotions"][0]["discount_percent"] = percent
                quote = self.service().get_price_quote(1, payment_method="pix")
                self.assertEqual(quote.final_price_brl, Decimal(expected))
                self.assertEqual(quote.discount_kind, "promotion")

    def test_unsupported_payment_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service().get_price_quote(1, payment_method="crypto")
