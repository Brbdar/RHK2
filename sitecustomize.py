"""
Clinical Runtime Shield & Environment Hardening.

This module is automatically loaded by Python at startup (via site-packages).
It establishes a 'Clinical Sandbox' to enforce privacy, stability, and headless operation
before any application code executes.

MASTERMIND IMPROVEMENTS:
- Privacy Force-Field: Disables HuggingFace Hub telemetry and Gradio analytics globally.
- Headless Enforcement: Forces Matplotlib to 'Agg' backend to prevent X11/GUI crashes.
- Thread Safety: Neutralizes background analytics threads that cause GIL/Segfaults in mixed envs.
- Runtime Audit: Logs security actions to stderr for traceability.

Usage:
  Deployed automatically via python's site-packages structure.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import os
import sys
from types import ModuleType
from typing import Any, List, Optional, Set

# ===========================================================================
# 1. CLINICAL ENVIRONMENT HARDENING (ENV VARS)
# ===========================================================================
# These must be set BEFORE any other imports occur to ensure libraries respect them.

_ENV_DEFAULTS = {
    # PRIVACY: Block all built-in analytics and telemetry
    "GRADIO_ANALYTICS_ENABLED": "False",
    "GRADIO_TELEMETRY_ENABLED": "False",
    "GRADIO_NO_ANALYTICS": "True",
    "GRADIO_CHECK_VERSION": "False",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "ANALYTICS_OPT_OUT": "true",
    
    # STABILITY: Force Headless Rendering (Critical for Server/Docker)
    # Prevents crash: "TclError: no display name and no $DISPLAY environment variable"
    "MPLBACKEND": "Agg",
    
    # LOGGING: Cleaner logs for clinical archiving (Unbuffered for Docker)
    "PYTHONUNBUFFERED": "1",
    "NO_COLOR": "1",
}

for key, val in _ENV_DEFAULTS.items():
    # Only set if not already present (allows explicit override by sysadmin)
    os.environ.setdefault(key, val)


# ===========================================================================
# 2. RUNTIME PATCHING LOGIC (The Neutralizer)
# ===========================================================================

def _audit_log(msg: str) -> None:
    """Writes to stderr to ensure visibility in systemd/docker logs without polluting stdout."""
    sys.stderr.write(f"[RUNTIME GUARD] {msg}\n")
    sys.stderr.flush()

def _safe_noop(*args: Any, **kwargs: Any) -> None:
    """Universal no-op function for neutralized methods."""
    return None

def _noop_false(*args: Any, **kwargs: Any) -> bool:
    """Universal no-op returning False."""
    return False

def _patch_gradio_analytics(mod: ModuleType) -> None:
    """
    Surgically disables Gradio's analytics module.
    Prevents network calls and dependency imports that trigger privacy violations.
    """
    targets = [
        "report", 
        "version_check", 
        "on_event", 
        "initiated_analytics", 
        "get_local_ip_address",
        "completed_usage",
        "error_analytics"
    ]
    
    # 1. Force Flags
    if hasattr(mod, "analytics_enabled"):
        try:
            # Force logic to always return False
            mod.analytics_enabled = _noop_false # type: ignore
        except Exception:
            pass

    # 2. Stub Functions
    count = 0
    for target in targets:
        if hasattr(mod, target):
            try:
                setattr(mod, target, _safe_noop)
                count += 1
            except Exception:
                pass
            
    if count > 0:
        _audit_log(f"Secured 'gradio.analytics' ({count} vectors neutralized).")

def _patch_gradio_queueing(mod: ModuleType) -> None:
    """
    Neutralizes background analytics threads in Gradio Queues.
    These threads are the #1 cause of 'pandas' import crashes in mixed NumPy envs.
    """
    target_classes = ("Queue", "Queueing", "QueueManager", "EventQueue")
    danger_methods = (
        "compute_analytics_summary", 
        "_compute_analytics_summary", 
        "_get_df", 
        "start_analytics_thread",
        "submit_analytics"
    )
    
    patched = 0
    for cls_name in target_classes:
        cls = getattr(mod, cls_name, None)
        if cls is None:
            continue
            
        for meth in danger_methods:
            if hasattr(cls, meth):
                try:
                    setattr(cls, meth, _safe_noop)
                    patched += 1
                except Exception:
                    pass
    
    if patched > 0:
        _audit_log(f"Stabilized 'gradio.queueing' ({patched} threads neutralized).")


# ===========================================================================
# 3. IMPORT INTERCEPTOR (META PATH FINDER)
# ===========================================================================

class _RuntimeGuard(importlib.abc.MetaPathFinder):
    """
    Intercepts imports to apply patches immediately after module loading,
    ensuring security before any library code executes.
    """
    
    TARGETS: Set[str] = {"gradio.queueing", "gradio.analytics"}

    def find_spec(self, fullname: str, path: Optional[List[str]], target: Optional[ModuleType] = None) -> Any:
        if fullname not in self.TARGETS:
            return None

        # Delegate to standard finder
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None

        # Wrap the loader
        spec.loader = _GuardedLoader(spec.loader)
        return spec


class _GuardedLoader(importlib.abc.Loader):
    """Wraps the original loader to inject patches post-execution."""
    
    def __init__(self, original_loader: Any):
        self.orig = original_loader

    def create_module(self, spec: Any) -> Optional[ModuleType]:
        # Respect standard creation protocol
        if hasattr(self.orig, "create_module"):
            return self.orig.create_module(spec) # type: ignore
        return None

    def exec_module(self, module: ModuleType) -> None:
        # 1. Load the module normally
        if hasattr(self.orig, "exec_module"):
            self.orig.exec_module(module) # type: ignore
        else:
            # Fallback for legacy loaders
            mod_spec = getattr(module, "__spec__", None)
            if mod_spec:
                try:
                    importlib._bootstrap._exec(mod_spec, module) # type: ignore
                except Exception:
                    pass

        # 2. Apply Clinical Security Patches
        name = module.__name__
        try:
            if name == "gradio.queueing":
                _patch_gradio_queueing(module)
            elif name == "gradio.analytics":
                _patch_gradio_analytics(module)
        except Exception as e:
             _audit_log(f"WARNING: Patching failed for {name}: {e}")


# ===========================================================================
# 4. INSTALLATION & BOOTSTRAP
# ===========================================================================

def _install_guard() -> None:
    """Installs the RuntimeGuard into sys.meta_path."""
    try:
        # Avoid duplicate installation
        if any(isinstance(f, _RuntimeGuard) for f in sys.meta_path):
            return

        # Insert at position 0 to ensure priority
        sys.meta_path.insert(0, _RuntimeGuard())
        
        # Retroactive Patching (if sitecustomize loaded late)
        for name in _RuntimeGuard.TARGETS:
            if name in sys.modules:
                _audit_log(f"Late patching applied to {name}")
                if name == "gradio.queueing":
                    _patch_gradio_queueing(sys.modules[name])
                elif name == "gradio.analytics":
                    _patch_gradio_analytics(sys.modules[name])
        
        _audit_log("Clinical Shield Active.")
                    
    except Exception as e:
        # Critical fail-safe: never crash python startup
        sys.stderr.write(f"[FATAL SITE ERROR] Could not install RuntimeGuard: {e}\n")

# Run installation
if __name__ != "__main__":
    _install_guard()