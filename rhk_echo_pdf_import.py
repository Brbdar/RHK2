#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo PDF Import.

Dieses Modul liest einen Echo-PDF (Textlayer) und extrahiert Messwerte.

Prinzipien
- OCR optional: PDFs ohne Textlayer (Scan) können via Seite-1-OCR verarbeitet werden,
  wenn ein OCR-Backend verfügbar ist (rapidocr-onnxruntime oder pytesseract).
- Keine Fantasie-Werte: nur extrahieren, was im Text vorhanden ist.
- Robust: Dezimalkomma, Unicode-Minus, variable Leerzeichen.
- Einheiten-Normalisierung (z. B. TRV cm/s -> m/s).
- Backends werden lazy geladen. Wenn ein Backend vorhanden ist, aber das PDF
  nicht gelesen werden kann, wird der Fehlertext als Hinweis zurückgegeben
  (statt fälschlich "kein Backend verfügbar").

Rückgabe
- ui_values: Dict[str, object] (kompatibel mit UI-Keys)
- meta: Dict[str, object] (Quelle/Backend, Seitenzahl, Hinweistext, Diagnose)

Hinweis
- Dieses Modul ist absichtlich schlank. Neue Parameter werden über PATTERNS ergänzt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List

import io
import re
import sys
import importlib


@dataclass(frozen=True)
class MatchSpec:
    ui_key: str
    pattern: str
    flags: int = re.IGNORECASE
    group: int = 1
    post: Optional[str] = None  # name of postprocessor

    # Backwards-compat alias: older call sites used `spec.key`.
    # Keep this property to avoid runtime errors when patterns are iterated.
    @property
    def key(self) -> str:
        return self.ui_key


