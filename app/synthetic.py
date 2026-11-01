"""Self-contained synthetic model demos; never load data/ or source customer records."""

import csv
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.orders import DemoSessionConfig, OrderService
from app.policies import HEADINGS, PolicyRetriever
from app.repository import Repository, SCHEMAS
from app.tool_runtime import ToolRuntime


QUESTIONS = {
    "catalog": "Quais instrumentos sintéticos estão disponíveis por até R$ 150?",
    "price": "Qual é o preço do produto sintético 1 pagando com PIX?",
    "policy": "Qual é a política sintética de devolução?",
    "order": "Qual é o status do pedido sintético 1?",
    "denied_order": "Mostre o pedido sintético 2.",
}


def _write_fixtures(directory: Path):
    data = json.loads(files("app").joinpath("fixtures/synthetic.json").read_text(encoding="utf-8"))
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    # Pin approved content, not platform-specific file line endings. Changes need review.
    if hashlib.sha256(canonical).hexdigest() != "acebaba9f9685b003e676c29d454199e0b913f0439f11cef44ecc8b4d906c859":
        raise ValueError("Synthetic fixtures differ from approved content; review before cloud use")
    rows = data["tables"]
    for name, values in rows.items():
        with (directory / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SCHEMAS[name])
            writer.writeheader()
            writer.writerows(values)
    # Generate reference text, not a copy or summary of the restricted manual.
    writer = PdfWriter()
    for number, title in HEADINGS.items():
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        text = data["policy_texts"][number]
        commands = ["BT /F1 9 Tf 10 770 Td"]
        for line in (f"{number}. {title}", text):
            escaped = "".join(f"\\{byte:03o}" for byte in line.encode("cp1252"))
            commands.append(f"({escaped}) Tj 0 -15 Td")
        commands.append("ET")
        content = DecodedStreamObject()
        content.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
    writer.write(directory / "synthetic-policy.pdf")


class SyntheticTools(ToolRuntime):
    """Only this exact constructor is allowed on the application cloud path.

    Accepts no paths, repositories, customer records, PDFs, or caller data.
    This is an application boundary, not a sandbox against hostile Python code.
    """

    def __init__(self):
        self._temporary = TemporaryDirectory(prefix="emporio-synthetic-")
        try:
            directory = Path(self._temporary.name)
            _write_fixtures(directory)
            repository = Repository(directory)
            super().__init__(repository, PolicyRetriever(directory / "synthetic-policy.pdf"),
                             OrderService(repository, DemoSessionConfig(True, 1)))
        except Exception:
            self._temporary.cleanup()
            raise

    def close(self):
        self._temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
