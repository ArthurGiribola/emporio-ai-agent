"""Receipt-window arithmetic from explicit policy evidence, never LLM prose.

Only the known affirmative online-withdrawal clause grammar is supported.
Missing/conflicting rules, unknown clocks/channels, and business-day conversions
fail closed. This assesses timing only, not legal or transactional eligibility.
"""

import re

from app.policies import normalize


NUMERALS = {"zero": "0", "um": "1", "dois": "2", "tres": "3", "quatro": "4", "cinco": "5", "seis": "6", "sete": "7", "oito": "8", "nove": "9", "dez": "10"}


def online_return_question(question: str) -> bool:
    text = normalize(question)
    if not re.search(r"\b(?:devol\w*|arrepend\w*|reembols\w*|estorn\w*)\b", text):
        return False
    if re.search(r"\b(?:defeito\w*|garanti\w*)\b", text) and not re.search(r"\barrepend\w*", text):
        return False
    return bool(re.search(r"\b(?:internet|online|on-line|site|arrepend\w*|recebimento|recebi)\b", text))


def extract_online_return_rule(section) -> dict:
    if section is None:
        return {"status": "insufficient_evidence", "request_window_days": None}
    normalized = normalize(section.text)
    windows = {int(n) for n in re.findall(
        r"\b(?:o )?cliente pode solicitar a devolucao em ate (\d{1,4})(?: \([^)]*\))? dias corridos apos o recebimento", normalized)}
    window = next(iter(windows)) if len(windows) == 1 and "cliente nao pode solicitar" not in normalized else None
    clauses = [s.strip(" .•") + "." for s in re.split(r"•|(?<=\.)\s+", section.text) if s.strip(" .•")]

    def clause(pattern):
        matches = [s for s in clauses if re.search(pattern, normalize(s))]
        return matches[0] if len(set(matches)) == 1 else None

    refund = clause(r"^o reembolso\b")
    refund_numbers = re.findall(r"em ate (\d{1,4})(?: \([^)]*\))? dias uteis", normalize(refund or ""))
    return {"status": "verified_clock" if window is not None else "insufficient_evidence",
            "section": section.number, "pages": section.pages, "source": section.source,
            "request_window_days": window,
            "refund_business_days": int(refund_numbers[0]) if len(refund_numbers) == 1 else None,
            "refund_statement": refund,
            "conditions_statement": clause(r"^o produto deve\b"),
            "shipping_statement": clause(r"^o frete de devolucao\b"),
            "eligibility_determined": False}


def elapsed_receipt_days(question: str) -> int | None:
    text = normalize(question)
    for word, number in NUMERALS.items():
        text = re.sub(r"\b" + word + r"\b", number, text)
    if re.search(r"(?:-|menos)\s*\d+\s+dias?|\bnao recebi\b", text):
        return None
    values = re.findall(r"(?:depois de|apos|ha) (\d{1,4}) dias?(?: corridos)? (?:do|de|desde o) recebimento", text)
    values += re.findall(r"(?:recebi|recebido|recebimento) (?:ha|faz|fazem) (\d{1,4}) dias?\b(?! uteis)", text)
    values = {int(value) for value in values}
    return next(iter(values)) if len(values) == 1 else None


def assess_online_return(question: str, rule: dict) -> dict:
    text = normalize(question)
    online = bool(re.search(r"\b(?:internet|online|on-line|site)\b", text))
    in_store = bool(re.search(r"presencial|loja fisica", text))
    channel = "online" if online and not in_store else "in_store" if in_store and not online else "unknown"
    elapsed = elapsed_receipt_days(question)
    window = rule.get("request_window_days")
    within = elapsed <= window if channel == "online" and elapsed is not None and window is not None else None
    return {"channel": channel, "elapsed_days": elapsed, "window_days": window,
            "within_window": within, "eligibility_determined": False}


def render_online_return(question: str, data: dict) -> str:
    rule = data.get("online_return_rule", {})
    assessment = assess_online_return(question, rule)
    window = rule.get("request_window_days")
    elapsed = assessment["elapsed_days"]
    if window is None:
        return "Não consigo confirmar o prazo de devolução com as informações disponíveis. O atendimento precisa esclarecer a política antes de avaliar a devolução ou o reembolso."
    if assessment["within_window"] is True:
        opening = (f"Sim — quanto ao prazo, {elapsed} dias após o recebimento estão dentro dos {window} dias corridos "
                   "previstos para solicitar a devolução de uma compra online.")
    elif assessment["within_window"] is False:
        opening = (f"Quanto ao prazo de arrependimento online descrito nesta seção, {elapsed} dias após o recebimento "
                   f"ultrapassam os {window} dias corridos previstos. Consulte o atendimento para avaliar outros procedimentos aplicáveis.")
    else:
        opening = (f"A regra para compras online prevê solicitar a devolução em até {window} dias corridos após o recebimento. "
                   "Preciso confirmar o canal da compra e quantos dias corridos se passaram desde o recebimento para avaliar esse prazo.")
    lines = [opening, "", "A devolução ainda depende das condições abaixo; estar no prazo não significa que ela já foi aprovada."]
    if rule.get("conditions_statement"):
        lines.append(rule["conditions_statement"])
    else:
        lines.append("As condições do produto precisam ser confirmadas com o atendimento.")
    if rule.get("refund_statement"):
        lines.append(rule["refund_statement"])
    else:
        lines.append("Não há informações suficientes para confirmar as condições de reembolso; o atendimento precisa esclarecê-las.")
    if rule.get("shipping_statement"):
        lines.append(rule["shipping_statement"])
    if any(issue["code"] == "return_exception_scope" for issue in data.get("issues", [])):
        lines.append("Casos especiais e exclusões precisam ser avaliados pelo atendimento; esta resposta não aprova a devolução.")
    pages = ", ".join(str(p) for p in rule["pages"])
    page_label = "página" if len(rule["pages"]) == 1 else "páginas"
    lines += ["", "Para solicitar a devolução, entre em contato com o atendimento.", "", f"Fonte: seção {rule['section']}, {page_label} {pages}."]
    return "\n".join(lines)