def _norm_text(s: str) -> str:
    """Normalize text from PDF text-layers and OCR.

    We explicitly strip common redaction/conversion artefacts that can break
    regex matching (seen in real-world Echo PDFs), e.g. "$30,4mm" or
    "KOF: $1,99~m^{2}$".
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


def _to_float(raw: str) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = _norm_text(s)
    s = re.sub(r"[^0-9,\.\-]", "", s)
    if not s or s in ("-", ".", ","):
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    if s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(s)
    except Exception:
        return None


def _auto_scale(ui_key: str, v: Optional[float]) -> Optional[float]:
    """Heuristics for OCR where decimal separators were dropped.

    We only rescale when the magnitude is implausible for the given parameter,
    to avoid silent corruption.

    Strategy
    - For each parameter we define a conservative plausible range.
    - If v is outside the range, but v/10 or v/100 falls inside, rescale.
    """
    if v is None:
        return None

    # Conservative plausibility ranges (min, max)
    R = {
        # anthropometrics
        'height_cm': (120.0, 220.0),
        'weight_kg': (30.0, 200.0),
        'bsa_m2': (1.0, 3.0),
        # mm values
        'tapse_mm': (5.0, 40.0),
        'rv_edd_mm': (20.0, 90.0),
        'rv_esd_mm': (10.0, 80.0),
        'rv_wall_thickness_mm': (1.0, 15.0),
        'ivc_exp_mm': (5.0, 35.0),
        'ivc_insp_mm': (0.0, 30.0),
        'ivc_diam_mm': (5.0, 35.0),
        # pressures / timings
        'pasp_echo': (10.0, 150.0),
        'paat_ms': (30.0, 200.0),
        'rvet_ms': (100.0, 600.0),
        # ratios
        'tapse_spap_ratio': (0.0, 2.0),
        'paat_rvet_ratio': (0.0, 1.0),
        # velocities
        'trv_ms': (1.0, 7.0),
        # areas / volumes
        'ra_esa_cm2': (5.0, 80.0),
        'ra_eda_cm2': (5.0, 80.0),
        'rv_eda_cm2': (5.0, 100.0),
        'rv_esa_cm2': (5.0, 100.0),
        # volumes (ml)
        'rv_3d_edv_ml': (20.0, 450.0),
        'rv_3d_esv_ml': (5.0, 350.0),
        'rv_3d_sv_ml': (5.0, 250.0),
        # indexed volumes (ml/m2)
        'rv_3d_edvi_ml_m2': (10.0, 250.0),
        'rv_3d_esvi_ml_m2': (1.0, 200.0),
        'lavi_ml_m2': (5.0, 120.0),
        'la_vmax_ml': (10.0, 250.0),
        'la_esa_cm2': (5.0, 80.0),
        # percents
        'lvef': (5.0, 90.0),
        'rvfac_pct': (5.0, 80.0),
        'rv_3d_ef_pct': (5.0, 90.0),
        'ivc_collapse_index_pct': (0.0, 100.0),
        # strain (negative)
        'rv_gls_pct': (-60.0, 0.0),
        'rv_fwls_pct': (-60.0, 0.0),
    }

    # Special conversions first
    if ui_key == 'trv_ms':
        # OCR often reads 340 for 3.40 m/s, or cm/s.
        if v > 20:
            v2 = v / 100.0
            if R['trv_ms'][0] <= v2 <= R['trv_ms'][1]:
                return round(v2, 2)
        return v

    # Strain: OCR sometimes drops the minus sign and/or decimal.
    if ui_key in ('rv_gls_pct', 'rv_fwls_pct') and v is not None:
        lo, hi = R.get(ui_key, (-60.0, 0.0))
        if lo <= v <= hi:
            return v
        # try -v
        if lo <= -v <= hi:
            return -v
        # try -v/10
        v10 = -v / 10.0
        if lo <= v10 <= hi:
            return round(v10, 1)
        # try -v/100
        v100 = -v / 100.0
        if lo <= v100 <= hi:
            return round(v100, 1)

    # If we have a plausibility range, rescale if clearly needed
    if ui_key in R:
        lo, hi = R[ui_key]
        if lo <= v <= hi:
            return v

        # Try /10
        v10 = v / 10.0
        if lo <= v10 <= hi:
            # mm fields are typically 1 decimal, percents 1 decimal, ratios 2 decimals
            if ui_key.endswith('_ratio'):
                return round(v10, 2)
            if ui_key.endswith('_mm'):
                return round(v10, 1)
            if ui_key.endswith('_pct') or ui_key in ('lvef', 'rvfac_pct', 'rv_3d_ef_pct', 'ivc_collapse_index_pct'):
                return round(v10, 1)
            if ui_key in ('height_cm',):
                return round(v10, 0)
            if ui_key in ('weight_kg',):
                return round(v10, 1)
            if ui_key.endswith('_ml'):
                return round(v10, 1)
            if ui_key.endswith('_ml_m2'):
                return round(v10, 2)
            return v10

        # Try /100 (e.g. 8200 -> 82.00 kg)
        v100 = v / 100.0
        if lo <= v100 <= hi:
            if ui_key in ('weight_kg',):
                return round(v100, 2)
            if ui_key in ('height_cm',):
                return round(v100, 0)
            if ui_key.endswith('_ratio'):
                return round(v100, 2)
            if ui_key.endswith('_mm'):
                return round(v100, 1)
            if ui_key.endswith('_pct') or ui_key in ('lvef', 'rvfac_pct', 'rv_3d_ef_pct', 'ivc_collapse_index_pct'):
                return round(v100, 1)
            if ui_key.endswith('_ml'):
                return round(v100, 1)
            if ui_key.endswith('_ml_m2'):
                return round(v100, 2)
            return v100

    # Default: keep
    return v


def _extract_text_from_pdf_scan_page1(pdf_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """Render page 1 and OCR it.

    Returns (text, meta). Works if either rapidocr-onnxruntime or pytesseract is
    available. If neither works, returns empty text with a hint.
    """
    meta: Dict[str, Any] = {"ok": False, "source": "pdf:scan", "hint": ""}

    fitz = None
    try:
        fitz = importlib.import_module("fitz")
    except Exception:
        pass
    if not fitz:
        meta["hint"] = "Scan-PDF erkannt, aber PyMuPDF fehlt (kann Seite nicht rendern)."
        return "", meta

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            meta["hint"] = "PDF hat keine Seiten."
            return "", meta
        page = doc.load_page(0)
        # 2x zoom for better OCR
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(pix.tobytes("png")))
    except Exception as e:
        meta["hint"] = f"Konnte Seite 1 nicht rendern: {e}"
        return "", meta

    # Try RapidOCR first (pure python, best on Render)
    try:
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()
        res, _ = ocr(img)
        # res is list of (box, text, score)
        texts: List[str] = []
        if res:
            for item in res:
                if len(item) >= 2:
                    texts.append(str(item[1]))
        txt = "\n".join(texts).strip()
        if txt:
            meta.update({"ok": True, "source": "pdf:scan:rapidocr", "hint": ""})
            return txt, meta
    except Exception:
        pass

    # Fallback: pytesseract (needs system tesseract)
    try:
        import pytesseract

        txt = pytesseract.image_to_string(img, lang="deu+eng")
        txt = (txt or "").strip()
        if txt:
            meta.update({"ok": True, "source": "pdf:scan:tesseract", "hint": ""})
            return txt, meta
        meta["hint"] = "OCR lieferte keinen Text."
        return "", meta
    except Exception as e:
        meta["hint"] = f"Scan-PDF erkannt. OCR nicht verfügbar: {e}"
        return "", meta



def _post_trv_to_ms(v: Optional[float]) -> Optional[float]:
    # TRV may be provided as cm/s (e.g. 340.1). If value looks like cm/s, convert.
    if v is None:
        return None
    if v > 20:  # implausible for m/s -> likely cm/s
        return round(v / 100.0, 3)
    return v


def _post_yesno(v: str) -> Optional[str]:
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


def _post_percent(v: Optional[float]) -> Optional[float]:
    return v


def _post_ivc_collapse_yesno(v: Optional[float]) -> Optional[str]:
    if v is None:
        return None
    return "ja" if v >= 50.0 else "nein"


_POST = {
    "trv_to_ms": _post_trv_to_ms,
    "percent": _post_percent,
    "ivc_collapse_yesno": _post_ivc_collapse_yesno,
}


# Patterns are intentionally permissive wrt whitespace/linebreaks.
PATTERNS: List[MatchSpec] = [
    # Klinik
    MatchSpec("height_cm", r"Gr[oö](?:ss|ß)e\s*:?\s*(\d{2,3}(?:[\.,]\d+)?)\s*cm"),
    MatchSpec("weight_kg", r"Gewicht\s*:?\s*(\d{2,3}(?:[\.,]\d+)?)\s*kg"),
    MatchSpec("bsa_m2", r"KOF\s*:?\s*(\d+(?:[\.,]\d+)?)\s*m2"),

    # Linksherz
    MatchSpec("lvef", r"LVEF\s*BiP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%?", post="percent"),
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
    MatchSpec("rv_3d_ef_pct", r"3D[- ]?RVEF\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%?", post="percent"),

    # RA planimetry
    MatchSpec("ra_esa_cm2", r"RA\s*ESA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("ra_eda_cm2", r"RA\s*EDA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),

    # RV function
    MatchSpec("tapse_mm", r"TAPSE\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    # S' kann als S', S´ etc. erscheinen
    MatchSpec("s_prime_cm_s", r"\bS\s*[\'´`]?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm\s*(?:/|\s)\s*s"),
    MatchSpec("rvfac_pct", r"RVFAC\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%", post="percent"),
    MatchSpec("tapse_spap_ratio", r"TAPSE\s*/\s*sPAP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm\s*(?:/|\s)\s*mmHg"),

    # Strain
    MatchSpec("rv_gls_pct", r"RV[- ]?GLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%", post="percent"),
    MatchSpec("rv_fwls_pct", r"RV\s*FWLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%", post="percent"),

    # PH signs
    MatchSpec("trv_ms", r"TRV\s*:?\s*(\d+(?:[\.,]\d+)?)\s*(?:m\s*(?:/|\s)\s*s|cm\s*(?:/|\s)\s*s)", post="trv_to_ms"),
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
    MatchSpec("ivc_collapse_index_pct", r"VCI[- ]Kollaps(?:\s*Index\s*:?)?\s*(\d+(?:[\.,]\d+)?)\s*%", post="percent"),
    MatchSpec("ivc_respiratory", r"VCI\s*atemvariabel\s*:?\s*(ja|nein)", group=1),

    MatchSpec("pericardial_effusion", r"Perikarderguss\s*:?\s*(ja|nein|0|1)", group=1),
]


def _safe_import(module_name: str) -> Tuple[Optional[object], Optional[str]]:
    try:
        mod = importlib.import_module(module_name)
        return mod, None
    except Exception as e:  # noqa: BLE001
        return None, f"{module_name}: {type(e).__name__}: {e}"


def _extract_text_backend(pdf_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """Extract text from PDF bytes using best available backend."""
    meta: Dict[str, Any] = {"ok": True, "hint": "", "pages": 0, "source": "", "diag": ""}

    errors: List[str] = []
    # 1) PyMuPDF
    fitz_mod, fitz_err = _safe_import("fitz")
    if fitz_mod is not None:
        try:
            doc = fitz_mod.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[attr-defined]
            try:
                meta["pages"] = int(getattr(doc, "page_count", 0))
                texts: List[str] = []
                for i in range(meta["pages"]):
                    try:
                        t = doc.load_page(i).get_text("text") or ""  # type: ignore[attr-defined]
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
            texts: List[str] = []
            for p in reader.pages:
                try:
                    t = p.extract_text() or ""
                except Exception:
                    t = ""
                if t.strip():
                    texts.append(t)
            meta["source"] = "pdf_text:pypdf"
            return "\n".join(texts), meta
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
            texts: List[str] = []
            for p in reader.pages:
                try:
                    t = p.extract_text() or ""
                except Exception:
                    t = ""
                if t.strip():
                    texts.append(t)
            meta["source"] = "pdf_text:pypdf2"
            return "\n".join(texts), meta
        except Exception as e:  # noqa: BLE001
            errors.append(f"pypdf2: {type(e).__name__}: {e}")
    elif pypdf2_err:
        errors.append(pypdf2_err)

    # No backend or all backends failed
    meta["ok"] = False
    # compact but useful diagnosis (shows the interpreter actually used)
    diag = f"python={sys.executable}"
    if errors:
        diag += " | " + " ; ".join(errors[:2])
        if len(errors) > 2:
            diag += f" (+{len(errors)-2} weitere)"
    meta["diag"] = diag
    meta["hint"] = "Kein PDF-Text-Backend verfügbar oder PDF konnte nicht gelesen werden."
    return "", meta


def extract_echo_from_pdf_bytes(pdf_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract echo values from a PDF (textlayer)."""
    full, meta = _extract_text_backend(pdf_bytes)

    if not meta.get("ok", True):
        return {}, meta

    full = _norm_text(full)

    if len(full.strip()) < 20:
        # Likely scan PDF -> try page-1 OCR if a backend is available.
        ocr_text, ocr_meta = _ocr_pdf_first_page(pdf_bytes)
        if ocr_meta.get("ok"):
            ui, meta2 = extract_echo_from_text(ocr_text, source=ocr_meta.get("source", "pdf_ocr"))
            meta2.update({"pages": meta.get("pages", 0), "hint": ocr_meta.get("hint", "")})
            return ui, meta2

        return {}, {
            "ok": False,
            "hint": "Im PDF wurde kein verwertbarer Textlayer gefunden (wahrscheinlich Scan). OCR war nicht verfügbar.",
            "pages": meta.get("pages", 0),
            "source": meta.get("source", "pdf_text"),
        }

    ui: Dict[str, Any] = {}

    for spec in PATTERNS:
        m = re.search(spec.pattern, full, flags=spec.flags)
        if not m:
            continue
        raw = m.group(spec.group) if spec.group else m.group(0)

        if spec.ui_key in ("ivc_respiratory", "pericardial_effusion", "rvot_notch"):
            val = str(raw).strip()
            val = re.sub(r"\s{2,}", " ", val)
            yn = _post_yesno(val)
            if yn:
                ui[spec.ui_key] = yn
            continue

        val = _to_float(raw)
        if spec.post:
            fn = _POST.get(spec.post)
            if fn is not None:
                val = fn(val)  # type: ignore[misc]
        if val is None:
            continue
        # OCR occasionally drops decimal separators. Apply conservative, key-specific scaling.
        val = _auto_scale(spec.ui_key, val)
        ui[spec.ui_key] = val

    # Derived: set ivc_collapse radio if collapse index present
    if "ivc_collapse_index_pct" in ui and "ivc_collapse" not in ui:
        yn = _post_ivc_collapse_yesno(_to_float(str(ui.get("ivc_collapse_index_pct"))))
        if yn:
            ui["ivc_collapse"] = yn

    # Derived: map VCI Durchmesser (basic field) to expir diameter (if available)
    if "ivc_exp_mm" in ui and "ivc_diam_mm" not in ui:
        ui["ivc_diam_mm"] = ui.get("ivc_exp_mm")

    # Derived: ensure rvot_notch is set if mid-systolic notch appears anywhere
    if "rvot_notch" not in ui:
        full_l = full.lower()
        if re.search(r"\b(mid[- ]?systolic|late[- ]?systolic)\s+notch\b", full_l):
            ui["rvot_notch"] = "ja"

    # Derive secondary values & plausibility hints
    _derive_values(ui, meta)

    return ui, meta




