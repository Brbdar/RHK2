"""Central structured logging for recoverable runtime errors."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

_LOGGER_NAME = "rhk.app"

# Correlation ID surfaced in every log line. Callers can push/pop one per
# logical operation (import, report build, save). Defaults to the empty string
# so log lines stay valid JSON even outside an operation scope.
_CORRELATION_ID: ContextVar[str] = ContextVar("rhk_correlation_id", default="")

_PATH_KEYS = {
    "export_dir",
    "file",
    "file_path",
    "loaded_path",
    "out_dir",
    "path",
    "source_path",
    "target_dir",
    "tmp_path",
}
_FILENAME_KEYS = {
    "case_filename",
    "file_name",
    "filename",
    "loaded_name",
    "source_name",
}
_PHI_KEYS = {
    "birthdate",
    "dob",
    "geburtsdatum",
    "kurzanamnese",
    "patient_id",
    "patient_name",
    "relevante_vorerkrankungen",
    "story",
}
_PAYLOAD_KEYS = {
    "baseline_payload",
    "case",
    "case_state",
    "echo_cur",
    "echo_prev",
    "imports",
    "migrated_payload",
    "parsed",
    "payload",
    "summary",
    "ui",
    "ui_dict",
}
_FILE_TOKEN_RE = re.compile(
    r"\b[\w.-]+\.(?:json|docx|pdf|zip|txt|csv|xlsx|png|jpg|jpeg|webp|bmp|tif|tiff|log)\b",
    flags=re.IGNORECASE,
)
_WINDOWS_PATH_RE = re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s\"']+\\)*[^\\\s\"']+")
_POSIX_PATH_RE = re.compile(r"(?<![A-Za-z0-9._-])/(?:[^/\s\"']+/)*[^/\s\"']+")


class _JsonLineFormatter(logging.Formatter):
    """Emit each record as a single JSON line.

    The log message is already a JSON payload produced by :func:`_build_payload`.
    This formatter wraps it with ``ts``/``level``/``logger`` envelope fields so
    the whole line can be parsed by downstream log tooling without splitting on
    whitespace.
    """

    def format(self, record: logging.LogRecord) -> str:
        # The message is the pre-serialised JSON string from _build_payload.
        try:
            inner = json.loads(record.getMessage())
        except (ValueError, TypeError):
            inner = {"message": record.getMessage()}
        envelope: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
        }
        envelope.update(inner)
        return json.dumps(envelope, ensure_ascii=False, default=str)


def _get_logger() -> logging.Logger:
    """Return (and lazily configure) the application-wide logger."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonLineFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def new_correlation_id() -> str:
    """Generate a short correlation ID suitable for a single logical operation."""
    return uuid.uuid4().hex[:12]


def set_correlation_id(cid: str | None) -> Any:
    """Bind *cid* as the correlation ID for the current context.

    Returns the :class:`contextvars.Token` that can be passed to
    :func:`contextvars.ContextVar.reset` to restore the previous value.
    """
    return _CORRELATION_ID.set(cid or "")


def get_correlation_id() -> str:
    """Return the correlation ID bound to the current context (``""`` if none)."""
    return _CORRELATION_ID.get()


def _redacted_summary(value: Any, *, reason: str) -> dict[str, Any]:
    """Build a safe metadata dict for a redacted value (type + size)."""
    summary: dict[str, Any] = {
        "_redacted": True,
        "reason": reason,
        "type": type(value).__name__,
    }
    try:
        summary["size"] = len(value)
    except TypeError:
        pass
    return summary


def _sanitize_text(value: Any, *, key: str | None = None) -> str:
    """Sanitize a text value by redacting paths, filenames, and PHI."""
    key_name = str(key or "").strip().lower()
    if key_name in _PATH_KEYS:
        return "<redacted:path>"
    if key_name in _FILENAME_KEYS:
        return "<redacted:file>"
    if key_name in _PHI_KEYS:
        return "<redacted:phi>"

    text = str(value)
    text = _WINDOWS_PATH_RE.sub("<redacted:path>", text)
    text = _POSIX_PATH_RE.sub("<redacted:path>", text)
    text = _FILE_TOKEN_RE.sub("<redacted:file>", text)
    return text


def _safe_value(key: str, value: Any) -> Any:
    """Return a JSON-safe, PHI-redacted representation of *value*."""
    key_name = str(key or "").strip().lower()

    if key_name in _PAYLOAD_KEYS:
        return _redacted_summary(value, reason="payload")
    if key_name in _PATH_KEYS:
        return "<redacted:path>"
    if key_name in _FILENAME_KEYS:
        return "<redacted:file>"
    if key_name in _PHI_KEYS:
        return "<redacted:phi>"
    if isinstance(value, os.PathLike):
        return "<redacted:path>"
    if isinstance(value, str):
        return _sanitize_text(value, key=key_name)
    if isinstance(value, Mapping):
        return {str(k): _safe_value(str(k), v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        seq = list(value)
        if key_name in _PAYLOAD_KEYS:
            return _redacted_summary(seq, reason="payload")
        safe_items = [_safe_value(key_name, item) for item in seq[:20]]
        if len(seq) > 20:
            safe_items.append("<truncated>")
        return safe_items

    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except (TypeError, ValueError):
        return _sanitize_text(value, key=key_name)


def _safe_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """Sanitize all values in a context dict for safe logging."""
    return {str(k): _safe_value(str(k), v) for k, v in (ctx or {}).items()}


def _build_payload(error_code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Construct the structured JSON payload for a log entry."""
    payload: dict[str, Any] = {
        "error_code": str(error_code),
        "message": _sanitize_text(message),
    }
    cid = get_correlation_id()
    if cid:
        payload["correlation_id"] = cid
    payload.update(extra)
    return payload


def log_warning(error_code: str, message: str, **context: Any) -> None:
    """Emit a structured WARNING log with sanitized context."""
    payload = _build_payload(
        error_code,
        message,
        context=_safe_context(context),
    )
    _get_logger().warning(json.dumps(payload, ensure_ascii=False, default=str))


def log_exception(error_code: str, message: str, exc: BaseException, **context: Any) -> None:
    """Emit a structured ERROR log for an exception with sanitized context."""
    payload = _build_payload(
        error_code,
        message,
        error_type=type(exc).__name__,
        error=_sanitize_text(exc),
        context=_safe_context(context),
    )
    _get_logger().error(json.dumps(payload, ensure_ascii=False, default=str))
