#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.27: rhk_launch.py - Star-Import entfernt (explizite Imports), Launch-Logik unverändert
"""RHK Befundassistent – Launcher (split from rhk_app_web_master.py).

Enthält:
- lokale/Cloud Launch-Logik (Ports, no_proxy, Render/Spaces)
- main() Entry-Point

"""

from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser
from typing import Any, Dict

from rhk_base import _require_gradio_version
from rhk_runtime_policy import (
    apply_deploy_profile,
    cleanup_runtime_retention,
    get_allowed_file_paths,
    get_deploy_profile,
)
from rhk_ui_utils import _gradio_major_version

# =============================================================================
# Main helpers
# =============================================================================

def _find_free_port(preferred: int) -> int:
    """
    Local/dev: choose a concrete free TCP port (so we can also open the browser).
    Cloud (Render): do NOT use this. Cloud must bind exactly to $PORT.
    """
    if isinstance(preferred, int) and preferred > 0:
        for port in range(preferred, preferred + 50):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    # Fallback: ask OS for an ephemeral free port and return the actual value.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _apply_no_proxy_for_localhost() -> None:
    """
    Ensure localhost bypasses proxies. Helps with Gradio/httpx self-checks on Windows.
    """
    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    tokens = [t.strip() for t in existing.split(",") if t.strip()]
    needed = ["localhost", "127.0.0.1", "0.0.0.0"]
    for item in needed:
        if item not in tokens:
            tokens.append(item)
    value = ",".join(tokens)
    os.environ["NO_PROXY"] = value
    os.environ["no_proxy"] = value


def _is_cloud_runtime() -> bool:
    """
    Hosted environment detection.
    Render always sets PORT, and often also RENDER.
    """
    return get_deploy_profile().name == "cloud"


def _open_browser_delayed(url: str, delay_seconds: float = 0.8) -> None:
    """
    Open the default browser after a short delay.
    Works reliably in PyInstaller one-dir/one-file executables.
    """
    try:
        time.sleep(float(delay_seconds))
        webbrowser.open(url, new=2)
    except Exception:
        # Do not hard-fail if the browser cannot be opened.
        pass


def _safe_launch_local(
    demo,
    launch_kwargs: Dict[str, Any],
    *,
    auto_open_browser: bool = True,
    browser_host: str = "127.0.0.1",
) -> None:
    """
    Local launch: tolerate port conflicts and proxy/loopback weirdness.
    Also opens the browser automatically (once per actual chosen port).
    """
    def start_browser_thread(port: int) -> None:
        if not auto_open_browser:
            return
        url = f"http://{browser_host}:{int(port)}"
        threading.Thread(target=_open_browser_delayed, args=(url,), daemon=True).start()

    # Ensure we always use a concrete port (not 0), so we know the URL.
    current_port = int(launch_kwargs.get("server_port") or 0)
    if current_port <= 0:
        current_port = _find_free_port(7860)
        launch_kwargs["server_port"] = current_port

    start_browser_thread(current_port)

    try:
        demo.launch(**launch_kwargs)
        return
    except OSError:
        # Port busy -> pick a new concrete port and try again.
        new_port = _find_free_port(0)
        launch_kwargs["server_port"] = new_port
        start_browser_thread(new_port)
        demo.launch(**launch_kwargs)
        return
    except Exception:
        # Last resort: force localhost binding + new concrete port.
        launch_kwargs["server_name"] = browser_host
        new_port = _find_free_port(0)
        launch_kwargs["server_port"] = new_port
        start_browser_thread(new_port)
        demo.launch(**launch_kwargs)
        return


def main() -> None:
    profile = apply_deploy_profile()
    cleanup_runtime_retention(profile.name)
    _require_gradio_version(5)

    from rhk_ui import build_demo
    from rhk_ui_assets import HEAD_HTML, JS_ON_LOAD

    demo, css, theme = build_demo()
    major = _gradio_major_version()
    cloud = _is_cloud_runtime()

    # -------------------------------------------------------------------------
    # File serving (Pre-RHK PDF + JSON saves)
    # -------------------------------------------------------------------------
    allowed_fileserve_paths = get_allowed_file_paths(profile.name)

    if cloud:
        # Render expects 0.0.0.0:$PORT exactly.
        port_env = os.environ.get("PORT") or os.environ.get("GRADIO_SERVER_PORT")
        if not port_env:
            raise RuntimeError("Cloud runtime detected but no PORT/GRADIO_SERVER_PORT set.")
        port = int(port_env)

        launch_kwargs: Dict[str, Any] = {
            "server_name": "0.0.0.0",
            "server_port": port,
            "share": profile.share,
        }

        # Allow serving generated export files.
        launch_kwargs["allowed_paths"] = allowed_fileserve_paths

        if (not major) or major >= 6:
            launch_kwargs.update(
                {
                    "theme": theme,
                    "css": css,
                    "js": JS_ON_LOAD,
                    "head": HEAD_HTML,
                }
            )

        try:
            demo.launch(**launch_kwargs)
        except TypeError:
            # Older Gradio: drop head/js first.
            launch_kwargs.pop("allowed_paths", None)
            launch_kwargs.pop("head", None)
            launch_kwargs.pop("js", None)
            demo.launch(**launch_kwargs)

        return

    # Local/dev
    _apply_no_proxy_for_localhost()

    env_port = os.environ.get("GRADIO_SERVER_PORT") or "7860"
    preferred_port = int(env_port) if str(env_port).isdigit() else 7860
    port = _find_free_port(preferred_port)

    launch_kwargs = {
        "server_name": os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        "server_port": port,
        "share": profile.share,
        "inbrowser": False,  # we open the browser ourselves (works best in .exe)
    }

    # Allow serving generated export files.
    launch_kwargs["allowed_paths"] = allowed_fileserve_paths

    if (not major) or major >= 6:
        launch_kwargs.update(
            {
                "theme": theme,
                "css": css,
                "js": JS_ON_LOAD,
                "head": HEAD_HTML,
            }
        )

    try:
        _safe_launch_local(
            demo,
            launch_kwargs,
            auto_open_browser=profile.auto_open_browser,
            browser_host=str(launch_kwargs["server_name"]),
        )
    except TypeError:
        # Older Gradio: drop head/js first.
        launch_kwargs.pop("allowed_paths", None)
        launch_kwargs.pop("head", None)
        launch_kwargs.pop("js", None)
        _safe_launch_local(
            demo,
            launch_kwargs,
            auto_open_browser=profile.auto_open_browser,
            browser_host=str(launch_kwargs["server_name"]),
        )


if __name__ == "__main__":
    main()
