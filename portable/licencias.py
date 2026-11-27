import importlib.metadata as metadata
from pathlib import Path
import shutil
import sys


def main(destino, frontend):
    destino.mkdir(parents=True, exist_ok=True)
    for paquete in metadata.distributions():
        name = paquete.metadata["Name"]
        for item in paquete.files or ():
            if ".dist-info" not in str(item) or not item.name.lower().startswith(
                ("license", "notice", "copying", "copyright")
            ):
                continue
            source = paquete.locate_file(item)
            if source.is_file():
                target = destino / name / item.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    for paquete in ("next", "react", "react-dom", "scheduler"):
        for source in (frontend / "node_modules" / paquete).glob("LICENSE*"):
            target = destino / paquete / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copyfile(python_license, destino / "Python-LICENSE.txt")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
