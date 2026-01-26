"""RHK Live-Fehleransicht Runner (robust, Jupyter-tauglich)

- Startet rhk_app_web_master.py als Subprocess
- Live stdout+stderr in Konsole + Logfile
- Erkennt sofort, wenn die App direkt beendet (Returncode + letzter Traceback)
- Prüft, ob der Port wirklich lauscht
- Nicht-blockierend (Jupyter geeignet)

Nutzung:
  python run_rhk_verbose.py
  (optional) GRADIO_DEBUG=0 python run_rhk_verbose.py
"""

from __future__ import annotations

from pathlib import Path
import os, sys, subprocess, threading, time, re, socket, signal, webbrowser
from datetime import datetime
from collections import deque
from typing import Optional

APP = Path("rhk_app_web_master.py")
HOST = os.environ.get("RHK_HOST", "127.0.0.1")
PORT = int(os.environ.get("RHK_PORT", os.environ.get("PORT", "7700")))

AUTO_OPEN_BROWSER = False
STARTUP_WAIT_SEC = 8.0

LOG_DIR = Path("run_logs")
LOG_DIR.mkdir(exist_ok=True)

if not APP.exists():
    raise FileNotFoundError(f"Nicht gefunden: {APP.resolve()}")  # fail fast

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = (LOG_DIR / f"gradio_verbose_{APP.stem}_{HOST}_{PORT}_{ts}.log").resolve()

env = os.environ.copy()
env["PORT"] = str(PORT)
env["GRADIO_SERVER_PORT"] = str(PORT)
env["GRADIO_SERVER_NAME"] = HOST
env["PYTHONUNBUFFERED"] = "1"
env["PYTHONFAULTHANDLER"] = "1"
env["PYTHONASYNCIODEBUG"] = env.get("PYTHONASYNCIODEBUG", "1")
env["PYTHONWARNINGS"] = env.get("PYTHONWARNINGS", "default")
env["GRADIO_DEBUG"] = env.get("GRADIO_DEBUG", "1")  # MUST be "0" or "1"
env["GRADIO_ANALYTICS_ENABLED"] = "false"
env["LOG_LEVEL"] = env.get("LOG_LEVEL", "DEBUG")

TB_START = "Traceback (most recent call last):"
TB_END_RE = re.compile(r"(\bError\b|\bException\b|SystemExit|KeyboardInterrupt)\s*:?")

HIGHLIGHT_RE = re.compile(
    r"\b("
    r"Traceback|Exception|Error|ValueError|NameError|AttributeError|KeyError|TypeError|"
    r"UnboundLocalError|AssertionError|RuntimeError|ImportError|ModuleNotFoundError|"
    r"SyntaxError|IndentationError|gradio|anyio|asyncio"
    r")\b"
)

_proc: Optional[subprocess.Popen] = None
_stop = threading.Event()

_last_logs = deque(maxlen=2000)
_last_traceback = deque(maxlen=800)
_tb_mode = False


def _is_port_listening(host: str, port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _stream_reader(proc: subprocess.Popen):
    global _tb_mode
    with LOG_PATH.open("w", encoding="utf-8", newline="\n") as lf:
        while not _stop.is_set():
            line = proc.stdout.readline() if proc.stdout is not None else ""
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.02)
                continue

            lf.write(line)
            lf.flush()

            s = line.rstrip("\n")
            _last_logs.append(s)

            if TB_START in s:
                _tb_mode = True
                _last_traceback.clear()
                _last_traceback.append(s)
                print("\n" + s)
                continue

            if _tb_mode:
                _last_traceback.append(s)
                print(s)
                if TB_END_RE.search(s):
                    _tb_mode = False
                    print("")
                continue

            if HIGHLIGHT_RE.search(s):
                _last_traceback.append(s)
                print("\n!!! " + s)
            else:
                print(s)


def start_app():
    global _proc
    if _proc is not None and _proc.poll() is None:
        print(f"App läuft bereits: PID={_proc.pid}")
        print(f"URL: http://{HOST}:{PORT}")
        print(f"Log: {LOG_PATH}")
        return

    _stop.clear()
    _last_logs.clear()
    _last_traceback.clear()

    print("=== STARTE APP (ROBUST VERBOSE RUNNER) ===")
    print(f"APP:  {APP.resolve()}")
    print(f"URL:  http://{HOST}:{PORT}")
    print(f"LOG:  {LOG_PATH}")
    print(f"ENV:  GRADIO_DEBUG={env.get('GRADIO_DEBUG')}  PYTHONWARNINGS={env.get('PYTHONWARNINGS')}")
    print("")

    cmd = [sys.executable, "-u", "-X", "faulthandler", str(APP)]
    print("$ " + " ".join(cmd))
    print("")

    _proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        cwd=str(Path.cwd()),
    )

    threading.Thread(target=_stream_reader, args=(_proc,), daemon=True).start()

    t0 = time.time()
    listened = False
    while time.time() - t0 < STARTUP_WAIT_SEC:
        if _proc.poll() is not None:
            print("\n=== APP BEENDET (früh) ===")
            print(f"Returncode: {_proc.returncode}")
            print(f"Log: {LOG_PATH}\n")
            print("Letzter Traceback/Fehlerpuffer:")
            show_last_traceback()
            return

        if _is_port_listening(HOST, PORT):
            listened = True
            break
        time.sleep(0.2)

    if listened:
        print("\n=== APP LISTENING ===")
        print(f"Öffne: http://{HOST}:{PORT}")
        print(f"Log:   {LOG_PATH}")
        if AUTO_OPEN_BROWSER:
            try:
                webbrowser.open(f"http://{HOST}:{PORT}")
            except Exception:
                pass
    else:
        print("\n=== WARNUNG: Port lauscht nicht (noch) ===")
        print("App könnte noch starten ODER intern hängen/fehlschlagen.")
        print("Nutze show_last_logs()/show_last_traceback().")
        print(f"Log: {LOG_PATH}")


def stop_app(force: bool = False):
    global _proc
    _stop.set()
    if _proc is None:
        print("Kein Prozess aktiv.")
        return

    if _proc.poll() is None:
        try:
            if force:
                if os.name == "nt":
                    _proc.kill()
                else:
                    _proc.send_signal(signal.SIGKILL)
            else:
                _proc.terminate()
            _proc.wait(timeout=5)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass

    print(f"\n=== GESTOPPT ===\nLog: {LOG_PATH}")
    _proc = None


def show_last_traceback():
    if not _last_traceback:
        print("(Kein Traceback/Fehler im Puffer.)")
        return
    print("\n--- LETZTER FEHLERBLOCK (gepuffert) ---")
    print("\n".join(_last_traceback))


def show_last_logs(n: int = 300):
    if not _last_logs:
        print("(Keine Logs im Puffer.)")
        return
    n = max(1, min(n, len(_last_logs)))
    print(f"\n--- LETZTE {n} LOGZEILEN ---")
    print("\n".join(list(_last_logs)[-n:]))


def status():
    if _proc is None:
        print("Status: kein Prozess.")
        return
    alive = _proc.poll() is None
    print(f"Status: PID={_proc.pid} alive={alive} returncode={_proc.returncode}")
    print(f"Port listening: {_is_port_listening(HOST, PORT)}")
    print(f"URL: http://{HOST}:{PORT}")
    print(f"Log: {LOG_PATH}")


if __name__ == "__main__":
    start_app()
