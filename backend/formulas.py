from dataclasses import dataclass
from decimal import Decimal
from math import pi, radians, tan
from typing import Callable

DOS_TERCIOS = Decimal(2) / 3
PI = Decimal(str(pi))
PULGADA = Decimal("0.0254")
CV_KW = Decimal("0.73549875")


@dataclass(frozen=True)
class Formula:
    entradas: tuple[str, ...]
    calcular: Callable[..., Decimal]
    expresion: str
    validar: Callable[..., bool]
    condicion: str

    def excel(self, celdas):
        refs = {key: f"C{celdas[key]}" for key in self.entradas}
        argumentos = ",".join(refs.values())
        condicion = self.condicion.format_map(refs)
        expresion = self.expresion.format_map(refs)
        return f'=IFERROR(IF(AND(COUNT({argumentos})={len(refs)},{condicion}),{expresion},""),"")'


def formula(entradas, calcular, expresion, validar, condicion):
    return Formula(tuple(entradas.split()), calcular, expresion, validar, condicion)


def no_negativos(*args):
    return all(x >= 0 for x in args)


def sumar(entradas):
    claves = entradas.split()
    return formula(entradas, lambda *args: sum(args), "+".join("{" + k + "}" for k in claves),
                   lambda *args: True, "TRUE")


FORMULAS = {
    "viga": {
        "mu": formula("wu l", lambda wu, l: wu * l**2 / 8, "{wu}*{l}^2/8",
                      lambda wu, l: wu >= 0 and l > 0, "{wu}>=0,{l}>0"),
        "mn": formula("mu phi", lambda mu, phi: mu / phi, "{mu}/{phi}",
                      lambda mu, phi: 0 < phi <= 1, "{phi}>0,{phi}<=1"),
    },
    "muro-gravedad": {
        "bz": formula("tw bt bpunta", lambda *xs: sum(xs), "{tw}+{bt}+{bpunta}",
                      no_negativos, "{tw}>=0,{bt}>=0,{bpunta}>=0"),
        "hsa": formula("hw hz", lambda *xs: sum(xs), "{hw}+{hz}", no_negativos, "{hw}>=0,{hz}>=0"),
    },
    "losa": {
        "mrel": formula("ls ll", lambda ls, ll: ls / ll, "{ls}/{ll}",
                        lambda ls, ll: 0 < ls <= ll, "{ls}>0,{ls}<={ll}"),
    },
    "muro-tem": {
        "ka": formula("phi", lambda phi: Decimal(str(tan(radians(45 - float(phi) / 2)) ** 2)),
                      "TAN(RADIANS(45-{phi}/2))^2", lambda phi: 0 <= phi < 90, "{phi}>=0,{phi}<90"),
    },
    "canales": {
        "ancho": formula("b z y", lambda b, z, y: b + 2*y*z, "{b}+2*{y}*{z}",
                         lambda b, z, y: b >= 0 and z >= 0 and y > 0, "{b}>=0,{z}>=0,{y}>0"),
        "area": formula("b z y", lambda b, z, y: b*y + z*y*y, "{b}*{y}+{z}*{y}^2",
                        lambda b, z, y: b >= 0 and z >= 0 and y > 0, "{b}>=0,{z}>=0,{y}>0"),
        "perimetro": formula("b z y", lambda b, z, y: b + 2*y*(1+z*z).sqrt(),
                             "{b}+2*{y}*SQRT(1+{z}^2)", lambda b, z, y: b >= 0 and z >= 0 and y > 0,
                             "{b}>=0,{z}>=0,{y}>0"),
        "radio": formula("area perimetro", lambda a, p: a/p, "{area}/{perimetro}",
                         lambda a, p: a > 0 and p > 0, "{area}>0,{perimetro}>0"),
        "vel": formula("radio s n", lambda r, s, n: r**DOS_TERCIOS*s.sqrt()/n,
                       "{radio}^(2/3)*SQRT({s})/{n}", lambda r, s, n: r > 0 and s >= 0 and n > 0,
                       "{radio}>0,{s}>=0,{n}>0"),
        "cap": formula("area vel", lambda a, v: a*v, "{area}*{vel}", no_negativos, "{area}>=0,{vel}>=0"),
    },
    "tuberias-impulsion": {
        "hmt": sumar("dz hvel hper hpi hdp"),
        "pot_cv": formula("rho q hmt eta", lambda r, q, h, e: r*q*h/(75*e),
                          "{rho}*{q}*{hmt}/(75*{eta})",
                          lambda r, q, h, e: r > 0 and q >= 0 and h >= 0 and 0 < e <= 1,
                          "{rho}>0,{q}>=0,{hmt}>=0,{eta}>0,{eta}<=1"),
        "pot": formula("pot_cv", lambda p: p*CV_KW, "{pot_cv}*0.73549875",
                       no_negativos, "{pot_cv}>=0"),
    },
    "tuberias-gravedad": {
        "vel": formula("q d", lambda q, d: (q/1000)/(PI*(d*PULGADA)**2/4),
                       "({q}/1000)/(PI()*({d}*0.0254)^2/4)", lambda q, d: q >= 0 and d > 0,
                       "{q}>=0,{d}>0"),
        "cp1": formula("cp0 hf", lambda c, h: c-h, "{cp0}-{hf}", lambda c, h: h >= 0, "{hf}>=0"),
        "p0": formula("cp0 z0", lambda c, z: c-z, "{cp0}-{z0}", lambda *xs: True, "TRUE"),
        "p1": formula("cp1 z1", lambda c, z: c-z, "{cp1}-{z1}", lambda *xs: True, "TRUE"),
    },
    "zapatas": {
        "sn": formula("sigma gm hf q", lambda s, g, h, q: s*10-g*h-q/1000,
                      "{sigma}*10-{gm}*{hf}-{q}/1000", no_negativos,
                      "{sigma}>=0,{gm}>=0,{hf}>=0,{q}>=0"),
        "az": formula("pd pl sn", lambda pd, pl, sn: (pd+pl)/sn, "({pd}+{pl})/{sn}",
                      lambda pd, pl, sn: pd >= 0 and pl >= 0 and sn > 0, "{pd}>=0,{pl}>=0,{sn}>0"),
    },
}


def calculados(tipo, valores):
    resultados = {}
    valores = dict(valores)
    for clave, regla in FORMULAS.get(tipo, {}).items():
        argumentos = [valores.get(k) for k in regla.entradas]
        if all(x is not None for x in argumentos) and regla.validar(*argumentos):
            resultado = regla.calcular(*argumentos)
            valores[clave] = resultado
            resultados[clave] = round(resultado, 8)
    return resultados
