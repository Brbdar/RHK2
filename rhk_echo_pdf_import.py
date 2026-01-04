#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo PDF Import (Textlayer only).

Dieses Modul liest einen Echo-PDF (Textlayer) und extrahiert Messwerte.

Prinzipien
- Kein OCR: bewusst. PDFs ohne Textlayer liefern ein leeres Ergebnis + Hinweis.
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


def _norm_text(s: str) -> str:
    # normalize unicode minus, decimal commas, and whitespace
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("cm²", "cm2").replace("m²", "m2")
    s = s.replace("\u00a0", " ")
    # keep line breaks, but normalize excessive spacing
    s = re.sub(r"[ \t]+", " ", s)
    return s


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
    MatchSpec("lavi_ml_m2", r"(?:3D[- ]?)?LAVI\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*/\s*m2"),
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
    MatchSpec("rv_3d_edvi_ml_m2", r"3D[- ]?RVEDVi\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*/\s*m2"),
    MatchSpec("rv_3d_esvi_ml_m2", r"3D[- ]?RVESVi\s*:?\s*(\d+(?:[\.,]\d+)?)\s*ml\s*/\s*m2"),
    MatchSpec("rv_3d_ef_pct", r"3D[- ]?RVEF\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%?", post="percent"),

    # RA planimetry
    MatchSpec("ra_esa_cm2", r"RA\s*ESA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),
    MatchSpec("ra_eda_cm2", r"RA\s*EDA\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm2"),

    # RV function
    MatchSpec("tapse_mm", r"TAPSE\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm"),
    # S' kann als S', S´ etc. erscheinen
    MatchSpec("s_prime_cm_s", r"\bS\s*[\'´`]?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*cm\s*/\s*s"),
    MatchSpec("rvfac_pct", r"RVFAC\s*:?\s*(\d+(?:[\.,]\d+)?)\s*%", post="percent"),
    MatchSpec("tapse_spap_ratio", r"TAPSE\s*/\s*sPAP\s*:?\s*(\d+(?:[\.,]\d+)?)\s*mm\s*/\s*mmHg"),

    # Strain
    MatchSpec("rv_gls_pct", r"RV[- ]?GLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%", post="percent"),
    MatchSpec("rv_fwls_pct", r"RV\s*FWLS\s*:?\s*([\-]?\d+(?:[\.,]\d+)?)\s*%", post="percent"),

    # PH signs
    MatchSpec("trv_ms", r"TRV\s*:?\s*(\d+(?:[\.,]\d+)?)\s*(?:m\s*/\s*s|cm\s*/\s*s)", post="trv_to_ms"),
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
        return {}, {
            "ok": False,
            "hint": "Im PDF wurde kein verwertbarer Textlayer gefunden (wahrscheinlich Scan). OCR ist aktuell deaktiviert.",
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



def extract_echo_from_text(text: str, *, source: str = "text") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract echo parameters from a plain text blob (already extracted from PDF or OCR).

    This reuses the same PATTERNS and post-processing as the PDF path.
    """
    meta: Dict[str, Any] = {"ok": True, "hint": "", "pages": 1, "source": source}

    full = _norm_text(text or "")
    if len(full.strip()) < 20:
        return {}, {"ok": False, "hint": "Kein verwertbarer Text gefunden.", "pages": 1, "source": source}

    ui: Dict[str, Any] = {}
    for spec in PATTERNS:
        m = re.search(spec.pattern, full, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        raw = m.group(1)
        val = _to_float(raw)
        if val is None:
            continue
        if spec.post == "trv_to_ms":
            val = _post_trv_to_ms(val, full)
        elif spec.post == "yesno":
            val = _post_yesno(val)
        elif spec.post == "percent":
            val = _post_percent(val)
        elif spec.post == "ivc_collapse_yesno":
            val = _post_ivc_collapse_yesno(val)
        ui[spec.key] = val

    # Normalize common unit spellings and compatibility keys
    if "la_esa_cm2" in ui and isinstance(ui["la_esa_cm2"], (int, float)):
        pass

    # Convenience: if explicit expiratory IVC exists, use as diameter
    if "ivc_diam_mm" not in ui and "ivc_exp_mm" in ui:
        ui["ivc_diam_mm"] = ui.get("ivc_exp_mm")

    # Derived: notch keyword anywhere
    if "rvot_notch" not in ui:
        full_l = full.lower()
        if re.search(r"\b(mid[- ]?systolic|late[- ]?systolic)\s+notch\b", full_l):
            ui["rvot_notch"] = "ja"

    return ui, meta


def _extract_text_from_image(path: str) -> Tuple[str, Dict[str, Any]]:
    """OCR helper for screenshots (PNG, JPG, WEBP, BMP, TIF).

    Nutzt pytesseract, sofern verfügbar. Die Tesseract Binary muss installiert sein.
    Optional kann der Pfad über die Umgebungsvariable TESSERACT_CMD gesetzt werden.
    """
    meta: Dict[str, Any] = {"ok": False, "hint": "", "pages": 1, "source": "image_ocr"}
    try:
        from PIL import Image, ImageOps
    except Exception as e:
        meta["hint"] = f"Pillow nicht verfügbar: {e}"
        return "", meta

    try:
        import pytesseract
    except Exception as e:
        meta["hint"] = f"pytesseract nicht verfügbar: {e}"
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
        meta["hint"] = (
            "Tesseract OCR ist nicht verfügbar. Bitte Tesseract installieren "
            "und sicherstellen, dass es im PATH liegt. "
            "Alternativ kann TESSERACT_CMD auf den Pfad zur tesseract.exe gesetzt werden. "
            f"Details: {e}"
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
