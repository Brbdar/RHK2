#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.29: rhk_echo_pdf_import.py - Sanitization (unphys/0->None) via HARD_LIMITS, safer autoscale, compiled regex, dead-code removal
"""Echo PDF / OCR Import (TTE).

Dieses Modul extrahiert Echo-Messwerte aus:
- PDF mit Textlayer (bevorzugt)
- Scan-PDF (Page-1 Render + optionales OCR)
- Screenshot-Bilder (OCR, optional)

Klinische Leitplanken (nicht verhandelbar)
- **Fehlende Werte ≠ 0**: numerische 0 wird als *fehlend* behandelt (Import-Sanitization).
- **Unphysiologische Werte gelten als nicht vorhanden**: Werte außerhalb sehr breiter Hard-Limits werden verworfen.
- **Keine Fantasie-Werte**: es werden nur Werte übernommen, die im Text tatsächlich vorkommen.
- **Manuelle Eingaben werden nicht überschrieben**: Dieses Modul liefert nur einen Payload; Merge-Policy liegt in der UI.

Design
- Dependency-light: Pflichtabhängigkeiten nur Standardbibliothek + Projektmodule.
- PDF/OCR Backends werden lazy geladen. Wenn ein Backend fehlt, wird das in ``meta.hint`` sichtbar.
- ``extract_echo_from_text`` darf niemals PDF-Backends benötigen (wird von Browser-OCR genutzt).

Rückgabe
- ui_values: ``dict[str, Any]`` (kompatibel mit UI-Keys)
- meta: ``dict[str, Any]`` (Quelle/Backend, Seitenzahl, Hinweise, Diagnostik)

Hinweis: Dieses Modul normalisiert Einheiten (z. B. TRV cm/s → m/s) und
ist absichtlich konservativ. Neue Parameter bitte über ``PATTERNS`` ergänzen.
"""

from __future__ import annotations

import importlib
import io
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Optional

from rhk_validation import sanitize_ui_numbers

# =============================================================================
# Types & Constants
# =============================================================================

Meta = dict[str, Any]
UI = dict[str, Any]

_MIN_TEXT_LEN: int = 20
_OCR_MIN_TEXT_LEN: int = 20
_OCR_SCORE_THRESHOLD: int = 4
_PDF_OCR_ZOOM: float = 2.0


@dataclass(frozen=True)
class MatchSpec:
    """Pattern spec for a single UI key."""

    ui_key: str
    pattern: str
    flags: int = re.IGNORECASE
    group: int = 1
    post: Optional[str] = None  # name of postprocessor

    # Backwards-compat alias: older call sites used `spec.key`.
    @property
    def key(self) -> str:  # pragma: no cover - compat shim
        return self.ui_key


def _append_hint(meta: Meta, msg: str) -> None:
    msg = (msg or "").strip()
    if not msg:
        return
    old = (meta.get("hint") or "").strip()
    meta["hint"] = (old + (" " if old else "") + msg).strip()


# =============================================================================
# Text normalization & parsing
# =============================================================================

