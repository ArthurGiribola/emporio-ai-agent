"""Fictional 65-product catalog for task-completion evaluation.

Entirely invented brands, models, people and policy text. It mirrors the SHAPE of
a real store catalog (size, categories, inactive items, zero stock, a promotion,
shared brand words, similar model names) so that list positions above 5,
truncation, name ambiguity and broad browsing are exercised. Safe to publish.
"""

import csv
import json
from importlib.resources import files
from pathlib import Path

from app.repository import SCHEMAS
from app.synthetic import _write_fixtures

CATEGORIES = [
    ("1", "Violões", "Instrumentos acústicos de cordas"),
    ("2", "Guitarras", "Guitarras elétricas"),
    ("3", "Baixos", "Contrabaixos elétricos"),
    ("4", "Ukuleles", "Ukuleles de vários tamanhos"),
    ("5", "Teclados", "Teclados e pianos digitais"),
]

# (brand, model, category, base price, stock, status, specs)
_LINES = {
    "1": [("Aurora", "AC-10 Clássico Nylon", {"strings": "nylon"}), ("Aurora", "AC-20 Clássico Nylon", {"strings": "nylon"}),
          ("Boreal", "Folk F-200 Aço", {"strings": "aço"}), ("Boreal", "Folk F-300 Aço Elétrico", {"strings": "aço"}),
          ("Cometa", "Estudante Nylon Natural", {"strings": "nylon"}), ("Delta", "Jumbo J-45 Aço Sunburst", {"strings": "aço"}),
          ("Eclipse", "Concerto Cedro Nylon", {"strings": "nylon"}), ("Farol", "Mini Viagem Aço", {"strings": "aço"}),
          ("Galáxia", "Flat Eletroacústico Nylon", {"strings": "nylon"}), ("Delta", "Dreadnought D-10 Aço Natural", {"strings": "aço"}),
          ("Cometa", "Infantil 3/4 Nylon", {"strings": "nylon"}), ("Aurora", "AC-30 Cutaway Nylon", {"strings": "nylon"}),
          ("Boreal", "Parlor P-10 Aço", {"strings": "aço"})],
    "2": [("Eclipse", "Strato ST-100 Preta", {}), ("Eclipse", "Strato ST-200 Branca", {}), ("Farol", "Tele T-50 Natural", {}),
          ("Galáxia", "Les Paul LP-60 Cereja", {}), ("Delta", "Superstrato SX-7 Azul", {}), ("Cometa", "Semi-acústica SA-90", {}),
          ("Aurora", "Jazz JZ-1 Sunburst", {}), ("Boreal", "Offset OF-22 Verde", {}), ("Farol", "Tele T-70 Preta", {}),
          ("Galáxia", "Les Paul LP-80 Dourada", {}), ("Eclipse", "Strato ST-300 Vermelha", {}), ("Delta", "Superstrato SX-9 Preta", {}),
          ("Cometa", "Hollow H-10 Natural", {})],
    "3": [("Boreal", "Precision PB-4 Preto", {"strings": "4"}), ("Boreal", "Jazz Bass JB-4 Sunburst", {"strings": "4"}),
          ("Delta", "Ativo AB-5 Natural", {"strings": "5"}), ("Galáxia", "Short Scale SS-4", {"strings": "4"}),
          ("Eclipse", "Precision PB-5 Branco", {"strings": "5"}), ("Farol", "Fretless FL-4", {"strings": "4"}),
          ("Cometa", "Iniciante BI-4 Vermelho", {"strings": "4"}), ("Aurora", "Jazz Bass JB-5 Natural", {"strings": "5"}),
          ("Delta", "Ativo AB-4 Preto", {"strings": "4"}), ("Galáxia", "Acústico Baixolão BA-4", {"strings": "4"}),
          ("Farol", "Precision PB-4 Azul", {"strings": "4"}), ("Eclipse", "Jazz Bass JB-4 Preto", {"strings": "4"}),
          ("Boreal", "Headless HL-5", {"strings": "5"})],
    "4": [("Kaiwa", "Soprano KS-10 Mogno", {}), ("Kaiwa", "Soprano KS-20 Spruce", {}), ("Kaiwa", "Concert KC-30 Mogno", {}),
          ("Aurora", "Tenor UT-40 Natural", {}), ("Farol", "Soprano FS-5 Rosa", {}), ("Galáxia", "Concert GC-15 Koa", {}),
          ("Cometa", "Barítono CB-25", {}), ("Delta", "Soprano DS-12 Preto", {}), ("Kaiwa", "Tenor KT-50 Elétrico", {}),
          ("Eclipse", "Concert EC-18 Natural", {}), ("Boreal", "Soprano BS-8 Azul", {}), ("Farol", "Tenor FT-35 Mogno", {}),
          ("Galáxia", "Soprano GS-6 Verde", {})],
    "5": [("Galáxia", "Piano Digital PD-88", {"keys": "88"}), ("Galáxia", "Arranjador AR-61", {"keys": "61"}),
          ("Eclipse", "Sintetizador SY-49", {"keys": "49"}), ("Delta", "Teclado Infantil TI-37", {"keys": "37"}),
          ("Aurora", "Piano de Palco PP-73", {"keys": "73"}), ("Cometa", "Controlador MIDI CM-25", {"keys": "25"}),
          ("Farol", "Teclado Portátil TP-61", {"keys": "61"}), ("Boreal", "Piano Digital BD-88 Branco", {"keys": "88"}),
          ("Galáxia", "Workstation WS-76", {"keys": "76"}), ("Delta", "Teclado Iniciante TK-61", {"keys": "61"}),
          ("Eclipse", "Sintetizador SY-61 Analógico", {"keys": "61"}), ("Aurora", "Órgão Digital OD-61", {"keys": "61"}),
          ("Cometa", "Controlador MIDI CM-49", {"keys": "49"})],
}
BASE_PRICE = {"1": 420, "2": 980, "3": 1150, "4": 190, "5": 1350}
INACTIVE = {7: "discontinued", 20: "discontinued", 33: "coming_soon", 58: "coming_soon"}
ZERO_STOCK = {12, 41}


