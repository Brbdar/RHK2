#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.48: rhk_app_web_master.py - Version/Label auf v1.48 (Parser-/Transparenz-/Performance-Release)
# Refactor v1.47: rhk_app_web_master.py - Version/Label auf v1.47 (UI-Übersicht + nummerierte Tabs)
# Refactor v1.46: rhk_app_web_master.py - Render Download Fix: allowlist /tmp/gradio + redirect broken file URLs (prevents 404)
# Refactor v1.43: rhk_app_web_master.py - Stabilität: Workdir fix, Thread-Limits, Download-Allowlist über Export-Dir, Crash-Logging
# Refactor v1.37: rhk_app_web_master.py - Version/Label auf v1.37, OCR defaults robust (Env blank -> default)
# Refactor v1.34: rhk_app_web_master.py - Versionskonsistenz + Online Echo Upload via render.yaml
# Refactor v1.32: rhk_app_web_master.py - Downloads/Allowlist stabilisiert (Exports), Cloud-Echo-OCR via render.yaml
# Refactor v1.30: rhk_app_web_master.py - Version/Label auf v1.30 aktualisiert (kein Logik-Change)
# Refactor v1.28: rhk_app_web_master.py - Version/Label auf v28 aktualisiert (kein Logik-Change)
"""RHK Befundassistent – v1.1 (Entry-Point).

Diese Datei startet die Gradio App deterministisch.

Warum v1.1?
- Hosted-Deployments (z.B. Render) können mit `demo.launch(server_name='0.0.0.0')` fehlschlagen,
  weil Gradio intern eine Erreichbarkeitsprüfung ausführt. Klinisch ist `share=True` i.d.R. nicht akzeptabel.
- Zusätzlich können in bestimmten Gradio-Versionen/Proxy-Setups Downloads (PDF/DOCX/ZIP) mit 404 fehlschlagen,
  wenn (a) der Gradio-Cache-Pfad (<tmp>/gradio) nicht allowlisted ist oder (b) fehlerhafte relative
  Download-URLs erzeugt werden.

Lösung:
- Lokal (localhost): `demo.launch(...)`
- Hosted / Bind auf 0.0.0.0: Gradio wird in ein FastAPI-ASGI-App gemountet und via uvicorn
  gestartet (kein Gradio-"localhost"-Reachability-Check, kein share-Link).

Start:
    python rhk_app_web_master.py
"""

from __future__ import annotations

import atexit
import inspect
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rhk_logging import log_exception
from rhk_runtime_policy import (
    apply_deploy_profile,
    cleanup_runtime_retention,
    get_allowed_file_paths,
    get_runtime_log_dir,
)

# ----------------------------------------------------------------------------
# Stability guardrails (clinical runtime)
# ----------------------------------------------------------------------------
# Some optional backends used by the app (OCR/PDF) rely on native libraries
# (onnxruntime, OpenMP, etc.). On certain Windows/Anaconda setups these can
# become unstable with aggressive thread defaults. Limiting threads improves
# stability and reproducibility.
for _k in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ.setdefault(_k, "1")

_RUNTIME_PROFILE = apply_deploy_profile()

# Enable faulthandler early so sudden interpreter crashes (native segfault)
# leave a traceback in the profile-specific runtime log dir.
_FAULTHANDLER_FH = None
try:  # pragma: no cover
    import faulthandler

    _log_dir = get_runtime_log_dir(_RUNTIME_PROFILE.name)
    _log_dir.mkdir(parents=True, exist_ok=True)
    _ts = time.strftime("%Y%m%d_%H%M%S")
    _FAULTHANDLER_FH = open(_log_dir / f"faulthandler_{_ts}.log", "w", encoding="utf-8")
    faulthandler.enable(file=_FAULTHANDLER_FH, all_threads=True)
except (OSError, ImportError, ValueError) as exc:
    log_exception("RHK_APP_FAULTHANDLER", "Faulthandler setup failed.", exc)
    _FAULTHANDLER_FH = None

if _FAULTHANDLER_FH is not None:
    def _close_faulthandler_file() -> None:
        if _FAULTHANDLER_FH is not None:
            _FAULTHANDLER_FH.close()

    atexit.register(_close_faulthandler_file)

# -----------------------------------------------------------------------------
# Gradio analytics / pandas / pyarrow / NumPy ABI guard
# -----------------------------------------------------------------------------
# On some systems Gradio's analytics thread can end up importing pandas/pyarrow
# and crash due to ABI mismatches. Disable analytics proactively.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_ANALYTICS", "False")
os.environ.setdefault("GRADIO_TELEMETRY", "False")
os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "False")


