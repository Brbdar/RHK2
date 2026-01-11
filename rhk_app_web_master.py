#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – v26 (Entry-Point).

Wichtig: Der Befundassistent enthält keine projektfremde "Launcher"-Automatik.
Diese Datei startet ausschließlich die Gradio-App.

Start:
    python rhk_app_web_master.py
"""

from __future__ import annotations

import os

# -----------------------------------------------------------------------------
# Gradio analytics / pandas / pyarrow / NumPy ABI guard
#
# Auf manchen Klinikrechnern (häufig Anaconda) sind optionale Abhängigkeiten
# wie pandas/pyarrow noch gegen NumPy 1.x gebaut, während NumPy 2.x installiert
# ist. Gradio versucht im Hintergrund Analytics-Summaries zu erzeugen und
# importiert dafür pandas → pyarrow → Crash.
#
# Wir deaktivieren Analytics robust (Env + Monkeypatch), damit die App immer
# startet – ohne dass Nutzer*innen ihre Python-Umgebung ändern müssen.
# -----------------------------------------------------------------------------
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_ANALYTICS", "False")
os.environ.setdefault("GRADIO_TELEMETRY", "False")
os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "False")


def _disable_gradio_analytics_runtime() -> None:
    """Disable Gradio queue analytics to avoid importing pandas/pyarrow.

    This must run **before** any queueing instance spawns the background
    analytics summary thread.
    """
    # Env flags (must be set before any Gradio internals might read them)
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    os.environ.setdefault("GRADIO_ANALYTICS", "False")
    os.environ.setdefault("GRADIO_TELEMETRY", "False")
    os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "False")

    try:  # pragma: no cover
        import gradio.queueing as _gq  # type: ignore

        def _noop(*_a, **_k):
            return None

        # Patch module-level helpers if present
        for _name in ("compute_analytics_summary", "_get_df", "get_df"):
            if hasattr(_gq, _name):
                try:
                    setattr(_gq, _name, _noop)
                except Exception:
                    pass

        # Patch all classes/objects that implement these methods
        for _obj in list(vars(_gq).values()):
            for _meth in ("compute_analytics_summary", "_get_df", "get_df"):
                if hasattr(_obj, _meth):
                    try:
                        setattr(_obj, _meth, _noop)
                    except Exception:
                        pass
    except Exception:
        # Never block startup.
        return


# Run the guard at import time too (covers cases where Gradio spawns threads
# very early during initialization in some versions/environments).
_disable_gradio_analytics_runtime()

import socket
import inspect

from rhk_base import _require_gradio_version


def main() -> None:
    """Start the Gradio app with minimal, predictable settings.

    - If PORT (Render/Cloud) is set: bind to 0.0.0.0:$PORT exactly.
    - Otherwise: bind locally to 127.0.0.1 and default port 7860 (overridable via GRADIO_SERVER_PORT).

    No proxy mutation, no browser auto-open.
    Local/dev quality-of-life: if the default port (7860) is occupied and the
    user did not explicitly set GRADIO_SERVER_PORT, the app will try the next
    free port in a small range.
    """

    _require_gradio_version(5)

    # IMPORTANT: patch Gradio analytics BEFORE importing rhk_ui/building Blocks.
    _disable_gradio_analytics_runtime()

    # Import UI only after analytics guard is in place.
    from rhk_ui import build_demo  # local import by design

    demo, _css, _theme = build_demo()

    # Gradio 6 moved theme/css/js/head to launch(); we stash these in build_demo.
    # Filter kwargs by the actual launch() signature to stay compatible across versions.
    launch_kwargs = getattr(demo, "_rhk_launch_kwargs", {}) or {}
    try:
        sig = inspect.signature(demo.launch)
        allowed = set(sig.parameters.keys())
        launch_kwargs = {k: v for k, v in launch_kwargs.items() if (k in allowed and v is not None)}

        # Explicitly disable analytics if supported by this Gradio version.
        for k in ("analytics_enabled", "enable_analytics"):
            if k in allowed:
                launch_kwargs[k] = False

        # Prefer disabling queueing entirely if supported (removes analytics thread
        # in some Gradio versions even when analytics flags are ignored).
        for k in ("enable_queue", "enable_queueing"):
            if k in allowed:
                launch_kwargs[k] = False
    except Exception:
        launch_kwargs = {}

    def _port_is_free(host: str, port: int) -> bool:
        """Best-effort check whether a TCP port can be bound.

        We only use this for local/dev when the user did not explicitly
        choose a port via GRADIO_SERVER_PORT.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
            return True
        except OSError:
            return False

    # Cloud/Render: bind exactly to provided PORT.
    port_env = os.environ.get("PORT")
    if port_env and str(port_env).isdigit():
        server_name = "0.0.0.0"
        server_port = int(port_env)
    else:
        # Local/dev: default to localhost.
        server_name = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")

        # If user explicitly chose a port -> respect it (no scanning).
        explicit_port = os.environ.get("GRADIO_SERVER_PORT")
        if explicit_port and str(explicit_port).isdigit():
            server_port = int(explicit_port)
        else:
            # Minimal, predictable fallback: if 7860 is taken, try next free ports.
            preferred = 7860
            if _port_is_free(server_name, preferred):
                server_port = preferred
            else:
                picked = None
                for p in range(preferred + 1, preferred + 51):
                    if _port_is_free(server_name, p):
                        picked = p
                        break
                if picked is None:
                    raise OSError(
                        "Cannot find an empty local port in range 7860-7910. "
                        "Close the other process using the port or set GRADIO_SERVER_PORT."
                    )
                server_port = picked

    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=False,
        **launch_kwargs,
    )


if __name__ == "__main__":
    main()
