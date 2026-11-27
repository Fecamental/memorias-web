from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from backend.documentos import planilla
from backend.dominio import CATALOGO, calculados


def test_catalogo_exporta_todos_los_campos_con_unidades_declaradas():
    assert len(CATALOGO) == 39
    for tipo in CATALOGO.values():
        ws = load_workbook(BytesIO(planilla(tipo)), read_only=True).active
        filas = list(ws.values)[4:]
        assert len(filas) == len(tipo["fields"])
        for fila, campo in zip(filas, tipo["fields"]):
            assert (fila[0], fila[1], fila[3]) == (campo["key"], campo["label"], campo["unit"])
            assert str(fila[2]).startswith("=") == campo["automatic"]


def test_formulas_con_datos_sinteticos():
    viga = {"wu": Decimal("18"), "l": Decimal("8"), "phi": Decimal("0.8")}
    assert calculados("viga", viga) == {"mu": Decimal("144"), "mn": Decimal("180")}
    viga["phi"] = Decimal("0")
    assert "mn" not in calculados("viga", viga)
    muro = {"tw": Decimal("0.65"), "bt": Decimal("2.3"), "bpunta": Decimal("0.55"),
            "hw": Decimal("3.6"), "hz": Decimal("0.65")}
    assert calculados("muro-gravedad", muro) == {"bz": Decimal("3.5"), "hsa": Decimal("4.25")}