def _disable_gradio_analytics_runtime() -> None:
    """Disable Gradio queue analytics to avoid importing pandas/pyarrow.

    This must run **before** any queueing instance spawns background
    analytics threads.
    """
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    os.environ.setdefault("GRADIO_ANALYTICS", "False")
    os.environ.setdefault("GRADIO_TELEMETRY", "False")
    os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "False")

    try:  # pragma: no cover
        import gradio.queueing as _gq

        def _noop(*_a, **_k):
            return None

        for _name in ("compute_analytics_summary", "_get_df", "get_df"):
            if hasattr(_gq, _name):
                try:
                    setattr(_gq, _name, _noop)
                except (AttributeError, TypeError) as exc:
                    log_exception("RHK_APP_ANALYTICS_PATCH", "Gradio analytics patch failed.", exc)

        for _obj in list(vars(_gq).values()):
            for _meth in ("compute_analytics_summary", "_get_df", "get_df"):
                if hasattr(_obj, _meth):
                    try:
                        setattr(_obj, _meth, _noop)
                    except (AttributeError, TypeError) as exc:
                        log_exception("RHK_APP_ANALYTICS_OBJ", "Gradio analytics object patch failed.", exc)
    except (ImportError, AttributeError) as exc:
        log_exception("RHK_APP_ANALYTICS_IMPORT", "Gradio queueing import/patch failed.", exc)
        return


def _normalize_gradio_debug_env() -> None:
    """Normalize GRADIO_DEBUG to the integer tokens expected by Gradio.

    Some deployments set `GRADIO_DEBUG=true/false`, while Gradio parses the
    variable via `int(os.getenv(...))`. Coerce common boolean spellings to
    `1`/`0` so local startup cannot crash on environment drift.
    """
    raw = os.environ.get("GRADIO_DEBUG")
    if raw is None:
        return
    text = str(raw).strip().lower()
    if text.isdigit():
        return
    if text in {"1", "true", "yes", "on"}:
        os.environ["GRADIO_DEBUG"] = "1"
        return
    if text in {"", "0", "false", "no", "off"}:
        os.environ["GRADIO_DEBUG"] = "0"
        return
    os.environ["GRADIO_DEBUG"] = "0"


# Run the guard at import time too.
_disable_gradio_analytics_runtime()

from rhk_base import _require_gradio_version


