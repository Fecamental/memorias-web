from decimal import Decimal
from pathlib import Path
from typing import Literal
import json

from pydantic import BaseModel, ConfigDict, Field

from .formulas import calculados


def leer_catalogo(archivo, modelo):
    return {t["code"]: {**t, "modelo": modelo} for t in json.loads(
        Path(__file__).with_name(archivo).read_text(encoding="utf-8")
    )}


CATALOGO = leer_catalogo("catalogo.json", 2)
CATALOGO_V1 = leer_catalogo("catalogo_v1.json", 1)
MODELOS = {1: CATALOGO_V1, 2: CATALOGO}


def modelo_calculo(tipo, version):
    return MODELOS[version][tipo]


ROLES = {
    "elaborador": "Elaborador técnico",
    "revisor": "Revisor técnico",
    "responsable": "Responsable técnico",
}
TRANSICIONES = {
    "enviar": ("elaborador", {"borrador"}, "revision", False),
    "derivar": ("revisor", {"revision"}, "aprobacion", False),
    "escalar": ("revisor", {"revision"}, "discrepancia", True),
    "resolver": ("responsable", {"discrepancia"}, "aprobacion", True),
    "observar": ("responsable", {"discrepancia", "aprobacion"}, "observada", True),
    "devolver": ("revisor", {"observada"}, "devuelta", True),
    "nueva_revision": ("elaborador", {"devuelta"}, "borrador", False),
    "aprobar": ("responsable", {"aprobacion"}, "aprobada", False),
}


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    valor: Decimal = Field(max_digits=14, decimal_places=8, allow_inf_nan=False)
    fuente: str = Field(default="", max_length=300)


class Nuevo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tipo: str = Field(max_length=50)
    titulo: str = Field(min_length=1, max_length=160)


class Comando(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(gt=0)
    motivo: str = Field(default="", max_length=2500)


class Borrador(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(gt=0)
    alcance: str = Field(default="", max_length=5000)
    desviacion: str = Field(default="", max_length=2000)
    conclusion: str = Field(default="", max_length=5000)
    veredicto: Literal["cumple", "no_cumple"] | None = None
    variables: dict[str, Entrada] = Field(default_factory=dict, max_length=50)


class Credencial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario: str = Field(max_length=40)
    clave: str = Field(max_length=200)


def verificar(tipo, revision, variables):
    por_codigo = {v["variable"]: v for v in variables}
    ficha = modelo_calculo(tipo, revision["modelo"])
    campos = ficha["fields"]
    faltantes = [f["label"] for f in campos if f["key"] not in por_codigo]
    sin_fuente = [f["label"] for f in campos
                  if f["key"] in por_codigo and not por_codigo[f["key"]]["fuente"]]
    hallazgos = []
    if faltantes:
        hallazgos.append("Completar valores de " + ", ".join(faltantes))
    if sin_fuente:
        hallazgos.append("Documentar la fuente de " + ", ".join(sin_fuente))
    for key, label in (("alcance", "alcance"), ("conclusion", "conclusión"),
                       ("veredicto", "veredicto del cálculo")):
        if not revision[key]:
            hallazgos.append("Completar " + label)
    alertas = [revision["desviacion"]] if revision["desviacion"] else []
    if ficha["coverage"] != "referencia":
        alertas.append("Ficha con cobertura de referencia parcial o preliminar.")
    estado = "corregir" if hallazgos else "apto_alerta" if alertas else "apto"
    return {"estado": estado, "hallazgos": hallazgos, "alertas": alertas,
            "alcance": "Completitud y fuentes. Revisión técnica a cargo de los perfiles designados."}
