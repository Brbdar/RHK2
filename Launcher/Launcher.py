#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# =============================================================================
# RHK Befundassistent Offline Builder
#
# Ergebnisstruktur
# releases/windows/dist/RHK_Befundassistent/...
# releases/windows/zip/RHK_Befundassistent_windows_<version>.zip
#
# releases/macos/... entsteht nur, wenn du das gleiche Script auf macOS ausführst
#
# Keine .venv im Projektordner
# Es wird eine temporäre Build Umgebung erzeugt und danach entfernt
#
# Zusätzlich: Runtime Hook, der beim Start der EXE automatisch den Browser öffnet
# =============================================================================

import sys
import json
import shutil
import zipfile
import hashlib
import subprocess
import platform
import tempfile
from pathlib import Path
from datetime import datetime


ANWENDUNGS_NAME = "RHK_Befundassistent"

PROJEKTWURZEL = Path(__file__).resolve().parent.parent
if str(PROJEKTWURZEL) not in sys.path:
    sys.path.insert(0, str(PROJEKTWURZEL))

from rhk_release_manifest import assert_release_ready, copy_release_bundle_files, get_release_build_config


def fuehre_subprozess_aus(command_argumente: list[str], arbeitsverzeichnis: Path) -> None:
    print("\nAusführen:")
    print(" ".join(str(a) for a in command_argumente))
    subprocess.check_call(command_argumente, cwd=str(arbeitsverzeichnis))


def ermittle_launcher_verzeichnis() -> Path:
    return Path(__file__).resolve().parent


def ermittle_projektwurzel_verzeichnis() -> Path:
    return ermittle_launcher_verzeichnis().parent


def ermittle_betriebssystem_schluessel() -> str:
    system_name = platform.system().lower()
    if "windows" in system_name:
        return "windows"
    if "darwin" in system_name or "mac" in system_name:
        return "macos"
    raise RuntimeError("Dieses Build Skript unterstützt nur Windows und macOS.")


def ermittle_versions_string(projektwurzel_verzeichnis: Path) -> str:
    version_datei = projektwurzel_verzeichnis / "VERSION.txt"
    if version_datei.exists():
        inhalt = version_datei.read_text(encoding="utf-8").strip()
        if inhalt:
            return inhalt
    return datetime.now().strftime("%Y.%m.%d.%H%M")


def hole_release_build_pfade(projektwurzel_verzeichnis: Path) -> tuple[Path, Path]:
    build = get_release_build_config(projektwurzel_verzeichnis)
    startdatei = projektwurzel_verzeichnis / build["entry_point"]
    requirements_datei = projektwurzel_verzeichnis / build["requirements"]
    return startdatei, requirements_datei


def ermittle_release_basisordner(projektwurzel_verzeichnis: Path) -> Path:
    return projektwurzel_verzeichnis / "releases"


def ermittle_release_os_ordner(projektwurzel_verzeichnis: Path, os_schluessel: str) -> Path:
    return ermittle_release_basisordner(projektwurzel_verzeichnis) / os_schluessel


def ermittle_venv_python_executable(venv_verzeichnis: Path) -> Path:
    os_schluessel = ermittle_betriebssystem_schluessel()
    if os_schluessel == "windows":
        return venv_verzeichnis / "Scripts" / "python.exe"
    return venv_verzeichnis / "bin" / "python"


def installiere_build_umgebung(temp_verzeichnis: Path, projektwurzel_verzeichnis: Path, requirements_datei: Path) -> Path:
    venv_verzeichnis = Path(temp_verzeichnis) / "build_env"
    python_executable = ermittle_venv_python_executable(venv_verzeichnis)

    fuehre_subprozess_aus([sys.executable, "-m", "venv", str(venv_verzeichnis)], arbeitsverzeichnis=projektwurzel_verzeichnis)
    fuehre_subprozess_aus([str(python_executable), "-m", "pip", "install", "--upgrade", "pip"], arbeitsverzeichnis=projektwurzel_verzeichnis)
    fuehre_subprozess_aus([str(python_executable), "-m", "pip", "install", "-r", str(requirements_datei)], arbeitsverzeichnis=projektwurzel_verzeichnis)
    fuehre_subprozess_aus([str(python_executable), "-m", "pip", "install", "pyinstaller"], arbeitsverzeichnis=projektwurzel_verzeichnis)

    return python_executable