def _port_is_free(host: str, port: int) -> bool:
    """Best-effort check whether a TCP port can be bound."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
        return True
    except OSError:
        return False


def _compute_allowlisted_paths() -> List[str]:
    """Directories that must be serve-able for downloads (DOCX/PDF/ZIP).

    Note:
    - Paths must be absolute.
    - Keep the list minimal (Datensparsamkeit).
    """
    return get_allowed_file_paths(_RUNTIME_PROFILE.name)


def _ensure_env_csv(var_name: str, items: List[str]) -> None:
    """Append items to a comma-separated env var without duplicates."""
    try:
        cur = str(os.environ.get(var_name, "") or "").strip()
        parts = [p.strip() for p in cur.split(",") if p.strip()] if cur else []
        for it in items:
            it = str(it).strip()
            if not it:
                continue
            if it not in parts:
                parts.append(it)
        if parts:
            os.environ[var_name] = ",".join(parts)
    except (TypeError, ValueError) as exc:
        # Never block startup.
        log_exception("RHK_APP_ENV_CSV", "Env CSV append failed.", exc)
        return


def _run_hosted_uvicorn(*, demo: Any, server_name: str, server_port: int, gradio_assets: Dict[str, Any], allowed_paths: List[str]) -> None:
    """Run the app in hosted mode without Gradio's localhost reachability check.

    We mount the Blocks into a FastAPI ASGI app and serve it with uvicorn.

    This avoids the common `ValueError: When localhost is not accessible ...`
    when binding to 0.0.0.0 in container/cloud environments.
    """
    # Imports here keep local startup lightweight and avoid accidental side effects.
    import gradio as gr
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI()

    # -----------------------------------------------------------------
    # Gradio hosted file download hotfix
    # -----------------------------------------------------------------
    # Some Gradio versions (observed behind Render/reverse proxies) can emit
    # download URLs without a leading slash, which the browser then resolves
    # relative to the last API endpoint (e.g. /gradio_api/run/predict/...).
    # This produces 404s like:
    #   /gradio_api/run/predict/gradio_api/file=/tmp/gradio/...
    # We intercept these broken URLs and redirect to the correct file route.
    try:  # pragma: no cover
        from fastapi.responses import RedirectResponse

        @app.get("/gradio_api/run/predict/gradio_api/file={file_path:path}")
        async def _rhk_fix_gradio_file_url(file_path: str):
            return RedirectResponse(url=f"/gradio_api/file={file_path}", status_code=307)

        @app.get("/gradio_api/run/predict/file={file_path:path}")
        async def _rhk_fix_gradio_file_url_alt(file_path: str):
            return RedirectResponse(url=f"/gradio_api/file={file_path}", status_code=307)
    except (ImportError, AttributeError) as exc:
        log_exception("RHK_APP_REDIRECT", "Gradio file redirect hotfix setup failed.", exc)


    # Filter kwargs defensively across Gradio versions.
    mount_kwargs: Dict[str, Any] = {}
    try:
        sig = inspect.signature(gr.mount_gradio_app)
        allowed = set(sig.parameters.keys())
        mount_kwargs = {k: v for k, v in (gradio_assets or {}).items() if (k in allowed and v is not None)}

        # Allow serving generated files.
        if "allowed_paths" in allowed:
            mount_kwargs["allowed_paths"] = allowed_paths

        # Optional: root_path if behind a proxy subpath (can be configured via env).
        root_path_env = os.environ.get("RHK_ROOT_PATH")
        if root_path_env and ("root_path" in allowed) and ("root_path" not in mount_kwargs):
            mount_kwargs["root_path"] = root_path_env
    except (TypeError, ValueError, AttributeError) as exc:
        # If signature inspection fails, still attempt a minimal mount.
        log_exception("RHK_APP_MOUNT_SIG", "Gradio mount signature inspection failed.", exc)
        mount_kwargs = {"allowed_paths": allowed_paths}

    app = gr.mount_gradio_app(app, demo, path="/", **mount_kwargs)

    # proxy_headers=True is usually correct on Render/any reverse proxy.
    uvicorn.run(
        app,
        host=server_name,
        port=server_port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level="info",
    )


def main() -> None:
    """Start the RHK Gradio app.

    Strategy:
    - If we bind to a non-loopback address (0.0.0.0/::) or PORT is provided -> use uvicorn.
    - Else (localhost dev) -> use demo.launch().
    """

    cleanup_runtime_retention(_RUNTIME_PROFILE.name)
    _normalize_gradio_debug_env()
    _require_gradio_version(5)

    # ---------------------------------------------------------------------
    # Workdir determinism
    # ---------------------------------------------------------------------
    try:
        here = Path(__file__).resolve().parent
        os.chdir(here)
    except OSError as exc:
        log_exception("RHK_APP_CHDIR", "Working directory change failed.", exc)

    # IMPORTANT: patch Gradio analytics BEFORE importing rhk_ui/building Blocks.
    _disable_gradio_analytics_runtime()

    # Import UI only after analytics guard is in place.
    from rhk_ui import build_demo  # local import by design

    demo, _css, _theme = build_demo()

    # Gradio 6 moved theme/css/js/head to launch(); we stash these in build_demo.
    gradio_assets: Dict[str, Any] = getattr(demo, "_rhk_launch_kwargs", {}) or {}

    # ---------------------------------------------------------------------
    # Resolve host/port
    # ---------------------------------------------------------------------
    port_env = os.environ.get("PORT")
    if port_env and str(port_env).isdigit():
        # Cloud/Render: bind exactly to provided PORT.
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
            preferred = 7860
            if _port_is_free(server_name, preferred):
                server_port = preferred
            else:
                picked: Optional[int] = None
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

    allowed_paths = _compute_allowlisted_paths()

    # Ensure Gradio file serving allowlist is set even if launch()/mount() kwargs
    # change across versions. Using the env var is the most robust cross-version
    # mechanism. (Comma-separated absolute paths.)
    _ensure_env_csv("GRADIO_ALLOWED_PATHS", allowed_paths)

    # Hosted mode criteria:
    # - Render sets PORT and expects binding to 0.0.0.0:$PORT.
    # - Gradio's own `launch(server_name='0.0.0.0')` can raise a ValueError because
    #   the local URL check uses `requests.head()` against 0.0.0.0.
    use_uvicorn = server_name in {"0.0.0.0", "::"}

    if use_uvicorn:
        _run_hosted_uvicorn(
            demo=demo,
            server_name=server_name,
            server_port=server_port,
            gradio_assets=gradio_assets,
            allowed_paths=allowed_paths,
        )
        return

    # ---------------------------------------------------------------------
    # Local/dev: use demo.launch()
    # ---------------------------------------------------------------------
    launch_kwargs = dict(gradio_assets)
    try:
        sig = inspect.signature(demo.launch)
        allowed = set(sig.parameters.keys())
        launch_kwargs = {k: v for k, v in launch_kwargs.items() if (k in allowed and v is not None)}

        # Allow serving generated export files (PDF/DOCX/ZIP).
        if "allowed_paths" in allowed:
            cur = launch_kwargs.get("allowed_paths")
            if cur is None:
                launch_kwargs["allowed_paths"] = allowed_paths
            else:
                try:
                    lst = list(cur) if isinstance(cur, (list, tuple, set)) else [cur]
                    for d in allowed_paths:
                        if d not in lst:
                            lst.append(d)
                    launch_kwargs["allowed_paths"] = lst
                except (TypeError, ValueError) as exc:
                    log_exception("RHK_APP_ALLOWED_PATHS", "Allowed paths merge failed.", exc)
                    launch_kwargs["allowed_paths"] = allowed_paths

        # Explicitly disable analytics if supported by this Gradio version.
        for k in ("analytics_enabled", "enable_analytics"):
            if k in allowed:
                launch_kwargs[k] = False

        # Prefer disabling queueing entirely if supported.
        for k in ("enable_queue", "enable_queueing"):
            if k in allowed:
                launch_kwargs[k] = False
    except (TypeError, ValueError, AttributeError) as exc:
        log_exception("RHK_APP_LAUNCH_SIG", "Launch signature inspection failed.", exc)
        launch_kwargs = {}

    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=_RUNTIME_PROFILE.share,
        **launch_kwargs,
    )


if __name__ == "__main__":
    main()
