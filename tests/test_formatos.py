from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from backend.documentos import planilla
from backend.dominio import CATALOGO, CATALOGO_V1, modelo_calculo
from backend.formulas import FORMULAS, calculados


def dec(**valores):
    return {k: Decimal(str(v)) for k, v in valores.items()}


@pytest.mark.parametrize("codigo", list(CATALOGO))
def test_plantilla_respeta_las_variables_y_unidades(codigo):
    tipo = CATALOGO[codigo]
    datos = planilla(tipo)
    hoja = load_workbook(BytesIO(datos), read_only=True).active
    filas = list(hoja.values)
    assert filas[2][4] == "Modelo 2"
    assert len(filas) - 4 == len(tipo["fields"])
    for fila, campo in zip(filas[4:], tipo["fields"]):
        assert (fila[0], fila[1], fila[3]) == (campo["key"], campo["label"], campo["unit"])
        assert str(fila[2]).startswith("=") == campo["automatic"]
        if campo["automatic"]:
            assert campo["key"] in FORMULAS[codigo]


def test_los_modelos_anteriores_conservan_sus_unidades():
    clave = "tuberias-gravedad"
    anterior = modelo_calculo(clave, 1)
    vigente = modelo_calculo(clave, 2)
    assert len(CATALOGO_V1) == 19
    assert next(f for f in anterior["fields"] if f["key"] == "d")["unit"] == "mm"
    assert next(f for f in vigente["fields"] if f["key"] == "d")["unit"] == "pulg"
    assert next(f for f in anterior["fields"] if f["key"] == "vel")["automatic"] is False
    assert next(f for f in vigente["fields"] if f["key"] == "vel")["automatic"] is True


def test_casos_sinteticos_hidraulicos():
    canal = calculados("canales", dec(b=3, z=1.2, y=0.85, s=0.0016, n=0.021))
    assert canal["ancho"] == Decimal("5.04")
    assert canal["area"] == Decimal("3.417")
    assert canal["cap"] == Decimal("4.65160073")

    bomba = calculados("tuberias-impulsion", dec(
        dz=26, hvel=1.25, hper=7.5, hpi=0.5, hdp=2.75, rho=985, q=0.075, eta=0.76))
    assert bomba["hmt"] == Decimal("38")
    assert bomba["pot_cv"] == Decimal("49.25")
    assert bomba["pot"] == Decimal("36.22331344")

    gravedad = calculados("tuberias-gravedad", dec(q=2.4, d=3.25, cp0=125, z0=112, z1=108.5, hf=1.7))
    assert gravedad == dec(vel=0.44842230, cp1=123.3, p0=13, p1=14.8)


def test_casos_sinteticos_estructurales_y_geotecnicos():
    assert calculados("losa", dec(ll=525, ls=315))["mrel"] == Decimal("0.6")
    assert calculados("muro-tem", dec(phi=20))["ka"] == Decimal("0.49029060")
    zapata = calculados("zapatas", dec(sigma=2.4, q=375, hf=1.15, pd=54, pl=18, gm=1.75))
    assert zapata["sn"] == Decimal("21.6125")
    assert zapata["az"] == Decimal("3.33140544")


def test_no_hay_resultados_dependientes_de_entradas_invalidas():
    assert "vel" not in calculados("canales", dec(b=3, z=1.2, y=0.85, s=0.0016, n=0))
    assert "pot" not in calculados("tuberias-impulsion", dec(
        dz=26, hvel=1.25, hper=7.5, hpi=0.5, hdp=2.75, rho=985, q=0.075, eta=0))
    assert "vel" not in calculados("tuberias-gravedad", dec(q=2.4, d=0))