def _derive_values(ui: Dict[str, Any], meta: Dict[str, Any]) -> None:
    """Derive secondary values and run conservative plausibility checks.

    Principles
    - Never overwrite an explicitly extracted value.
    - Only fill missing derived values.
    - Add human-readable hints to meta when inconsistencies are detected.
    """
    derived: List[str] = []

    # Derive BSA (Mosteller) if missing and height/weight present
    if ui.get("bsa_m2") is None:
        h = ui.get("height_cm")
        w = ui.get("weight_kg")
        if isinstance(h, (int, float)) and isinstance(w, (int, float)) and h > 0 and w > 0:
            try:
                bsa = (h * w / 3600.0) ** 0.5
                # round like typical echo reports
                ui["bsa_m2"] = round(bsa, 2)
                derived.append("bsa_m2")
            except Exception:
                pass

    bsa = ui.get("bsa_m2") if isinstance(ui.get("bsa_m2"), (int, float)) else None

    # RV 3D indexed volumes
    edv = ui.get("rv_3d_edv_ml") if isinstance(ui.get("rv_3d_edv_ml"), (int, float)) else None
    esv = ui.get("rv_3d_esv_ml") if isinstance(ui.get("rv_3d_esv_ml"), (int, float)) else None
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
    hints: List[str] = []
    # Consistency: SV approx EDV-ESV
    sv = ui.get("rv_3d_sv_ml") if isinstance(ui.get("rv_3d_sv_ml"), (int, float)) else None
    if edv is not None and esv is not None and sv is not None:
        if abs((edv - esv) - sv) > 5.0:
            hints.append("Plausibilität: RVSV passt nicht zu RVEDV-RVESV (bitte prüfen).")

    # Consistency: EDVi approx EDV/BSA
    edvi = ui.get("rv_3d_edvi_ml_m2") if isinstance(ui.get("rv_3d_edvi_ml_m2"), (int, float)) else None
    if bsa and edv is not None and edvi is not None:
        pred = edv / bsa
        if pred > 0 and abs(pred - edvi) / pred > 0.08:
            hints.append("Plausibilität: RVEDVi passt nicht zu RVEDV und KOF (bitte prüfen).")

    if derived:
        meta["derived"] = derived
    if hints:
        old = meta.get("hint", "") or ""
        meta["hint"] = (old + (" " if old else "") + " ".join(hints)).strip()


