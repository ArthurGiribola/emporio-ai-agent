"""Category filters for multi-word category labels (fictional fixture)."""

import tempfile
import unittest
from pathlib import Path

from app.grounding import catalog_arguments, requested_category_ids
from app.repository import Repository
from app.services import CatalogService
from tests.helpers import fixture_rows, write_fixture


def rows():
    data = fixture_rows()
    data["categories"] = [
        dict(category_id="1", name="Violões", description="Acoustic"),
        dict(category_id="2", name="Baterias e Percussão", description="Drums"),
        dict(category_id="3", name="Teclados e Pianos", description="Keys"),
        dict(category_id="4", name="Instrumentos de Sopro (Madeiras)", description="Woodwinds"),
        dict(category_id="5", name="Instrumentos de Sopro (Metais)", description="Brass"),
        dict(category_id="6", name="Cordas Orquestrais", description="Orchestral strings"),
    ]
    extra = [("6", "2", "Kit Ficticio Estudio"), ("7", "2", "Kit Ficticio Palco"), ("8", "3", "Piano Ficticio 88")]
    for product_id, category_id, name in extra:
        data["products"].append(dict(product_id=product_id, price_brl="999", name=name, category_id=category_id,
                                     description="Synthetic instrument for tests", stock_quantity="2",
                                     status="active", specs="{}", created_at="2025-01-01"))
    return data


class CategoryFilterTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        write_fixture(Path(directory.name), rows())
        self.catalog = CatalogService(Repository(Path(directory.name)))

    def category(self, question):
        return requested_category_ids(question, self.catalog)

    def test_a_word_unique_to_one_label_identifies_that_category(self):
        self.assertEqual(self.category("quais opções de bateria você tem?"), {2})
        self.assertEqual(self.category("tem percussão?"), {2})
        self.assertEqual(self.category("quero ver os teclados"), {3})
        self.assertEqual(self.category("tem piano digital?"), {3})
        self.assertEqual(self.category("vocês vendem algo de madeiras?"), {4})

    def test_full_label_wins_over_words_shared_with_other_labels(self):
        self.assertEqual(self.category("violões com cordas de aço"), {1})
        self.assertEqual(self.category("tem cordas orquestrais?"), {6})

    def test_words_shared_by_several_labels_identify_no_single_category(self):
        self.assertEqual(self.category("quais instrumentos vocês têm?"), set())
        self.assertEqual(len(self.category("instrumentos de sopro")), 0)

    def test_browse_of_a_compound_category_filters_by_that_category(self):
        args = catalog_arguments("quais opções de bateria você tem?", {"scope": "browse"}, self.catalog)
        self.assertEqual(args["category_id"], 2)
        self.assertEqual(args["query"], "")
        products = self.catalog.search_products(args["query"], category_id=args["category_id"])
        self.assertEqual({p.product_id for p in products}, {6, 7})

    def test_category_word_in_a_specific_search_is_a_filter_not_a_text_term(self):
        args = catalog_arguments("tem bateria Palco?", {"scope": "search", "query": "bateria Palco"}, self.catalog)
        self.assertEqual(args["category_id"], 2)
        self.assertEqual(args["query"], "palco")


if __name__ == "__main__":
    unittest.main()
