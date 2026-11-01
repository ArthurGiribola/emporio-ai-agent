"""Small deterministic guards for explicit catalog requests and critical facts."""

import re
from decimal import Decimal

from app.policies import normalize
from app.services import _normalize


def wants_all(question: str) -> bool:
    return bool(re.search(r"\b(?:todos|todas|completa|completo|all|every)\b", normalize(question)))


def catalog_question(question: str) -> bool:
    return bool(re.search(r"\b(?:quais|existem|modelos|opcoes|disponiveis|liste|listar|catalogo|todos|todas|all|list|available)\b", normalize(question)))


def requested_budget(question: str) -> Decimal | None:
    match = re.search(r"(?:ate|no maximo|up to|under)\s*(?:r\$\s*)?(\d[\d.,]*)", normalize(question))
    if not match:
        return None
    number = match.group(1).rstrip(".,")
    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", number):
        number = number.replace(".", "")
    if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", number):
        return None
    return Decimal(number)


def catalog_arguments(question: str, arguments: dict, catalog) -> dict:
    """Explicit customer category/budget beat hallucinated model arguments.

    For exhaustive lists, discard invented query qualifiers while retaining
    qualifiers literally present in the request. This is not a general NL parser.
    """
    result = dict(arguments)
    categories = catalog.category_ids_from_text(question)
    if len(categories) == 1:
        result["category_id"] = next(iter(categories))
    if catalog_question(question):
        budget = requested_budget(question)
        if budget is not None:
            result["max_price_brl"] = str(budget)
        if wants_all(question):
            result["all_results"] = True
            broad_scope = re.search(r"\ball (?:available )?(?:products|instruments)\b|\btodos (?:os )?(?:produtos|instrumentos)\b", normalize(question))
            if broad_scope and budget is None:
                result.pop("max_price_brl", None)
            if broad_scope and not categories:
                result.pop("category_id", None)
            words = set(re.findall(r"\w+", _normalize(question)))
            query = result.get("query", "")
            if isinstance(query, str):
                result["query"] = " ".join(term for term in _normalize(query).split() if term in words and term not in {
                    "all", "every", "available", "products", "instruments", "models", "todos", "todas", "disponiveis", "produtos", "instrumentos", "modelos"})
    return result


def brl(value) -> str:
    formatted = f"{Decimal(value):,.2f}"
    return "R$ " + formatted.translate(str.maketrans({",": ".", ".": ","}))


def render_catalog(data: dict, categories, *, english: bool = False) -> str:
    products = data["products"]
    total = data["total_matches"]
    returned = len(products)
    filters = data["filters"]
    names = [categories[i].name for i in filters["category_ids"] if i in categories]
    label = ", ".join(names).lower() if names else "instrumentos"
    budget = filters["max_price_brl"]
    if english:
        return _render_english_catalog(data, categories)
    qualifier = " até " + brl(budget) if budget is not None else ""
    if not total:
        return f"Não encontrei {label} disponíveis{qualifier} nos arquivos fornecidos."
    if data["truncated"]:
        heading = f"Mostrando {returned} de {total} resultados de {label}{qualifier}: lista parcial, do menor para o maior preço."
    else:
        heading = f"Lista completa dos {total} resultados de {label} disponíveis{qualifier} nos arquivos fornecidos, do menor para o maior preço:"
    lines = [heading, ""]
    for index, product in enumerate(products, 1):
        lines.append(f"{index}. {product['name']} — {brl(product['list_price_brl'])}")
    if any(p["warnings"] for p in products):
        lines.append("Alguns modelos têm informações divergentes no cadastro; confirme esses detalhes com o atendimento.")
    if data["truncated"]:
        lines.append("Há outros resultados. Esta lista não inclui todos; peça todos os modelos para ampliar a consulta.")
    lines.append("Preços e disponibilidade são do catálogo fornecido; não representam uma confirmação em tempo real.")
    return "\n".join(lines)


def english_question(question: str) -> bool:
    """Small display-language hint; source product names remain unchanged."""
    return bool(re.search(r"\b(?:please|list|show|available|which|what|english|products|instruments)\b", normalize(question)))


def _render_english_catalog(data: dict, categories) -> str:
    products, total = data["products"], data["total_matches"]
    filters = data["filters"]
    labels = {"violoes": "acoustic guitars", "guitarras": "electric guitars", "baixos": "basses", "ukuleles": "ukuleles"}
    label = ", ".join(labels.get(_normalize(categories[i].name), categories[i].name)
                      for i in filters["category_ids"] if i in categories) or "instruments"
    budget = filters["max_price_brl"]
    qualifier = f" up to R$ {Decimal(budget):,.2f}" if budget is not None else ""
    if not total:
        return f"No available {label}{qualifier} matched the supplied snapshot."
    if data["truncated"]:
        heading = f"Showing {len(products)} of {total} matching {label}{qualifier}: a partial list, lowest price first."
    else:
        heading = f"Complete list of {total} matching available {label}{qualifier} in the supplied snapshot, lowest price first:"
    lines = [heading, ""]
    lines += [f"{i}. {p['name']} — R$ {Decimal(p['list_price_brl']):,.2f}" for i, p in enumerate(products, 1)]
    if any(p["warnings"] for p in products):
        lines.append("Some product attributes conflict in the source; confirm those details with customer service.")
    if data["truncated"]:
        lines.append("More matches exist; this is not the complete result set. Request all models to expand the search.")
    lines.append("Prices and availability are snapshot records, not real-time confirmation.")
    return "\n".join(lines)
