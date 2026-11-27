import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
import ctypes
import json
import msvcrt
import os
from pathlib import Path
from secrets import token_urlsafe
import signal
import socket
import subprocess
import sys
import threading
from time import sleep
from urllib.request import urlopen
import webbrowser

import asyncpg
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles
import uvicorn

from backend.setup_local import crear_cuentas, preparar_esquema

HOST = "127.0.0.1"
DATABASE = "memorias_web"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
PG_BIN = ASSETS / "postgresql" / "bin"


def pg(nombre, *argumentos, **kwargs):
    # El bootloader agrega su directorio de DLL. PostgreSQL usa sus propias DLL.
    if getattr(sys, "frozen", False):
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        return subprocess.Popen(
            [str(PG_BIN / (nombre + ".exe")), *map(str, argumentos)],
            creationflags=subprocess.CREATE_NO_WINDOW, **kwargs,
        )
    finally:
        if getattr(sys, "frozen", False):
            ctypes.windll.kernel32.SetDllDirectoryW(str(ASSETS))


def pg_cmd(nombre, *argumentos, log):
    with pg(nombre, *argumentos, stdout=log, stderr=subprocess.STDOUT) as proceso:
        return proceso.wait()


def secreto(path):
    if not path.exists():
        path.write_text(token_urlsafe(36) + "\n", encoding="ascii")
    return path.read_text(encoding="ascii").strip()


@contextmanager
def instancia(runtime):
    with (runtime / "instancia.lock").open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"1")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
        else:
            try:
                yield True
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def puerto(preferido):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind((HOST, preferido))
        except OSError:
            if not preferido:
                raise
            sock.bind((HOST, 0))
        yield sock


async def conectar(usuario, clave, port, database):
    return await asyncpg.connect(
        user=usuario, password=clave, host=HOST, port=port,
        database=database, timeout=2,
    )


async def provisionar(proceso, clave, api_clave, port):
    for _ in range(60):
        if proceso.poll() is not None:
            raise RuntimeError("La base integrada se cerró durante el arranque.")
        try:
            con = await conectar("postgres", clave, port, "postgres")
            break
        except (OSError, TimeoutError, asyncpg.CannotConnectNowError):
            await asyncio.sleep(0.25)
    else:
        raise RuntimeError("La base integrada no respondió durante el arranque.")
    try:
        if not await con.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", DATABASE):
            await con.execute("CREATE DATABASE memorias_web")
    finally:
        await con.close()
    con = await conectar("postgres", clave, port, DATABASE)
    try:
        await preparar_esquema(con, api_clave)
    finally:
        await con.close()


@contextmanager
def base_local(runtime):
    data = runtime / "postgres-data"
    clave = secreto(runtime / "db-password")
    api_clave = secreto(runtime / "api-password")
    with (runtime / "postgres.log").open("ab") as log:
        if not (data / "PG_VERSION").exists():
            codigo = pg_cmd("initdb", "-D", data, "-U", "postgres", "--encoding=UTF8",
                            "--locale=C", "--auth=scram-sha-256",
                            "--pwfile", runtime / "db-password", log=log)
            if codigo:
                raise RuntimeError("No se pudo crear la base integrada.")
        if pg_cmd("pg_ctl", "status", "-D", data, log=log) == 0:
            if pg_cmd("pg_ctl", "stop", "-D", data, "-m", "fast", "-w", "-t", "15", log=log):
                raise RuntimeError("La instancia anterior de la base sigue abierta.")
        with puerto(0) as sock:
            db_port = sock.getsockname()[1]
        with pg("postgres", "-D", data, "-h", HOST, "-p", db_port,
                stdout=log, stderr=subprocess.STDOUT) as proceso:
            try:
                asyncio.run(provisionar(proceso, clave, api_clave, db_port))
                yield f"postgresql://memorias_api:{api_clave}@{HOST}:{db_port}/{DATABASE}"
            finally:
                if proceso.poll() is None:
                    pg_cmd("pg_ctl", "stop", "-D", data, "-m", "fast", "-w", "-t", "15", log=log)
                    try:
                        proceso.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proceso.terminate()
                        proceso.wait(timeout=5)


def abrir(url, token, browser=True):
    for _ in range(40):
        try:
            with urlopen(url + "/estado-portable", timeout=1) as res:
                if res.read().decode() == token:
                    if browser:
                        webbrowser.open(url)
                    return True
        except OSError:
            sleep(0.25)
    return False


def servir(runtime, sock, dsn, no_browser):
    url = f"http://{HOST}:{sock.getsockname()[1]}"
    os.environ["MEMORIAS_DSN"] = dsn
    os.environ["MEMORIAS_RUNTIME"] = str(runtime)
    os.environ["MEMORIAS_ORIGINS"] = url
    os.environ["MEMORIAS_SESSION_COOKIE"] = "memorias_sesion_portable"
    from backend.app import app as api

    token = token_urlsafe(24)

    @asynccontextmanager
    async def lifespan(_):
        async with api.router.lifespan_context(api):
            yield

    web = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    web.get("/estado-portable", response_class=PlainTextResponse)(lambda: token)
    web.mount("/api", api)
    web.mount("/", StaticFiles(directory=ASSETS / "web", html=True))

    archivo = runtime / "servidor.json"
    archivo.write_text(json.dumps({"url": url, "token": token}), encoding="utf-8")
    print(f"Memorias Web     {url}", flush=True)
    print(f"Usuarios y claves     {runtime / 'accesos.txt'}", flush=True)
    print("Presiona Ctrl+C para cerrar la aplicación.", flush=True)
    if not no_browser:
        threading.Thread(target=abrir, args=(url, token), daemon=True).start()
    config = uvicorn.Config(web, host=HOST, port=sock.getsockname()[1], access_log=False,
                            loop="asyncio", http="h11", ws="none")
    server = uvicorn.Server(config)
    anterior = signal.signal(signal.SIGBREAK, server.handle_exit)
    try:
        server.run(sockets=[sock])
    finally:
        signal.signal(signal.SIGBREAK, anterior)
        archivo.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Memorias Web para Windows")
    parser.add_argument("--sin-navegador", action="store_true")
    parser.add_argument("--datos", type=Path,
                        default=Path(os.environ["LOCALAPPDATA"]) / "MemoriasWebPortable")
    args = parser.parse_args()
    runtime = args.datos.resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    if sys.stdout:
        sys.stdout.reconfigure(errors="replace")
    with instancia(runtime) as libre:
        if not libre:
            try:
                estado = json.loads((runtime / "servidor.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                print("Memorias Web ya se está iniciando.", flush=True)
                return
            abrir(estado["url"], estado["token"], not args.sin_navegador)
            return
        print("Preparando Memorias Web…", flush=True)
        nuevas = crear_cuentas(runtime)
        try:
            with puerto(14550) as sock, base_local(runtime) as dsn:
                if nuevas and not args.sin_navegador:
                    os.startfile(runtime / "accesos.txt")
                servir(runtime, sock, dsn, args.sin_navegador)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            print(f"No se pudo iniciar Memorias Web. {exc}", file=sys.stderr, flush=True)
            print(f"Registro de la base: {runtime / 'postgres.log'}", file=sys.stderr, flush=True)
            if not args.sin_navegador:
                input("Presiona Intro para cerrar…")
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
