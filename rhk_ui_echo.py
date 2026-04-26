#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.38: rhk_ui_echo.py - Diagnostics: effektive Browser-OCR/PDF Flags im UI (schnelle Ops-Diagnose)
# Refactor v1.36: rhk_ui_echo.py - Browser-OCR/PDF Hinweistexte korrigiert (Vendor-Assets oder CDN)
# Refactor v1.30: rhk_ui_echo.py - Browser-PDF Tab (kein Upload), Import-Merge Policy (Stale-Wipe/Undo-Provenance), Apply aktualisiert State
# Refactor v1.24: rhk_ui_echo.py - Datenschutz-Gating (Cloud Upload), Browser-OCR optional, UI-Texte präzisiert
"""Echo (TTE) UI section.

Refactor v1.30
- Browser-PDF Import UI hinzugefügt (pdf.js lokal): PDF bleibt lokal, es wird nur Text extrahiert.
- Auto-Fill Merge über zentrale Policy (`apply_import_updates`):
  - verhindert stale carry-over bei neuem Import (Wipe nur wenn unverändert)
  - Radio-Defaults ("keine Angabe", "-") gelten als *leer* → Import darf sie ersetzen
  - Apply-Button aktualisiert Provenance für Undo
- Clear-Current löscht nur Import-Payload, behält Undo-Provenance.

Refactor v1.24
- Datenschutz: Server-Upload kann in Cloud-Runtimes standardmäßig deaktiviert werden (RHK_ALLOW_SERVER_UPLOAD=1 zum Freischalten).
- Browser-OCR (Tesseract.js) ist optional (RHK_ENABLE_BROWSER_IMPORT=1, RHK_ENABLE_BROWSER_OCR=1).
- UI-Texte präzisiert: klarer Unterschied zwischen lokalem Upload und clientseitiger Extraktion (kein stilles CDN).
"""

from __future__ import annotations

import functools
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from rhk_base import gr
from rhk_echo_guidelines import guidelines_sources
from rhk_echo_guidelines import severity as guideline_severity
from rhk_echo_pdf_import import extract_echo_from_file, extract_echo_from_text
from rhk_import_merge import apply_import_updates
from rhk_logging import log_exception
from rhk_ui_assets import (
    ALLOW_CDN_ASSETS,
    BROWSER_OCR_AVAILABLE,
    BROWSER_PDF_IMPORT_AVAILABLE,
    ENABLE_BROWSER_IMPORT,
    ENABLE_BROWSER_OCR,
    FORCE_HOSTED_BROWSER_TOOLS,
    OFFLINE_MODE,
)

