"""Small evidence/memory helpers, not a separate model or general-purpose router."""

import copy
import re
from app.policies import normalize


def memory_exchange(messages):
    """Retain valid call/result pairs while compacting exhaustive catalog evidence."""
    exchange = copy.deepcopy(messages)
    large_catalog = False
    for message in exchange:
        if message.get('role') == 'tool' and message.get('name') == 'search_products':
            data = message.get('result', {}).get('data', {})
            products = data.get('products', [])
            if len(products) > 5:
                large_catalog = True
                data.update(products=products[:5], returned_count=5, truncated=True,
                            memory_excerpt=True)
    if large_catalog and exchange[-1].get('role') == 'assistant':
        native = exchange[-1]['native']
        text = 'Catalog results were displayed in full outside model memory. This memory excerpt is partial. Use fresh tools for product facts; list references are resolved by Python.'
        if native.get('role') == 'model':
            native['parts'] = [{'text': text}]
        else:
            native['content'] = text
    return exchange


def assistant_text(message):
    native = message.get('native', {})
    return native.get('content', '') or ''.join(p.get('text', '') for p in native.get('parts', []))


def conversation_question(question):
    t = normalize(question)
    return (not re.search(r'\b(code|codigo|program|write|escreva|script|algorithm)\w*\b', t)
            and bool(re.search(r'conversa|historico|\bchat\b|conversation|history', t))
            and bool(re.search(r'apag|limp|sum|resto|lembr|esque|delete|clear|forget|remember|where', t)))


def purchase_interest(question):
    t = normalize(question)
    return bool(re.search(r'\b(?:comprar|adquirir|buy|purchase)\b', t) or
                (re.search(r'\b\d+\s+(?:unidades?|units?)\b', t)
                 and re.search(r'\b(?:quero|gostaria|agora|mude|troque|desejo|want|change|make)\b', t)))


def explanation_followup(question):
    t = normalize(question)
    return bool(re.search(r'\b(?:por\s*que|porque|why|explain|explique|nao encontr|not found|restantes|remaining|outro produto|other product|vi .*lista)\b', t))


def product_followup(question):
    """Only pronouns/elliptical questions inherit a selection, never a new name."""
    t = normalize(question)
    if re.search(r'\b(?:ele|ela|dele|dela|esse|este|isso|it|its|that|this|ambos|both)\b|\bos dois\b', t):
        return True
    words = set(re.findall(r'\w+', t))
    return bool(words) and words <= set(('qual e o a preco valor quanto custa estoque tem esta disponivel '
        'no pix pagando com desconto price cost stock available availability and what is the how much '
        'does in on by using payment inclui promocao na promocional pagar se for de do da unitario').split())


def failure_followup(question):
    t = normalize(question)
    words = set(re.findall(r'\w+', t))
    return bool(re.match(r'^(?:por\s*que|porque|why)\b', t) and words and words <= set(
        ('por que porque voce nao conseguiu encontrar encontrou isso aconteceu consulta falhou falha '
         'erro resposta why could not you did find found lookup failed error happened this the answer '
         'was it wrong missing').split()))


def policy_followup(question):
    t = normalize(question)
    return (len(t.split()) <= 12 and not re.search(r'\d|garantia|devolucao|refund|return|warranty|online', t)
            and bool(re.search(r'^(?:por\s*que|porque|why)\W*$|\b(?:fonte|sources?|secao|section|pagina|page|referencia)\b', t)))


def failure_message(reason, english=False):
    reasons = {
      'timeout': ('The local model timed out. Try again; your conversation was kept.', 'O modelo local demorou além do limite. Tente novamente; sua conversa foi mantida.'),
      'connection_error': ('I could not connect to Ollama. Check that it is running, then retry; your conversation was kept.', 'Não consegui conectar ao Ollama. Verifique se ele está em execução e tente novamente; sua conversa foi mantida.'),
      'invalid_json': ('The local model returned an unreadable response. Please retry this question.', 'O modelo local retornou uma resposta que não consegui interpretar. Tente enviar esta pergunta novamente.'),
      'invalid_tool_calls': ('The model sent an invalid lookup request. Tell me the instrument name or catalog item.', 'O modelo enviou uma consulta inválida. Me diga o nome do instrumento ou o item do catálogo para tentar novamente.'),
      'invalid_arguments': ('The lookup failed because its arguments were invalid; no facts were confirmed. Specify the product or order reference.', 'A consulta falhou porque os dados enviados eram inválidos; nenhuma informação foi confirmada. Informe o instrumento ou a referência do pedido.'),
      'product_not_found': ('The requested product identifier was not found by the catalog service. Check its name or catalog item.', 'O identificador consultado não foi encontrado no catálogo. Confira o nome do instrumento ou o item da lista.'),
      'ambiguous_product_reference': ('I could not safely identify that product. Choose a catalog item or give its name.', 'Não consegui identificar esse produto com segurança. Escolha um item do catálogo ou me diga o nome.'),
      'tool_failure': ('The lookup failed; I cannot confirm the requested information. Please retry.', 'A consulta falhou; não posso confirmar a informação solicitada. Tente novamente.'),
      'pricing_conflict': ('The recorded promotions conflict, so I cannot confirm this price. Customer service must clarify it.', 'Há promoções conflitantes no cadastro, então não posso confirmar este preço. O atendimento precisa esclarecer qual promoção se aplica.'),
      'result_too_large': ('The lookup returned too much information. Ask about one instrument or topic; no facts were confirmed.', 'A consulta retornou informação demais. Pergunte sobre um instrumento ou assunto por vez; os dados não foram confirmados.'),
      'internal_error': ('A processing failure prevented this lookup. Please retry; your conversation was kept.', 'Uma falha de processamento impediu esta consulta. Tente novamente; sua conversa foi mantida.'),
      'output_limit': ('The local model returned an incomplete answer. Try a more specific question; the conversation was kept.', 'O modelo local retornou uma resposta incompleta. Tente uma pergunta mais específica; a conversa foi mantida.'),
      'context_limit': ('This request exceeds the model context limit. Ask about one instrument or topic; your visible conversation was kept.', 'Esta consulta excede o contexto do modelo. Pergunte sobre um instrumento ou assunto por vez; o histórico visível foi mantido.'),
      'limit_reached': ('The model could not finish within its lookup limit. Specify the instrument or question; no action was taken.', 'O modelo não concluiu a consulta dentro do limite de tentativas. Indique o instrumento ou a dúvida; nenhuma ação foi realizada.'),
      'unverified': ('I could not verify the requested facts. Tell me the instrument name or catalog item so I can check it.', 'Não consegui confirmar os dados solicitados. Me diga o nome do instrumento ou o item do catálogo para consultar novamente.'),
    }
    pair = reasons.get(reason, ('The local model could not complete this turn. Please retry; your conversation was kept.', 'O modelo local não conseguiu concluir esta resposta. Tente novamente; sua conversa foi mantida.'))
    return pair[0 if english else 1]
