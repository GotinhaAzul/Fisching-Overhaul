import importlib.util
import subprocess
import sys


DEPENDENCIAS_OBRIGATORIAS = {
    "pygame": "pygame",
    "colorama": "colorama",
    "pynput": "pynput",
}


def _instalar_dependencias_ausentes() -> None:
    ausentes = [
        pacote
        for modulo, pacote in DEPENDENCIAS_OBRIGATORIAS.items()
        if importlib.util.find_spec(modulo) is None
    ]

    if not ausentes:
        return

    print(
        "Dependências ausentes detectadas. Instalando automaticamente: "
        + ", ".join(ausentes)
    )
    subprocess.check_call([sys.executable, "-m", "pip", "install", *ausentes])


_instalar_dependencias_ausentes()

from utils.pesca import main


if __name__ == "__main__":
    main()
