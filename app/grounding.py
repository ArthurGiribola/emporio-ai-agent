"""Small deterministic guards for explicit catalog requests and critical facts."""

import re
from decimal import Decimal

from app.policies import normalize
from app.services import _normalize


def wants_all(question: str) -> bool:
    text = normalize(question)
    return bool(re.search(r"\b(?:todos|todas|completa|completo|all|every|everything)\b", text)
                or (re.search(r"\btudo\b", text) and not re.match(r"^tudo\s+bem\b", text)))


def catalog_question(question: str) -> bool:
    return bool(re.search(r"\b(?:quais|existem|modelos|opcoes|disponiveis|disponivel|liste|listar|catalogo|todos|todas|all|list|available|tem|vende|estoque|baratos|barato|precos|prices|instrument\w*|viol\w*|guit\w*|ukulel\w*|baix\w*)\b", normalize(question)))


def requested_budget(question: str) -> Decimal | None:
    match = re.search(r"(?:ate|no maximo|up to|under)\s*(?:r\$\s*)?(\d[\d.,]*)", normalize(question))
    if match:
        number = match.group(1).rstrip(".,")
        if "," in number:
            number = number.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", number):
            number = number.replace(".", "")
        if re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", number):
            return Decimal(number)
        return None
    text = normalize(question)
    words = re.search(r"(?:ate|no maximo|up to|under)\s+((?:zero|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem|cento|duzentos|duzentas|trezentos|trezentas|quatrocentos|quatrocentas|quinhentos|quinhentas|seiscentos|seiscentas|setecentos|setecentas|oitocentos|oitocentas|novecentos|novecentas|mil)(?:\s+e\s+(?:zero|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quatorze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cento|duzentos|duzentas|trezentos|trezentas|quatrocentos|quatrocentas|quinhentos|quinhentas|seiscentos|seiscentas|setecentos|setecentas|oitocentos|oitocentas|novecentos|novecentas))*)(?:\s+reais?)?\b", text)
    if not words:
        return None
    values = {'zero':0,'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'quatro':4,'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,
              'dez':10,'onze':11,'doze':12,'treze':13,'quatorze':14,'catorze':14,'quinze':15,'dezesseis':16,'dezessete':17,'dezoito':18,'dezenove':19,
              'vinte':20,'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,'setenta':70,'oitenta':80,'noventa':90,
              'cem':100,'cento':100,'duzentos':200,'duzentas':200,'trezentos':300,'trezentas':300,'quatrocentos':400,'quatrocentas':400,
              'quinhentos':500,'quinhentas':500,'seiscentos':600,'seiscentas':600,'setecentos':700,'setecentas':700,
              'oitocentos':800,'oitocentas':800,'novecentos':900,'novecentas':900}
    total = current = 0
    for word in words.group(1).split():
        if word == 'e':
            continue
        if word == 'mil':
            total += max(current, 1) * 1000
            current = 0
        else:
            current += values[word]
    amount = total + current
    return Decimal(amount) if 0 < amount < 10**12 else None