def catalog_rows() -> dict[str, list[dict[str, str]]]:
    products, index = [], 0
    for category_id, lines in _LINES.items():
        for offset, (brand, model, specs) in enumerate(lines):
            index += 1
            products.append(dict(
                product_id=str(200 + index),
                price_brl=f"{BASE_PRICE[category_id] + offset * 73 + (index % 7) * 11}.90",
                name=f"{brand} {model}", category_id=category_id,
                description=f"Modelo fictício {brand} da linha {model.split()[0]} para testes de atendimento.",
                stock_quantity=str(0 if index in ZERO_STOCK else (index * 7) % 13 + 1),
                status=INACTIVE.get(index, "active"),
                specs=json.dumps(specs, ensure_ascii=False), created_at="2025-01-01"))
    assert len(products) == 65
    return {
        "categories": [dict(category_id=c, name=n, description=d) for c, n, d in CATEGORIES],
        "products": products,
        "promotions": [dict(promotion_id="1", product_id="203", discount_percent="10",
                            description="Oferta fictícia", is_active="1"),
                       dict(promotion_id="2", product_id="243", discount_percent="15",
                            description="Oferta fictícia", is_active="1")],
        "customers": [dict(customer_id="1", name="Cliente Fictício", phone="TEST-ONLY",
                           email="cliente@example.invalid", city="Cidade Fictícia")],
        "orders": [dict(order_id="1", customer_id="1", order_date="2025-03-02", status="shipped",
                        total_brl="1399.80", payment_method="pix", tracking_code="FIC123456BR",
                        estimated_delivery="2025-03-09", notes="")],
        "order_items": [dict(order_id="1", quantity="1", product_id="214"),
                        dict(order_id="1", quantity="2", product_id="240")],
    }


def write_catalog65(directory: Path) -> Path:
    """Write CSVs plus the existing generated synthetic policy PDF; return the policy path."""
    directory = Path(directory)
    _write_fixtures(directory)  # approved synthetic policy text (generated, not the store manual)
    for name, rows in catalog_rows().items():
        with (directory / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=SCHEMAS[name])
            writer.writeheader()
            writer.writerows(rows)
    return directory / "synthetic-policy.pdf"
