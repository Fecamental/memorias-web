from contextlib import asynccontextmanager
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from secrets import token_urlsafe
import asyncio
import json
import os

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .documentos import memoria_word, planilla
from .dominio import (
    Borrador, CATALOGO, Comando, Credencial, Nuevo, ROLES, TRANSICIONES, calculados, modelo_calculo, verificar,
)

COOKIE = os.getenv("MEMORIAS_SESSION_COOKIE", "memorias_sesion")
ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app):
    app.state.db = await asyncpg.create_pool(os.environ["MEMORIAS_DSN"], min_size=1, max_size=6)
    runtime = Path(os.environ.get("MEMORIAS_RUNTIME", ROOT / ".runtime"))
    app.state.cuentas = json.loads((runtime / "cuentas.json").read_text(encoding="utf-8-sig"))
    try:
        yield
    finally:
        await app.state.db.close()


app = FastAPI(title="Memorias de cálculo", lifespan=lifespan)


@app.middleware("http")
async def mismo_origen(request, call_next):
    origin = request.headers.get("origin")
    origins = os.getenv("MEMORIAS_ORIGINS", "http://localhost:14500,http://127.0.0.1:14500")
    if (request.method in {"POST", "PUT", "DELETE"} and origin
            and origin not in origins.split(",")):
        return JSONResponse({"detail": "Origen no autorizado"}, status_code=403)
    return await call_next(request)


def error(codigo, mensaje):
    raise HTTPException(codigo, mensaje)


def digest(value):
    return sha256(value.encode()).hexdigest()


async def actor(request: Request):
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 120:
        error(401, "Inicia sesión para continuar")
    user = await request.app.state.db.fetchval(
        "SELECT usuario FROM sesion WHERE hash=$1 AND vence>now()", digest(token))
    cuenta = request.app.state.cuentas.get(user)
    if not cuenta:
        error(401, "Sesión vencida")
    return {"usuario": user, "rol": cuenta["rol"], "nombre": ROLES[cuenta["rol"]]}


@app.get("/health")
async def health(request: Request):
    await request.app.state.db.fetchval("SELECT 1")
    return {"estado": "ok"}


@app.post("/sesion")
async def entrar(form: Credencial, request: Request, response: Response):
    cuenta = request.app.state.cuentas.get(form.usuario)
    esperado = cuenta["hash"] if cuenta else "0" * 64
    if not compare_digest(digest(form.clave), esperado) or not cuenta:
        await asyncio.sleep(0.15)
        error(401, "Credenciales incorrectas")
    token = token_urlsafe(32)
    pool = request.app.state.db
    await pool.execute("DELETE FROM sesion WHERE vence<=now() OR hash=$1",
                       digest(request.cookies.get(COOKIE, "")[:120]))
    await pool.execute(
        "INSERT INTO sesion VALUES ($1,$2,now()+interval '8 hours')", digest(token), form.usuario)
    response.set_cookie(COOKIE, token, max_age=28800, httponly=True, samesite="strict",
                        secure=os.getenv("MEMORIAS_COOKIE_SECURE") == "1")
    return {"usuario": form.usuario, "rol": cuenta["rol"], "nombre": ROLES[cuenta["rol"]]}


@app.delete("/sesion")
async def salir(request: Request, response: Response, usuario=Depends(actor)):
    await request.app.state.db.execute("DELETE FROM sesion WHERE hash=$1",
                                       digest(request.cookies[COOKIE]))
    response.delete_cookie(COOKIE)
    return {"estado": "ok"}


@app.get("/sesion")
async def sesion(usuario=Depends(actor)):
    return usuario


@app.get("/catalogo")
async def catalogo(usuario=Depends(actor)):
    return list(CATALOGO.values())


def tipo_valido(code):
    if code not in CATALOGO:
        error(404, "Tipo de cálculo desconocido")
    return CATALOGO[code]