def catalog_arguments(question: str, arguments: dict, catalog) -> dict:
    """Explicit customer category/budget beat hallucinated model arguments.

    For exhaustive lists, discard invented query qualifiers while retaining
    qualifiers literally present in the request. This is not a general NL parser.
    """
    # Never let model-inferred values silently add or retain filters. The customer
    # question is the only source of query, category, budget, and availability scope.
    result = {}
    text = normalize(question)
    include_unavailable = bool(re.search(r'\b(?:indisponiveis|inativos|unavailable|inactive)\b|sem estoque|out of stock', text))
    result['available_only'] = not include_unavailable
    categories = catalog.category_ids_from_text(question)
    if len(categories) == 1:
        result["category_id"] = next(iter(categories))
    budget = requested_budget(question)
    if budget is not None:
        result["max_price_brl"] = str(budget)
    result["all_results"] = wants_all(question)
    if result["all_results"] or re.search(r"\b(?:efetiv|final|desconto|effective|discount|promoc|pix|preco|custa|quanto|price|cost)\b", text):
        result["sort_by"] = "effective_price"
    # Build the search phrase from user-provided qualifiers only; never trust a
    # model's guessed category, currency, pagination, or stale search query.
    ignored = set((
        "quais qual que produto produtos instrumento instrumentos modelo modelos opcoes existem liste listar lista catalogo todos todas completo completa"
        " disponivel disponiveis disponivel tem temos vende vendem estoque barato baratos barata baratas caro caros mais menos ao"
        " estao esta primeiro primeiros primeira primeiras ultimo ultimos do da de dos das um uma uns umas o a os as me mostra mostre ver"
        " por ate no maximo reais real r com ate todos tudo incluindo pf favor please all every available product products"
        " quanto custa cost costs preco precos price prices valor values quanto custa aceita aceitam aceita bem comparar compare comparison differences difference diferenca"
        " quero queria queremos gostariamos estou estamos pensando considerando escolhendo ainda levar separar choose choosing looking help me can you please"
        " stock stocks inventory in stock do you does it"
        " demonstration synthetic only filtered intent tokens original text withheld"
        " instrument instruments models options list show catalog full complete cheapest cheapest first lowest highest price sorted price prices preco precos valor final"
        " tiver tenham tenha haja"
        " in stock out of stock unavailable inactive indisponiveis indisponivel inativos inativo sem estoque and or to from the a an de do da dos das e ou no na nos nas"
        ""
        " zero dez vinte trinta quarenta cinquenta sessenta setenta oitenta noventa cem cento duzentos duzentas"
        " trezentos trezentas quatrocentos quatrocentas quinhentos quinhentas seiscentos seiscentas setecentos"
        " setecentas oitocentos oitocentas novecentos novecentas mil"
    ).split())
    category_words = set()
    for category_id in categories:
        category_words.update(re.findall(r"\w+", _normalize(catalog.repository.categories[category_id].name)))
    terms = [term for term in re.findall(r"\w+", _normalize(question))
             if term not in ignored and term not in category_words
             and not re.fullmatch(r"\d+(?:[.,]\d+)?", term)]
    # Common English material terms map to the Portuguese catalog labels.
    terms = ['aco' if term in {'steel', 'steelstring'} else term for term in terms]
    result["query"] = " ".join(terms)
    return result


def brl(value) -> str:
    formatted = f"{Decimal(value):,.2f}"
    return "R$ " + formatted.translate(str.maketrans({",": ".", ".": ","}))


def render_catalog(data: dict, categories, *, english: bool = False, synthetic: bool = False) -> str:
    products = data["products"]
    total = data["total_matches"]
    returned = len(products)
    filters = data["filters"]
    names = [categories[i].name for i in filters["category_ids"] if i in categories]
    label = ", ".join(names).lower() if names else "instrumentos"
    budget = filters["max_price_brl"]
    if english:
        return _render_english_catalog(data, categories, synthetic=synthetic)
    catalog = "catálogo de demonstração" if synthetic else "catálogo"
    qualifier = " até " + brl(budget) if budget is not None else ""
    availability = " disponíveis" if filters.get('available_only', True) else ""
    if data.get("catalog_state") == "empty_dataset":
        return f"O {catalog} está vazio no momento; não há produtos para consultar."
    if not total:
        return f"Não encontrei {label}{availability}{qualifier} no {catalog}."
    if data["truncated"]:
        heading = f"Encontrei {total} opções de {label}{qualifier} no {catalog}. Aqui estão {returned} de {total}, do mais barato ao mais caro (lista parcial):"
    else:
        heading = f"Encontrei {total} opções de {label}{availability}{qualifier} no {catalog}. Esta é a lista completa, do mais barato ao mais caro:"
    lines = [heading, ""]
    for index, product in enumerate(products, 1):
        unavailable = ' · Indisponível' if not product['available'] else ''
        lines.append(f"{index}. {product['name']} — {brl(product.get('effective_price_brl', product['list_price_brl']))}{unavailable}")
    lines.append("")
    for product in products:
        lines.extend(f"{product['name']}: {issue}" for issue in product.get('issues', ()))
    if data["truncated"]:
        lines.append("Há outros resultados. Esta lista não inclui todos; peça todos os modelos para ampliar a consulta.")
    if data.get("sort_order") == "effective_price_ascending":
        lines.append("Os preços incluem as promoções ativas, sem desconto extra de PIX.")
        if budget is not None:
            lines.append("O limite de orçamento considera o preço de tabela, antes dos descontos.")
    return "\n".join(lines)


