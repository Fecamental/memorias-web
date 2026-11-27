from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import argparse

from .documentos import planilla
from .dominio import CATALOGO


def main():
    parser = argparse.ArgumentParser(description="Exporta las planillas del catálogo vigente")
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.destino, "w", compression=ZIP_DEFLATED) as bundle:
        for tipo in CATALOGO.values():
            bundle.writestr(f"{tipo['category']}/{tipo['code']}.xlsx", planilla(tipo))
    print(f"{len(CATALOGO)} planillas en {args.destino}")


if __name__ == "__main__":
    main()
