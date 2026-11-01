"""Small document-profile retriever. Extracted text is untrusted reference data.

No execution, instruction following, model calls, embeddings, or filesystem
writes occur. Section mappings intentionally target the supplied manual layout.
"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PolicyDataError(ValueError):
    """Missing, malformed, unreadable, or unsupported policy document."""


def normalize(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(c))
    return " ".join(text.split())


# Structural labels only, never a replacement for extracted policy rules.
HEADINGS = {
    "1": "Sobre a Empório da Música", "1.1": "Missão", "1.2": "Dados da Empresa",
    "2": "Horário de Funcionamento", "3": "Formas de Pagamento", "3.1": "Regras de Parcelamento",
    "4": "Política de Trocas e Devoluções", "4.1": "Direito de Arrependimento (Compras Online)",
    "4.2": "Trocas por Defeito", "4.3": "Trocas por Preferência", "4.4": "Itens Não Elegíveis para Troca",
    "5": "Política de Frete e Entregas", "5.1": "Entregas na Região Metropolitana de Campo Grande",
    "5.2": "Entregas para Outras Cidades", "5.3": "Código de Rastreamento",
    "6": "Promoções e Descontos", "6.1": "Tipos de Promoção", "6.2": "Regras de Promoções",
    "7": "Atendimento via WhatsApp", "7.1": "Diretrizes de Atendimento",
    "7.2": "Fluxo de Atendimento Padrão", "7.3": "Situações Especiais",
    "8": "Garantia", "8.1": "Garantia Legal", "8.2": "Garantia do Fabricante",
    "8.3": "O que Não Cobre a Garantia", "9": "Privacidade e Proteção de Dados",
    "10": "Disposições Finais",
}

# Whole-word stems are deliberate; unrelated words must not match short substrings.
TOPICS = {
    "returns": (r"\b(?:devol\w*|troc\w*|arrepend\w*|reembols\w*|ressarc\w*|estorn\w*|desist\w*)\b", ("4.1", "4.2", "4.3", "4.4")),
    "warranty": (r"\b(?:garanti\w*|defeit\w*|avari\w*|quebrad\w*|consert\w*)\b|assistencia tecnica", ("4.2", "8.1", "8.2", "8.3")),
    "payments": (r"\b(?:pix|paga\w*|pago|pagou|pagamento\w*|cartao|cartoes|credito|debito|boleto\w*|parcel\w*|prestac\w*)\b", ("3", "3.1", "6.2")),
    "shipping": (r"\b(?:frete\w*|entreg\w*|envio\w*|enviar|postag\w*|despach\w*|rastre\w*|correios|sedex|pac|jadlog)\b", ("5.1", "5.2", "5.3")),
    "promotions": (r"\b(?:promoc\w*|descont\w*|oferta\w*|cumul\w*|acumul\w*)\b|black friday", ("3", "6.1", "6.2")),
    "hours": (r"\b(?:horario\w*|abre|abrem|abrir|aberta|aberto|fecha|fecham|fechada|fechado|funcionamento|expediente|sabado|domingo|feriado\w*)\b|que horas|loja funciona", ("2",)),
    "complaints": (r"\b(?:reclam\w*|queixa\w*|insatisfeit\w*|insatisf\w*)\b", ("7.3",)),
    "contact": (r"\b(?:telefone\w*|whatsapp|contato|email|endereco)\b|e-mail", ("1.2", "7")),
    "privacy": (r"\b(?:privacidade|lgpd)\b|dados pessoais", ("9",)),
}


@dataclass(frozen=True)
class PolicySection:
    number: str
    title: str
    text: str
    pages: tuple[int, ...]
    source: str
    reference_only: bool = True


@dataclass(frozen=True)
class PolicyIssue:
    code: str
    sections: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class PolicyRetrieval:
    status: str
    sections: tuple[PolicySection, ...]
    issues: tuple[PolicyIssue, ...]
    limitations: tuple[str, ...]
    reference_only: bool = True


class PolicyRetriever:
    def __init__(self, path: str | Path):
        path = Path(path)
        try:
            # The file is opened and closed here; no resources remain open afterward.
            with path.open("rb") as stream:
                if path.stat().st_size > 10 * 1024 * 1024 or stream.read(5) != b"%PDF-":
                    raise PolicyDataError("Policy PDF has an invalid header or exceeds the size limit")
                stream.seek(0)
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted or not 1 <= len(reader.pages) <= 100:
                    raise PolicyDataError("Policy PDF is encrypted, empty, or exceeds the page limit")
                pages = tuple(page.extract_text() or "" for page in reader.pages)
        except PolicyDataError:
            raise
        except (OSError, PdfReadError, ValueError, TypeError, KeyError, IndexError, RecursionError, NotImplementedError):
            raise PolicyDataError("Cannot extract the policy PDF; provide an authorized, valid text PDF") from None
        self.sections = MappingProxyType(_parse_pages(pages, path.name))
        self.issues = tuple(_detect_issues(self.sections))

    def search(self, question: str) -> PolicyRetrieval:
        """Return evidence, NOT an answer or permission to execute PDF directives.

        Status is evidence_found, needs_review, or insufficient_evidence.
        Topic matches alone never establish individualized eligibility or a live fact.
        """
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            return PolicyRetrieval("insufficient_evidence", (), (), ("A nonempty question of at most 4000 characters is required.",))
        query = normalize(question)
        topics = [topic for topic, (pattern, _) in TOPICS.items() if re.search(pattern, query)]
        if not topics:
            return PolicyRetrieval("insufficient_evidence", (), (), ("No supported policy topic matched the question.",))
        requested = {number for topic in topics for number in TOPICS[topic][1]}
        # Related sources needed to interpret a return involving a defect.
        if "returns" in topics and "warranty" in topics:
            requested.update(TOPICS["warranty"][1])
        if "pix" in query and not re.search(r"parcel\w*|prestac\w*|cartao|credito", query):
            requested.discard("3.1")
        issues = [issue for issue in self.issues if requested.intersection(issue.sections)
                  and not (issue.code.startswith("installment_") and "3.1" not in requested)]
        # Include the counterpart source for a conflict, not just its warning.
        for issue in issues:
            requested.update(issue.sections)
        limitations = ["Reference evidence only; source freshness and individual eligibility are not verified."]
        missing = sorted(number for number in requested if number not in self.sections or not self.sections[number].text)
        if missing:
            limitations.append("Missing policy evidence for section(s): " + ", ".join(missing))
        unsupported = _unsupported_details(query, topics)
        limitations.extend(unsupported)
        if "hours" in topics and re.search(r"\b(?:agora|hoje|amanha|feriado)\b", query):
            issues.append(PolicyIssue("live_schedule_unknown", ("2",), "No live holiday or exceptional-hours calendar is supplied."))
        sections = tuple(self.sections[number] for number in sorted(requested, key=_section_order) if number in self.sections)
        status = "insufficient_evidence" if missing or unsupported else "needs_review" if issues else "evidence_found"
        return PolicyRetrieval(status, sections, tuple(issues), tuple(limitations))


def _section_order(number: str) -> tuple[int, ...]:
    return (0,) if number == "cover" else tuple(map(int, number.split(".")))


def _parse_pages(pages: tuple[str, ...], source: str) -> dict[str, PolicySection]:
    if not pages or any(not page.strip() for page in pages):
        raise PolicyDataError("Policy PDF has blank or scanned pages; OCR is not implemented")
    chunks: dict[str, list[tuple[int, str]]] = {"cover": []}
    current = "cover"
    for page_number, text in enumerate(pages, 1):
        for raw in text.splitlines():
            line = " ".join(raw.split())
            folded = normalize(line)
            if not line or re.fullmatch(r"pagina \d+", folded) or folded == "emporio da musica manual de politicas e procedimentos":
                continue
            if folded.startswith("emporio da musica — sua musica comeca aqui."):
                continue
            match = re.match(r"^(\d+(?:\.\d+)?)\.?\s+(.+)$", line)
            if match and match.group(1) in HEADINGS:
                number, rest = match.groups()
                title = HEADINGS[number]
                # A known title avoids mistaking numbered service steps for headings.
                if normalize(rest).startswith(normalize(title)):
                    if number in chunks or _section_order(number) <= _section_order(current):
                        raise PolicyDataError("Policy headings are duplicated or out of order")
                    chunks[number] = [(page_number, "")]
                    current = number
                    # Normalization changes accent codepoints but not character count for these titles.
                    line = rest[len(title):].strip()
                elif _section_order(number) > _section_order(current):
                    raise PolicyDataError("Policy heading does not match the supported document profile")
            elif match and ("." in match.group(1) or re.match(r"^\d+\.\s+[A-ZÀ-Ý]", line)):
                raise PolicyDataError("Unsupported policy heading; review the document profile")
            chunks[current].append((page_number, line))
    if len(chunks) == 1:
        raise PolicyDataError("No supported numbered policy sections found")
    return {
        number: PolicySection(number, "Document cover" if number == "cover" else HEADINGS[number],
                              " ".join(part for _, part in fragments if part),
                              tuple(sorted({page for page, _ in fragments})), source)
        for number, fragments in chunks.items() if fragments
    }


def _detect_issues(sections):
    def text(number):
        return normalize(sections[number].text) if number in sections else ""

    contact_sections = tuple(number for number in ("cover", "1.2", "7") if number in sections)
    phones = {re.sub(r"\D", "", phone) for number in contact_sections
              for phone in re.findall(r"\(\d{2}\)\s*\d{4,5}\s*-\s*\d{4}", text(number))}
    if len(phones) > 1:
        yield PolicyIssue("conflicting_contacts", contact_sections, "The sources list different contact phone numbers; confirmation is required.")
    # Case-fold but do not remove accents: the domain spelling itself may conflict.
    emails = {email.casefold() for number in contact_sections
              for email in re.findall(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", sections[number].text)}
    if len(emails) > 1:
        yield PolicyIssue("conflicting_email_spelling", contact_sections, "Contact email spellings differ across sources; confirmation is required.")
    amounts = lambda value: set(re.findall(r"parcela minima (?:de )?r\$\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)", value))
    general, detailed = amounts(text("3")), amounts(text("3.1"))
    if general and detailed and detailed - general:
        yield PolicyIssue("installment_minimum_conflict", ("3", "3.1"), "General and tier-specific installment minimums differ; do not promise disputed terms.")
    if re.search(r"sem valor minimo.*exceto abaixo", text("3.1")):
        yield PolicyIssue("installment_exception_ambiguous", ("3.1",), "The low-value installment exception does not clearly define its application.")
    above = set(re.findall(r"acima de r\$\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)", text("5.1")))
    below = set(re.findall(r"abaixo de r\$\s*([0-9]+(?:\.[0-9]{3})*(?:,[0-9]{2})?)", text("5.1")))
    if above & below and "igual" not in text("5.1"):
        yield PolicyIssue("shipping_threshold_gap", ("5.1",), "The local shipping rule omits the exact threshold boundary.")
    tracking = text("5.3")
    claimed = re.search(r"br seguido de (\d+) caracteres", tracking)
    example = re.search(r"exemplo:\s*(br[a-z0-9]+br)", tracking)
    if claimed and example and len(example.group(1)) - 4 != int(claimed.group(1)):
        yield PolicyIssue("tracking_format_conflict", ("5.3",), "The tracking-format description and its example disagree; do not rewrite recorded tracking codes.")
    if all(text(n) for n in ("4.1", "4.4")):
        yield PolicyIssue("return_exception_scope", ("4.1", "4.4"), "The relationship between general return rights and exchange exclusions requires clarification; do not determine legal eligibility.")
    if all(text(n) for n in ("4.2", "8.1")):
        yield PolicyIssue("exchange_warranty_scope", ("4.2", "8.1"), "Exchange procedures and legal warranty are separate; do not treat the exchange period as the end of warranty rights.")


def _unsupported_details(query: str, topics: list[str]) -> list[str]:
    limitations = []
    if "payments" in topics and re.search(r"\b(?:bitcoin|cripto\w*|paypal|apple pay|google pay|cheque|dinheiro|transferencia)\b", query):
        limitations.append("The requested payment method is not documented.")
    if "shipping" in topics and re.search(r"\b(?:quanto|custa|custo|cotacao|calcule|calcular|cep|peso|dimensoes)\b", query):
        limitations.append("An individual shipping quote needs order/destination details and a shipping integration.")
    if "warranty" in topics and re.search(r"\b(?:estendida|vitalicia)\b", query):
        limitations.append("Extended or lifetime warranty coverage is not documented.")
    if "warranty" in topics and re.search(r"\b(?:yamaha|fender|gibson|ibanez|korg|roland|modelo|especifico|especifica)\b", query):
        limitations.append("Product-specific manufacturer warranty terms are not mapped in this manual.")
    if re.search(r"\b(?:meu|minha)\b.*\b(?:pedido|entrega|reembolso|devolucao)\b", query) and re.search(r"\b(?:status|onde|rastrear|ja|chegou|aprovado)\b", query):
        limitations.append("The manual cannot establish an individual order or refund status.")
    return limitations