def schreibe_runtime_hook_datei(zielpfad: Path) -> None:
    """
    PyInstaller Runtime Hook
    Wird beim Start der EXE ausgeführt und öffnet den Browser automatisch,
    sobald ein lokaler Gradio Port erreichbar ist.
    """
    inhalt = r'''
import os
import time
import socket
import threading
import webbrowser

def _port_offen(host: str, port: int, timeout_s: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False

def _oeffne_browser_sobald_server_da_ist() -> None:
    host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
    start_port = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))
    anzahl_ports = int(os.environ.get("GRADIO_NUM_PORTS", "100"))

    deadline = time.time() + 120.0
    bereits_geoeffnet = False

    while time.time() < deadline and not bereits_geoeffnet:
        for port in range(start_port, start_port + anzahl_ports):
            if _port_offen(host, port, timeout_s=0.2):
                url = f"http://{host}:{port}"
                try:
                    webbrowser.open(url, new=2)
                except Exception:
                    pass
                bereits_geoeffnet = True
                break
        if not bereits_geoeffnet:
            time.sleep(0.2)

def _setze_gradio_env_defaults() -> None:
    os.environ.setdefault("GRADIO_SERVER_NAME", "127.0.0.1")
    os.environ.setdefault("GRADIO_SERVER_PORT", "7860")
    os.environ.setdefault("GRADIO_NUM_PORTS", "100")

_setze_gradio_env_defaults()

thread = threading.Thread(target=_oeffne_browser_sobald_server_da_ist, daemon=True)
thread.start()
'''
    zielpfad.parent.mkdir(parents=True, exist_ok=True)
    zielpfad.write_text(inhalt.strip() + "\n", encoding="utf-8")


def kopiere_zusaetzliche_dateien(projektwurzel_verzeichnis: Path, dist_app_verzeichnis: Path) -> list[str]:
    return copy_release_bundle_files(projektwurzel_verzeichnis, dist_app_verzeichnis)