def extract_echo_from_text(text: str, *, source: str = "text") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract echo parameters from a plain text blob (from OCR or PDF textlayer).

    NOTE: This function is used by the Browser OCR import path.
    It must therefore be extremely robust and must never depend on PDF backends.
    """
    meta: Dict[str, Any] = {"ok": True, "hint": "", "pages": 1, "source": source}

    full = _norm_text(text or "")
    if len(full.strip()) < 20:
        return {}, {"ok": False, "hint": "Kein verwertbarer Text gefunden.", "pages": 1, "source": source}

    ui: Dict[str, Any] = {}

    for spec in PATTERNS:
        m = re.search(spec.pattern, full, flags=spec.flags | re.MULTILINE)
        if not m:
            continue

        raw = m.group(spec.group) if spec.group else m.group(1)

        # Free-text / yes-no fields
        if spec.ui_key in ("rvot_notch", "ivc_respiratory", "pericardial_effusion"):
            yn = _post_yesno(raw)
            if yn is not None:
                ui[spec.ui_key] = yn
            continue

        val = _to_float(raw)
        if val is None:
            continue

        if spec.post:
            fn = _POST.get(spec.post)
            if fn is not None:
                val = fn(val)  # type: ignore[misc]
        if val is None:
            continue
        val = _auto_scale(spec.ui_key, val)
        ui[spec.ui_key] = val

    # Derived: set ivc_collapse radio if collapse index present
    if "ivc_collapse_index_pct" in ui and "ivc_collapse" not in ui:
        yn = _post_ivc_collapse_yesno(_to_float(str(ui.get("ivc_collapse_index_pct"))))
        if yn:
            ui["ivc_collapse"] = yn

    # Derived: map VCI Durchmesser (basic field) to expir diameter (if available)
    if "ivc_exp_mm" in ui and "ivc_diam_mm" not in ui:
        ui["ivc_diam_mm"] = ui.get("ivc_exp_mm")

    # Derived: ensure rvot_notch is set if mid-systolic notch appears anywhere
    if "rvot_notch" not in ui:
        full_l = full.lower()
        if re.search(r"\b(mid[- ]?systolic|late[- ]?systolic)\s+notch\b", full_l):
            ui["rvot_notch"] = "ja"

    return ui, meta


def _extract_text_from_image(path: str) -> Tuple[str, Dict[str, Any]]:
    """OCR helper for screenshots (local files on server).

    Priority:
    1) pytesseract (needs system tesseract)
    2) rapidocr-onnxruntime (pure python)
    """
    meta: Dict[str, Any] = {"ok": False, "hint": "", "pages": 1, "source": "image_ocr"}
    try:
        from PIL import Image
        img = Image.open(path)
    except Exception as e:
        return "", {"ok": False, "hint": f"Bild nicht lesbar: {e}", "pages": 1, "source": "image_ocr"}

    def _ocr_score(t: str) -> int:
        """Heuristische Bewertung von OCR-Text für Echo-Screenshots.

        Ziel: aus mehreren OCR-Versuchen die wahrscheinlich beste Variante wählen
        (mehr relevante Echo-Labels erkannt).
        """
        if not t:
            return 0
        t = t.lower()
        patterns = [
            r"\bef\b", r"tapse", r"tr\s*vmax", r"tr\s*vmax", r"tr v", r"s\s*'", r"lavi",
            r"e/e", r"pasp", r"spap", r"ava", r"mitr", r"aorten", r"trikus",
        ]
        s = 0
        for p in patterns:
            if re.search(p, t):
                s += 1
        # Bonus: je länger (aber gedeckelt) desto besser (reduziert leere OCR)
        s += min(10, max(0, len(t) // 200))
        return s

    def _iter_variants(im: "Image.Image"):
        """Generiere robuste OCR-Varianten für beliebige Echo-Screenshots."""
        try:
            from PIL import ImageOps, ImageEnhance
        except Exception:
            yield ("orig", im)
            return

        base = im.convert("RGB")
        yield ("orig", base)

        # 1) Graustufen + autocontrast
        g = ImageOps.grayscale(base)
        yield ("gray", g)
        yield ("gray_autocontrast", ImageOps.autocontrast(g))

        # 2) Kontrastverstärkung
        try:
            yield ("gray_contrast2", ImageEnhance.Contrast(g).enhance(2.0))
        except Exception:
            pass

        # 3) Skalierung (kleine Screenshots)
        try:
            w, h = base.size
            if max(w, h) < 2000:
                yield ("gray_x2", g.resize((w * 2, h * 2)))
        except Exception:
            pass

        # 4) Simple threshold (für Tabellen)
        try:
            g2 = ImageOps.autocontrast(g)
            bw = g2.point(lambda x: 0 if x < 160 else 255, mode="1")
            yield ("bw", bw)
        except Exception:
            pass

    # --- Multi-pass OCR: try several image variants, pick best by heuristic score
    best_txt = ""
    best_score = 0

    # pytesseract (if available)
    try:
        import pytesseract
        configs = [
            "--psm 6",
            "--psm 4",
            "--psm 6 -c preserve_interword_spaces=1",
        ]
        for vname, vimg in _iter_variants(img):
            for cfg in configs:
                try:
                    t = pytesseract.image_to_string(vimg, lang="deu+eng", config=cfg)
                    t = _norm_text(t)
                    sc = _ocr_score(t)
                    if sc > best_score:
                        best_score, best_txt = sc, t
                except Exception:
                    continue
        if best_score >= 4 and len(best_txt.strip()) >= 20:
            return best_txt, {"ok": True, "hint": "", "pages": 1, "source": "image_ocr:tesseract"}
    except Exception:
        pass

    # rapidocr fallback (if available)
    try:
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np
        ocr = RapidOCR()
        for vname, vimg in _iter_variants(img):
            try:
                arr = np.array(vimg)
                result, _ = ocr(arr)
                if result:
                    t = _norm_text("\n".join([r[1] for r in result if r and len(r) >= 2]))
                    sc = _ocr_score(t)
                    if sc > best_score:
                        best_score, best_txt = sc, t
            except Exception:
                continue
        if best_score >= 4 and len(best_txt.strip()) >= 20:
            return best_txt, {"ok": True, "hint": "", "pages": 1, "source": "image_ocr:rapidocr"}
    except Exception as e:
        meta["hint"] = f"OCR Backend nicht verfügbar: {e}"

    # If we got *some* text but low score, still return it (caller can decide)
    if len(best_txt.strip()) >= 20:
        meta.update({"ok": True, "hint": "OCR mit niedriger Zuverlässigkeit.", "source": "image_ocr"})
        return best_txt, meta
    return "", meta


def _ocr_pdf_first_page(pdf_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """OCR first page of a PDF (scan PDFs) on the server.

    Uses PyMuPDF to render page 1 and then OCR via rapidocr (preferred) or pytesseract.
    """
    meta: Dict[str, Any] = {"ok": False, "hint": "", "pages": 1, "source": "pdf_ocr"}
    try:
        fitz = importlib.import_module("fitz")
        from PIL import Image
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            return "", {"ok": False, "hint": "PDF ohne Seiten.", "pages": 0, "source": "pdf_ocr"}
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    except Exception as e:
        return "", {"ok": False, "hint": f"PDF Render fehlgeschlagen: {e}", "pages": 1, "source": "pdf_ocr"}

    # Robust multi-pass OCR similar to screenshots: try multiple render variants
    best_txt = ""
    best_score = 0

    def _ocr_score(t: str) -> int:
        if not t:
            return 0
        t = t.lower()
        patterns = [r"\bef\b", r"tapse", r"tr\s*vmax", r"lavi", r"e/e", r"pasp", r"spap", r"aorten", r"trikus"]
        s = sum(1 for p in patterns if re.search(p, t))
        s += min(10, max(0, len(t) // 200))
        return s

    def _iter_variants(im: "Image.Image"):
        try:
            from PIL import ImageOps, ImageEnhance
        except Exception:
            yield ("orig", im)
            return
        base = im.convert("RGB")
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

    # rapidocr first (if available)
    try:
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np
        ocr = RapidOCR()
        for vname, vimg in _iter_variants(img):
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

    # pytesseract fallback (if available)
    try:
        import pytesseract
        configs = ["--psm 6", "--psm 4", "--psm 6 -c preserve_interword_spaces=1"]
        for vname, vimg in _iter_variants(img):
            for cfg in configs:
                try:
                    t = _norm_text(pytesseract.image_to_string(vimg, lang="deu+eng", config=cfg))
                    sc = _ocr_score(t)
                    if sc > best_score:
                        best_score, best_txt = sc, t
                except Exception:
                    continue
    except Exception as e:
        meta["hint"] = f"OCR Backend nicht verfügbar: {e}"

    if best_score >= 4 and len(best_txt.strip()) >= 20:
        return best_txt, {"ok": True, "hint": "", "pages": 1, "source": "pdf_ocr"}
    if len(best_txt.strip()) >= 20:
        return best_txt, {"ok": True, "hint": "OCR mit niedriger Zuverlässigkeit.", "pages": 1, "source": "pdf_ocr"}
    return "", {"ok": False, "hint": "OCR lieferte keinen verwertbaren Text.", "pages": 1, "source": "pdf_ocr"}

    def _windows_ocr(img_path: str) -> Tuple[str, Dict[str, Any]]:
        """Windows OCR via PowerShell/WinRT. No external binaries required."""
        m: Dict[str, Any] = {"ok": False, "hint": "", "pages": 1, "source": "windows_ocr"}
        try:
            import sys
            if not sys.platform.startswith("win"):
                m["hint"] = "Windows OCR ist nur unter Windows verfügbar."
                return "", m
            import subprocess
            import json

            # PowerShell script: load bitmap, run Windows.Media.Ocr, print text.
            # Keep it in one -Command to avoid writing temp files.
            # We wrap output in JSON to preserve newlines safely.
            ps = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$p = @'
__IMG__
'@
try {
  $bytes = [System.IO.File]::ReadAllBytes($p)
  $ms = New-Object System.IO.MemoryStream(,$bytes)
  $ras = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($ms)
  $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras).GetAwaiter().GetResult()
  $bmp = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  if ($engine -eq $null) { throw 'OcrEngine nicht verfügbar (Sprachen/Features?)' }
  $res = $engine.RecognizeAsync($bmp).GetAwaiter().GetResult()
  $t = $res.Text
  $obj = @{ ok = $true; text = $t }
  $obj | ConvertTo-Json -Compress
} catch {
  $obj = @{ ok = $false; error = $_.Exception.Message }
  $obj | ConvertTo-Json -Compress
}
""".replace("__IMG__", str(img_path).replace("'", "''"))

            # Run PowerShell
            cp = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                capture_output=True,
                text=True,
                timeout=20,
            )
            out = (cp.stdout or "").strip()
            if not out:
                # Some systems write JSON to stderr
                out = (cp.stderr or "").strip()
            if not out:
                m["hint"] = "Windows OCR hat keine Ausgabe geliefert."
                return "", m
            try:
                obj = json.loads(out)
            except Exception:
                # If non-JSON came through, return raw.
                txt = out
                if txt:
                    m["ok"] = True
                    return txt, m
                m["hint"] = "Windows OCR Ausgabe nicht interpretierbar."
                return "", m
            if obj.get("ok") is True:
                m["ok"] = True
                return (obj.get("text") or ""), m
            m["hint"] = obj.get("error") or "Windows OCR fehlgeschlagen."
            return "", m
        except Exception as e:
            m["hint"] = f"Windows OCR fehlgeschlagen: {e}"
            return "", m
    try:
        from PIL import Image, ImageOps
    except Exception as e:
        meta["hint"] = f"Pillow nicht verfügbar: {e}"
        return "", meta

    try:
        import pytesseract
    except Exception as e:
        # Fallback: Windows OCR (no Tesseract dependency)
        txt, m = _windows_ocr(path)
        if m.get("ok"):
            return txt, m
        meta["hint"] = f"pytesseract nicht verfügbar ({e}) und Windows OCR nicht möglich: {m.get('hint','')}"
        return "", meta

    # Optional override for binary path (Windows friendly)
    try:
        import os
        cmd = os.environ.get("TESSERACT_CMD") or os.environ.get("TESSERACT_PATH")
        if cmd:
            try:
                pytesseract.pytesseract.tesseract_cmd = cmd  # type: ignore
            except Exception:
                pass
    except Exception:
        pass

    # Validate tesseract binary availability
    try:
        _ = pytesseract.get_tesseract_version()
    except Exception as e:
        # Fallback: Windows OCR (no Tesseract dependency)
        txt, m = _windows_ocr(path)
        if m.get("ok"):
            return txt, m
        meta["hint"] = (
            "Tesseract OCR ist nicht verfügbar (Tesseract nicht im PATH / nicht installiert). "
            "Alternativ kann TESSERACT_CMD auf den Pfad zur tesseract.exe gesetzt werden. "
            "Windows OCR Fallback war ebenfalls nicht möglich: "
            f"{m.get('hint','')}. Details: {e}"
        )
        return "", meta

    try:
        img = Image.open(path)
        # Preprocess: grayscale + autocontrast + upscale for better OCR
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        w, h = img.size
        if w and h:
            scale = 2 if max(w, h) < 2000 else 1
            if scale > 1:
                img = img.resize((w * scale, h * scale))

        config = "--psm 6"
        # OCR: try German first, then fallback
        text = ""
        try:
            text = pytesseract.image_to_string(img, lang="deu", config=config)
        except Exception as e_deu:
            try:
                text = pytesseract.image_to_string(img, lang="eng", config=config)
            except Exception:
                # last resort: no lang
                text = pytesseract.image_to_string(img, config=config)
        meta["ok"] = True
        meta["hint"] = ""
        return text or "", meta
    except Exception as e:
        meta["hint"] = f"OCR fehlgeschlagen: {e}"
        return "", meta


def extract_echo_from_file(path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
    # image
    if p.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")):
        text, meta = _extract_text_from_image(path)
        if not meta.get("ok"):
            return {}, meta
        parsed, meta2 = extract_echo_from_text(text, source="image_ocr")
        # keep diagnostic hint if extraction yields nothing
        if not parsed:
            meta2["ok"] = False
            meta2["hint"] = meta.get("hint") or "OCR ok, aber keine bekannten Parameter erkannt."
        return parsed, meta2

    return {}, {"ok": False, "hint": "Dateityp nicht unterstützt.", "pages": 0, "source": "unknown"}


# Backwards-compatible alias used by UI helper
def extract_echo_from_pdf(pdf_bytes: bytes):
    return extract_echo_from_pdf_bytes(pdf_bytes)
