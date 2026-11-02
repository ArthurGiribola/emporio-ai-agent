"""Immutable product-only presentation data; no Markdown parsing or LLM fields."""

from dataclasses import dataclass
from decimal import Decimal
import unicodedata

from app.repository import attribute_conflicts
from app.services import PricingConflictError


PAGE_SIZE = 4


@dataclass(frozen=True)
class CatalogEntry:
    position: int
    product_id: int
    name: str
    category_id: int
    category: str
    price_brl: Decimal | None
    available: bool
    stock_quantity: int | None
    issues: tuple[str, ...] = ()
    promotion_percent: Decimal | None = None
    base_price_brl: Decimal | None = None


@dataclass(frozen=True)
class CatalogView:
    entries: tuple[CatalogEntry, ...]
    total_matches: int
    truncated: bool
    synthetic: bool


def product_issues(product, *, english=False):
    issues = []
    labels = {'brand': ('Brand', 'Marca'), 'keys': ('Number of keys', 'Número de teclas'),
              'strings': ('Number of strings', 'Número de cordas')}
    for field, declared, described in attribute_conflicts(product):
        label = labels[field][0 if english else 1]
        origin = ('name' if english else 'nome') if field == 'brand' else ('specifications' if english else 'especificações')
        issues.append(f'{label}: {origin} = {declared}; ' +
                      (f'description = {described}. Confirm this detail before choosing.' if english else
                       f'descrição = {described}. Confirme esse detalhe antes de escolher.'))
    if product.status != 'active' and product.stock_quantity > 0:
        issues.append((f'Recorded status: {product.status}, despite {product.stock_quantity} units in stock; unavailable.' if english else
                       f'Situação do cadastro: {product.status}, apesar de {product.stock_quantity} unidades em estoque; indisponível.'))
    return tuple(issues)


def build_catalog_view(service, data, *, synthetic=False):
    entries = []
    for position, row in enumerate(data['products'], 1):
        product = service.get_product(row['product_id'])
        issues = product_issues(product)
        promotion_percent = None
        try:
            quote = service.get_price_quote(product.product_id)
            price = quote.final_price_brl
            if quote.discount_kind == 'promotion':
                promotion_percent = quote.discount_percent
        except PricingConflictError:
            price = None
            issues += ('Há promoções ativas concorrentes sem prioridade definida; preço não confirmado.',)
        entries.append(CatalogEntry(position, product.product_id, product.name, product.category_id,
            service.repository.categories[product.category_id].name, price, product.available,
            product.stock_quantity, issues, promotion_percent, product.price_brl))
    return CatalogView(tuple(entries), data['total_matches'], data['truncated'], synthetic)


def catalog_page(view, category_id=0, page=0, search=''):
    def folded(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    terms = folded(search).split()
    entries = tuple(e for e in view.entries if (not category_id or e.category_id == category_id)
                    and all(term in folded(e.name) for term in terms))
    pages = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    return entries[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], len(entries), page, pages
