"""Read-only catalog and deterministic, nonbinding snapshot price calculations."""

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP, localcontext

from app.models import PriceQuote, Product, Promotion
from app.repository import Repository


class PricingConflictError(ValueError):
    """Source data cannot establish one promotional price."""


def _normalize(value: str) -> str:
    folded = "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))
    aliases = {"violao": "violoes", "ukulele": "ukuleles", "guitarra": "guitarras",
               "baixo": "baixos", "bateria": "baterias", "teclado": "teclados"}
    return re.sub(r"\b\w+\b", lambda match: aliases.get(match.group(), match.group()), folded)


def _budget(value: Decimal | None) -> None:
    if value is not None and (not isinstance(value, Decimal) or not value.is_finite() or value < 0):
        raise ValueError("Budget must be a finite, nonnegative Decimal")


class CatalogService:
    def __init__(self, repository: Repository):
        self.repository = repository

    def search_products(
        self, query: str = "", *, category_id: int | None = None,
        min_price_brl: Decimal | None = None, max_price_brl: Decimal | None = None,
        available_only: bool = True,
    ) -> tuple[Product, ...]:
        """AND-match normalized terms; inclusive list-price bounds; stable price/ID sort.

        Empty results mean absent from this snapshot, not absent from the store.
        Specs are excluded from free-text matching because their semantics vary.
        """
        if not isinstance(query, str) or not isinstance(available_only, bool):
            raise ValueError("query must be text and available_only must be boolean")
        if category_id is not None and (type(category_id) is not int or category_id < 1):
            raise ValueError("category_id must be a positive integer")
        _budget(min_price_brl)
        _budget(max_price_brl)
        if min_price_brl is not None and max_price_brl is not None and min_price_brl > max_price_brl:
            raise ValueError("Minimum price exceeds maximum price")
        terms = _normalize(query).split()
        result = []
        for product in self.repository.products.values():
            if available_only and not product.available:
                continue
            if category_id is not None and product.category_id != category_id:
                continue
            if min_price_brl is not None and product.price_brl < min_price_brl:
                continue
            if max_price_brl is not None and product.price_brl > max_price_brl:
                continue
            category = self.repository.categories[product.category_id]
            haystack = _normalize(f"{product.name} {product.description} {category.name}")
            if all(term in haystack for term in terms):
                result.append(product)
        return tuple(sorted(result, key=lambda p: (p.price_brl, p.product_id)))

    def get_product(self, product_id: int) -> Product:
        if type(product_id) is not int or product_id < 1:
            raise ValueError("product_id must be a positive integer")
        return self.repository.products[product_id]

    def list_promotions(self, *, available_only: bool = True) -> tuple[Promotion, ...]:
        if not isinstance(available_only, bool):
            raise ValueError("available_only must be boolean")
        return tuple(sorted((p for p in self.repository.promotions.values()
                             if p.is_active and (not available_only or self.repository.products[p.product_id].available)),
                            key=lambda p: p.promotion_id))

    def get_price_quote(self, product_id: int, *, payment_method: str = "list") -> PriceQuote:
        """PIX gets 5% off list price only when no active promotion exists.

        Source: manual sections 3 and 6.2. No stacking, installments, shipping,
        mixed payments, reservations, or actual purchases are implemented.
        Cent rounding is ROUND_HALF_UP, an explicit implementation convention.
        """
        if payment_method not in {"list", "pix", "debit", "credit", "boleto"}:
            raise ValueError("Unsupported payment method")
        product = self.get_product(product_id)
        promotions = [p for p in self.repository.promotions.values()
                      if p.is_active and p.product_id == product_id]
        if len(promotions) > 1:
            raise PricingConflictError("Multiple active promotions; source clarification required")
        promotion = promotions[0] if promotions else None
        percent = promotion.discount_percent if promotion else Decimal("5") if payment_method == "pix" else Decimal("0")
        kind = "promotion" if promotion else "pix" if payment_method == "pix" else "none"
        with localcontext() as context:
            context.prec = 40
            final = (product.price_brl * (1 - percent / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return PriceQuote(
            product_id=product_id, base_price_brl=product.price_brl,
            final_price_brl=final, discount_percent=percent, discount_kind=kind,
            promotion_id=promotion.promotion_id if promotion else None,
            payment_method=payment_method, available=product.available,
            warnings=tuple(w for w in self.repository.warnings
                           if w.code == "unknown_freshness" or (w.source == "products.csv" and w.record_id == str(product_id))),
        )