def archivo(data, nombre, mimetype):
    return Response(data, media_type=mimetype, headers={
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.get("/catalogo/{tipo}/plantilla")
def exportar_plantilla(tipo: str, usuario=Depends(actor)):
    return archivo(planilla(tipo_valido(tipo)), f"{tipo}.xlsx", XLSX)


def ficha(datos):
    return {**dict(datos), "codigo": f"{datos['tipo'].upper()}-{datos['correlativo']:04d}"}


def es_propia(memoria, usuario):
    return usuario["rol"] == "elaborador" and memoria["generador"] == usuario["usuario"]


async def cargar(con, id, usuario, bloquear=False):
    if bloquear:
        memoria = await con.fetchrow("SELECT * FROM memoria WHERE id=$1 FOR UPDATE", id)
    else:
        memoria = await con.fetchrow("SELECT * FROM memoria WHERE id=$1", id)
    if memoria is None:
        error(404, "Memoria no encontrada")
    if usuario["rol"] == "elaborador" and not es_propia(memoria, usuario):
        error(404, "Memoria no encontrada")
    if usuario["rol"] != "elaborador" and memoria["estado"] == "borrador" and memoria["actual"] == 1:
        error(404, "Memoria no encontrada")
    return memoria


def revisar_version(memoria, version):
    if memoria["version"] != version:
        error(409, "La memoria cambió. Actualiza la ficha antes de volver a intentar.")


async def registrar(con, id, numero, usuario, accion, motivo, estado):
    await con.execute("""
        INSERT INTO movimiento (memoria_id,revision,actor,rol,accion,motivo,estado)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """, id, numero, usuario["usuario"], usuario["rol"], accion, motivo, estado)


async def revision_detalle(con, id, numero, solo_enviadas=False):
    revision = await con.fetchrow("""
        SELECT * FROM revision WHERE memoria_id=$1 AND numero=$2
        AND (NOT $3::boolean OR enviada IS NOT NULL)
        """, id, numero, solo_enviadas)
    if not revision:
        error(404, "Revisión no encontrada")
    variables = await con.fetch("""
        SELECT variable,valor,unidad,fuente FROM variable_revision
        WHERE memoria_id=$1 AND revision=$2 ORDER BY variable
        """, id, numero)
    return {**dict(revision), "reporte": json.loads(revision["reporte"]) if revision["reporte"] else None,
            "variables": [{**dict(v), "valor": str(v["valor"])} for v in variables]}


@app.get("/memorias")
async def bandeja(request: Request, usuario=Depends(actor)):
    if usuario["rol"] == "elaborador":
        items = await request.app.state.db.fetch(
            "SELECT * FROM memoria WHERE generador=$1 ORDER BY id DESC", usuario["usuario"])
    else:
        items = await request.app.state.db.fetch("""
            SELECT * FROM memoria WHERE estado<>'borrador' OR actual>1 ORDER BY id DESC
            """)
    return [ficha(m) for m in items]


@app.post("/memorias", status_code=201)
async def crear(form: Nuevo, request: Request, usuario=Depends(actor)):
    if usuario["rol"] != "elaborador":
        error(403, "Solo el elaborador puede generar una memoria")
    tipo = tipo_valido(form.tipo)
    async with request.app.state.db.acquire() as con, con.transaction():
        numero = await con.fetchval("""
            INSERT INTO correlativo_tipo AS c VALUES ($1,1)
            ON CONFLICT (tipo) DO UPDATE SET numero=c.numero+1 RETURNING numero
            """, form.tipo)
        item = await con.fetchrow("""
            INSERT INTO memoria (tipo,correlativo,titulo,generador,estado,actual)
            VALUES ($1,$2,$3,$4,'borrador',1) RETURNING *
            """, form.tipo, numero, form.titulo, usuario["usuario"])
        await con.execute("INSERT INTO revision (memoria_id,numero,generador,modelo) VALUES ($1,1,$2,$3)",
                          item["id"], usuario["usuario"], tipo["modelo"])
        await registrar(con, item["id"], 1, usuario, "crear", "", "borrador")
    return ficha(item)


@app.get("/memorias/{id}")
async def ver(id: int, request: Request, numero: int | None = None, usuario=Depends(actor)):
    async with request.app.state.db.acquire() as con, con.transaction(isolation="repeatable_read", readonly=True):
        item = await cargar(con, id, usuario)
        solo_enviadas = usuario["rol"] != "elaborador"
        versiones = await con.fetch("""
            SELECT numero, enviada FROM revision WHERE memoria_id=$1
            AND (NOT $2::boolean OR enviada IS NOT NULL) ORDER BY numero DESC
            """, id, solo_enviadas)
        revision = await revision_detalle(con, id, numero if numero is not None else versiones[0]["numero"],
                                          solo_enviadas)
        movimientos = await con.fetch("""
            SELECT m.* FROM movimiento m JOIN revision r
            ON r.memoria_id=m.memoria_id AND r.numero=m.revision
            WHERE m.memoria_id=$1 AND (NOT $2::boolean OR r.enviada IS NOT NULL)
            ORDER BY m.id DESC
            """, id, solo_enviadas)
    acciones = [key for key, (rol, previos, _, _) in TRANSICIONES.items()
                if rol == usuario["rol"] and item["estado"] in previos]
    if item["estado"] == "borrador" and es_propia(item, usuario):
        acciones.extend(("guardar", "verificar"))
        if not revision["reporte"] or revision["reporte"]["estado"] == "corregir":
            acciones.remove("enviar")
    if revision["numero"] != item["actual"]:
        acciones = []
    return {"memoria": ficha(item), "revision": revision, "revisiones": versiones,
            "tipo": modelo_calculo(item["tipo"], revision["modelo"]),
            "movimientos": movimientos, "acciones": acciones}


def nuevo_valor(id, numero, codigo, valor, fuente, campos):
    return (id, numero, codigo, valor, campos[codigo]["unit"], fuente)


@app.put("/memorias/{id}/borrador")
async def guardar(id: int, form: Borrador, request: Request, usuario=Depends(actor)):
    async with request.app.state.db.acquire() as con, con.transaction():
        item = await cargar(con, id, usuario, bloquear=True)
        if not es_propia(item, usuario):
            error(403, "Solo el elaborador puede editar su borrador")
        revisar_version(item, form.version)
        if item["estado"] != "borrador":
            error(409, "La revisión ya está cerrada para edición")
        numero = item["actual"]
        modelo = await con.fetchval("SELECT modelo FROM revision WHERE memoria_id=$1 AND numero=$2", id, numero)
        tipo = modelo_calculo(item["tipo"], modelo)
        campos = {f["key"]: f for f in tipo["fields"]}
        valores = {}
        filas = []
        for codigo, dato in form.variables.items():
            if codigo not in campos or campos[codigo]["automatic"]:
                error(422, f"Variable no editable: {codigo}")
            valores[codigo] = dato.valor
            filas.append(nuevo_valor(id, numero, codigo, dato.valor, dato.fuente, campos))
        for codigo, valor in calculados(item["tipo"], valores).items():
            if codigo in campos and campos[codigo]["automatic"]:
                filas.append(nuevo_valor(id, numero, codigo, valor, tipo["source"], campos))
        await con.execute("""
            UPDATE revision SET alcance=$3,desviacion=$4,conclusion=$5,veredicto=$6,reporte=NULL
            WHERE memoria_id=$1 AND numero=$2
            """, id, numero, form.alcance, form.desviacion, form.conclusion, form.veredicto)
        await con.execute("DELETE FROM variable_revision WHERE memoria_id=$1 AND revision=$2", id, numero)
        await con.executemany("INSERT INTO variable_revision VALUES ($1,$2,$3,$4,$5,$6)", filas)
        version = await con.fetchval("UPDATE memoria SET version=version+1 WHERE id=$1 RETURNING version", id)
    return {"version": version}


@app.post("/memorias/{id}/{accion}")
async def transitar(id: int, accion: str, form: Comando, request: Request, usuario=Depends(actor)):
    async with request.app.state.db.acquire() as con, con.transaction():
        item = await cargar(con, id, usuario, bloquear=True)
        revisar_version(item, form.version)
        numero = item["actual"]
        if accion == "verificar":
            if not es_propia(item, usuario):
                error(403, "Solo el elaborador puede verificar su borrador")
            if item["estado"] != "borrador":
                error(409, "La revisión ya fue enviada")
            revision = await revision_detalle(con, id, numero)
            reporte = verificar(item["tipo"], revision, revision["variables"])
            await con.execute("UPDATE revision SET reporte=$3::jsonb WHERE memoria_id=$1 AND numero=$2",
                              id, numero, json.dumps(reporte))
            await con.execute("UPDATE memoria SET version=version+1 WHERE id=$1", id)
            await registrar(con, id, numero, usuario, accion, reporte["estado"], "borrador")
            return reporte

        if accion not in TRANSICIONES:
            error(404, "Acción desconocida")
        rol, previos, destino, requiere_motivo = TRANSICIONES[accion]
        if usuario["rol"] != rol:
            error(403, "Tu perfil no tiene permiso para esta acción")
        if item["estado"] not in previos:
            error(409, "La acción no corresponde al estado actual")
        if requiere_motivo and not form.motivo:
            error(422, "Indica el motivo")
        if accion == "enviar":
            revision = await revision_detalle(con, id, numero)
            if not revision["reporte"] or revision["reporte"]["estado"] == "corregir":
                error(409, "Completa la verificación antes de enviar")
            await con.execute("UPDATE revision SET enviada=now() WHERE memoria_id=$1 AND numero=$2", id, numero)
        if accion == "nueva_revision":
            await con.execute("""
                INSERT INTO revision (memoria_id,numero,modelo,generador,alcance,desviacion,conclusion,veredicto)
                SELECT memoria_id,numero+1,modelo,generador,alcance,desviacion,conclusion,veredicto
                FROM revision WHERE memoria_id=$1 AND numero=$2
                """, id, numero)
            await con.execute("""
                INSERT INTO variable_revision
                SELECT memoria_id,revision+1,variable,valor,unidad,fuente
                FROM variable_revision WHERE memoria_id=$1 AND revision=$2
                """, id, numero)
            numero += 1
        await con.execute(
            "UPDATE memoria SET estado=$2, actual=$3, version=version+1 WHERE id=$1", id, destino, numero)
        await registrar(con, id, numero, usuario, accion, form.motivo, destino)
    return {"estado": destino, "revision": numero}


@app.get("/memorias/{id}/revision/{numero}/{formato}")
async def descargar(id: int, numero: int, formato: str, request: Request, usuario=Depends(actor)):
    async with request.app.state.db.acquire() as con, con.transaction(isolation="repeatable_read", readonly=True):
        item = ficha(await cargar(con, id, usuario))
        revision = await revision_detalle(con, id, numero, usuario["rol"] != "elaborador")
    tipo = modelo_calculo(item["tipo"], revision["modelo"])
    nombre = f"{item['codigo']}-R{numero}"
    if formato == "xlsx":
        return archivo(await asyncio.to_thread(planilla, tipo, item, revision), f"{nombre}.xlsx", XLSX)
    if formato == "docx":
        return archivo(await asyncio.to_thread(memoria_word, tipo, item, revision), f"{nombre}.docx", DOCX)
    error(404, "Formato desconocido")
