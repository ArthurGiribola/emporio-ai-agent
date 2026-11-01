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
            words = set(re.findall(r"\w+", _normalize(question)))
            query = result.get("query", "")
            if isinstance(query, str):
                result["query"] = " ".join(term for term in _normalize(query).split() if term in words)
    return result


def brl(value) -> str:
    formatted = f"{Decimal(value):,.2f}"
    return "R$ " + formatted.translate(str.maketrans({",": ".", ".": ","}))


def render_catalog(data: dict, categories) -> str:
    products = data["products"]
    total = data["total_matches"]
    returned = len(products)
    filters = data["filters"]
    names = [categories[i].name for i in filters["category_ids"] if i in categories]
    label = ", ".join(names).lower() if names else "instrumentos"
    budget = filters["max_price_brl"]
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
