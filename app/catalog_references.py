"""Resolve customer-visible list positions, never order/customer identities."""

import re

from app.grounding import english_question


def resolve_list_reference(question, product_ids):
    if re.search(r'\b(?:pedido|order)\b', question, re.IGNORECASE):
        return question, None
    explicit = re.sub(r'\b(produto|product)\s+(?:id|identificador)\s*#?\s*(\d{1,12})\b',
                      r'\1 \2', question, flags=re.IGNORECASE)
    if explicit != question:
        return explicit, None
    matches = list(re.finditer(r'\b(item|produto|product)\s+(\d{1,12})\b', question, re.IGNORECASE))
    if not matches:
        return question, None
    if not product_ids and all(m[1].lower() != 'item' for m in matches):
        return question, None
    if len(matches) != 1 or not product_ids or not 1 <= int(matches[0][2]) <= len(product_ids):
        message = ('Please choose a number from the latest product list, or tell me the product name.'
                   if english_question(question) else
                   'Use um número da última lista de produtos ou me diga o nome do instrumento.')
        return question, message
    match = matches[0]
    label = 'product' if match[1].lower() == 'product' else 'produto'
    product_id = product_ids[int(match[2]) - 1]
    return question[:match.start()] + f'{label} {product_id}' + question[match.end():], None
