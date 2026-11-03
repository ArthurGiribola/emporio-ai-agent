"""Resolve display positions before tools; quantities are never product IDs."""

import re
from app.grounding import english_question
from app.policies import normalize


def resolve_list_reference(question, product_ids):
    if re.search(r'\b(?:pedido|order)\b', question, re.IGNORECASE):
        return question, None
    plural = r'\b(?:itens|produtos|items|products)\s+(\d{1,12}(?:\s*(?:,|e\b|and\b|&)\s*\d{1,12})*)\b'
    singular = r'\b(item|produto|product)\s+(\d{1,12})\b'
    positions = [int(m[2]) for m in re.finditer(singular, question, re.IGNORECASE)]
    positions += [int(n) for m in re.finditer(plural, question, re.IGNORECASE) for n in re.findall(r'\d+', m[1])]
    ordinal_map = {'primeiro': 1, 'primeira': 1, 'segundo': 2, 'segunda': 2,
                   'terceiro': 3, 'terceira': 3, 'quarto': 4, 'quarta': 4,
                   'first': 1, 'second': 2, 'third': 3, 'fourth': 4}
    ordinal_matches = list(re.finditer(r'\b(?:o|a|the)\s+(primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|first|second|third|fourth)(?:\s+(?:item|produto|product|one))?\b', question, re.IGNORECASE))
    has_catalog_action = bool(re.search(
        r'\b(?:item|items|produto|produtos|product|products|instrumento|instrumentos|instrument|instruments|'
        r'estoque|stock|disponivel|available|preco|price|custa|cost|comparar|compare)\b', normalize(question), re.IGNORECASE))
    if not positions and has_catalog_action and len(ordinal_matches) == 1:
        positions = [ordinal_map[ordinal_matches[0][1].casefold()]]
        question = question[:ordinal_matches[0].start()] + ('item ' if not english_question(question) else 'item ') + str(positions[0]) + question[ordinal_matches[0].end():]
    if not positions:
        return question, None  # Explicit "product ID N" and fixture labels remain explicit IDs.
    if not product_ids or any(not 1 <= n <= len(product_ids) for n in positions):
        return question, ('Please choose an item from the latest catalog list, or tell me its name. A list number is not a database ID.'
            if english_question(question) else 'Me diga o nome do instrumento ou escolha um item da última lista do catálogo. O número da lista não é o identificador do cadastro.')
    def one(position):
        label = 'product' if english_question(question) else 'produto'
        return f'{label} ID {product_ids[int(position)-1]}'
    resolved = re.sub(plural, lambda m: ', '.join(one(n) for n in re.findall(r'\d+', m[1])), question, flags=re.IGNORECASE)
    return re.sub(singular, lambda m: one(m[2]), resolved, flags=re.IGNORECASE), None
