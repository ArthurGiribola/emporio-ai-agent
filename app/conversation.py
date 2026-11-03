"""Small evidence/memory helpers, not a separate model or general-purpose router."""

import copy
import re
from app.policies import normalize
from app.return_policy import NUMERALS


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


def conversational_intent(question):
    """Recognize ordinary rapport and exploratory help that need no tool facts."""
    t = normalize(question)
    if re.fullmatch(r'(?:oi(?:e+)?|ola|hello|hi|hey|e ai|bom dia|boa tarde|boa noite|beleza)(?:[,!? ]+(?:tudo bem|tudo certo|como vai|beleza))?[.!?, ]*', t):
        return 'greeting'
    if re.search(r'\b(?:em que (?:voce|posso) (?:me )?ajudar|que tipo de ajuda|como podem me ajudar|'
                 r'o que (?:voce|voces|a loja) (?:pode|podem|faz|fazem|atende|atendem)|'
                 r'cheguei agora|primeira vez (?:aqui|por aqui)|como (?:voces|voce) podem me dar uma forca|'
                 r'o que da pra (?:fazer|resolver) por aqui|no que (?:voces|voce) (?:ajudam|ajuda)|'
                 r'what can you help|how can you help|what help can i get|'
                 r'como funciona (?:esse|o) (?:atendimento|chat)|how does (?:this|your) service work|'
                 r'sou novo|sou nova|acabei de chegar|new here|first time here)\b', t):
        return 'capabilities'
    objective = re.search(r'\b(?:preco|valor|custa|quanto|estoque|stock|disponivel|available|pix|'
                          r'promoc\w*|desconto|politic\w*|garanti\w*|devol\w*|reembols\w*|pedido|order)\b'
                          r'|\b(?:produto|product|item)\s*(?:id\s*)?\d+\b', t)
    beginner = re.search(r'\b(?:nunca (?:toquei|toque|encostei)|never played|beginner|iniciante|'
                         r'nao entendo nada de musica|nao entendo de instrumentos|nao manjo nada|'
                         r'leig\w*|sou zero|zero a esquerda|primeiro instrumento|'
                         r'(?:pra|para|for) quem.{0,25}(?:aprend\w*|comec\w*|iniciante|beginner)|'
                         r'(?:comec|aprend\w*|experienc\w*).{0,30}(?:zero|nada)|do zero)\b', t)
    if beginner and not objective:
        return 'exploration'
    open_advice = (re.search(r'\b(?:me ajudar a escolher|ajuda(?:r)? (?:a|pra|para) escolher|'
                             r'me ajuda(?:r)? a decidir|me orientar|combina comigo|'
                             r'o que seria bom pra mim|qual seria ideal pra mim|'
                             r'help me choose|what suits me|what would suit me)\b', t)
                   and not objective)
    if open_advice:
        return 'exploration'
    if re.search(r'\b(?:nao (?:encontrei|achei|localizei)|cant find|could not find)\b.*\b(?:produto|instrumento|product|instrument|item)\b', t):
        return 'product_search_help'
    if (re.search(r'\b(?:nao foi isso|nao era isso|nao entendeu|nao respondeu|'
                 r'nao resolveu|nao ficou claro|nao entendi|pegou outra coisa|'
                 r'fiquei na duvida|ainda estou na duvida|pode explicar melhor|'
                 r'that is not what|you misunderstood|that did not answer|can you clarify|'
                 r'explic\w* de outro jeito)\b', t)
            and not re.search(r'\b(?:viol\w*|instrument\w*|guit\w*|ukulel\w*|baix\w*|aco|nylon|preco|estoque|pedido|garantia|devolucao|pix|produto\s+id)\b', t)):
        return 'repair'
    if re.fullmatch(r'(?:valeu|obrigado|obrigada|muito obrigado|muito obrigada|thanks|thank you|cheers)'
                    r'(?:[, ]+(?:era isso mesmo|era so|por enquanto|that is all|that was all|thats it|for now))?[.! ]*', t):
        return 'gratitude'
    return None


