"""Self-contained synthetic model demos; never load data/ or source customer records."""

import csv
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
    rows = {
        "categories": [dict(category_id="1", name="Violões", description="Synthetic category")],
        "products": [dict(product_id=str(i), price_brl=price, name=name, category_id="1", description="Instrumento sintético de demonstração",
                          stock_quantity=stock, status="active", specs='{"strings":"nylon"}', created_at="2025-01-01")
                     for i, price, name, stock in [(1, "100.10", "Violão Sintético Nylon", "3"), (2, "200.00", "Violão Sintético Folk", "0")]],
        "promotions": [dict(promotion_id="1", product_id="1", discount_percent="10", description="Synthetic offer", is_active="1")],
        "customers": [dict(customer_id=str(i), name=f"Synthetic Customer {i}", phone=f"SYNTHETIC-{i}",
                           email=f"demo-{i}@example.invalid", city="Synthetic City") for i in (1, 2)],
        "orders": [dict(order_id=str(i), customer_id=str(i), order_date="2025-01-02", status="confirmed", total_brl="99.00",
                        payment_method="pix", tracking_code="", estimated_delivery="", notes="") for i in (1, 2)],
        "order_items": [dict(order_id=str(i), product_id="1", quantity="1") for i in (1, 2)],
    }
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
        text = "Synthetic reference only; demo operator review required."
        if number == "4.1":
            text = "Synthetic return window: 11 days. This is not the real store policy."
        if number == "6.2":
            text = "Synthetic PIX and promotional discounts do not stack."
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
