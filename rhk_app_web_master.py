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
import socket
import inspect

from rhk_base import _require_gradio_version
from rhk_ui import build_demo


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

    demo, _css, _theme = build_demo()

    # Gradio 6 moved theme/css/js/head to launch(); we stash these in build_demo.
    # Filter kwargs by the actual launch() signature to stay compatible across versions.
    launch_kwargs = getattr(demo, "_rhk_launch_kwargs", {}) or {}
    try:
        sig = inspect.signature(demo.launch)
        allowed = set(sig.parameters.keys())
        launch_kwargs = {k: v for k, v in launch_kwargs.items() if (k in allowed and v is not None)}
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
