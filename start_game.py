import importlib.util
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys


DEPENDENCIAS_OBRIGATORIAS = {
    "colorama": "colorama",
    "pynput": "pynput",
}


def _in_virtualenv() -> bool:
    return (
        getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or bool(os.environ.get("VIRTUAL_ENV"))
    )


def _get_scripts_dir() -> Path:
    if _in_virtualenv():
        return Path(sys.executable).resolve().parent

    user_site = Path(site.getusersitepackages())
    if user_site.name == "site-packages":
        scripts_folder = "Scripts" if os.name == "nt" else "bin"
        return (user_site.parent / scripts_folder).resolve()

    fallback_scripts = Path(sys.executable).resolve().parent
    return fallback_scripts.resolve()


def _command_in_scripts_dir(command_name: str, scripts_dir: Path) -> bool:
    command_file = f"{command_name}.exe" if os.name == "nt" else command_name
    return (scripts_dir / command_file).exists()


def _ensure_scripts_on_process_path(scripts_dir: Path) -> None:
    current = os.environ.get("PATH", "")
    entries = [entry for entry in current.split(os.pathsep) if entry]
    target = os.path.normcase(os.path.normpath(str(scripts_dir)))
    for entry in entries:
        normalized_entry = os.path.normcase(os.path.normpath(entry))
        if normalized_entry == target:
            return

    os.environ["PATH"] = current + (os.pathsep if current else "") + str(scripts_dir)


def _ensure_scripts_on_user_path_windows(scripts_dir: Path) -> bool:
    if os.name != "nt" or _in_virtualenv():
        return False

    try:
        import winreg
    except ImportError:
        return False

    target = os.path.normcase(os.path.normpath(str(scripts_dir)))

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE,
        ) as key:
            try:
                current_path, value_type = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path, value_type = "", winreg.REG_EXPAND_SZ

            entries = [entry for entry in current_path.split(";") if entry]
            normalized_entries = {
                os.path.normcase(os.path.normpath(entry))
                for entry in entries
            }
            if target in normalized_entries:
                return False

            separator = ";" if current_path and not current_path.endswith(";") else ""
            updated_path = f"{current_path}{separator}{scripts_dir}" if current_path else str(scripts_dir)
            if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                value_type = winreg.REG_EXPAND_SZ
            winreg.SetValueEx(key, "Path", 0, value_type, updated_path)
            return True
    except OSError:
        return False


def _bootstrap_console_command() -> None:
    project_root = Path(__file__).resolve().parent
    if not (project_root / "pyproject.toml").exists():
        return

    scripts_dir = _get_scripts_dir()
    _ensure_scripts_on_process_path(scripts_dir)

    if shutil.which("fisching") or _command_in_scripts_dir("fisching", scripts_dir):
        _ensure_scripts_on_user_path_windows(scripts_dir)
        return

    print("Primeira execucao detectada. Instalando comando 'fisching'...")
    pip_command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-e",
        str(project_root),
    ]
    if not _in_virtualenv():
        pip_command.append("--user")

    try:
        subprocess.check_call(pip_command)
    except subprocess.CalledProcessError:
        print("Aviso: nao foi possivel instalar o comando 'fisching' automaticamente.")
        return

    scripts_dir = _get_scripts_dir()
    _ensure_scripts_on_process_path(scripts_dir)
    if _ensure_scripts_on_user_path_windows(scripts_dir):
        print("Comando instalado. Abra um novo terminal para usar 'fisching'.")


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


_bootstrap_console_command()
_instalar_dependencias_ausentes()

from utils.pesca import main


if __name__ == "__main__":
    main()