def english_question(question: str) -> bool:
    """Small display-language hint; source product names remain unchanged."""
    return bool(re.search(r"\b(?:please|list|show|available|which|what|english|products|instruments|order|tracking|recorded|refund|return|can|how|does|the)\b", normalize(question)))


def _render_english_catalog(data: dict, categories, *, synthetic: bool = False) -> str:
    products, total = data["products"], data["total_matches"]
    filters = data["filters"]
    labels = {"violoes": "acoustic guitars", "guitarras": "electric guitars", "baixos": "basses", "ukuleles": "ukuleles"}
    label = ", ".join(labels.get(_normalize(categories[i].name), categories[i].name)
                      for i in filters["category_ids"] if i in categories) or "instruments"
    budget = filters["max_price_brl"]
    qualifier = f" up to R$ {Decimal(budget):,.2f}" if budget is not None else ""
    catalog = "demonstration catalog" if synthetic else "catalog"
    availability = 'available ' if filters.get('available_only', True) else ''
    if data.get("catalog_state") == "empty_dataset":
        return f"The {catalog} is empty at the moment; there are no products to browse."
    if not total:
        return f"I couldn't find any {availability}{label}{qualifier} in our {catalog}."
    if data["truncated"]:
        heading = f"I found {total} matching {label}{qualifier} in our {catalog}. Here are {len(products)} of {total}, lowest price first (partial list):"
    else:
        heading = f"I found {total} {availability}{label}{qualifier} in our {catalog}. Here's the complete list, lowest price first:"
    lines = [heading, ""]
    lines += [f"{i}. {p['name']} — R$ {Decimal(p.get('effective_price_brl', p['list_price_brl'])):,.2f}" + (' · Unavailable' if not p['available'] else '') for i, p in enumerate(products, 1)]
    lines.append("")
    for product in products:
        lines.extend(f"{product['name']}: {issue}" for issue in product.get('issues', ()))
    if data["truncated"]:
        lines.append("More matches exist; this is not the complete result set. Request all models to expand the search.")
    if data.get("sort_order") == "effective_price_ascending":
        lines.append("Prices include active promotions, without an additional PIX discount.")
        if budget is not None:
            lines.append("The budget limit applies to list prices, before discounts.")
    return "\n".join(lines)


def requested_order_id(question: str) -> int | None:
    matches = {int(n) for n in re.findall(r"\b(?:order|pedido)\s*(?:number\s*|numero\s*|#\s*)?(\d{1,12})\b", normalize(question))}
    return next(iter(matches)) if len(matches) == 1 else None


def order_record_followup(question: str) -> bool:
    text = normalize(question)
    return (requested_order_id(question) is None and not re.search(r"\b(?:product|produto|customer|cliente|identity|identidade|catalog|price)\b", text)
            and bool(re.search(r"record|this order|that order|registro|esse pedido", text))
            and bool(re.search(r"tracking|delivery|status|total|rastre|entrega", text)))


