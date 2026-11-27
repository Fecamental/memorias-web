import argparse
from hashlib import file_digest
from pathlib import Path, PurePosixPath
import shutil
from zipfile import ZipFile

DIGEST = "74f3740a2e7844118857f297c2067d226f8f2b0652de96022ce54bb27cd60a79"
BINARIOS = {
    "postgres.exe", "initdb.exe", "pg_ctl.exe",
    "icudt77.dll", "icuin77.dll", "icuuc77.dll", "libcrypto-3-x64.dll", "libiconv-2.dll",
    "libintl-9.dll", "liblz4.dll", "libpq.dll", "libssl-3-x64.dll", "libxml2.dll",
    "libzstd.dll", "zlib1.dll",
}
RUNTIME = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
AVISOS = {"server_license.txt", "commandlinetools_3rd_party_licenses.txt"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("crt", type=Path)
    args = parser.parse_args()
    with args.zip.open("rb") as archivo:
        if file_digest(archivo, "sha256").hexdigest() != DIGEST:
            raise ValueError("El archivo PostgreSQL no coincide con el SHA-256 oficial.")
    with ZipFile(args.zip) as zip:
        for source in zip.namelist():
            p = PurePosixPath(source)
            partes = p.parts
            if not partes or partes[0] != "pgsql" or ".." in partes or source.endswith("/"):
                continue
            if (partes[1] in {"share", "lib"} or p.name in AVISOS
                    or (partes[1] == "bin" and p.name in BINARIOS)):
                target = args.destino.joinpath(*partes[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with zip.open(source) as data, target.open("wb") as output:
                    shutil.copyfileobj(data, output)
    for name in RUNTIME:
        shutil.copyfile(args.crt / name, args.destino / "bin" / name)


if __name__ == "__main__":
    main()
