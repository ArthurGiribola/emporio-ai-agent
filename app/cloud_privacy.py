"""Cloud chat projection: never forward arbitrary customer text to Gemini.

This is a deliberately limited vocabulary, not a general PII anonymizer.
Known identifiers are rejected; all remaining unknown tokens are discarded.
Only synthetic entity IDs and fixed demo budget values may survive projection.
"""

import re
import unicodedata

from app.synthetic import QUESTIONS


WORDS = frozenset("""oi ola obrigado ajuda quero preciso tem quais qual como posso pode podemos
instrumento instrumentos violao violoes guitarra guitarras ukulele ukuleles nylon aco
natural preto acustico eletrico iniciante iniciantes barato baratos disponivel disponiveis
estoque esgotado preco precos valor custa pagar pagamento pix credito debito boleto cartao
promocao promocoes oferta ofertas desconto descontos acumular cumulativo cumulativos
pedido pedidos status rastreio rastreamento entrega entregue confirmado cancelado
politica politicas devolucao devolver reembolso estorno troca trocar garantia defeito
horario funcionamento abre fecha sabado domingo reclamacao queixa frete envio
sintetico sintetica sinteticos sinteticas demonstracao exemplo reais ate abaixo acima
com sem de do da dos das em no na por para e ou o a os as um uma meu minha esse essa
este esta desses dessas deles delas primeiro primeira segundo segunda anterior anteriores mais menos mesmo mesma
agora ainda tambem somente detalhes comparar compare liste mostrar mostre""".split())
NUMBERS = frozenset({"1", "2", "3", "50", "100", "150", "200", "250", "500", "1000"})
DOMAIN = WORDS - frozenset("""de do da dos das em no na por para e ou o a os as um uma
meu minha esse essa este esta com sem mais menos mesmo mesma ainda tambem agora""".split())


def project_synthetic_question(question: str) -> str | None:
    # Constant approved prompts can be reused without alteration.
    if question in QUESTIONS.values():
        return question
    folded = "".join(c for c in unicodedata.normalize("NFKD", question.casefold()) if not unicodedata.combining(c))
    if ("@" in question or re.search(r"(?:\d[\s().+-]*){8,}", question)
            or re.search(r"\b(?:nome|name|email|telefone|phone|cpf|cnpj|senha|password|token|customer_id|api_key|endereco)\b", folded)):
        return None
    tokens = re.findall(r"[a-z_]+|\d+(?:[.,]\d+)?", folded)
    # Deduplication also prevents arbitrary repeated-token/number sequences.
    selected = list(dict.fromkeys(token for token in tokens if token in WORDS or token in NUMBERS))[:40]
    if not DOMAIN.intersection(selected):
        return None
    return "Synthetic demonstration only. Filtered intent tokens; original text withheld: " + " ".join(selected)