def _norm_text(s: str) -> str:
    """Normalize text from PDF text-layers and OCR.

    Entfernt typische Converter-Artefakte, normalisiert Unicode-Minus und Einheiten.
    """
    if not s:
        return ""
    # Unicode minus variants
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    # Common artefacts from redactors / converters
    s = s.replace("$", " ").replace("~", " ").replace("|", " ").replace("`", "")
    # Units
    s = s.replace("cm²", "cm2").replace("m²", "m2")
    # OCR artefacts: superscript '2' becomes '?' or is dropped
    s = re.sub(r"\b(cm|m)\?\b", lambda m: m.group(1) + "2", s)
    s = re.sub(r"\bml\s*/\s*(cm|m)\?\b", lambda m: f"ml/{m.group(1)}2", s, flags=re.IGNORECASE)
    # LaTeX-ish / converter variants
    s = re.sub(r"m\s*\^\s*2", "m2", s, flags=re.IGNORECASE)
    s = re.sub(r"m\s*\{\s*2\s*\}", "m2", s, flags=re.IGNORECASE)
    s = re.sub(r"m\s*\^\s*\{\s*2\s*\}", "m2", s, flags=re.IGNORECASE)
    s = re.sub(r"cm\s*\^\s*2", "cm2", s, flags=re.IGNORECASE)
    # OCR sometimes splits superscripts: 'ml/m 2' or 'cm 2'
    s = re.sub(r"\b(m|cm)\s+2\b", lambda m: m.group(1) + "2", s)
    s = s.replace("\u00a0", " ")
    # Keep line breaks, but normalize excessive spacing
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _to_float(raw: Any) -> Optional[float]:
    """Parse a number from a raw regex group.

    - supports German decimal comma
    - strips stray unit characters
    - returns None on failure

    Note: This is importer-local parsing. Final plausibility gating happens via
    ``sanitize_ui_numbers`` (HardLimits).
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = _norm_text(s)
    # keep digits, comma, dot, minus
    s = re.sub(r"[^0-9,\.\-]", "", s)
    if not s or s in ("-", ".", ","):
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    # If multiple dots exist, keep only the last as decimal separator (conservative)
    if s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        v = float(s)
        # reject NaN/Inf
        if v != v or v in (float("inf"), float("-inf")):
            return None
        return v
    except Exception:
        return None


# =============================================================================
# Post-processing / unit conversion
# =============================================================================

def _post_trv_to_ms(v: Optional[float]) -> Optional[float]:
    """Convert TRV to m/s.

    Some sources provide TRV as cm/s (e.g. 340.0). If magnitude suggests cm/s,
    convert to m/s.
    """
    if v is None:
        return None
    if v > 20:  # implausible for m/s -> likely cm/s
        return round(v / 100.0, 3)
    return v


def _post_yesno(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "ja", "yes", "true"):
        return "ja"
    if s in ("0", "nein", "no", "false"):
        return "nein"
    if "nein" in s or "kein" in s:
        return "nein"
    if "ja" in s or "notch" in s:
        return "ja"
    return None


def _post_ivc_collapse_yesno(v: Optional[float]) -> Optional[str]:
    if v is None:
        return None
    return "ja" if v >= 50.0 else "nein"


_POST: dict[str, Callable[[Any], Any]] = {
    "trv_to_ms": _post_trv_to_ms,
    "ivc_collapse_yesno": _post_ivc_collapse_yesno,
}


# =============================================================================
# OCR autoscale heuristics
# =============================================================================

# Thresholds: rescale only when value is *clearly* out-of-range by a large factor.
# This avoids corrupting legitimate extreme values (e.g. RA area 90 cm2).
_SCALE10_TRIGGER_FACTOR: float = 2.0
_SCALE100_TRIGGER_FACTOR: float = 20.0


def _auto_scale(ui_key: str, v: Optional[float]) -> Optional[float]:
    """Conservative OCR autoscaling for dropped decimal separators.

    We only rescale if:
    - v is outside a very conservative plausible range, AND
    - v is at least N× above the upper bound, AND
    - v/10 or v/100 falls into the plausible range.

    This prevents silent corruption for *moderately* out-of-range values.
    """
    if v is None:
        return None

    # Conservative plausibility ranges (min, max) used ONLY for autoscale triggers.
    # Final hard gating is done in rhk_validation.HARD_LIMITS.
    R: dict[str, tuple[float, float]] = {
        # anthropometrics
        "height_cm": (120.0, 220.0),
        "weight_kg": (30.0, 200.0),
        "bsa_m2": (1.0, 3.0),
        # mm values
        "tapse_mm": (5.0, 40.0),
        "rv_edd_mm": (20.0, 90.0),
        "rv_esd_mm": (10.0, 80.0),
        "rv_wall_thickness_mm": (1.0, 15.0),
        "ivc_exp_mm": (5.0, 35.0),
        "ivc_insp_mm": (0.0, 30.0),
        "ivc_diam_mm": (5.0, 35.0),
        # pressures / timings
        "pasp_echo": (10.0, 150.0),
        "paat_ms": (30.0, 200.0),
        "rvet_ms": (100.0, 600.0),
        # ratios
        "tapse_spap_ratio": (0.05, 2.0),
        "paat_rvet_ratio": (0.05, 1.0),
        # velocities
        "trv_ms": (1.0, 7.0),
        # areas / volumes
        "ra_esa_cm2": (5.0, 120.0),
        "ra_eda_cm2": (5.0, 140.0),
        "rv_eda_cm2": (5.0, 160.0),
        "rv_esa_cm2": (5.0, 160.0),
        # volumes (ml)
        "rv_3d_edv_ml": (20.0, 450.0),
        "rv_3d_esv_ml": (5.0, 350.0),
        "rv_3d_sv_ml": (5.0, 250.0),
        # indexed volumes (ml/m2)
        "rv_3d_edvi_ml_m2": (10.0, 250.0),
        "rv_3d_esvi_ml_m2": (1.0, 200.0),
        "lavi_ml_m2": (5.0, 120.0),
        "la_vmax_ml": (10.0, 250.0),
        "la_esa_cm2": (5.0, 120.0),
        # percents
        "lvef": (5.0, 90.0),
        "rvfac_pct": (5.0, 80.0),
        "rv_3d_ef_pct": (5.0, 90.0),
        "ivc_collapse_index_pct": (0.0, 100.0),
        # strain (negative)
        "rv_gls_pct": (-60.0, 0.0),
        "rv_fwls_pct": (-60.0, 0.0),
    }

    # Special conversions first
    if ui_key == "trv_ms":
        # OCR often reads 340 for 3.40 m/s, or cm/s.
        if v > 20:
            v2 = v / 100.0
            lo, hi = R.get("trv_ms", (1.0, 7.0))
            if lo <= v2 <= hi:
                return round(v2, 2)
        return v

    # Strain: OCR sometimes drops the minus sign and/or decimal.
    if ui_key in ("rv_gls_pct", "rv_fwls_pct"):
        lo, hi = R.get(ui_key, (-60.0, 0.0))
        if lo <= v <= hi:
            return v
        if lo <= -v <= hi:
            return -v
        v10 = -v / 10.0
        if lo <= v10 <= hi:
            return round(v10, 1)
        v100 = -v / 100.0
        if lo <= v100 <= hi:
            return round(v100, 1)

    rng = R.get(ui_key)
    if not rng:
        return v

    lo, hi = rng
    if lo <= v <= hi:
        return v

    # Only scale down if value is far above plausible hi.
    if v > hi * _SCALE10_TRIGGER_FACTOR:
        v10 = v / 10.0
        if lo <= v10 <= hi:
            if ui_key.endswith("_ratio") or ui_key.endswith("_ml_m2"):
                return round(v10, 2)
            if ui_key.endswith("_mm") or ui_key.endswith("_pct") or ui_key in ("lvef", "rvfac_pct", "rv_3d_ef_pct"):
                return round(v10, 1)
            if ui_key in ("height_cm",):
                return round(v10, 0)
            if ui_key in ("weight_kg",):
                return round(v10, 1)
            if ui_key.endswith("_ml"):
                return round(v10, 1)
            return v10

    if v > hi * _SCALE100_TRIGGER_FACTOR:
        v100 = v / 100.0
        if lo <= v100 <= hi:
            if ui_key in ("weight_kg",):
                return round(v100, 2)
            if ui_key in ("height_cm",):
                return round(v100, 0)
            if ui_key.endswith("_ratio") or ui_key.endswith("_ml_m2"):
                return round(v100, 2)
            if ui_key.endswith("_mm") or ui_key.endswith("_pct") or ui_key in ("lvef", "rvfac_pct", "rv_3d_ef_pct"):
                return round(v100, 1)
            if ui_key.endswith("_ml"):
                return round(v100, 1)
            return v100

    return v


# =============================================================================
# Patterns (additive list)
# =============================================================================

# Patterns are intentionally permissive wrt whitespace/linebreaks.
PATTERNS: list[MatchSpec] = [
    # Klinik
    MatchSpec("height_cm", r"Gr[oö](?:ss|ß)e\s*:?\s*(\d{2,3}(?:[\.,]\d+)?)\s*cm"),
    MatchSpec("weight_kg", r"Gewicht\s*:?\s*(\d{2,3}(?:[\.,]\d+)?)\s*kg"),
    MatchSpec("bsa_m2", r"KOF\s*:?\s*(\d+(?:[\.,]\d+)?)\s*m2"),

    # Linksherz
    MatchSpec("lvef", r"LVEF\s*BiP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%?"),

    MatchSpec("la_vmax_ml", r"LA\s*Vmax\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml"),
    MatchSpec("la_esa_cm2", r"LA\s*ESA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("lavi_ml_m2", r"(?:3D[- ]?)?LAVI\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*(?:/|\s)\s*m2"),
    MatchSpec("ee_ratio", r"E\s*/\s*e\'?\s*:?\s*(\d+(?:[\.,]\d+)?)"),

    # RV dimensions/areas
    MatchSpec("rv_edd_mm", r"RVEDD\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    MatchSpec("rv_esd_mm", r"RVESD\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    MatchSpec("rv_eda_cm2", r"RVEDA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("rv_esa_cm2", r"RVESA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("rv_wall_thickness_mm", r"RV\s*wall\s*thickness\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),

    # 3D RV volumes (UI keys!)
    MatchSpec("rv_3d_edv_ml", r"3D[- ]?RVEDV\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml"),
    MatchSpec("rv_3d_esv_ml", r"3D[- ]?RVESV\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml"),
    MatchSpec("rv_3d_sv_ml", r"3D[- ]?RVSV\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml"),
    MatchSpec("rv_3d_edvi_ml_m2", r"3D[- ]?RVEDVi\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*(?:/|\s)\s*m2"),
    MatchSpec("rv_3d_esvi_ml_m2", r"3D[- ]?RVESVi\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*(?:/|\s)\s*m2"),
    MatchSpec("rv_3d_ef_pct", r"3D[- ]?RVEF\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%?"),

    # RA planimetry
    MatchSpec("ra_esa_cm2", r"RA\s*ESA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("ra_eda_cm2", r"RA\s*EDA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),

    # RV function
    MatchSpec("tapse_mm", r"TAPSE\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    # S' kann als S', S´ etc. erscheinen
    MatchSpec("s_prime_cm_s", r"\bS\s*[\'´`]?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm\s*(?:/|\s)\s*s"),
    MatchSpec("rvfac_pct", r"RVFAC\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%"),
    MatchSpec("tapse_spap_ratio", r"TAPSE\s*/\s*sPAP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm\s*(?:/|\s)\s*mmHg"),

    # Strain
    MatchSpec("rv_gls_pct", r"RV[- ]?GLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%"),
    MatchSpec("rv_fwls_pct", r"RV\s*FWLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%"),

    # PH signs
    MatchSpec("trv_ms", r"(?:TRV|TR\s*Vmax|TR\s*V\s*max)\s*:?\s*(\d+(?:[\.,]\d+)?)\s*(?:m\s*(?:/|\s)\s*s|cm\s*(?:/|\s)\s*s)", post="trv_to_ms"),
    MatchSpec("pasp_echo", r"sPAP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mmHg"),
    MatchSpec("paat_ms", r"PAAT\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ms"),
    MatchSpec("rvet_ms", r"RVET\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ms"),
    MatchSpec("paat_rvet_ratio", r"PAAT\s*/\s*RVET\s*:?\s*(\d+(?:[\.,]\d+)?)"),

    # Optional: PA diameter / RV-LV ratio
    MatchSpec("pa_diam_mm", r"PA\s*Durchmesser\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    MatchSpec("rv_lv_ratio", r"RV\s*/\s*LV\s*Ratio\s*:?\s*(\d+(?:[\.,]\d+)?)"),

    # Notch (maps to radio in UI)
    MatchSpec("rvot_notch", r"Notch\s*:?\s*([^\n\r]+)", group=1),

    # IVC (VCI)
    MatchSpec("ivc_exp_mm", r"VCI\s*expir\.?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    MatchSpec("ivc_insp_mm", r"VCI\s*inspir\.?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    MatchSpec("ivc_collapse_index_pct", r"VCI[- ]Kollaps(?:\s*Index\s*:?)?\s*(\d+(?:[\.,]\d+)?)\s*%"),

    MatchSpec("ivc_respiratory", r"VCI\s*atemvariabel\s*:?\s*(ja|nein)", group=1),
    MatchSpec("pericardial_effusion", r"Perikarderguss\s*:?\s*(ja|nein|0|1)", group=1),
]


@lru_cache(maxsize=1)
def _compiled_patterns() -> list[tuple[MatchSpec, re.Pattern[str]]]:
    out: list[tuple[MatchSpec, re.Pattern[str]]] = []
    for spec in PATTERNS:
        out.append((spec, re.compile(spec.pattern, flags=spec.flags | re.MULTILINE)))
    return out


# =============================================================================
# Sanitization + derived values
# =============================================================================

def _sanitize(ui: UI, meta: Meta) -> UI:
    """Apply hard plausibility gates and record dropped keys (without values)."""
    before = dict(ui or {})
    after = sanitize_ui_numbers(before)

    # Track keys that were removed/cleared by hard limits.
    dropped: list[str] = []
    for k, old_v in before.items():
        if old_v is None:
            continue
        if k in after and after.get(k) is None and isinstance(old_v, (int, float)) and not isinstance(old_v, bool):
            dropped.append(k)

    if dropped:
        dropped = sorted(set(dropped))
        meta.setdefault("sanitized_keys", [])
        # merge unique
        existing = set(meta.get("sanitized_keys") or [])
        merged = sorted(existing.union(dropped))
        meta["sanitized_keys"] = merged
        # concise UI hint
        if len(dropped) <= 5:
            _append_hint(meta, "Unplausible Werte verworfen: " + ", ".join(dropped) + ".")
        else:
            _append_hint(meta, f"Unplausible Werte verworfen (n={len(dropped)}).")

    # Drop None keys to keep payload small and UI logic simple.
    return {k: v for k, v in after.items() if v is not None}


def _postprocess(ui: UI, full_text: str) -> None:
    """Fill derived / mapped fields (does not overwrite extracted values)."""
    # Derived: set ivc_collapse radio if collapse index present
    if "ivc_collapse_index_pct" in ui and "ivc_collapse" not in ui:
        yn = _post_ivc_collapse_yesno(_to_float(ui.get("ivc_collapse_index_pct")))
        if yn:
            ui["ivc_collapse"] = yn

    # Derived: map VCI expir diameter to generic diameter field (if available)
    if "ivc_exp_mm" in ui and "ivc_diam_mm" not in ui:
        ui["ivc_diam_mm"] = ui.get("ivc_exp_mm")

    # Derived: ensure rvot_notch is set if mid-systolic notch appears anywhere
    if "rvot_notch" not in ui:
        full_l = (full_text or "").lower()
        if re.search(r"\b(mid[- ]?systolic|late[- ]?systolic)\s+notch\b", full_l):
            ui["rvot_notch"] = "ja"


def _derive_values(ui: UI, meta: Meta) -> None:
    """Derive secondary values and run conservative consistency checks.

    Principles
    - Never overwrite an explicitly extracted value.
    - Only fill missing derived values.
    - Add human-readable hints to meta when inconsistencies are detected.
    """
    derived: list[str] = []

    def _num(x: Any) -> Optional[float]:
        if isinstance(x, bool) or x is None:
            return None
        if isinstance(x, (int, float)):
            try:
                v = float(x)
                return v if v == v else None
            except (TypeError, ValueError):
                return None
        return None

    # Derive BSA (Mosteller) if missing and height/weight present
    if ui.get("bsa_m2") is None:
        h = _num(ui.get("height_cm"))
        w = _num(ui.get("weight_kg"))
        if h and w and h > 0 and w > 0:
            try:
                bsa = (h * w / 3600.0) ** 0.5
                ui["bsa_m2"] = round(bsa, 2)
                derived.append("bsa_m2")
            except Exception:
                pass

    bsa = _num(ui.get("bsa_m2"))

    # RV 3D indexed volumes
    edv = _num(ui.get("rv_3d_edv_ml"))
    esv = _num(ui.get("rv_3d_esv_ml"))
    if bsa and edv is not None and ui.get("rv_3d_edvi_ml_m2") is None:
        ui["rv_3d_edvi_ml_m2"] = round(edv / bsa, 2)
        derived.append("rv_3d_edvi_ml_m2")
    if bsa and esv is not None and ui.get("rv_3d_esvi_ml_m2") is None:
        ui["rv_3d_esvi_ml_m2"] = round(esv / bsa, 2)
        derived.append("rv_3d_esvi_ml_m2")

    # RV stroke volume
    if edv is not None and esv is not None and ui.get("rv_3d_sv_ml") is None:
        ui["rv_3d_sv_ml"] = round(edv - esv, 1)
        derived.append("rv_3d_sv_ml")

    # Plausibility checks (non-blocking)
    hints: list[str] = []
    sv = _num(ui.get("rv_3d_sv_ml"))
    if edv is not None and esv is not None and sv is not None:
        if abs((edv - esv) - sv) > 5.0:
            hints.append("Plausibilität: RVSV passt nicht zu RVEDV-RVESV (bitte prüfen).")

    edvi = _num(ui.get("rv_3d_edvi_ml_m2"))
    if bsa and edv is not None and edvi is not None:
        pred = edv / bsa
        if pred > 0 and abs(pred - edvi) / pred > 0.08:
            hints.append("Plausibilität: RVEDVi passt nicht zu RVEDV und KOF (bitte prüfen).")

    if derived:
        meta["derived"] = derived
    if hints:
        _append_hint(meta, " ".join(hints))


# =============================================================================
# PDF text extraction backends
# =============================================================================

def _safe_import(module_name: str) -> tuple[Optional[object], Optional[str]]:
    try:
        mod = importlib.import_module(module_name)
        return mod, None
    except Exception as e:  # noqa: BLE001
        return None, f"{module_name}: {type(e).__name__}: {e}"


def _extract_text_backend(pdf_bytes: bytes) -> tuple[str, Meta]:
    """Extract text from PDF bytes using best available backend."""
    meta: Meta = {"ok": True, "hint": "", "pages": 0, "source": "", "diag": ""}

    errors: list[str] = []
    # 1) PyMuPDF
    fitz_mod, fitz_err = _safe_import("fitz")
    if fitz_mod is not None:
        try:
            doc = fitz_mod.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[attr-defined]
            try:
                meta["pages"] = int(getattr(doc, "page_count", 0))
                texts: list[str] = []
                for i in range(meta["pages"]):
                    try:
                        t = doc.load_page(i).get_text("text") or ""
                    except Exception:
                        t = ""
                    if t.strip():
                        texts.append(t)
                meta["source"] = "pdf_text:pymupdf"
                return "\n".join(texts), meta
            finally:
                try:
                    doc.close()
                except Exception:
                    pass
        except Exception as e:  # noqa: BLE001
            errors.append(f"pymupdf: {type(e).__name__}: {e}")
    elif fitz_err:
        errors.append(fitz_err)

    # 2) pypdf
    pypdf_mod, pypdf_err = _safe_import("pypdf")
    if pypdf_mod is not None:
        try:
            PdfReader = getattr(pypdf_mod, "PdfReader", None)
            if PdfReader is None:
                raise ImportError("pypdf.PdfReader not found")
            reader = PdfReader(io.BytesIO(pdf_bytes))
            meta["pages"] = int(len(reader.pages))
            texts_pypdf: list[str] = []
            for p in reader.pages:
                try:
                    t = p.extract_text() or ""
                except Exception:
                    t = ""
                if t.strip():
                    texts_pypdf.append(t)
            meta["source"] = "pdf_text:pypdf"
            return "\n".join(texts_pypdf), meta
        except Exception as e:  # noqa: BLE001
            errors.append(f"pypdf: {type(e).__name__}: {e}")
    elif pypdf_err:
        errors.append(pypdf_err)

    # 3) PyPDF2
    pypdf2_mod, pypdf2_err = _safe_import("PyPDF2")
    if pypdf2_mod is not None:
        try:
            PdfReader2 = getattr(pypdf2_mod, "PdfReader", None)
            if PdfReader2 is None:
                raise ImportError("PyPDF2.PdfReader not found")
            reader = PdfReader2(io.BytesIO(pdf_bytes))
            meta["pages"] = int(len(reader.pages))
            texts_pypdf2: list[str] = []
            for p in reader.pages:
                try:
                    t = p.extract_text() or ""
                except Exception:
                    t = ""
                if t.strip():
                    texts_pypdf2.append(t)
            meta["source"] = "pdf_text:pypdf2"
            return "\n".join(texts_pypdf2), meta
        except Exception as e:  # noqa: BLE001
            errors.append(f"pypdf2: {type(e).__name__}: {e}")
    elif pypdf2_err:
        errors.append(pypdf2_err)

    # No backend or all backends failed
    meta["ok"] = False
    diag = f"python={sys.executable}"
    if errors:
        diag += " | " + " ; ".join(errors[:2])
        if len(errors) > 2:
            diag += f" (+{len(errors)-2} weitere)"
    meta["diag"] = diag
    meta["hint"] = "Kein PDF-Text-Backend verfügbar oder PDF konnte nicht gelesen werden."
    return "", meta


# =============================================================================
# OCR helpers (optional)
# =============================================================================

def _ocr_score(text: str) -> int:
    """Heuristic score for OCR text quality (Echo screenshot / report)."""
    if not text:
        return 0
    t = text.lower()
    patterns = [
        r"\bef\b", r"tapse", r"tr\s*vmax", r"trv", r"s\s*'", r"lavi",
        r"e/e", r"pasp", r"spap", r"rvfac", r"rvef", r"rv(edv|esv|sv)",
        r"vci", r"ivc", r"kof", r"gewicht", r"größe",
    ]
    s = sum(1 for p in patterns if re.search(p, t))
    s += min(10, max(0, len(t) // 200))
    return s


def _iter_variants(img: "Any"):
    """Generate robust OCR variants for images (tables/screenshots)."""
    try:
        from PIL import ImageEnhance, ImageOps
    except Exception:
        yield ("orig", img)
        return

    base = img.convert("RGB")
    yield ("orig", base)

    g = ImageOps.grayscale(base)
    yield ("gray", g)
    yield ("gray_autocontrast", ImageOps.autocontrast(g))

    try:
        yield ("gray_contrast2", ImageEnhance.Contrast(g).enhance(2.0))
    except Exception:
        pass

    try:
        w, h = base.size
        if max(w, h) < 2000:
            yield ("gray_x2", g.resize((w * 2, h * 2)))
    except Exception:
        pass

    try:
        g2 = ImageOps.autocontrast(g)
        bw = g2.point(lambda x: 0 if x < 160 else 255, mode="1")
        yield ("bw", bw)
    except Exception:
        pass


def _ocr_best_from_pil_image(img: "Any") -> tuple[str, Meta]:
    """Run multi-pass OCR on a PIL image and pick best candidate by heuristic score."""
    meta: Meta = {"ok": False, "hint": "", "pages": 1, "source": "ocr"}
    best_txt = ""
    best_score = 0

    # 1) rapidocr (preferred for rendered PDFs)
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()
        for _vname, vimg in _iter_variants(img):
            try:
                arr = np.array(vimg)
                result, _ = ocr(arr)
                if not result:
                    continue
                t = _norm_text("\n".join([r[1] for r in result if r and len(r) >= 2]))
                sc = _ocr_score(t)
                if sc > best_score:
                    best_score, best_txt = sc, t
            except Exception:
                continue
    except Exception:
        pass

    # 2) pytesseract fallback
    try:
        import pytesseract

        configs = ["--psm 6", "--psm 4", "--psm 6 -c preserve_interword_spaces=1"]
        for _vname, vimg in _iter_variants(img):
            for cfg in configs:
                try:
                    t = pytesseract.image_to_string(vimg, lang="deu+eng", config=cfg)
                    t = _norm_text(t or "")
                    sc = _ocr_score(t)
                    if sc > best_score:
                        best_score, best_txt = sc, t
                except Exception:
                    continue
    except Exception:
        pass

    if best_score >= _OCR_SCORE_THRESHOLD and len(best_txt.strip()) >= _OCR_MIN_TEXT_LEN:
        meta.update({"ok": True, "source": "ocr", "hint": ""})
        return best_txt, meta

    if len(best_txt.strip()) >= _OCR_MIN_TEXT_LEN:
        meta.update({"ok": True, "source": "ocr", "hint": "OCR mit niedriger Zuverlässigkeit."})
        return best_txt, meta

    meta["hint"] = "OCR lieferte keinen verwertbaren Text."
    return "", meta


def _ocr_pdf_first_page(pdf_bytes: bytes) -> tuple[str, Meta]:
    """OCR first page of a PDF (scan PDFs) on the server.

    Requires PyMuPDF to render the page and Pillow for image handling.
    """
    meta: Meta = {"ok": False, "hint": "", "pages": 1, "source": "pdf_ocr"}
    fitz = None
    try:
        fitz = importlib.import_module("fitz")
    except Exception:
        _append_hint(meta, "Scan-PDF erkannt, aber PyMuPDF fehlt (kann Seite nicht rendern).")
        return "", meta

    try:
        from PIL import Image
    except Exception as e:
        _append_hint(meta, f"Pillow nicht verfügbar: {e}")
        return "", meta

    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if getattr(doc, "page_count", 0) < 1:
            return "", {"ok": False, "hint": "PDF ohne Seiten.", "pages": 0, "source": "pdf_ocr"}
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(_PDF_OCR_ZOOM, _PDF_OCR_ZOOM), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    except Exception as e:
        _append_hint(meta, f"PDF Render fehlgeschlagen: {e}")
        return "", meta
    finally:
        try:
            if doc is not None:
                doc.close()
        except Exception:
            pass

    txt, ocr_meta = _ocr_best_from_pil_image(img)
    if ocr_meta.get("ok"):
        ocr_meta["source"] = "pdf_ocr"
        return txt, ocr_meta
    return "", {"ok": False, "hint": ocr_meta.get("hint") or "OCR nicht verfügbar.", "pages": 1, "source": "pdf_ocr"}


def _ocr_image_file(path: str) -> tuple[str, Meta]:
    """OCR helper for screenshots (local files on server)."""
    try:
        from PIL import Image
        img = Image.open(path)
    except Exception as e:
        return "", {"ok": False, "hint": f"Bild nicht lesbar: {e}", "pages": 1, "source": "image_ocr"}

    txt, m = _ocr_best_from_pil_image(img)
    if m.get("ok"):
        m["source"] = "image_ocr"
        return txt, m
    return "", {"ok": False, "hint": m.get("hint") or "OCR nicht verfügbar.", "pages": 1, "source": "image_ocr"}


# =============================================================================
# Core extraction routines
# =============================================================================

def _extract_from_text(full: str, meta: Meta) -> UI:
    """Extract values from normalized text."""
    ui: UI = {}
    for spec, cre in _compiled_patterns():
        m = cre.search(full)
        if not m:
            continue
        raw = m.group(spec.group) if spec.group else m.group(0)

        # Free-text / yes-no fields
        if spec.ui_key in ("ivc_respiratory", "pericardial_effusion", "rvot_notch"):
            raw_text = str(raw).strip()
            raw_text = re.sub(r"\s{2,}", " ", raw_text)
            yn = _post_yesno(raw_text)
            if yn is not None:
                ui[spec.ui_key] = yn
            continue

        num_val = _to_float(raw)
        if num_val is None:
            continue

        if spec.post:
            fn = _POST.get(spec.post)
            if fn is not None:
                try:
                    num_val = fn(num_val)
                except Exception:
                    pass

        if num_val is None:
            continue

        # OCR occasionally drops decimal separators. Apply conservative, key-specific scaling.
        num_val = _auto_scale(spec.ui_key, num_val)
        if num_val is None:
            continue
        ui[spec.ui_key] = num_val

    return ui


# =============================================================================
# Public API
# =============================================================================

def extract_echo_from_pdf_bytes(pdf_bytes: bytes) -> tuple[UI, Meta]:
    """Extract echo values from a PDF (textlayer preferred, scan via OCR fallback)."""
    full, meta = _extract_text_backend(pdf_bytes)

    if not meta.get("ok", True):
        return {}, meta

    full = _norm_text(full)

    if len(full.strip()) < _MIN_TEXT_LEN:
        # Likely scan PDF -> try page-1 OCR if available.
        ocr_text, ocr_meta = _ocr_pdf_first_page(pdf_bytes)
        if ocr_meta.get("ok"):
            ui, meta2 = extract_echo_from_text(ocr_text, source=ocr_meta.get("source", "pdf_ocr"))
            meta2.update({"pages": meta.get("pages", 0), "source": ocr_meta.get("source", "pdf_ocr")})
            _append_hint(meta2, ocr_meta.get("hint") or "")
            return ui, meta2

        return {}, {
            "ok": False,
            "hint": "Im PDF wurde kein verwertbarer Textlayer gefunden (wahrscheinlich Scan). OCR war nicht verfügbar.",
            "pages": meta.get("pages", 0),
            "source": meta.get("source", "pdf_text"),
        }

    ui = _extract_from_text(full, meta)
    _postprocess(ui, full)

    # Sanitization before derivation (so derived values are based on plausible inputs)
    ui = _sanitize(ui, meta)
    _derive_values(ui, meta)
    ui = _sanitize(ui, meta)

    meta.setdefault("ok", True)
    meta.setdefault("source", meta.get("source") or "pdf_text")
    return ui, meta


def extract_echo_from_text(text: str, *, source: str = "text") -> tuple[UI, Meta]:
    """Extract echo parameters from a plain text blob (OCR or browser PDF text).

    NOTE: This function must never depend on PDF backends (used by Browser OCR import path).
    """
    meta: Meta = {"ok": True, "hint": "", "pages": 1, "source": source}

    full = _norm_text(text or "")
    if len(full.strip()) < _MIN_TEXT_LEN:
        return {}, {"ok": False, "hint": "Kein verwertbarer Text gefunden.", "pages": 1, "source": source}

    ui = _extract_from_text(full, meta)
    _postprocess(ui, full)

    ui = _sanitize(ui, meta)
    _derive_values(ui, meta)
    ui = _sanitize(ui, meta)

    return ui, meta


def extract_echo_from_file(path: str) -> tuple[UI, Meta]:
    """Extract echo parameters from either a PDF (textlayer) or an image screenshot (OCR)."""
    if not path:
        return {}, {"ok": False, "hint": "Kein Dateipfad.", "pages": 0, "source": "none"}

    p = str(path).lower()
    if p.endswith(".pdf"):
        try:
            with open(path, "rb") as f:
                data = f.read()
            return extract_echo_from_pdf_bytes(data)
        except Exception as e:
            return {}, {"ok": False, "hint": f"PDF konnte nicht gelesen werden: {e}", "pages": 0, "source": "pdf"}

    if p.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
        text, meta = _ocr_image_file(path)
        if not meta.get("ok"):
            return {}, meta
        parsed, meta2 = extract_echo_from_text(text, source=meta.get("source", "image_ocr"))
        # keep diagnostic hint if extraction yields nothing
        if not parsed:
            meta2["ok"] = False
            _append_hint(meta2, meta.get("hint") or "OCR ok, aber keine bekannten Parameter erkannt.")
        return parsed, meta2

    return {}, {"ok": False, "hint": "Dateityp nicht unterstützt.", "pages": 0, "source": "unknown"}


# Backwards-compatible alias used by UI helper
def extract_echo_from_pdf(pdf_bytes: bytes):  # pragma: no cover - legacy API
    return extract_echo_from_pdf_bytes(pdf_bytes)
