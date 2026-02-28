import importlib.util
import json
import os
from importlib import metadata as importlib_metadata
from pathlib import Path
import shutil
import site
import subprocess
import sys
from urllib.parse import unquote, urlparse


DEPENDENCIAS_OBRIGATORIAS = {
    "colorama": "colorama",
    "pynput": "pynput",
}
COMANDO_FISCHING = "fisching"
COMANDO_ENTRYPOINT = "start_game:main"
PACOTE_DISTRIBUICAO = "fisching-overhaul"


def _entrypoint_module_name(entrypoint: str) -> str:
    return entrypoint.split(":", 1)[0].strip()


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


def _normalize_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve())))


def _distribution_by_name(distribution_name: str):
    try:
        return importlib_metadata.distribution(distribution_name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _distribution_direct_url_file(distribution) -> Path | None:
    files = distribution.files or ()
    for file in files:
        if file.name == "direct_url.json":
            return Path(distribution.locate_file(file))
    return None


def _file_url_to_path(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None

    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return None

    if parsed.netloc and parsed.netloc not in ("", "localhost"):
        raw_path = f"//{parsed.netloc}{raw_path}"

    if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]

    return Path(raw_path).resolve()


def _editable_source_root(distribution) -> Path | None:
    direct_url_file = _distribution_direct_url_file(distribution)
    if direct_url_file is None:
        return None

    try:
        direct_url_data = json.loads(direct_url_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    dir_info = direct_url_data.get("dir_info")
    if not isinstance(dir_info, dict) or not dir_info.get("editable"):
        return None

    url = direct_url_data.get("url")
    if not isinstance(url, str):
        return None

    return _file_url_to_path(url)


def _distribution_has_expected_entrypoint(distribution) -> bool:
    for entrypoint in distribution.entry_points:
        if entrypoint.group != "console_scripts":
            continue
        if entrypoint.name != COMANDO_FISCHING:
            continue
        return entrypoint.value == COMANDO_ENTRYPOINT
    return False


def _entrypoint_module_is_importable(module_name: str, probe_cwd: Path | None = None) -> bool:
    if not module_name:
        return False

    check_code = (
        "import importlib.util, sys; "
        f"sys.exit(0 if importlib.util.find_spec({module_name!r}) else 1)"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            cwd=str(probe_cwd) if probe_cwd else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False

    return result.returncode == 0


def _console_command_needs_reinstall(project_root: Path, scripts_dir: Path) -> bool:
    distribution = _distribution_by_name(PACOTE_DISTRIBUICAO)
    if distribution is None:
        return True

    if not _distribution_has_expected_entrypoint(distribution):
        return True

    entrypoint_module = _entrypoint_module_name(COMANDO_ENTRYPOINT)
    probe_cwd = scripts_dir if scripts_dir.exists() else None
    if not _entrypoint_module_is_importable(entrypoint_module, probe_cwd):
        return True

    editable_source = _editable_source_root(distribution)
    if editable_source is None:
        return False

    return _normalize_path(editable_source) != _normalize_path(project_root)


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

    command_exists = bool(
        shutil.which(COMANDO_FISCHING) or _command_in_scripts_dir(COMANDO_FISCHING, scripts_dir)
    )
    if command_exists and not _console_command_needs_reinstall(project_root, scripts_dir):
        _ensure_scripts_on_user_path_windows(scripts_dir)
        return

    if command_exists:
        print("Instalacao existente do comando 'fisching' esta desatualizada. Reinstalando...")
    else:
        print("Primeira execucao detectada. Instalando comando 'fisching'...")
    pip_command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-e",
        str(project_root),
        "--force-reinstall",
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
