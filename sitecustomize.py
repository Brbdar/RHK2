"""Site customizations for the RHK Befundassistent.

This module is imported automatically by Python (if present on sys.path).

Why this exists
----------------
Some clinic setups use Anaconda with NumPy 2.x but older compiled extension
packages (pyarrow/numexpr/bottleneck). Gradio's background analytics thread
may import pandas which then imports these extensions and can crash the app.

We *do not need* Gradio's analytics for clinical use.

So we:
1) disable Gradio analytics via environment variables
2) monkeypatch Gradio queue analytics collectors to no-op at import time

This avoids hard failures without changing any clinical logic.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import os
import sys
from types import ModuleType
from typing import Optional


# ---------------------------------------------------------------------------
# 1) Environment-level opt-out (must be set as early as possible)
# ---------------------------------------------------------------------------
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "0")
os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "False")
os.environ.setdefault("GRADIO_TELEMETRY_ENABLED", "0")


def _patch_gradio_queueing(mod: ModuleType) -> None:
    """Best-effort patch for multiple Gradio versions."""

    def _noop(self, *args, **kwargs):  # noqa: D401
        """No-op analytics."""
        return None

    # Newer Gradio versions: class Queue; older: Queueing/QueueManager.
    for cls_name in ("Queue", "Queueing", "QueueManager", "EventQueue"):
        cls = getattr(mod, cls_name, None)
        if cls is None:
            continue
        for meth in ("compute_analytics_summary", "_get_df", "_compute_analytics_summary"):
            if hasattr(cls, meth):
                try:
                    setattr(cls, meth, _noop)
                except Exception:
                    pass


def _patch_module_if_needed(fullname: str, module: ModuleType) -> None:
    if fullname == "gradio.queueing":
        _patch_gradio_queueing(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    """MetaPath finder that wraps loader.exec_module to patch after import."""

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if fullname not in {"gradio.queueing"}:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

        original_loader = spec.loader

        class _Loader(importlib.abc.Loader):
            def create_module(self, spec):  # type: ignore[override]
                if hasattr(original_loader, "create_module"):
                    return original_loader.create_module(spec)  # type: ignore[misc]
                return None

            def exec_module(self, module: ModuleType) -> None:  # type: ignore[override]
                if hasattr(original_loader, "exec_module"):
                    original_loader.exec_module(module)  # type: ignore[misc]
                else:
                    # Very old loaders
                    importlib._bootstrap._exec(module.__spec__, module)  # type: ignore[attr-defined]
                _patch_module_if_needed(fullname, module)

        spec.loader = _Loader()
        return spec


# Install the import patcher early.
try:
    if not any(isinstance(f, _PatchFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())
except Exception:
    pass


# If gradio.queueing is already imported, patch immediately.
try:
    m = sys.modules.get("gradio.queueing")
    if m is not None:
        _patch_gradio_queueing(m)
except Exception:
    pass