def exploration_response(question, *, english=False):
    """Short general guidance for beginner/discovery intent, with no store claims."""
    t = normalize(question)
    if re.search(r'\bnylon\b', t) and re.search(r'\b(?:aco|steel)\b', t):
        return ("Nylon costuma ter um toque mais suave; aço costuma ter som mais brilhante e maior tensão. Nenhum é melhor para todo mundo: pense no estilo que você quer tocar e no conforto ao experimentar." if not english else
                "Nylon strings often feel softer, while steel strings often sound brighter and have more tension. Neither is best for everyone; consider the music you want to play and what feels comfortable.")
    if re.search(r'\b(?:combina comigo|me ajuda(?:r)? a decidir|me orientar|'
                 r'o que seria bom pra mim|qual seria ideal pra mim|help me choose|what suits me|what would suit me)\b', t):
        return ("Claro. Para sugerir algo que combine com você, ajuda saber o estilo de música que gosta, seu orçamento e se pretende tocar sozinho ou em grupo. Qual estilo você curte?" if not english else
                "Sure. To suggest something that fits, it helps to know the music you enjoy, your budget, and whether you plan to play alone or with others. What style do you like?")
    if re.search(r'\b(?:nao manjo nada|tem problema|leig\w*|sou zero|zero a esquerda|'
                 r'primeiro instrumento|no experience|beginner)\b', t):
        return ("Não tem problema começar do zero. Pense no som que você gosta, no conforto e no orçamento; posso comparar opções reais do catálogo quando você quiser. Que estilo de música você curte?" if not english else
                "Starting from zero is completely fine. Think about the sound you like, comfort, and budget; I can compare actual catalog options when you are ready. What kind of music do you enjoy?")
    return ("Começar do zero é normal. A escolha depende do som que você gosta, do conforto e do orçamento; posso comparar opções reais do catálogo. Você prefere explorar instrumentos de cordas, teclas ou outro tipo?" if not english else
            "Starting from zero is normal. Your choice depends on the sound you like, comfort, and budget; I can compare real catalog options. Would you like to explore strings, keyboards, or another kind of instrument?")


def simplify_request(question):
    """Identify a request to restate the immediately discussed point more simply."""
    t = normalize(question)
    return bool(re.search(r'\b(?:explica|explique|fala|fale|diz|diga|resume|resuma|simplifica|simplifique)\b'
                          r'.{0,50}\b(?:simples|facil|claro|sem complic|sem termo|sem palavra|'
                          r'pra leigo|para leigo|de um jeito|in plain|simple terms|plain english)\b', t)
                or re.search(r'\b(?:eli5|em palavras simples|em termos simples|mais simples por favor)\b', t))


def purchase_interest(question):
    t = normalize(question)
    explicit_action = re.search(r'\b(?:comprar|compro|compraria|adquirir|adquiro|separ\w*|pegar|pego|buy|purchase)\b', t)
    explicit_take = re.search(r'\b(?:quero|queria|gostaria|pretendo|vou|want|would like|plan to)\s+(?:levar|pegar|take)\b', t)
    return bool(explicit_action or explicit_take or
                re.search(r'\b(?:pensando|considerando|looking|planning)\b.*\b(?:viol|instrument|product|guit|music)\w*', t) or
                (re.search(r'\b(?:namorando a ideia|thinking about|considerando a ideia)\b', t)
                 and re.search(r'\b(?:viol\w*|instrument\w*|product|guit\w*|music)\b', t)) or
                (re.search(r'\b\d+\s+(?:unidades?|units?)\b', t)
                 and re.search(r'\b(?:quero|gostaria|agora|mude|troque|desejo|want|change|make)\b', t)))


def requested_quantity(question):
    """Extract an explicitly requested count without mistaking item numbers for quantity."""
    text = normalize(question)
    purchase_quantity = re.search(
        r'\b(?:comprar|compro|compraria|adquirir|buy|purchase)\s+'
        r'(\d{1,6}|zero|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\b', text)
    if purchase_quantity:
        value = purchase_quantity[1]
        return int(value) if value.isdigit() else int({**NUMERALS, "uma": "1", "duas": "2"}[value])
    match = re.search(
        r'\b(\d{1,6})\s+(?:(?:unidades?|units?|pecas?)\b|(?:desse|dessa|deste|desta|do|da|dos|das)\b)',
        text)
    if match:
        return int(match[1])
    # Portuguese quantity agrees in gender with "unidade": both "dois" and
    # "duas unidades" express the same count. Keep these aliases local to
    # quantity parsing; elapsed policy-day parsing has separate semantics.
    quantity_words = {**NUMERALS, "uma": "1", "duas": "2"}
    number_words = "|".join(sorted(quantity_words, key=len, reverse=True))
    word_match = re.search(r'\b(' + number_words + r')\s+(?:unidades?|units?|pecas?)\b', text)
    return int(quantity_words[word_match[1]]) if word_match else None


