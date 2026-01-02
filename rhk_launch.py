#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – Launcher (split from rhk_app_web_master.py).

Enthält:
- lokale/Cloud Launch-Logik (Ports, no_proxy, Render/Spaces)
- main() Entry-Point

"""

from __future__ import annotations

from rhk_base import *  # noqa: F401,F403
from rhk_ui import build_demo, JS_ON_LOAD, HEAD_HTML  # noqa: F401

# =============================================================================
# Main
# =============================================================================

def _find_free_port(preferred: int) -> int:
    """
    Local/dev: try a few ports starting at preferred, else return 0 (OS chooses).
    Cloud (Render): do NOT use this. Cloud must bind exactly to $PORT.
    """
    import socket

    for port in range(preferred, preferred + 50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue

    return 0


def _apply_no_proxy_for_localhost() -> None:
    """
    Ensure localhost bypasses proxies. Helps with Gradio/httpx self-checks on Windows.
    """
    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    tokens = [t.strip() for t in existing.split(",") if t.strip()]
    needed = ["localhost", "127.0.0.1", "0.0.0.0"]
    for n in needed:
        if n not in tokens:
            tokens.append(n)
    value = ",".join(tokens)
    os.environ["NO_PROXY"] = value
    os.environ["no_proxy"] = value


def _is_cloud_runtime() -> bool:
    """
    Hosted environment detection.
    Render always sets PORT, and often also RENDER.
    """
    if os.environ.get("RENDER"):
        return True
    if os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"):
        return True
    if os.environ.get("FLY_APP_NAME"):
        return True
    if os.environ.get("DYNO"):
        return True
    # If PORT is set, assume hosted (Render/Heroku/etc.) unless you intentionally set it locally.
    return bool(os.environ.get("PORT"))


def _safe_launch_local(demo, launch_kwargs: Dict[str, Any]) -> None:
    """
    Local launch: tolerate port conflicts and proxy/loopback weirdness.
    """
    try:
        demo.launch(**launch_kwargs)
        return
    except OSError:
        # Port busy -> let OS/Gradio choose
        launch_kwargs["server_port"] = 0
        demo.launch(**launch_kwargs)
        return
    except Exception:
        # As a last resort: force localhost binding + OS port
        launch_kwargs["server_name"] = "127.0.0.1"
        launch_kwargs["server_port"] = 0
        demo.launch(**launch_kwargs)


def main():
    _require_gradio_version(5)

    demo, css, theme = build_demo()
    cloud = _is_cloud_runtime()

    def _launch_with_compat(_demo, _kwargs: Dict[str, Any]) -> None:
        """Launch with best-effort support across Gradio 5.x/6.x.

        Depending on Gradio version, theme/css/js/head may be accepted either in
        Blocks() or in launch(). We try them in launch() first and gracefully
        drop unsupported keys.
        """
        drop_plans = [
            [],
            ["head"],
            ["head", "js"],
            ["head", "js", "css"],
            ["head", "js", "css", "theme"],
        ]
        last_err = None
        for drop in drop_plans:
            try:
                k = dict(_kwargs)
                for kk in drop:
                    k.pop(kk, None)
                _demo.launch(**k)
                return
            except TypeError as e:
                last_err = e
                continue
        if last_err:
            raise last_err

    if cloud:
        # Render expects 0.0.0.0:$PORT exactly
        port_env = os.environ.get("PORT") or os.environ.get("GRADIO_SERVER_PORT")
        if not port_env:
            raise RuntimeError("Cloud runtime detected but no PORT/GRADIO_SERVER_PORT set.")
        port = int(port_env)

        launch_kwargs: Dict[str, Any] = {
            "server_name": "0.0.0.0",
            "server_port": port,
            "share": False,
        }

        # Always try to pass UI assets into launch(). If unsupported, we drop them.
        # (Blocks() also tries to accept them; see rhk_ui.build_demo)
        launch_kwargs.update(
            {
                "theme": theme,
                "css": css,
                "js": JS_ON_LOAD,
                "head": HEAD_HTML,
            }
        )

        _launch_with_compat(demo, launch_kwargs)

        return

    # Local/dev
    _apply_no_proxy_for_localhost()

    env_port = os.environ.get("GRADIO_SERVER_PORT") or "7860"
    preferred_port = int(env_port) if str(env_port).isdigit() else 7860
    port = _find_free_port(preferred_port)

    launch_kwargs: Dict[str, Any] = {
        "server_name": "127.0.0.1",  # local default -> avoids some httpx startup-events issues
        "server_port": port,         # may be 0
        "share": False,
    }

    launch_kwargs.update(
        {
            "theme": theme,
            "css": css,
            "js": JS_ON_LOAD,
            "head": HEAD_HTML,
        }
    )

    try:
        # local: keep existing port/proxy fallbacks
        _safe_launch_local(demo, launch_kwargs)
    except TypeError:
        # Some Gradio builds reject theme/css/js/head in launch(); try compat drops
        # but still keep the port fallback behaviour.
        try:
            _launch_with_compat(demo, launch_kwargs)
        except OSError:
            launch_kwargs["server_port"] = 0
            _launch_with_compat(demo, launch_kwargs)


if __name__ == "__main__":
    main()


