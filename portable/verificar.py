import argparse
from contextlib import contextmanager
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from time import monotonic, sleep
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]


def esperar(proceso, runtime):
    limite = monotonic() + 65
    while proceso.poll() is None and monotonic() < limite:
        try:
            estado = json.loads((runtime / "servidor.json").read_text(encoding="utf-8"))
            with urlopen(estado["url"] + "/estado-portable", timeout=1) as res:
                if res.read().decode() == estado["token"]:
                    return estado["url"]
        except (OSError, ValueError):
            sleep(0.4)
    detalle = (runtime / "arranque.log").read_text(encoding="utf-8", errors="replace")
    registro = runtime / "postgres.log"
    if registro.exists():
        detalle += "\n" + registro.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError(detalle)


@contextmanager
def ejecutar(exe, runtime):
    runtime.mkdir(exist_ok=True)
    sistema = Path(os.environ["WINDIR"])
    env = os.environ.copy()
    env["PATH"] = str(sistema / "System32") + ";" + str(sistema)
    with (runtime / "arranque.log").open("wb") as log:
        proceso = subprocess.Popen(
            [str(exe), "--sin-navegador", "--datos", str(runtime)],
            env=env, cwd=runtime, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            yield esperar(proceso, runtime)
        finally:
            if proceso.poll() is None:
                proceso.send_signal(signal.CTRL_BREAK_EVENT)
                proceso.wait(timeout=35)
                assert proceso.returncode == 0, proceso.returncode
                assert not (runtime / "postgres-data" / "postmaster.pid").exists()


def principal():
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    args = parser.parse_args()
    exe = args.exe.resolve(strict=True)
    runtime = Path(tempfile.mkdtemp(prefix="memorias-portable-prueba-"))
    print(f"Datos de prueba: {runtime}", flush=True)
    accesos = runtime / "accesos.txt"
    with ejecutar(exe, runtime) as url:
        env = {**os.environ, "MEMORIAS_TEST_URL": url + "/api",
               "MEMORIAS_TEST_WEB": url, "MEMORIAS_TEST_CREDENCIALES": str(accesos),
               "MEMORIAS_TEST_CAPTURA": str(runtime / "ficha.png")}
        subprocess.run(["node", "tests/flujo.mjs"], cwd=ROOT, env=env, check=True)
        if env.get("MEMORIAS_PLAYWRIGHT"):
            subprocess.run(["node", "tests/interfaz.mjs"], cwd=ROOT, env=env, check=True)
        credenciales = accesos.read_bytes()
        assert dict(linea.split(": ") for linea in credenciales.decode().splitlines()) == {
            "elaborador": "elaborador", "revisor": "revisor", "responsable": "responsable",
        }
    with ejecutar(exe, runtime) as url:
        assert accesos.read_bytes() == credenciales
        clave = dict(linea.split(": ") for linea in credenciales.decode().splitlines())["elaborador"]
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        body = json.dumps({"usuario": "elaborador", "clave": clave}).encode()
        opener.open(Request(url + "/api/sesion", data=body,
                            headers={"Content-Type": "application/json"})).close()
        with opener.open(url + "/api/memorias") as response:
            registros = json.load(response)
        assert any(m["codigo"] == "VIGA-0001" and m["estado"] == "aprobada" for m in registros)
    print("Portátil verificado: arranque limpio, flujo, cierre y persistencia tras reapertura.")


if __name__ == "__main__":
    principal()
