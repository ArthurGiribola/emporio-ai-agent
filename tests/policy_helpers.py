"""Generate tiny synthetic text PDFs in temporary directories, never source copies."""

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.policies import HEADINGS


def heading(number: str) -> str:
    return number + ". " + HEADINGS[number]


def synthetic_pages() -> list[list[str]]:
    return [
        ["Synthetic policy fixture", "Contact: (11) 1111-1111 desk@example.invalid",
         heading("1"), "A synthetic test store.", heading("1.2"),
         "Telefone (11) 1111-1111. Email desk@example.invalid",
         heading("2"), "Atendimento somente com agendamento.",
         heading("3"), "PIX e cartao. Parcela minima de R$ 120,00.",
         heading("3.1"), "Parcela minima de R$ 60,00. Sem valor minimo (exceto abaixo de R$ 20,00).",
         heading("4"), "Procedimentos de teste.", heading("4.1"),
         "Devolucao online: prazo sintetico de 11 dias. Reembolso no pagamento original.",
         heading("4.2"), "Defeito exige avaliacao tecnica de teste.",
         heading("4.3"), "Troca por preferencia sujeita a avaliacao.",
         heading("4.4"), "Exclusoes de teste precisam de confirmacao.",
         heading("5"), heading("5.1"),
         "Acima de R$ 700,00 ha uma regra; abaixo de R$ 700,00 ha outra.", heading("5.2")],
        ["Envios para outras cidades seguem cotacao externa de teste.",
         heading("5.3"), "BR seguido de 9 caracteres alfanumericos e BR (exemplo: BR123BR).",
         heading("6"), heading("6.1"), "Ofertas selecionadas de teste.",
         heading("6.2"), "PIX e promocao nao sao cumulativos neste exemplo sintetico.",
         heading("7"), "WhatsApp (11) 2222-2222. Email support@example.invalid",
         heading("7.2"), "1. Saudacao: passo sintetico.", "3. Consulta: passo sintetico.",
         heading("7.3"), "Reclamacao deve ser encaminhada para avaliacao.",
         heading("8"), heading("8.1"), "Garantia legal: consulte o procedimento de teste.",
         heading("8.2"), "Garantia do fabricante depende do certificado.",
         heading("8.3"), "Exclusoes de garantia exigem analise.",
         heading("9"), "Dados pessoais restritos.", heading("10"), "Fim do documento sintetico."]
    ]


def write_pdf(path: Path, pages: list[list[str]], *, encrypted: bool = False) -> None:
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica"),
                             NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        commands = ["BT /F1 8 Tf 10 770 Td"]
        for line in lines:
            escaped = "".join(f"\\{byte:03o}" for byte in line.encode("cp1252"))
            commands.append(f"({escaped}) Tj 0 -14 Td")
        commands.append("ET")
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password", algorithm="RC4-128")
    writer.write(path)
