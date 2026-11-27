import asyncio
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
import json

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"


async def preparar_esquema(con, password):
    await con.execute((ROOT / "database" / "001_inicial.sql").read_text(encoding="utf-8"))
    if not await con.fetchval("SELECT 1 FROM pg_roles WHERE rolname='memorias_api'"):
        literal = await con.fetchval("SELECT quote_literal($1::text)", password)
        await con.execute("CREATE ROLE memorias_api LOGIN PASSWORD " + literal)
    await con.execute("""
        GRANT USAGE ON SCHEMA public TO memorias_api;
        GRANT SELECT, INSERT, UPDATE ON memoria, revision, correlativo_tipo TO memorias_api;
        GRANT SELECT, INSERT, DELETE ON variable_revision, sesion TO memorias_api;
        GRANT SELECT, INSERT ON movimiento TO memorias_api;
        GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO memorias_api;
    """)


def crear_cuentas(runtime):
    roles = ("elaborador", "revisor", "responsable")
    cuentas = {rol: {"rol": rol, "hash": sha256(rol.encode()).hexdigest()} for rol in roles}
    accesos = "".join(f"{rol}: {rol}\n" for rol in roles)
    destino = runtime / "cuentas.json"
    listado = runtime / "accesos.txt"
    try:
        if (json.loads(destino.read_text(encoding="utf-8-sig")) == cuentas
                and listado.read_text(encoding="utf-8-sig") == accesos):
            return False
    except (FileNotFoundError, ValueError):
        pass
    for archivo, contenido in ((listado, accesos), (destino, json.dumps(cuentas))):
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(contenido, encoding="utf-8")
        temporal.replace(archivo)
    return True


async def main():
    admin = (RUNTIME / "db-password").read_text(encoding="utf-8-sig").strip()
    dsn = RUNTIME / "api-dsn"
    if not dsn.exists():
        password = token_urlsafe(30)
        dsn.write_text(f"postgresql://memorias_api:{password}@127.0.0.1:15484/memorias_web", encoding="utf-8")
    password = dsn.read_text(encoding="utf-8").split("@", 1)[0].rsplit(":", 1)[1]
    con = await asyncpg.connect(user="postgres", password=admin, host="127.0.0.1",
                                port=15484, database="memorias_web")
    try:
        await preparar_esquema(con, password)
    finally:
        await con.close()
    crear_cuentas(RUNTIME)


if __name__ == "__main__":
    asyncio.run(main())