def render_quote(data: dict, name: str, *, english: bool, synthetic: bool = False, issues=()) -> str:
    money = (lambda value: f"R$ {Decimal(value):,.2f}") if english else brl
    if english:
        context = " in our demonstration catalog" if synthetic else ""
        lines = [f"**{name} costs {money(data['final_price_brl'])}**{context}.", ""]
        if data["discount_kind"] == "promotion":
            lines.append(f"That includes the {data['discount_percent']}% promotion, down from {money(data['base_price_brl'])}.")
            if data["payment_method"] == "pix":
                lines.append("You can pay by PIX, but no additional PIX discount applies on top of this promotion.")
        elif data["discount_kind"] == "pix":
            lines.append(f"That includes the {data['discount_percent']}% PIX discount, down from {money(data['base_price_brl'])}.")
        if not data["available"]:
            lines.append("The product is recorded as unavailable; this is an informational quote only.")
    else:
        context = " no nosso catálogo de demonstração" if synthetic else ""
        lines = [f"**{name} sai por {money(data['final_price_brl'])}**{context}.", ""]
        if data["discount_kind"] == "promotion":
            lines.append(f"O valor já inclui a promoção de {data['discount_percent']}%, sobre o preço de {money(data['base_price_brl'])}.")
            if data["payment_method"] == "pix":
                lines.append("Você pode pagar por PIX, mas o desconto de PIX não se soma a essa promoção.")
        elif data["discount_kind"] == "pix":
            lines.append(f"O valor inclui {data['discount_percent']}% de desconto no PIX, sobre o preço de {money(data['base_price_brl'])}.")
        if not data["available"]:
            lines.append("O produto consta como indisponível; o valor é apenas informativo.")
    if issues:
        lines.extend(['', *issues])
    return "\n".join(lines)


def render_order(data: dict, *, english: bool, synthetic: bool = False) -> str:
    if data["status"] != "available":
        return "Order information is unavailable for this session." if english else "As informações do pedido não estão disponíveis para esta sessão."
    order = data["order"]
    if english:
        label = "Demonstration order" if synthetic else "Order"
        lines = [f"{label} #{order['order_id']} is recorded as **{order['status']}**, with a total of **R$ {Decimal(order['total_brl']):,.2f}**.", ""]
        for label, key in [("Tracking code", "tracking_code"), ("Estimated delivery date", "estimated_delivery"), ("Actual delivery date", "actual_delivery")]:
            lines.append(f"- {label}: {order[key] if order[key] is not None else 'not recorded'}.")
        lines.append("")
        if "historical_total_difference" in order["warnings"]:
            lines.append("The original order total is preserved, even if today's catalog prices differ.")
        if "historical_unit_prices_unavailable" in order["warnings"]:
            lines.append("The price paid for each item is not recorded.")
        lines += ["", "These are the recorded order details; I haven't made any changes to the order."]
    else:
        statuses = {"confirmed": "confirmado", "pending": "pendente", "shipped": "enviado", "delivered": "entregue", "cancelled": "cancelado"}
        label = "O pedido de demonstração" if synthetic else "O pedido"
        lines = [f"{label} #{order['order_id']} está registrado como **{statuses[order['status']]}**, com total de **{brl(order['total_brl'])}**.", ""]
        for label, key in [("Código de rastreamento", "tracking_code"), ("Previsão de entrega", "estimated_delivery"), ("Data efetiva de entrega", "actual_delivery")]:
            missing = 'não informado' if key == 'tracking_code' else 'não informada'
            lines.append(f"- {label}: {order[key] if order[key] is not None else missing}.")
        lines.append("")
        if "historical_total_difference" in order["warnings"]:
            lines.append("O total original do pedido foi mantido, mesmo que os preços atuais do catálogo sejam diferentes.")
        if "historical_unit_prices_unavailable" in order["warnings"]:
            lines.append("O preço pago por cada item não está informado.")
        lines += ["", "Essas são as informações registradas do pedido; não fiz nenhuma alteração nele."]
    items = order.get('items', [])
    item_lines = [('Recorded products:' if english else 'Produtos registrados:')]
    item_lines.extend(f"- {item['quantity']}× {item['product_name']}" for item in items)
    if not items:
        item_lines.append('Products are not recorded.' if english else 'Os produtos não estão informados no registro.')
    if order.get('items_truncated'):
        item_lines.append('This is a partial item list.' if english else 'Esta é uma lista parcial de produtos.')
    lines[2:2] = item_lines + ['']
    return "\n".join(lines)


def requested_product_id(question: str) -> int | None:
    matches = set(requested_product_ids(question))
    return next(iter(matches)) if len(matches) == 1 else None


def requested_product_ids(question: str) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(n) for n in re.findall(
        r'\b(?:product|produto)\s+(?:(?:id|identificador|synthetic|sintetico)\s+)?#?(\d{1,12})\b', normalize(question))))