def erstelle_zip_datei_aus_verzeichnis(quellverzeichnis: Path, zip_datei_pfad: Path) -> None:
    if zip_datei_pfad.exists():
        zip_datei_pfad.unlink()

    with zipfile.ZipFile(zip_datei_pfad, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        for dateipfad in quellverzeichnis.rglob("*"):
            if dateipfad.is_file():
                zip_handle.write(dateipfad, arcname=str(dateipfad.relative_to(quellverzeichnis)))


def berechne_sha256_fuer_datei(datei_pfad: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(datei_pfad, "rb") as file_handle:
        while True:
            block = file_handle.read(1024 * 1024)
            if not block:
                break
            sha256_hash.update(block)
    return sha256_hash.hexdigest()


def schreibe_update_json(release_basisordner: Path, version_string: str, os_schluessel: str, zip_dateiname: str, sha256_string: str) -> Path:
    update_pfad = release_basisordner / "update.json"
    metadata = {}
    if update_pfad.exists():
        try:
            metadata = json.loads(update_pfad.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

    metadata["version"] = version_string
    metadata["published"] = datetime.now().strftime("%Y-%m-%d")

    if os_schluessel not in metadata:
        metadata[os_schluessel] = {}

    metadata[os_schluessel]["filename"] = zip_dateiname
    metadata[os_schluessel]["sha256"] = sha256_string
    if "url" not in metadata[os_schluessel]:
        metadata[os_schluessel]["url"] = ""

    update_pfad.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return update_pfad


def baue_mit_pyinstaller(
    projektwurzel_verzeichnis: Path,
    python_executable: Path,
    startdatei: Path,
    spec_verzeichnis: Path,
    build_verzeichnis: Path,
    dist_verzeichnis: Path,
    runtime_hook_datei: Path
) -> None:
    if spec_verzeichnis.exists():
        shutil.rmtree(spec_verzeichnis, ignore_errors=True)
    if build_verzeichnis.exists():
        shutil.rmtree(build_verzeichnis, ignore_errors=True)
    if dist_verzeichnis.exists():
        shutil.rmtree(dist_verzeichnis, ignore_errors=True)

    spec_verzeichnis.mkdir(parents=True, exist_ok=True)
    build_verzeichnis.mkdir(parents=True, exist_ok=True)
    dist_verzeichnis.mkdir(parents=True, exist_ok=True)

    argumente = [
        str(python_executable),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        ANWENDUNGS_NAME,
        "--specpath",
        str(spec_verzeichnis),
        "--workpath",
        str(build_verzeichnis),
        "--distpath",
        str(dist_verzeichnis),
        "--runtime-hook",
        str(runtime_hook_datei),
        str(startdatei),
    ]

    fuehre_subprozess_aus(argumente, arbeitsverzeichnis=projektwurzel_verzeichnis)


def main() -> None:
    projektwurzel_verzeichnis = ermittle_projektwurzel_verzeichnis()
    assert_release_ready(projektwurzel_verzeichnis)
    os_schluessel = ermittle_betriebssystem_schluessel()
    version_string = ermittle_versions_string(projektwurzel_verzeichnis)

    release_basisordner = ermittle_release_basisordner(projektwurzel_verzeichnis)
    release_os_ordner = ermittle_release_os_ordner(projektwurzel_verzeichnis, os_schluessel)

    spec_verzeichnis = release_os_ordner / "spec"
    build_verzeichnis = release_os_ordner / "build"
    dist_basisverzeichnis = release_os_ordner / "dist"
    zip_verzeichnis = release_os_ordner / "zip"
    zip_verzeichnis.mkdir(parents=True, exist_ok=True)

    startdatei, requirements_datei = hole_release_build_pfade(projektwurzel_verzeichnis)

    print("\nProjektwurzel:")
    print(projektwurzel_verzeichnis)
    print("\nZiel Betriebssystem:")
    print(os_schluessel)
    print("\nVersion:")
    print(version_string)
    print("\nStartdatei:")
    print(startdatei)
    print("\nRequirements:")
    print(requirements_datei)
    print("\nRelease Ordner:")
    print(release_os_ordner)

    runtime_hook_datei = spec_verzeichnis / "runtime_hook_open_browser.py"
    schreibe_runtime_hook_datei(runtime_hook_datei)

    with tempfile.TemporaryDirectory() as temp_verzeichnis:
        python_executable = installiere_build_umgebung(
            temp_verzeichnis=Path(temp_verzeichnis),
            projektwurzel_verzeichnis=projektwurzel_verzeichnis,
            requirements_datei=requirements_datei
        )

        baue_mit_pyinstaller(
            projektwurzel_verzeichnis=projektwurzel_verzeichnis,
            python_executable=python_executable,
            startdatei=startdatei,
            spec_verzeichnis=spec_verzeichnis,
            build_verzeichnis=build_verzeichnis,
            dist_verzeichnis=dist_basisverzeichnis,
            runtime_hook_datei=runtime_hook_datei
        )

    dist_app_verzeichnis = dist_basisverzeichnis / ANWENDUNGS_NAME
    if not dist_app_verzeichnis.exists():
        raise FileNotFoundError(f"dist App Ordner fehlt: {dist_app_verzeichnis}")

    kopierte_dateien = kopiere_zusaetzliche_dateien(projektwurzel_verzeichnis, dist_app_verzeichnis)

    zip_dateiname = f"{ANWENDUNGS_NAME}_{os_schluessel}_{version_string}.zip"
    zip_pfad = zip_verzeichnis / zip_dateiname

    erstelle_zip_datei_aus_verzeichnis(dist_app_verzeichnis, zip_pfad)
    sha256_string = berechne_sha256_fuer_datei(zip_pfad)

    update_pfad = schreibe_update_json(
        release_basisordner=release_basisordner,
        version_string=version_string,
        os_schluessel=os_schluessel,
        zip_dateiname=zip_dateiname,
        sha256_string=sha256_string
    )

    print("\nBuild fertig.")
    print("EXE liegt hier:")
    if os_schluessel == "windows":
        print(dist_app_verzeichnis / f"{ANWENDUNGS_NAME}.exe")
    else:
        print(dist_app_verzeichnis)

    print("\nZIP:")
    print(zip_pfad)
    print("\nAllowlist-Dateien:")
    for relpath in kopierte_dateien:
        print(relpath)
    print("\nSHA256:")
    print(sha256_string)
    print("\nupdate.json:")
    print(update_pfad)
    print("\nHinweis:")
    print("macOS Build entsteht nur, wenn du dieses Script auf einem Mac ausführst.")


if __name__ == "__main__":
    main()


# In[18]:



