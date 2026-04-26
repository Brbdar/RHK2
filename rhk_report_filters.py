"""Pure text-processing helpers extracted from ``rhk_reports``.

These functions are deliberately small, side-effect-free, and easy to test
in isolation. They were factored out of the 9 000-LoC ``rhk_reports.py``
during the architectural cleanup so that the report builder can be
understood and reviewed in pieces.

Public surface
--------------
- ``_md_kv`` / ``_md_section``: tiny markdown helpers.
- ``_format_warning_item``: render structured warnings without leaking dicts.
- ``_strip_procedere_from_text``: drop procedural paragraphs from a narrative.
- ``_sanitize_concluding`` / ``_sanitize_interpretation_block``: keep
  diagnostic interpretation, remove recommendation-style content.
- ``_no_congestion_context`` / ``_filter_narrative_block``: gate-aware
  narrative filtering keyed on the (now-explicit) congestion-assessability.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from rhk_base import fmt_float
from rhk_logging import log_exception
from rhk_validation import safe_float as _safe_float

# Match the recoverable-error tuple used by the rest of rhk_reports so that
# extracted helpers preserve the original except clauses verbatim.
_REPORT_RECOVERABLE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    TypeError,
    ValueError,
    ImportError,
    ModuleNotFoundError,
)

__all__ = [
    "_md_kv",
    "_md_section",
    "_format_warning_item",
    "_strip_procedere_from_text",
    "_sanitize_concluding",
    "_sanitize_interpretation_block",
    "_no_congestion_context",
    "_filter_narrative_block",
]


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _md_kv(label: str, value: str) -> str:
    return f"- **{label}:** {value}"


def _md_section(title: str, lines: List[str], *, add_colon: bool = False) -> str:
    """Build a section from a list of list-items.

    ``add_colon=True`` yields plain-text headers like ``Klinik:`` (used for
    Arztbericht summary blocks).
    """
    if not lines:
        return ""
    if add_colon:
        return f"{title}:\n" + "\n".join(lines)
    return f"### {title}\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Warning rendering
# ---------------------------------------------------------------------------

def _format_warning_item(w: Any) -> str:
    """Render warning/hint items robustly.

    Some logic paths attach structured dicts like
    ``{"code": ..., "severity": ..., "message": ..., "fields": ..., "values": ...}``.
    We must never leak raw dict representations into the UI/report.
    """
    if w is None:
        return ""
    if isinstance(w, dict):
        msg = str((w.get("message") or "")).strip()
        if not msg:
            msg = str((w.get("code") or "")).strip()
        try:
            vals = w.get("values") or {}
            if isinstance(vals, dict) and vals:
                k0 = next(iter(vals.keys()))
                v0 = vals.get(k0)
                if isinstance(v0, (int, float)):
                    key_map = {
                        "pasp_echo": "sPAP (Echo)",
                        "trv_ms": "TRV",
                        "rap_rest": "RAP",
                        "pawp_rest": "PAWP",
                        "mpap_rest": "mPAP",
                        "co_rest": "CO",
                        "ci_rest": "CI",
                    }
                    lab = key_map.get(str(k0), str(k0))
                    if lab:
                        msg = f"{msg} ({lab}: {fmt_float(v0, 1)})"
        except _REPORT_RECOVERABLE_ERRORS as exc:
            log_exception(
                "RHK_REP_WARN_ITEM_FORMAT",
                "Warning item value formatting failed.",
                exc,
            )
        return msg
    return str(w).strip()


# ---------------------------------------------------------------------------
# Narrative sanitisers
# ---------------------------------------------------------------------------

def _strip_procedere_from_text(text: str) -> str:
    """Remove procedural / repetitive paragraphs from a narrative used outside Procedere."""
    if not isinstance(text, str):
        return ""
    raw = text.strip()
    if not raw:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    keep: List[str] = []
    bad_kw = [
        "Empfohlen:", "Empfohlen", "Procedere", "Vorstellung", "Board", "Mitbeurteilung",
        "Therapieoptimierung", "Abklärung", "PH-Zentrum", "Autoimmun", "HIV", "Infektiologie",
        "Genetik", "angeborene", "HRCT", "V/Q", "Pulmonalisangiographie", "Therapie",
        "Diagnose/Einordnung", "ESC/ERS", "REVEAL",
    ]
    for p in paras:
        if any(k.lower() in p.lower() for k in bad_kw):
            continue
        keep.append(p)
    return "\n\n".join(keep).strip()


def _sanitize_concluding(text: str) -> str:
    """Keep etiological conclusion, but strip recommendation-style content.

    For the Arztbericht interpretation block we must NOT output
    "Zusatzhinweis:" paragraphs or any explicit recommendation phrasing
    ("Empfohlen", "Mitbeurteilung", "Therapieplanung", "PH-Zentrum",
    "Abklärung gemäß Leitlinie", etc.). Those belong only in the dedicated
    Procedere section.
    """
    if not isinstance(text, str):
        return ""
    t = str(text or "").strip()
    if not t:
        return ""

    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    cleaned_paras: List[str] = []
    for p in paras:
        if re.match(r"^zusatzhinweis\s*:\s*", p.strip(), flags=re.IGNORECASE):
            continue
        cleaned_paras.append(p)
    t = "\n\n".join(cleaned_paras).strip()
    if not t:
        return ""

    rec_markers = [
        "empfehl",
        "ph-zentrum",
        "mitbeurteilung",
        "therapieplanung",
        "therapie nach",
        "strukturierte komplettierung",
        "abklärung gemäß",
        "leitlinie",
        "risikoadaptiert",
        "komplette",
        "optimierung/abklärung",
    ]

    lines = [ln.strip() for ln in t.splitlines()]
    kept_lines: List[str] = []
    for ln in lines:
        s = ln.lower()
        if any(m in s for m in rec_markers):
            continue
        kept_lines.append(ln)
    t = " ".join([ln for ln in kept_lines if ln]).strip()
    if not t:
        return ""

    sents = re.split(r"(?<=[.!?])\s+", t)
    keep_sents = [s for s in sents if not any(m in s.lower() for m in rec_markers)]
    return " ".join([s.strip() for s in keep_sents if s.strip()]).strip()


def _sanitize_interpretation_block(text: str) -> str:
    """Final safety net for the Arztbericht interpretation block.

    Keeps diagnostic / etiology interpretation sentences. Reliably removes
    procedural recommendations even when they appear inline in the middle
    of a sentence. Drops any dedicated 'Zusatzhinweis:' paragraph.
    """
    if not isinstance(text, str):
        return ""
    t = str(text or "").strip()
    if not t:
        return ""

    rec_markers = [
        "empfehl",
        "ph-zentrum",
        "mitbeurteilung",
        "therapieplanung",
        "therapie nach",
        "abklärung gemäß",
        "leitlinie",
        "risikoadaptiert",
        "komplette",
        "optimierung/abklärung",
        "interdisziplin",
        "diagnostik werden empfohlen",
        "werden empfohlen",
        "empfohlen wird",
    ]

    def _truncate_before_marker(sentence: str) -> str:
        s = str(sentence or "").strip()
        if not s:
            return ""
        sl = s.lower()
        cut_positions = [p for p in (sl.find(mk) for mk in rec_markers) if p >= 0]
        if not cut_positions:
            return s
        prefix = s[: min(cut_positions)].rstrip(" ;,–-:\n\t")
        return prefix if len(prefix) >= 20 else ""

    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    content_paras = [p for p in paras if not re.match(r"^zusatzhinweis\s*:\s*", p, flags=re.IGNORECASE)]

    kept_sents = [
        cleaned
        for p in content_paras
        for s in re.split(r"(?<=[.!?])\s+", p.strip())
        for cleaned in [_truncate_before_marker(s)]
        if cleaned
    ]
    out = " ".join(s.strip() for s in kept_sents if s.strip()).strip()
    return re.sub(r"\s+", " ", out).strip()


# ---------------------------------------------------------------------------
# Congestion gating (uses the assessability flag introduced in rhk_case)
# ---------------------------------------------------------------------------

def _no_congestion_context(ui: Dict[str, Any], der: Dict[str, Any]) -> bool:
    """Return True only when there is *positive* evidence of "no congestion".

    Gates downstream filtering of contradictory phrases like
    "Bei führender Stauung". It must NOT fire when congestion data is
    simply missing (no RAP / no IVC / no PAWP) — in that case the absence
    of a positive flag does not mean absence of congestion, and we keep
    the template content as-is rather than silently editing it out.
    """
    der_d = der or {}
    ui_d = ui or {}
    congestion_likely = bool(der_d.get("congestion_likely"))
    congestion_assessable = bool(der_d.get("congestion_assessable"))
    pawp = _safe_float(ui_d.get("pawp_rest"))
    pv_assessable = pawp is not None
    pv_stauung_likely = bool(pv_assessable and pawp > 15)

    cv_negative = congestion_assessable and not congestion_likely
    pv_negative = pv_assessable and not pv_stauung_likely
    return cv_negative and pv_negative


def _filter_narrative_block(text: str, ui: Dict[str, Any], der: Dict[str, Any]) -> str:
    """Conservatively remove known contradictory stock phrases from narrative bundles.

    IMPORTANT: This must never invent content; it only removes text that
    is internally contradictory to the current case (e.g. "Bei führender
    Stauung" while no congestion).
    """
    t = str(text or "")
    if not t.strip():
        return ""

    if _no_congestion_context(ui, der):
        if "Bei führender Stauung" in t:
            t = re.sub(r"\s*Bei führender Stauung:\s*[^.]*\.?\s*", " ", t, flags=re.IGNORECASE)

    # Reduce redundant one-liners that often duplicate earlier context.
    # Only strip the *bare* "Aktuell RHK in Ruhe." sentence — extended
    # variants ("Aktuell RHK in Ruhe mit ergänzender Belastungsmessung.", …)
    # carry information the referring physician needs and must remain intact.
    t = t.replace("Aktuell RHK in Ruhe.", "").strip()

    # In-house center reports must not recommend referral to themselves.
    t = re.sub(r"\s*Diskussion\s+im\s+Expert[^.]*\.\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*Diskussion\s+im\s+PH-Board[^.]*\.\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*Vorstellung\s+im\s+PH-Zentrum[^.]*\.\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*Vorstellung\s+im\s+Referenzzentrum[^.]*\.\s*", " ", t, flags=re.IGNORECASE)

    # Clean multiple spaces introduced by removals.
    return " ".join(t.split())