def advisory_question(question):
    """Allow scoped, non-transactional guidance without inventing store facts."""
    t = normalize(question)
    factual = r'\b(?:preco|valor|custa|quanto|stock|estoque|disponivel|available|promotion|promoc|discount|desconto|policy|politica|warranty|garantia|return|devolucao|refund|reembolso|order|pedido|tracking|rastre|opening hours|horario)\b'
    if re.search(factual, t):
        return False
    return bool(re.search(r'\b(?:help me choose|help me decide|what suits me|recommend|recommendation|suggestion|'
                          r'good fit|where should i start|beginner advice|advice for|which should i learn|'
                          r'me ajudar a escolher|me ajudar a decidir|combina comigo|me orientar|qual instrumento devo|'
                          r'o que voce recomenda|dica para comecar|por onde comecar|por qual lado comecar|'
                          r'o que faz (?:mais )?sentido explorar|o que vale a pena explorar|what makes sense to explore|what should i explore|'
                          r'explica.*simples|sem palavra complicada|melhor|nao manjo nada|tem problema|'
                          r'zero experiencia|sem experiencia|nunca toquei|nunca encostei|getting started|'
                          r'no experience|just starting|beginner|which is better)\b', t)
                or (re.search(r'\b(?:how|como|what|o que|why|por que|explain|explique|difference|diferenca)\b', t)
                    and re.search(r'\b(?:instrument\w*|viol\w*|guit\w*|ukulel\w*|baix\w*|keyboard|teclado|midi|strings?|cordas?|nylon|steel|aco|tocar|play|tune|afinar)\b', t)))


def contextual_advisory_question(question, previous_questions):
    """Recognize a non-factual advice follow-up whose subject is already in context."""
    if advisory_question(question):
        return True
    t = normalize(question)
    factual = r'\b(?:preco|valor|custa|quanto|stock|estoque|disponivel|available|promotion|promoc|discount|desconto|policy|politica|warranty|garantia|return|devolucao|refund|reembolso|order|pedido|tracking|rastre|opening hours|horario)\b'
    if re.search(factual, t) or not re.search(
            r'\b(?:explic\w*|explain\w*|diferenc\w*|differences?|sem (?:precisar )?(?:escolher|decidir)|without (?:choosing|deciding))\b', t):
        return False
    context = normalize(' '.join(previous_questions[-3:]))
    return bool(re.search(
        r'\b(?:gosto|prefiro|curto|som|estilo|explor\w*|escolh\w*|combina comigo|'
        r'come\w*|aprend\w*|beginner|like|prefer|sound|style|explor\w*|choose|start)\b', context))


def explanation_followup(question):
    t = normalize(question)
    return bool(re.search(r'\b(?:por\s*que|porque|why|explain|explique|nao encontr|not found|restantes|remaining|outro produto|other product|vi .*lista)\b', t))


def product_followup(question):
    """Only pronouns/elliptical questions inherit a selection, never a new name."""
    t = normalize(question)
    # Normalization turns the verb "está" into "esta". Treat normalized
    # "esta" as a pronoun only when it is actually written that way, and not
    # when it introduces a state/description such as "está marcada".
    state_description = bool(re.search(
        r'\besta\s+(?:marcad\w*|registrad\w*|anotad\w*|indicad\w*|listad\w*)\b', t))
    demonstrative_esta = bool(re.search(r'\besta\b', question, re.IGNORECASE) and not state_description)
    if (demonstrative_esta or re.search(r'\b(?:ele|ela|dele|dela|deles|delas|esse|essa|este|isso|disso|daquele|daquela|'
                  r'dessa|desse|it|its|that|this|both)\b|\bos dois\b', t)
            or (re.match(r'^(?:e|ah e|voltando|sobre)\b', t)
                and re.search(r'\b(?:pre\w*|valor|custa|quanto|pix|pag\w*|estoque|disponivel|stock|available)\b', t))):
        return True
    words = set(re.findall(r'\w+', t))
    return bool(words) and words <= set(('qual e o a preco precinho precos valor quanto fica sai custa estoque tem esta disponivel '
        'no pix pagando pagarei pagando com desconto se eu consigo price cost stock available availability and what is the how much '
        'does in on by using payment inclui promocao na promocional pagar se for de do da unitario normal '
        'deles delas desse dessa aquele aquela primeiro primeira').split())


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
            and bool(re.search(r'^(?:por\s*que|porque|why)\W*$|\b(?:fonte|sources?|secao|section|pagina|page|referencia|onde encontro|where.*find)\b', t)))


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