IS_RENDER_NATIVE = bool(os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER"))
IS_CLOUD_RUNTIME = bool(
    IS_RENDER_NATIVE
    or os.environ.get("SPACE_ID")
    or os.environ.get("HF_SPACE")
    or os.environ.get("KAGGLE_URL_BASE")
)
# In Cloud-Runtimes kann ein File-Upload (Server) PHI an einen entfernten Server übertragen.
# Default: in Cloud deaktiviert, lokal aktiviert. Override via RHK_ALLOW_SERVER_UPLOAD=1/0.
ALLOW_SERVER_UPLOAD: bool = os.environ.get("RHK_ALLOW_SERVER_UPLOAD", "0" if IS_CLOUD_RUNTIME else "1").strip().lower() in (
    "1", "true", "yes", "on"
)
_SUPPORTED_IMPORT_TYPES = [".pdf"] if IS_RENDER_NATIVE else [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"]

# Derived feature flags for the UI
BROWSER_OCR_ENABLED: bool = bool(ENABLE_BROWSER_IMPORT and ENABLE_BROWSER_OCR and BROWSER_OCR_AVAILABLE)
BROWSER_PDF_IMPORT_ENABLED: bool = bool(ENABLE_BROWSER_IMPORT and BROWSER_PDF_IMPORT_AVAILABLE)



# Order for preview/compare table (ui_key, label, unit)
_PREVIEW_ORDER: List[Tuple[str, str, str]] = [
    # Klinik
    ("height_cm", "Größe", "cm"),
    ("weight_kg", "Gewicht", "kg"),
    ("bsa_m2", "KOF", "m²"),

    # Linksherz
    ("lvef", "LV-EF", "%"),
    ("ee_ratio", "E/e'", ""),
    ("la_vmax_ml", "LA Vmax", "ml"),
    ("la_esa_cm2", "LA ESA", "cm²"),
    ("lavi_ml_m2", "LAVI", "ml/m²"),
    ("pericardial_effusion", "Perikarderguss", ""),

    # PH / RV Basis
    ("pasp_echo", "sPAP Echo", "mmHg"),
    ("trv_ms", "TRV max", "m/s"),
    ("tapse_mm", "TAPSE", "mm"),
    ("tapse_spap_ratio", "TAPSE/sPAP", "mm/mmHg"),
    ("s_prime_cm_s", "Trikuspidales S'", "cm/s"),

    # RA / RV Größen
    ("ra_esa_cm2", "RA ESA", "cm²"),
    ("ra_eda_cm2", "RA EDA", "cm²"),
    ("rv_edd_mm", "RV EDD", "mm"),
    ("rv_esd_mm", "RV ESD", "mm"),
    ("rv_eda_cm2", "RV EDA", "cm²"),
    ("rv_esa_cm2", "RV ESA", "cm²"),
    ("rv_wall_thickness_mm", "RV Wanddicke", "mm"),

    # RV Funktion/3D
    ("rvfac_pct", "RVFAC", "%"),
    ("rv_3d_edv_ml", "3D-RVEDV", "ml"),
    ("rv_3d_edvi_ml_m2", "3D-RVEDVi", "ml/m²"),
    ("rv_3d_esv_ml", "3D-RVESV", "ml"),
    ("rv_3d_esvi_ml_m2", "3D-RVESVi", "ml/m²"),
    ("rv_3d_sv_ml", "3D-RVSV", "ml"),
    ("rv_3d_ef_pct", "3D-RVEF", "%"),

    # Strain
    ("rv_gls_pct", "RV-GLS", "%"),
    ("rv_fwls_pct", "RV FWLS", "%"),

    # RVOT/PA
    ("paat_ms", "PAAT", "ms"),
    ("rvet_ms", "RVET", "ms"),
    ("paat_rvet_ratio", "PAAT/RVET", ""),
    ("rvot_notch", "Mid-systolic Notch", ""),

    # VCI
    ("ivc_diam_mm", "VCI Durchmesser", "mm"),
    ("ivc_exp_mm", "VCI expir.", "mm"),
    ("ivc_insp_mm", "VCI inspir.", "mm"),
    ("ivc_collapse_index_pct", "VCI Kollaps Index", "%"),
    ("ivc_collapse", "VCI Kollaps >50%", ""),
]

# Compact HTML table styles (inline)
_TABLE_WRAP_STYLE = "max-height:760px;min-height:420px;overflow:auto;resize:vertical;border:1px solid rgba(0,0,0,.08);border-radius:10px;"
_TABLE_STYLE = "width:100%;table-layout:fixed;font-size:11px;line-height:1.25;border-collapse:collapse;"
_TH_STYLE = "position:sticky;top:0;background:#fff;border-bottom:1px solid rgba(0,0,0,.08);padding:6px 8px;text-align:left;"
_TD_STYLE = "border-bottom:1px solid rgba(0,0,0,.06);padding:6px 8px;vertical-align:top;"

_MUTED = "color:rgba(0,0,0,.55);font-size:12px;"


def _escape(x: Any) -> str:
    import html
    return html.escape("" if x is None else str(x))


def _fmt_num(v: Any, digits: int = 2) -> str:
    try:
        if v is None:
            return "—"
        if isinstance(v, bool):
            return "ja" if v else "nein"
        if isinstance(v, (int, float)):
            if digits <= 0:
                return str(int(round(float(v))))
            return f"{float(v):.{digits}f}".replace(".", ",")
        s = str(v).strip()
        return s if s else "—"
    except (ValueError, TypeError, AttributeError) as exc:
        log_exception("RHK_ECHO_FMT_NUM", "Numeric formatting failed.", exc)
        return "—"


# Ampel Styling (schnelle visuelle Stratifizierung) – centralised in rhk_config
from rhk_config import SEV_BG as _SEV_BG
from rhk_config import SEV_BORDER as _SEV_BORDER
from rhk_config import SEV_RANK as _SEV_RANK


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            x = float(v)
            if x != x:  # NaN
                return None
            return x
        except (ValueError, TypeError, OverflowError) as exc:
            log_exception("RHK_ECHO_AS_FLOAT", "Float coercion from numeric failed.", exc)
            return None
    if isinstance(v, str):
        s = v.strip().lower()
        if not s or s in ('—', '-', 'keine angabe', 'ja', 'nein'):
            return None
        s = s.replace(',', '.')
        try:
            x = float(s)
            if x != x:
                return None
            return x
        except (ValueError, TypeError, OverflowError) as exc:
            log_exception("RHK_ECHO_AS_FLOAT_STR", "Float coercion from string failed.", exc)
            return None
    return None


def _sev_css(sev: str) -> str:
    return _SEV_BG.get(sev or '', '')


def _severity(key: str, v: Any) -> str:
    """Ampel severity via central guideline rule library."""
    return guideline_severity(key, v)


def _normalize_radio_value(key: str, val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, bool):
        return 'ja' if val else 'nein'
    if isinstance(val, (int, float)):
        # manche Quellen geben 0 oder 1
        if key in ('pericardial_effusion', 'rvot_notch', 'ivc_respiratory', 'ivc_collapse'):
            return 'ja' if float(val) >= 0.5 else 'nein'
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ('ja', 'nein'):
            return s
        if s in ('true', 'wahr', 'yes', 'y'):
            return 'ja'
        if s in ('false', 'falsch', 'no', 'n'):
            return 'nein'
        if s in ('keine angabe', 'na', 'n/a', '-'):
            return 'keine Angabe'
        return val
    return val


def _coerce_path(file_obj: Any) -> Optional[str]:
    """Normalize Gradio file object to a local filepath."""
    if not file_obj:
        return None
    if isinstance(file_obj, str):
        return file_obj
    if isinstance(file_obj, dict):
        p = file_obj.get("path") or file_obj.get("name") or file_obj.get("file")
        return p if isinstance(p, str) and p else None
    for attr in ("path", "name"):
        try:
            p = getattr(file_obj, attr, None)
            if isinstance(p, str) and p:
                return p
        except (AttributeError, TypeError) as exc:
            log_exception("RHK_ECHO_COERCE_PATH", f"Failed to read attribute '{attr}' from file object.", exc)
    return None


def _parse_file_to_state(file_obj: Any) -> Dict[str, Any]:
    """Return state dict: {parsed, meta, has_file}

    Supports:
    - PDF (Textlayer): via PyMuPDF / pypdf / PyPDF2 (depending on availability)
    - Image screenshot: OCR via Tesseract (optional)
    """
    path = _coerce_path(file_obj)
    if not path:
        return {"parsed": {}, "meta": {"ok": False, "hint": ""}, "has_file": False}

    try:
        parsed, meta = extract_echo_from_file(path)
        meta = meta or {}
        return {"parsed": parsed or {}, "meta": meta, "has_file": True}
    except (IOError, OSError, ValueError, KeyError, TypeError) as e:
        log_exception("RHK_ECHO_FILE_PARSE", "Echo file import failed.", e)
        return {"parsed": {}, "meta": {"ok": False, "hint": f"Import fehlgeschlagen: {e}"}, "has_file": True}


def _echo_state_render_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return a stable, render-relevant state payload for HTML caching."""
    st = state or {}
    return {
        "parsed": st.get("parsed") or {},
        "meta": st.get("meta") or {},
        "has_file": bool(st.get("has_file")),
    }


def _cache_json(payload: Dict[str, Any]) -> str:
    """Serialize payload in a stable way for LRU cache keys."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


@functools.lru_cache(maxsize=256)
def _render_import_table_cached(payload_json: str, title: str) -> str:
    state = json.loads(payload_json)
    parsed = (state or {}).get("parsed") or {}
    meta = (state or {}).get("meta") or {}
    has_file = bool((state or {}).get("has_file"))

    hint = (meta.get("hint") or "").strip()
    backend = (meta.get("backend") or meta.get("source") or "").strip()

    if not has_file and not parsed:
        return f"<div style='{_MUTED}'>{_escape(title)}: noch kein PDF hochgeladen.</div>"

    if has_file and not parsed:
        # show reason prominently
        reason = hint or "Keine Werte extrahiert."
        diag = (meta.get("diag") or "").strip()
        if "Backend" in reason or "pypdf" in reason.lower() or "PyMuPDF" in reason or "Backend" in diag:
            reason += " Installiere mindestens <b>pypdf</b> (oder PyMuPDF) in genau dieser Python-Umgebung."
        diag_html = ""
        if diag:
            diag_html = (
                "<details style='margin-top:6px'>"
                "<summary style='cursor:pointer;color:rgba(0,0,0,.55)'>Diagnose</summary>"
                f"<pre style='white-space:pre-wrap;margin:6px 0 0 0;color:rgba(0,0,0,.55)'>"
                f"{_escape(diag)}</pre></details>"
            )
        return f"<div style='{_MUTED}'><b>{_escape(title)}</b>: 0 Werte. { _escape(reason) }{diag_html}</div>"

    # rows
    rows = []
    for k, label, unit in _PREVIEW_ORDER:
        if k in parsed and parsed.get(k) is not None:
            rows.append((label, parsed.get(k), unit))

    head_parts = [f"<b>{_escape(title)}</b>: {len(rows)} Werte"]
    if backend:
        head_parts.append(f"Quelle: {_escape(backend)}")
    if hint:
        head_parts.append(_escape(hint))
    head = f"<div style='{_MUTED};margin-bottom:6px'>{' · '.join(head_parts)}</div>"

    trs = "".join(
        f"<tr><td style='{_TD_STYLE};width:58%'>{_escape(label)}</td>"
        f"<td style='{_TD_STYLE};width:24%;text-align:right'>{_escape(_fmt_num(val))}</td>"
        f"<td style='{_TD_STYLE};width:18%'>{_escape(unit)}</td></tr>"
        for (label, val, unit) in rows
    )
    table = (
        f"<div style='{_TABLE_WRAP_STYLE}'>"
        f"<table style='{_TABLE_STYLE}'>"
        "<thead><tr>"
        f"<th style='{_TH_STYLE};width:58%'>Parameter</th>"
        f"<th style='{_TH_STYLE};width:24%;text-align:right'>Wert</th>"
        f"<th style='{_TH_STYLE};width:18%'>Einheit</th>"
        "</tr></thead>"
        f"<tbody>{trs}</tbody></table></div>"
    )
    return head + table


def _render_import_table(state: Dict[str, Any], title: str) -> str:
    payload_json = _cache_json(_echo_state_render_payload(state))
    return _render_import_table_cached(payload_json, title)


@functools.lru_cache(maxsize=256)
def _render_compare_table_cached(prev_payload_json: str, cur_payload_json: str) -> str:
    state_prev = json.loads(prev_payload_json)
    state_cur = json.loads(cur_payload_json)
    p_prev = (state_prev or {}).get('parsed') or {}
    p_cur = (state_cur or {}).get('parsed') or {}
    has_prev = bool((state_prev or {}).get('has_file'))
    has_cur = bool((state_cur or {}).get('has_file'))

    if not has_prev and not has_cur:
        return f"<div style='{_MUTED}'>Kein Echo importiert. Bitte aktuelles oder Vor Echo hochladen.</div>"

    rows = []
    for k, label, unit in _PREVIEW_ORDER:
        pv = p_prev.get(k) if has_prev else None
        cv = p_cur.get(k) if has_cur else None
        if pv is None and cv is None:
            continue

        # Delta nur fuer Zahlen
        dv = '—'
        try:
            if pv is not None and cv is not None:
                fp = _as_float(pv)
                fc = _as_float(cv)
                if fp is not None and fc is not None:
                    dv = _fmt_num(fc - fp, 2)
        except (ValueError, TypeError, OverflowError) as exc:
            log_exception("RHK_ECHO_DELTA_CALC", "Delta calculation for compare table failed.", exc)
            dv = '—'

        sev_p = _severity(k, pv) if pv is not None else ''
        sev_c = _severity(k, cv) if cv is not None else ''

        # Delta Ampel: verschlechtert oder verbessert relativ zur Ampel
        sev_d = ''
        try:
            rp = _SEV_RANK.get(sev_p or '', 0)
            rc = _SEV_RANK.get(sev_c or '', 0)
            if rp and rc:
                if rc > rp:
                    sev_d = 'r'
                elif rc < rp:
                    sev_d = 'g'
        except (KeyError, TypeError) as exc:
            log_exception("RHK_ECHO_SEV_RANK", "Severity rank comparison failed.", exc)
            sev_d = ''

        rows.append((k, label, pv, cv, dv, unit, sev_p, sev_c, sev_d))

    if not rows:
        return f"<div style='{_MUTED}'>PDF(s) hochgeladen, aber keine Werte extrahiert.</div>"

    legend = (
        "<span style='display:inline-flex;align-items:center;gap:8px'>"
        "<span style='display:inline-flex;align-items:center;gap:4px'><span style='width:10px;height:10px;border-radius:50%;background:rgba(34,197,94,.5)'></span>normal</span>"
        "<span style='display:inline-flex;align-items:center;gap:4px'><span style='width:10px;height:10px;border-radius:50%;background:rgba(234,179,8,.6)'></span>grenzwertig</span>"
        "<span style='display:inline-flex;align-items:center;gap:4px'><span style='width:10px;height:10px;border-radius:50%;background:rgba(239,68,68,.55)'></span>auffaellig</span>"
        "</span>"
    )

    trs = ''
    for _k, label, pv, cv, dv, unit, sev_p, sev_c, sev_d in rows:
        pv_style = f"{_TD_STYLE};width:18%;text-align:right;{_sev_css(sev_p)}"
        cv_style = f"{_TD_STYLE};width:18%;text-align:right;{_sev_css(sev_c)}"
        dv_style = f"{_TD_STYLE};width:10%;text-align:right;{_sev_css(sev_d)}"

        trs += (
            f"<tr>"
            f"<td style='{_TD_STYLE};width:44%;{_SEV_BORDER.get((sev_c or sev_p) or '', _SEV_BORDER[''])}'>{_escape(label)}</td>"
            f"<td style='{pv_style}'>{_escape(_fmt_num(pv))}</td>"
            f"<td style='{cv_style}'>{_escape(_fmt_num(cv))}</td>"
            f"<td style='{dv_style}'>{_escape(dv)}</td>"
            f"<td style='{_TD_STYLE};width:10%'>{_escape(unit)}</td>"
            f"</tr>"
        )

    table = (
        f"<div style='{_MUTED};margin:6px 0;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap'>"
        f"<b>Vergleich</b>: Vor Echo vs aktuelles Echo {legend}"
        f"</div>"
        f"<div style='color:rgba(0,0,0,.55);font-size:12px;margin:0 0 8px 0'>Ampel-Klassifikation basiert auf: {', '.join(guidelines_sources())}. Hinweis: reine Orientierung, Kontext und Bildqualität beachten.</div>"
        f"<div style='{_TABLE_WRAP_STYLE}'>"
        f"<table style='{_TABLE_STYLE}'>"
        "<thead><tr>"
        f"<th style='{_TH_STYLE};width:44%'>Parameter</th>"
        f"<th style='{_TH_STYLE};width:18%;text-align:right'>Vor</th>"
        f"<th style='{_TH_STYLE};width:18%;text-align:right'>Aktuell</th>"
        f"<th style='{_TH_STYLE};width:10%;text-align:right'>Δ</th>"
        f"<th style='{_TH_STYLE};width:10%'>Einheit</th>"
        "</tr></thead>"
        f"<tbody>{trs}</tbody></table></div>"
    )

    return table


def _render_compare_table(state_prev: Dict[str, Any], state_cur: Dict[str, Any]) -> str:
    prev_payload_json = _cache_json(_echo_state_render_payload(state_prev))
    cur_payload_json = _cache_json(_echo_state_render_payload(state_cur))
    return _render_compare_table_cached(prev_payload_json, cur_payload_json)


def build_echo_section(add) -> Dict[str, Any]:
    """Build Echo section UI."""
    gr.Markdown("### Echokardiographie")

    # --- Import block ---------------------------------------------------------
    with gr.Accordion("Echo Import (PDF oder Screenshot)", open=True):
        server_upload_status = "✅ aktiv" if ALLOW_SERVER_UPLOAD else "⛔ deaktiviert"
        browser_ocr_status = "✅ aktiv" if BROWSER_OCR_ENABLED else "⛔ deaktiviert"
        browser_pdf_status = "✅ aktiv" if BROWSER_PDF_IMPORT_ENABLED else "⛔ deaktiviert"
        gr.Markdown(
            f"**Datenschutz & Importwege**\n\n"
            f"- Datei (Server-Upload): {server_upload_status}. (Überträgt Datei an Server; lokal empfohlen)\n"
            f"- Screenshot OCR (Browser): {browser_ocr_status}. (Bild bleibt lokal; es wird nur Text übertragen)\n"
            f"- PDF (Browser): {browser_pdf_status}. (PDF bleibt lokal; es wird nur Text übertragen)\n\n"
            "Schalter: `RHK_ALLOW_SERVER_UPLOAD`, `RHK_ENABLE_BROWSER_IMPORT`, `RHK_ENABLE_BROWSER_OCR`, `RHK_ALLOW_CDN_ASSETS`, `RHK_FORCE_HOSTED_BROWSER_TOOLS`, `RHK_OFFLINE`/`RHK_PRIVACY_MODE`.\n"
            f"<div style='color:rgba(0,0,0,.55);font-size:12px;margin-top:6px'>"
            f"Effektiv: browser_import={int(bool(ENABLE_BROWSER_IMPORT))}, browser_ocr={int(bool(ENABLE_BROWSER_OCR))}, cdn={int(bool(ALLOW_CDN_ASSETS))}, ocr_available={int(bool(BROWSER_OCR_AVAILABLE))}, pdf_available={int(bool(BROWSER_PDF_IMPORT_AVAILABLE))}, force_hosted={int(bool(FORCE_HOSTED_BROWSER_TOOLS))}, offline={int(bool(OFFLINE_MODE))}."
            f"</div>",
        )

        # "Hidden" OCR text fields (filled by Browser OCR via JS)
        # IMPORTANT: visible=False may prevent Gradio from rendering the DOM nodes at all.
        # We render them (visible=True) but hide via CSS class, so JS can reliably set values.
        echo_ocr_text_cur = add(
            "echo_ocr_text_cur",
            gr.Textbox(
                label="Echo OCR Text (aktuell, browser)",
                visible=True,
                elem_id="echo_ocr_text_cur",
                elem_classes=["rhk-hidden"],
            ),
        )
        echo_ocr_text_prev = add(
            "echo_ocr_text_prev",
            gr.Textbox(
                label="Echo OCR Text (Vor, browser)",
                visible=True,
                elem_id="echo_ocr_text_prev",
                elem_classes=["rhk-hidden"],
            ),
        )

        # "Hidden" PDF text fields (filled by Browser PDF text extraction via JS)
        echo_pdf_text_cur = add(
            "echo_pdf_text_cur",
            gr.Textbox(
                label="Echo PDF Text (aktuell, browser)",
                visible=True,
                elem_id="echo_pdf_text_cur",
                elem_classes=["rhk-hidden"],
            ),
        )
        echo_pdf_text_prev = add(
            "echo_pdf_text_prev",
            gr.Textbox(
                label="Echo PDF Text (Vor, browser)",
                visible=True,
                elem_id="echo_pdf_text_prev",
                elem_classes=["rhk-hidden"],
            ),
        )

        
        # Import UI (slim): Tabs for PDF vs Screenshot. Keep Legacy server upload (Option B).
        with gr.Accordion("Import", open=True):
            with gr.Tabs():
                with gr.Tab("Datei (Server)"):
                    gr.Markdown(
                        "Datei-Upload (Server): PDF oder Screenshot. **Hinweis:** Upload überträgt die Datei an den Server (lokal ok).",
                        visible=ALLOW_SERVER_UPLOAD,
                    )
                    gr.Markdown(
                        "⛔ Server-Upload ist in dieser Umgebung deaktiviert (Datenschutz). "
                        "Für lokale Nutzung: `RHK_ALLOW_SERVER_UPLOAD=1`. "
                        "Alternativ: Screenshot OCR im Browser aktivieren.",
                        visible=(not ALLOW_SERVER_UPLOAD),
                    )
                    with gr.Row():
                        import_pdf_cur = gr.File(
                            label="Aktuell",
                            file_types=_SUPPORTED_IMPORT_TYPES,
                            type="filepath",
                            file_count="single",
                            visible=ALLOW_SERVER_UPLOAD,
                        )
                        import_pdf_prev = gr.File(
                            label="Vor Echo (optional)",
                            file_types=_SUPPORTED_IMPORT_TYPES,
                            type="filepath",
                            file_count="single",
                            visible=ALLOW_SERVER_UPLOAD,
                        )

                with gr.Tab("Screenshot (Browser)"):
                    gr.Markdown(
                        "Screenshot OCR im Browser (keine Datei wird an den Server hochgeladen).",
                        visible=BROWSER_OCR_ENABLED,
                    )
                    gr.Markdown(
                        "⛔ Browser-OCR ist deaktiviert oder nicht verfügbar. "
                        "Aktivieren: `RHK_ENABLE_BROWSER_IMPORT=1` und `RHK_ENABLE_BROWSER_OCR=1` (Vendor-Assets **oder** `RHK_ALLOW_CDN_ASSETS=1`). "
                        f"(Effektiv: browser_import={int(bool(ENABLE_BROWSER_IMPORT))}, browser_ocr={int(bool(ENABLE_BROWSER_OCR))}, cdn={int(bool(ALLOW_CDN_ASSETS))}, ocr_available={int(bool(BROWSER_OCR_AVAILABLE))}, offline={int(bool(OFFLINE_MODE))})",
                        visible=(not BROWSER_OCR_ENABLED),
                    )
                    gr.HTML(
                        """
                        <div style='display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;padding:6px 0'>
                          <div style='min-width:280px'>
                            <div style='font-size:12px;color:rgba(0,0,0,.65);margin-bottom:4px'>Aktuell</div>
                            <input id='rhk_echo_ocr_file_cur' type='file' accept='image/*' />
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoOcr && window.rhkRunEchoOcr("cur")'>OCR</button>
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoClipboard && window.rhkRunEchoClipboard("cur")'>Zwischenablage</button>
                            <span id='rhk_echo_ocr_status_cur' style='margin-left:8px;color:rgba(0,0,0,.55);font-size:12px'></span>
                          </div>
                          <div style='min-width:280px'>
                            <div style='font-size:12px;color:rgba(0,0,0,.65);margin-bottom:4px'>Vor Echo</div>
                            <input id='rhk_echo_ocr_file_prev' type='file' accept='image/*' />
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoOcr && window.rhkRunEchoOcr("prev")'>OCR</button>
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoClipboard && window.rhkRunEchoClipboard("prev")'>Zwischenablage</button>
                            <span id='rhk_echo_ocr_status_prev' style='margin-left:8px;color:rgba(0,0,0,.55);font-size:12px'></span>
                          </div>
                        </div>
                        """,
                        visible=BROWSER_OCR_ENABLED,
                    )

                with gr.Tab("PDF (Browser)"):
                    gr.Markdown(
                        "PDF Import im Browser (kein Upload): Textlayer wird lokal extrahiert; Scan-PDF: optional OCR Seite 1.",
                        visible=BROWSER_PDF_IMPORT_ENABLED,
                    )
                    gr.Markdown(
                        "⛔ Browser-PDF-Import ist deaktiviert oder nicht verfügbar. "
                        "Aktivieren: `RHK_ENABLE_BROWSER_IMPORT=1` (Vendor-Assets **oder** `RHK_ALLOW_CDN_ASSETS=1` für pdf.js). "
                        f"(Effektiv: browser_import={int(bool(ENABLE_BROWSER_IMPORT))}, cdn={int(bool(ALLOW_CDN_ASSETS))}, pdf_available={int(bool(BROWSER_PDF_IMPORT_AVAILABLE))}, offline={int(bool(OFFLINE_MODE))})",
                        visible=(not BROWSER_PDF_IMPORT_ENABLED),
                    )
                    gr.HTML(
                        """
                        <div style='display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end;padding:6px 0'>
                          <div style='min-width:280px'>
                            <div style='font-size:12px;color:rgba(0,0,0,.65);margin-bottom:4px'>Aktuell</div>
                            <input id='rhk_echo_pdf_file_cur' type='file' accept='application/pdf' />
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoPdf && window.rhkRunEchoPdf("cur")'>Text extrahieren</button>
                            <span id='rhk_echo_pdf_status_cur' style='margin-left:8px;color:rgba(0,0,0,.55);font-size:12px'></span>
                          </div>
                          <div style='min-width:280px'>
                            <div style='font-size:12px;color:rgba(0,0,0,.65);margin-bottom:4px'>Vor Echo</div>
                            <input id='rhk_echo_pdf_file_prev' type='file' accept='application/pdf' />
                            <button type='button' style='margin-left:6px' onclick='window.rhkRunEchoPdf && window.rhkRunEchoPdf("prev")'>Text extrahieren</button>
                            <span id='rhk_echo_pdf_status_prev' style='margin-left:8px;color:rgba(0,0,0,.55);font-size:12px'></span>
                          </div>
                        </div>
                        """,
                        visible=BROWSER_PDF_IMPORT_ENABLED,
                    )

        # Legacy server upload remains available (Option B) but stays collapsed to avoid overload.
        with gr.Accordion("Legacy: Server Upload (nicht empfohlen)", open=False, visible=ALLOW_SERVER_UPLOAD):
            with gr.Row():
                legacy_pdf_cur = gr.File(
                    label="Echo Datei (aktuell) – Upload",
                    file_types=_SUPPORTED_IMPORT_TYPES,
                    type="filepath",
                    file_count="single",
                )
                legacy_pdf_prev = gr.File(
                    label="Vor Echo Datei (optional) – Upload",
                    file_types=_SUPPORTED_IMPORT_TYPES,
                    type="filepath",
                    file_count="single",
                )

        with gr.Row():
            btn_apply = gr.Button("Werte übernehmen (nur leere Felder)", variant="primary")
            btn_clear_cur = gr.Button("Import löschen", variant="secondary")
            btn_clear_prev = gr.Button("Vor-Echo löschen", variant="secondary")
            btn_wipe_echo_fields = gr.Button("Echo Werte entfernen", variant="secondary")

        # state
        state_echo_cur = gr.State(value={"parsed": {}, "meta": {}, "has_file": False, "_ui_autofill_values": {}, "_ui_autofill_keys": []})
        state_echo_prev = gr.State(value={"parsed": {}, "meta": {}, "has_file": False})

        # compact previews
        with gr.Row():
            import_preview_cur_html = gr.HTML(value=_render_import_table(state_echo_cur.value, "Aktuell"))
            import_preview_prev_html = gr.HTML(value=_render_import_table(state_echo_prev.value, "Vor"))

        compare_html = gr.HTML(value=_render_compare_table(state_echo_prev.value, state_echo_cur.value))

        with gr.Accordion("Import Details (Aktuell/Vor)", open=False):
            details_html = gr.HTML(value="<div style='color:rgba(0,0,0,.55)'>Noch keine Details.</div>")

    
    # Hidden: Vor Echo Werte als JSON für Reports (Verlauf und Dynamik)
    # Diese Felder sind unsichtbar und werden automatisch beim Vor Echo Import gesetzt.
    add("echo_prev_json", gr.Textbox(label="echo_prev_json", visible=False))
    add("echo_prev_meta_json", gr.Textbox(label="echo_prev_meta_json", visible=False))

    # --- Manual input fields --------------------------------------------------
    with gr.Accordion("Echo Eingabefelder (manuell)", open=False):
        # Basic / visible
        with gr.Row():
            add("echo_done", gr.Checkbox(label="Echo durchgeführt"))
            add("lvef", gr.Number(label="LV-EF (%)"))
            add("ee_ratio", gr.Number(label="E/e'"))
            add("la_enlarged", gr.Checkbox(label="Linksatrium erweitert"))

        with gr.Row():
            add("la_vmax_ml", gr.Number(label="LA Vmax (ml)"))
            add("la_esa_cm2", gr.Number(label="LA ESA (cm²)"))
            add("lavi_ml_m2", gr.Number(label="LAVI (ml/m²)"))
            add("afib", gr.Checkbox(label="Vorhofflimmern"))

        with gr.Row():
            add("pasp_echo", gr.Number(label="sPAP Echo (mmHg)"))
            add("trv_ms", gr.Number(label="TRV max (m/s)"))
            add("tapse_mm", gr.Number(label="TAPSE (mm)"))
            add("tapse_spap_ratio", gr.Number(label="TAPSE/sPAP (mm/mmHg)"))

        with gr.Row():
            add("s_prime_cm_s", gr.Number(label="Trikuspidales S' (cm/s)"))
            add("ra_esa_cm2", gr.Number(label="RA ESA (cm²)"))
            add("rv_edd_mm", gr.Number(label="RV EDD (mm)"))
            add("septal_flattening", gr.Checkbox(label="Septumflattening"))

        with gr.Row():
            add("ivc_diam_mm", gr.Number(label="VCI Durchmesser (mm)"))
            add(
                "ivc_collapse",
                gr.Radio(
                    label="VCI Kollaps >50%?",
                    choices=["keine Angabe", "ja", "nein"],
                    value="keine Angabe",
                ),
            )
            add(
                "pericardial_effusion",
                gr.Radio(
                    label="Perikarderguss?",
                    choices=["keine Angabe", "nein", "ja"],
                    value="keine Angabe",
                ),
            )

        with gr.Row():
            add(
                "rvot_notch",
                gr.Radio(
                    label="Mid-systolic Notch?",
                    choices=["keine Angabe", "nein", "ja"],
                    value="keine Angabe",
                ),
            )
            add(
                "ivc_respiratory",
                gr.Radio(
                    label="VCI atemvariabel?",
                    choices=["keine Angabe", "nein", "ja"],
                    value="keine Angabe",
                ),
            )

        with gr.Accordion("Echo erweitert (Rechtes Herz & PH)", open=False):
            with gr.Row():
                add("ra_eda_cm2", gr.Number(label="RA EDA (cm²)"))
                add("rv_esd_mm", gr.Number(label="RV ESD (mm)"))
                add("rv_eda_cm2", gr.Number(label="RV EDA (cm²)"))
                add("rv_esa_cm2", gr.Number(label="RV ESA (cm²)"))

            with gr.Row():
                add("rv_wall_thickness_mm", gr.Number(label="RV Wanddicke (mm)"))
                add("rvfac_pct", gr.Number(label="RVFAC (%)"))
                add("rv_gls_pct", gr.Number(label="RV GLS (%)"))
                add("rv_fwls_pct", gr.Number(label="RV FWLS (%)"))

            with gr.Row():
                add("rv_3d_edv_ml", gr.Number(label="3D RVEDV (ml)"))
                add("rv_3d_esv_ml", gr.Number(label="3D RVESV (ml)"))
                add("rv_3d_sv_ml", gr.Number(label="3D RVSV (ml)"))
                add("rv_3d_ef_pct", gr.Number(label="3D RVEF (%)"))

            with gr.Row():
                add("rv_3d_edvi_ml_m2", gr.Number(label="3D RVEDVi (ml/m²)"))
                add("rv_3d_esvi_ml_m2", gr.Number(label="3D RVESVi (ml/m²)"))
                add("paat_ms", gr.Number(label="PAAT (ms)"))
                add("rvet_ms", gr.Number(label="RVET (ms)"))

            with gr.Row():
                add("paat_rvet_ratio", gr.Number(label="PAAT/RVET"))
                add("ivc_exp_mm", gr.Number(label="VCI expir. (mm)"))
                add("ivc_insp_mm", gr.Number(label="VCI inspir. (mm)"))
                add("ivc_collapse_index_pct", gr.Number(label="VCI Kollaps Index (%)"))

    return {
        "import_pdf_cur": import_pdf_cur,
        "import_pdf_prev": import_pdf_prev,
        "legacy_pdf_cur": legacy_pdf_cur,
        "legacy_pdf_prev": legacy_pdf_prev,
        "echo_ocr_text_cur": echo_ocr_text_cur,
        "echo_ocr_text_prev": echo_ocr_text_prev,
        "echo_pdf_text_cur": echo_pdf_text_cur,
        "echo_pdf_text_prev": echo_pdf_text_prev,
        "import_preview_cur_html": import_preview_cur_html,
        "import_preview_prev_html": import_preview_prev_html,
        "compare_html": compare_html,
        "details_html": details_html,
        "state_echo_cur": state_echo_cur,
        "state_echo_prev": state_echo_prev,
        "btn_apply": btn_apply,
        "btn_clear_cur": btn_clear_cur,
        "btn_clear_prev": btn_clear_prev,
        "btn_wipe_echo_fields": btn_wipe_echo_fields,
    }




def render_echo_import_views(state_prev: Dict[str, Any], state_cur: Dict[str, Any]):
    """Render HTML blocks + apply-button state for persisted echo import states.

    Used when loading a saved case: uploaded file objects cannot be restored,
    but parsed/meta payloads can be, so we rebuild the preview/compare panels.
    """
    prev_state = state_prev or {"parsed": {}, "meta": {}, "has_file": False}
    cur_state = state_cur or {"parsed": {}, "meta": {}, "has_file": False}

    try:
        cur_html = _render_import_table(cur_state, "Aktuell")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        log_exception("RHK_ECHO_RENDER_CUR", "Rendering current echo import table failed.", exc)
        cur_html = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
    try:
        prev_html = _render_import_table(prev_state, "Vor")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        log_exception("RHK_ECHO_RENDER_PREV", "Rendering previous echo import table failed.", exc)
        prev_html = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
    try:
        cmp_html = _render_compare_table(prev_state, cur_state)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        log_exception("RHK_ECHO_RENDER_CMP", "Rendering echo compare table failed.", exc)
        cmp_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"

    details_html = "<div style='display:grid;gap:10px'>"
    details_html += "<div>" + cur_html + "</div>"
    details_html += "<div>" + prev_html + "</div>"
    details_html += "<div>" + cmp_html + "</div>"
    details_html += "</div>"

    enable = bool((cur_state.get("parsed") or {}) or (prev_state.get("parsed") or {}))
    return cur_html, prev_html, cmp_html, details_html, gr.update(interactive=enable)


def bind_echo_import(echo_ui: Dict[str, Any], *,
                    field_components: Dict[str, Any]) -> Dict[str, Any]:
    """Bind callbacks for echo PDF imports (current + previous).

    - Aktuelles Echo: nach Import werden Werte automatisch in die manuellen Felder uebernommen
      (nur wenn dort noch leer/0/keine Angabe steht).
    - Vor-Echo: bleibt unabhaengig; dient v.a. dem Vergleich.
    """

    import_pdf_cur = echo_ui["import_pdf_cur"]
    import_pdf_prev = echo_ui["import_pdf_prev"]
    legacy_pdf_cur = echo_ui.get("legacy_pdf_cur")
    legacy_pdf_prev = echo_ui.get("legacy_pdf_prev")
    echo_ocr_text_cur = echo_ui.get("echo_ocr_text_cur")
    echo_ocr_text_prev = echo_ui.get("echo_ocr_text_prev")
    echo_pdf_text_cur = echo_ui.get("echo_pdf_text_cur")
    echo_pdf_text_prev = echo_ui.get("echo_pdf_text_prev")
    preview_cur = echo_ui["import_preview_cur_html"]
    preview_prev = echo_ui["import_preview_prev_html"]
    compare_html = echo_ui["compare_html"]
    details_html = echo_ui["details_html"]
    state_cur = echo_ui["state_echo_cur"]
    state_prev = echo_ui["state_echo_prev"]
    btn_apply = echo_ui["btn_apply"]
    btn_clear_cur = echo_ui["btn_clear_cur"]
    btn_clear_prev = echo_ui["btn_clear_prev"]
    btn_wipe_echo_fields = echo_ui.get("btn_wipe_echo_fields")

    prev_json_comp = field_components.get("echo_prev_json")
    prev_meta_comp = field_components.get("echo_prev_meta_json")

    # keys we allow auto-fill
    target_keys = [k for (k, _, _) in _PREVIEW_ORDER] + [
        # additional fields that exist in UI but not in preview list
        "echo_done", "la_enlarged", "afib", "septal_flattening",
        "ra_eda_cm2", "rv_esd_mm", "rv_eda_cm2", "rv_esa_cm2", "rv_wall_thickness_mm",
        "rvfac_pct", "rv_gls_pct", "rv_fwls_pct",
        "rv_3d_edv_ml", "rv_3d_esv_ml", "rv_3d_sv_ml", "rv_3d_ef_pct", "rv_3d_edvi_ml_m2", "rv_3d_esvi_ml_m2",
        "paat_ms", "rvet_ms", "paat_rvet_ratio",
        "ivc_exp_mm", "ivc_insp_mm", "ivc_collapse_index_pct", "ivc_respiratory",
    ]

    apply_keys = [k for k in target_keys if k in field_components]
    apply_components = [field_components[k] for k in apply_keys]

    RADIO_KEYS = {"ivc_collapse", "pericardial_effusion", "rvot_notch", "ivc_respiratory"}

    def _default_value(cur: Any) -> Any:
        """Return the canonical *empty* default for a UI field value.

        This is used for *stale wipe* (old imported values that disappear in a new import)
        and for the explicit "Echo Werte entfernen" action.
        """
        if isinstance(cur, bool):
            return False
        if isinstance(cur, (int, float)) and not isinstance(cur, bool):
            return None
        if isinstance(cur, str):
            s = cur.strip().lower()
            return "" if s in ("", "-") else "keine Angabe"
        return None

    def _build_updates_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Build an update payload for manual echo fields from an import parse."""
        updates: Dict[str, Any] = {}
        for k in apply_keys:
            v = (parsed or {}).get(k)
            if v is None:
                continue
            if k in RADIO_KEYS:
                v = _normalize_radio_value(k, v)
                if v is None:
                    continue
            updates[k] = v

        # Ensure `echo_done` is True when any meaningful echo parameters were parsed.
        if "echo_done" in apply_keys:
            try:
                if parsed and any(
                    kk for kk in parsed.keys() if kk not in ("height_cm", "weight_kg", "bsa_m2")
                ):
                    updates.setdefault("echo_done", True)
            except (KeyError, TypeError, AttributeError) as exc:
                log_exception("RHK_ECHO_BUILD_UPDATES", "Failed to set echo_done from parsed keys.", exc)
        return updates

    def _merge_with_policy(
        *,
        ui_map: Dict[str, Any],
        updates: Dict[str, Any],
        prev_applied_keys: Optional[List[str]],
        prev_applied_values: Optional[Dict[str, Any]],
        enable_stale_wipe: bool,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """Apply import updates to the current UI values under strict rules.

        - Fills only empty fields (None/0/"keine Angabe"/etc.)
        - Overwrites values that were previously imported (and remain unchanged)
        - Optionally wipes stale imported values when a new import no longer contains them
        """
        if not updates:
            return [ui_map.get(k) for k in apply_keys], {}

        prev_vals = dict(prev_applied_values or {})

        if enable_stale_wipe:
            prev_keys = list(prev_applied_keys or list(prev_vals.keys()))
            wipe_defaults = {k: _default_value(ui_map.get(k)) for k in apply_keys}
        else:
            prev_keys = []
            wipe_defaults = {}

        ui_new, applied = apply_import_updates(
            ui=ui_map,
            updates=updates,
            prev_applied_keys=prev_keys,
            prev_applied_values=prev_vals,
            wipe_defaults=wipe_defaults,
        )
        out_vals = [ui_new.get(k) for k in apply_keys]
        return out_vals, applied
    def _update_all(state_prev_new, state_cur_new):
        cur_html = _render_import_table(state_cur_new, "Aktuell")
        prev_html = _render_import_table(state_prev_new, "Vor")
        cmp_html = _render_compare_table(state_prev_new, state_cur_new)

        # Details is just concatenation
        d = "<div style='display:grid;gap:10px'>"
        d += "<div>" + cur_html + "</div>"
        d += "<div>" + prev_html + "</div>"
        d += "<div>" + cmp_html + "</div>"
        d += "</div>"

        # enable apply if at least one side has parsed values
        enable = bool((state_cur_new.get("parsed") or {}) or (state_prev_new.get("parsed") or {}))
        return cur_html, prev_html, cmp_html, d, gr.update(interactive=enable)

    def _parse_cur(file_obj, cur_state_in, prev_state, *current_vals):
        """Parse current echo file (server upload) and auto-fill manual fields.

        Safety:
        - Never overwrites non-empty manual fields.
        - Prevents stale carry-over: imported values that disappear in a new import
          are reset to defaults **only** if they were previously imported and remain
          unchanged by the user.
        """
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}

        # Keep previous provenance so the wipe-button can still revert auto-filled values
        # even if the current import yields 0 parsed parameters.
        prev_autofill_vals: Dict[str, Any] = dict((cur_state_in.get("_ui_autofill_values") or {}) if isinstance(cur_state_in, dict) else {})
        prev_autofill_keys: List[str] = list((cur_state_in.get("_ui_autofill_keys") or list(prev_autofill_vals.keys())) if isinstance(cur_state_in, dict) else [])

        cur_state = _parse_file_to_state(file_obj)
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)

        parsed = cur_state.get("parsed") or {}
        updated_vals: List[Any] = list(current_vals)

        if parsed:
            ui_map = {k: v for k, v in zip(apply_keys, current_vals, strict=False)}
            updates = _build_updates_from_parsed(parsed)
            try:
                out_vals, applied = _merge_with_policy(
                    ui_map=ui_map,
                    updates=updates,
                    prev_applied_keys=prev_autofill_keys,
                    prev_applied_values=prev_autofill_vals,
                    enable_stale_wipe=True,
                )
                updated_vals = list(out_vals)
                cur_state["_ui_autofill_values"] = dict(applied or {})
                cur_state["_ui_autofill_keys"] = sorted(list((applied or {}).keys()))
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                log_exception("RHK_ECHO_MERGE_CUR", "Merge policy for current echo auto-fill failed.", exc)
                # If anything goes wrong, keep UI values unchanged and preserve provenance.
                updated_vals = list(current_vals)
                if prev_autofill_vals:
                    cur_state["_ui_autofill_values"] = prev_autofill_vals
                    cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))
        else:
            if prev_autofill_vals:
                cur_state["_ui_autofill_values"] = prev_autofill_vals
                cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))

        return (cur_state, cur_html, cmp_html, d, btnu, *updated_vals)

    def _wipe_echo_all(state_cur_in, state_prev_in, *current_vals):
        """Remove imported echo payloads and revert auto-filled manual fields (only if unchanged)."""
        stc = state_cur_in or {"parsed": {}, "meta": {}, "has_file": False}
        _stp = state_prev_in or {"parsed": {}, "meta": {}, "has_file": False}  # noqa: F841

        applied_vals = (stc.get("_ui_autofill_values") or {}) if isinstance(stc, dict) else {}
        cur_map = {k: v for k, v in zip(apply_keys, current_vals, strict=False)}

        out_updates: List[Any] = []
        for k in apply_keys:
            cur = cur_map.get(k)
            if k in applied_vals and cur == applied_vals.get(k):
                out_updates.append(_default_value(cur))
            else:
                out_updates.append(cur)

        # Reset import states
        new_cur = {"parsed": {}, "meta": {}, "has_file": False}
        new_prev = {"parsed": {}, "meta": {}, "has_file": False}

        cur_html = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
        prev_html = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
        cmp_html = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
        d = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"
        btnu = gr.update(interactive=False)

        import json
        prev_json = json.dumps({}, ensure_ascii=False)
        prev_meta_json = json.dumps({}, ensure_ascii=False)

        return (new_cur, new_prev, cur_html, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json, *out_updates)

    def _parse_prev(file_obj, cur_state):
        import json
        prev_state = _parse_file_to_state(file_obj)
        cur_state = cur_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)
        prev_json = json.dumps(prev_state.get("parsed") or {}, ensure_ascii=False)
        prev_meta_json = json.dumps(prev_state.get("meta") or {}, ensure_ascii=False)
        return prev_state, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json

    def _parse_ocr_cur(text, cur_state_in, prev_state, *current_vals):
        """Parse Browser OCR text for current echo and auto-fill.

        IMPORTANT: Never raise on missing text (otherwise Gradio shows error toasts).
        We keep the previous state unchanged if the payload is empty.
        """
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}

        prev_autofill_vals: Dict[str, Any] = dict((cur_state_in.get("_ui_autofill_values") or {}) if isinstance(cur_state_in, dict) else {})
        prev_autofill_keys: List[str] = list((cur_state_in.get("_ui_autofill_keys") or list(prev_autofill_vals.keys())) if isinstance(cur_state_in, dict) else [])

        if not text or not str(text).strip():
            cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state_in)
            return ("", cur_state_in, cur_html, cmp_html, d, btnu, *list(current_vals))

        try:
            parsed, meta = extract_echo_from_text(str(text), source="browser_ocr")
            cur_state = {"parsed": parsed or {}, "meta": meta or {}, "has_file": True}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            log_exception("RHK_ECHO_OCR_CUR_PARSE", "Browser OCR text parsing for current echo failed.", e)
            cur_state = {
                "parsed": {},
                "meta": {"ok": False, "hint": f"Browser OCR Import fehlgeschlagen: {e}"},
                "has_file": True,
            }

        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)

        parsed = cur_state.get("parsed") or {}
        updated_vals: List[Any] = list(current_vals)

        if parsed:
            ui_map = {k: v for k, v in zip(apply_keys, current_vals, strict=False)}
            updates = _build_updates_from_parsed(parsed)
            try:
                out_vals, applied = _merge_with_policy(
                    ui_map=ui_map,
                    updates=updates,
                    prev_applied_keys=prev_autofill_keys,
                    prev_applied_values=prev_autofill_vals,
                    enable_stale_wipe=True,
                )
                updated_vals = list(out_vals)
                cur_state["_ui_autofill_values"] = dict(applied or {})
                cur_state["_ui_autofill_keys"] = sorted(list((applied or {}).keys()))
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                log_exception("RHK_ECHO_OCR_CUR_MERGE", "Merge policy for OCR current echo auto-fill failed.", exc)
                updated_vals = list(current_vals)
                if prev_autofill_vals:
                    cur_state["_ui_autofill_values"] = prev_autofill_vals
                    cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))
        else:
            if prev_autofill_vals:
                cur_state["_ui_autofill_values"] = prev_autofill_vals
                cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))

        # clear the OCR textbox after processing to allow repeated triggers
        return ("", cur_state, cur_html, cmp_html, d, btnu, *updated_vals)

    def _parse_ocr_prev(text, prev_state_in, cur_state):
        """Parse Browser OCR text for previous echo (no auto-fill)."""
        import json
        prev_state_in = prev_state_in or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state = cur_state or {"parsed": {}, "meta": {}, "has_file": False}

        if not text or not str(text).strip():
            cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state_in, cur_state)
            prev_json = json.dumps(prev_state_in.get("parsed") or {}, ensure_ascii=False)
            prev_meta_json = json.dumps(prev_state_in.get("meta") or {}, ensure_ascii=False)
            return "", prev_state_in, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json

        try:
            parsed, meta = extract_echo_from_text(str(text), source="browser_ocr")
            prev_state = {"parsed": parsed or {}, "meta": meta or {}, "has_file": True}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            log_exception("RHK_ECHO_OCR_PREV_PARSE", "Browser OCR text parsing for previous echo failed.", e)
            prev_state = {
                "parsed": {},
                "meta": {"ok": False, "hint": f"Browser OCR Import fehlgeschlagen: {e}"},
                "has_file": True,
            }

        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)
        prev_json = json.dumps(prev_state.get("parsed") or {}, ensure_ascii=False)
        prev_meta_json = json.dumps(prev_state.get("meta") or {}, ensure_ascii=False)
        return "", prev_state, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json

    def _parse_pdftext_cur(text, cur_state_in, prev_state, *current_vals):
        """Parse Browser PDF text for current echo and auto-fill (no upload)."""
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}

        prev_autofill_vals: Dict[str, Any] = dict((cur_state_in.get("_ui_autofill_values") or {}) if isinstance(cur_state_in, dict) else {})
        prev_autofill_keys: List[str] = list((cur_state_in.get("_ui_autofill_keys") or list(prev_autofill_vals.keys())) if isinstance(cur_state_in, dict) else [])

        if not text or not str(text).strip():
            cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state_in)
            return ("", cur_state_in, cur_html, cmp_html, d, btnu, *list(current_vals))

        try:
            parsed, meta = extract_echo_from_text(str(text), source="browser_pdf")
            cur_state = {"parsed": parsed or {}, "meta": meta or {}, "has_file": True}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            log_exception("RHK_ECHO_PDF_CUR_PARSE", "Browser PDF text parsing for current echo failed.", e)
            cur_state = {
                "parsed": {},
                "meta": {"ok": False, "hint": f"Browser PDF Import fehlgeschlagen: {e}"},
                "has_file": True,
            }

        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)

        parsed = cur_state.get("parsed") or {}
        updated_vals: List[Any] = list(current_vals)

        if parsed:
            ui_map = {k: v for k, v in zip(apply_keys, current_vals, strict=False)}
            updates = _build_updates_from_parsed(parsed)
            try:
                out_vals, applied = _merge_with_policy(
                    ui_map=ui_map,
                    updates=updates,
                    prev_applied_keys=prev_autofill_keys,
                    prev_applied_values=prev_autofill_vals,
                    enable_stale_wipe=True,
                )
                updated_vals = list(out_vals)
                cur_state["_ui_autofill_values"] = dict(applied or {})
                cur_state["_ui_autofill_keys"] = sorted(list((applied or {}).keys()))
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                log_exception("RHK_ECHO_PDF_CUR_MERGE", "Merge policy for PDF current echo auto-fill failed.", exc)
                updated_vals = list(current_vals)
                if prev_autofill_vals:
                    cur_state["_ui_autofill_values"] = prev_autofill_vals
                    cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))
        else:
            if prev_autofill_vals:
                cur_state["_ui_autofill_values"] = prev_autofill_vals
                cur_state["_ui_autofill_keys"] = sorted(list(prev_autofill_vals.keys()))

        return ("", cur_state, cur_html, cmp_html, d, btnu, *updated_vals)

    def _parse_pdftext_prev(text, prev_state_in, cur_state):
        """Parse Browser PDF text for previous echo (no auto-fill)."""
        import json
        prev_state_in = prev_state_in or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state = cur_state or {"parsed": {}, "meta": {}, "has_file": False}

        if not text or not str(text).strip():
            cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state_in, cur_state)
            prev_json = json.dumps(prev_state_in.get("parsed") or {}, ensure_ascii=False)
            prev_meta_json = json.dumps(prev_state_in.get("meta") or {}, ensure_ascii=False)
            return "", prev_state_in, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json

        try:
            parsed, meta = extract_echo_from_text(str(text), source="browser_pdf")
            prev_state = {"parsed": parsed or {}, "meta": meta or {}, "has_file": True}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            log_exception("RHK_ECHO_PDF_PREV_PARSE", "Browser PDF text parsing for previous echo failed.", e)
            prev_state = {
                "parsed": {},
                "meta": {"ok": False, "hint": f"Browser PDF Import fehlgeschlagen: {e}"},
                "has_file": True,
            }

        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)
        prev_json = json.dumps(prev_state.get("parsed") or {}, ensure_ascii=False)
        prev_meta_json = json.dumps(prev_state.get("meta") or {}, ensure_ascii=False)
        return "", prev_state, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json


    def _apply_btn(state_cur_in, state_prev_in, *current_vals):
        """Explicit apply-button: fill only empty fields from parsed imports.

        - Uses **current** import if available, otherwise falls back to **previous** import.
        - No stale-wipe here (this is not a new import event).
        - Updates provenance so that "Echo Werte entfernen" can still undo imported values.
        """
        stc = state_cur_in or {}
        stp = state_prev_in or {}
        parsed_cur = (stc.get("parsed") or {}) if isinstance(stc, dict) else {}
        parsed_prev = (stp.get("parsed") or {}) if isinstance(stp, dict) else {}
        parsed = parsed_cur if parsed_cur else parsed_prev

        ui_map = {k: v for k, v in zip(apply_keys, current_vals, strict=False)}
        updates = _build_updates_from_parsed(parsed)
        if not updates:
            return (state_cur_in, *list(current_vals))

        prev_autofill_vals: Dict[str, Any] = dict((stc.get("_ui_autofill_values") or {}) if isinstance(stc, dict) else {})
        prev_autofill_keys: List[str] = list((stc.get("_ui_autofill_keys") or list(prev_autofill_vals.keys())) if isinstance(stc, dict) else [])

        try:
            out_vals, applied = _merge_with_policy(
                ui_map=ui_map,
                updates=updates,
                prev_applied_keys=prev_autofill_keys,
                prev_applied_values=prev_autofill_vals,
                enable_stale_wipe=False,
            )

            # Keep previous provenance for keys not touched in this call.
            merged_imported = dict(prev_autofill_vals)
            merged_imported.update(dict(applied or {}))

            stc_new: Dict[str, Any] = dict(stc) if isinstance(stc, dict) else {}
            stc_new["_ui_autofill_values"] = merged_imported
            stc_new["_ui_autofill_keys"] = sorted(list(merged_imported.keys()))

            return (stc_new, *list(out_vals))
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            log_exception("RHK_ECHO_APPLY_BTN", "Apply button merge policy failed.", exc)
            return (state_cur_in, *list(current_vals))

    # Bind upload/change for both (independent)
    out_cur = [state_cur, preview_cur, compare_html, details_html, btn_apply] + apply_components
    in_cur = [import_pdf_cur, state_cur, state_prev] + apply_components

    try:
        import_pdf_cur.change(_parse_cur, inputs=in_cur, outputs=out_cur, queue=False)
    except (AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_ECHO_BIND_CUR_CHANGE", "Binding change event for current PDF upload failed.", exc)
    try:
        import_pdf_prev.change(
            _parse_prev,
            inputs=[import_pdf_prev, state_cur],
            outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
            queue=False,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_ECHO_BIND_PREV_CHANGE", "Binding change event for previous PDF upload failed.", exc)

    # Some Gradio versions prefer `.upload()`
    try:
        import_pdf_cur.upload(_parse_cur, inputs=in_cur, outputs=out_cur, queue=False)
    except (AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_ECHO_BIND_CUR_UPLOAD", "Binding upload event for current PDF failed.", exc)
    try:
        import_pdf_prev.upload(
            _parse_prev,
            inputs=[import_pdf_prev, state_cur],
            outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
            queue=False,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        log_exception("RHK_ECHO_BIND_PREV_UPLOAD", "Binding upload event for previous PDF failed.", exc)


    # Legacy upload inputs (optional). Bind to same parsers for compatibility.
    if legacy_pdf_cur is not None:
        try:
            legacy_pdf_cur.change(_parse_cur, inputs=[legacy_pdf_cur, state_cur, state_prev] + apply_components, outputs=out_cur, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_LEGACY_CUR_CHANGE", "Binding change event for legacy current PDF failed.", exc)
        try:
            legacy_pdf_cur.upload(_parse_cur, inputs=[legacy_pdf_cur, state_cur, state_prev] + apply_components, outputs=out_cur, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_LEGACY_CUR_UPLOAD", "Binding upload event for legacy current PDF failed.", exc)

    if legacy_pdf_prev is not None:
        try:
            legacy_pdf_prev.change(
                _parse_prev,
                inputs=[legacy_pdf_prev, state_cur],
                outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
                queue=False,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_LEGACY_PREV_CHANGE", "Binding change event for legacy previous PDF failed.", exc)
        try:
            legacy_pdf_prev.upload(
                _parse_prev,
                inputs=[legacy_pdf_prev, state_cur],
                outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
                queue=False,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_LEGACY_PREV_UPLOAD", "Binding upload event for legacy previous PDF failed.", exc)

    # Browser OCR inputs (textboxes filled by JS). Works on Render/online.
    if echo_ocr_text_cur is not None:
        out_ocr_cur = [echo_ocr_text_cur, state_cur, preview_cur, compare_html, details_html, btn_apply] + apply_components
        in_ocr_cur = [echo_ocr_text_cur, state_cur, state_prev] + apply_components
        try:
            echo_ocr_text_cur.change(_parse_ocr_cur, inputs=in_ocr_cur, outputs=out_ocr_cur, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_OCR_CUR", "Binding change event for OCR current text failed.", exc)

    if echo_ocr_text_prev is not None:
        out_ocr_prev = [echo_ocr_text_prev, state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp]
        in_ocr_prev = [echo_ocr_text_prev, state_prev, state_cur]
        try:
            echo_ocr_text_prev.change(_parse_ocr_prev, inputs=in_ocr_prev, outputs=out_ocr_prev, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_OCR_PREV", "Binding change event for OCR previous text failed.", exc)

    # Browser PDF inputs (textboxes filled by JS). Works on Render/online.
    if echo_pdf_text_cur is not None:
        out_pdf_cur = [echo_pdf_text_cur, state_cur, preview_cur, compare_html, details_html, btn_apply] + apply_components
        in_pdf_cur = [echo_pdf_text_cur, state_cur, state_prev] + apply_components
        try:
            echo_pdf_text_cur.change(_parse_pdftext_cur, inputs=in_pdf_cur, outputs=out_pdf_cur, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_PDF_CUR", "Binding change event for browser PDF current text failed.", exc)

    if echo_pdf_text_prev is not None:
        out_pdf_prev = [echo_pdf_text_prev, state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp]
        in_pdf_prev = [echo_pdf_text_prev, state_prev, state_cur]
        try:
            echo_pdf_text_prev.change(_parse_pdftext_prev, inputs=in_pdf_prev, outputs=out_pdf_prev, queue=False)
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_PDF_PREV", "Binding change event for browser PDF previous text failed.", exc)

    # Remove imported echo payloads + revert auto-filled values
    if btn_wipe_echo_fields is not None:
        try:
            btn_wipe_echo_fields.click(
                _wipe_echo_all,
                inputs=[state_cur, state_prev] + apply_components,
                outputs=[state_cur, state_prev, preview_cur, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp] + apply_components,
                queue=False,
            )
        except (AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_ECHO_BIND_WIPE", "Binding click event for wipe echo fields button failed.", exc)

    # Wire apply button: explicit action (fills only empty fields)
    btn_apply.click(
        _apply_btn,
        inputs=[state_cur, state_prev] + apply_components,
        outputs=[state_cur] + apply_components,
        queue=False,
    )

    # Clear buttons: clear only that side (independent) + update compare
    def _clear_cur(prev_state, cur_state_in):
        """Clear current import payload (does not touch manual fields)."""
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}

        # Preserve provenance for undo (manual fields may still contain imported values)
        cur_state_new: Dict[str, Any] = {"parsed": {}, "meta": {}, "has_file": False}
        if isinstance(cur_state_in, dict):
            prev_vals = cur_state_in.get("_ui_autofill_values") or {}
            prev_keys = cur_state_in.get("_ui_autofill_keys") or list(prev_vals.keys())
            if prev_vals:
                cur_state_new["_ui_autofill_values"] = dict(prev_vals)
                cur_state_new["_ui_autofill_keys"] = list(prev_keys)

        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state_new)
        return None, cur_state_new, cur_html, cmp_html, d, btnu

    def _clear_prev(cur_state_in):
        prev_state_new = {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state_new, cur_state_in)
        return None, prev_state_new, prev_html, cmp_html, d, btnu, "", ""
    btn_clear_cur.click(
        _clear_cur,
        inputs=[state_prev, state_cur],
        outputs=[import_pdf_cur, state_cur, preview_cur, compare_html, details_html, btn_apply],
        queue=False,
    )

    btn_clear_prev.click(
        _clear_prev,
        inputs=[state_cur],
        outputs=[import_pdf_prev, state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
        queue=False,
    )

    return echo_ui
