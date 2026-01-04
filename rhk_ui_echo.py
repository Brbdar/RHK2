#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo UI helpers.

Kapselt:
- Echo-Inputfelder (Basic + Extended in Accordions)
- PDF-Import UI (Textlayer only) inkl. Preview, Vor-Echo und Direktvergleich
- "nur leere Felder füllen"

Optional OCR: Screenshots (PNG/JPG/WebP) werden über Tesseract OCR gelesen (wenn verfügbar).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rhk_base import gr  # type: ignore

from rhk_echo_pdf_import import extract_echo_from_file, extract_echo_from_pdf


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
_TABLE_WRAP_STYLE = "max-height:560px;min-height:320px;overflow:auto;resize:vertical;border:1px solid rgba(0,0,0,.08);border-radius:10px;"
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
    except Exception:
        return "—"


# Ampel Styling (schnelle visuelle Stratifizierung)
_SEV_BG = {
    'g': 'background:rgba(34,197,94,.14);',
    'y': 'background:rgba(234,179,8,.16);',
    'r': 'background:rgba(239,68,68,.14);',
    '':  ''
}
_SEV_BORDER = {
    'g': 'border-left:6px solid rgba(34,197,94,.45);',
    'y': 'border-left:6px solid rgba(234,179,8,.55);',
    'r': 'border-left:6px solid rgba(239,68,68,.45);',
    '':  'border-left:6px solid rgba(0,0,0,.04);',
}
_SEV_RANK = {'': 0, 'g': 1, 'y': 2, 'r': 3}


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
        except Exception:
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
        except Exception:
            return None
    return None


def _sev_css(sev: str) -> str:
    return _SEV_BG.get(sev or '', '')


def _severity(key: str, v: Any) -> str:
    """Return g, y, r or empty.

    Ampel = schnelle visuelle Orientierung (kein Ersatz fuer klinische Bewertung).
    Mapping:
      - g: normal
      - y: mild / grenzwertig
      - r: moderat / schwer oder klares Hochrisiko-Zeichen
    Rechtsherz-Grenzen orientieren sich primaer an ASE Right Heart 2025 (Table 1).
    PH-Risikomarker (z.B. TAPSE/sPAP) nach ESC/ERS 2022.
    Linksherz (E/e', LAVI) nach ASE LV Diastolic Update (aktueller Konsens).
    """
    if v is None:
        return ''

    # Ja/Nein Felder: klarer Marker
    if key in ('pericardial_effusion', 'rvot_notch'):
        s = str(v).strip().lower()
        if s in ('ja', 'true', '1'):
            return 'r'
        if s in ('nein', 'false', '0'):
            return 'g'
        return ''

    if key == 'ivc_collapse':
        s = str(v).strip().lower()
        if s == 'ja':
            return 'g'
        if s == 'nein':
            return 'r'
        return ''

    x = _as_float(v)
    if x is None:
        return ''

    # ---------------- Linksherz ----------------
    if key == 'lvef':
        return 'g' if x >= 55 else ('y' if x >= 45 else 'r')

    # ASE diastolic: E/e' <=14 und LAVI <=34 als Normalbereich (vereinfachte Ampel)
    if key == 'ee_ratio':
        return 'g' if x <= 14 else ('y' if x <= 19 else 'r')
    if key == 'lavi_ml_m2':
        return 'g' if x <= 34 else ('y' if x <= 48 else 'r')

    # ---------------- Haemodynamik / PH Zeichen (ASE 2025 Table 1) ----------------
    # TRV maximum (m/s): <2.8 normal; 2.8-3.1 mild; >=3.2 moderat/schwer
    if key == 'trv_ms':
        return 'g' if x < 2.8 else ('y' if x <= 3.1 else 'r')

    # RVSP/sPAP (mmHg): <=34 normal; 35-49 mild; >=50 moderat/schwer
    if key == 'pasp_echo':
        return 'g' if x <= 34 else ('y' if x <= 49 else 'r')

    # RVOT AccT / PAAT (ms): >105 normal; 80-105 mild; <80 moderat/schwer
    if key == 'paat_ms':
        return 'g' if x > 105 else ('y' if x >= 80 else 'r')

    # PAAT/RVET: kein offizieller ASE-Grad in Table 1, aber als PH-Surrogat hilfreich (grob)
    if key == 'paat_rvet_ratio':
        return 'g' if x >= 0.34 else ('y' if x >= 0.28 else 'r')

    # ---------------- RV Funktion (ASE 2025 Table 1) ----------------
    # TAPSE (cm): >1.7 normal; 1.7-1.3 mild; <1.3 moderat/schwer  -> in UI mm
    if key == 'tapse_mm':
        return 'g' if x >= 17 else ('y' if x >= 13 else 'r')

    # Tissue Doppler S' (cm/s): >9.5 normal; 9.5-7.2 mild; <7.2 moderat/schwer
    if key == 's_prime_cm_s':
        return 'g' if x > 9.5 else ('y' if x >= 7.2 else 'r')

    # FAC (%): >35 normal; 35-29 mild; <29 moderat/schwer
    if key == 'rvfac_pct':
        return 'g' if x > 35 else ('y' if x >= 29 else 'r')

    # 3D RVEF (%): >45 normal; 45-39 mild; <39 moderat/schwer
    if key == 'rv_3d_ef_pct':
        return 'g' if x > 45 else ('y' if x >= 39 else 'r')

    # Strain: Werte sind typischerweise negativ; Table 1 gibt Absolutwerte an
    # Free wall strain (3 Seg.): >20 normal; 20-15 mild; <15 moderat/schwer
    if key == 'rv_fwls_pct':
        ax = abs(x)
        return 'g' if ax > 20 else ('y' if ax >= 15 else 'r')

    # Global strain (6 Seg.): >17 normal; 17-13 mild; <13 moderat/schwer
    if key == 'rv_gls_pct':
        ax = abs(x)
        return 'g' if ax > 17 else ('y' if ax >= 13 else 'r')

    # ---------------- RV/RA Groesse (ASE 2025 Table 1) ----------------
    # RV diameter basal (cm): <4.1 normal; 4.1-4.4 mild; >4.4 moderat/schwer -> UI mm
    if key == 'rv_edd_mm':
        cm = x / 10.0
        return 'g' if cm < 4.1 else ('y' if cm <= 4.4 else 'r')

    # RV wall thickness (cm): <0.5 normal; 0.5-0.7 mild; >0.7 moderat/schwer -> UI mm
    if key == 'rv_wall_thickness_mm':
        cm = x / 10.0
        return 'g' if cm < 0.5 else ('y' if cm <= 0.7 else 'r')

    # RV end-diastolic area (cm2): <25 normal; 25-28 mild; >28 moderat/schwer
    if key == 'rv_eda_cm2':
        return 'g' if x < 25 else ('y' if x <= 28 else 'r')

    # RV end-systolic area (cm2): <14 normal; 14-16 mild; >16 moderat/schwer
    if key == 'rv_esa_cm2':
        return 'g' if x < 14 else ('y' if x <= 16 else 'r')

    # 3D Volumina / Indizes (ASE 2025 Table 1)
    if key == 'rv_3d_edv_ml':
        return 'g' if x < 130 else ('y' if x <= 150 else 'r')
    if key == 'rv_3d_esv_ml':
        return 'g' if x < 66 else ('y' if x <= 77 else 'r')
    if key == 'rv_3d_edvi_ml_m2':
        return 'g' if x < 90 else ('y' if x <= 103 else 'r')
    if key == 'rv_3d_esvi_ml_m2':
        return 'g' if x < 41 else ('y' if x <= 48 else 'r')

    # ---------------- PH Risk (ESC/ERS 2022) ----------------
    if key == 'tapse_spap_ratio':
        return 'g' if x >= 0.32 else ('y' if x >= 0.19 else 'r')

    # RA Area (ESC/ERS 2022): <18 low, 18-26 intermediate, >26 high
    if key == 'ra_esa_cm2':
        return 'g' if x < 18 else ('y' if x <= 26 else 'r')

    # ---------------- VCI ----------------
    if key == 'ivc_collapse_index_pct':
        return 'g' if x >= 50 else ('y' if x >= 35 else 'r')
    if key == 'ivc_diam_mm':
        return 'g' if x <= 21 else ('y' if x <= 23 else 'r')

    return ''


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
        except Exception:
            pass
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
    except Exception as e:
        return {"parsed": {}, "meta": {"ok": False, "hint": f"Import fehlgeschlagen: {e}"}, "has_file": True}


def _render_import_table(state: Dict[str, Any], title: str) -> str:
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


def _render_compare_table(state_prev: Dict[str, Any], state_cur: Dict[str, Any]) -> str:
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
        except Exception:
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
        except Exception:
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
    for k, label, pv, cv, dv, unit, sev_p, sev_c, sev_d in rows:
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
        f"<div style='color:rgba(0,0,0,.55);font-size:12px;margin:0 0 8px 0'>Ampel-Klassifikation: Rechtsherz nach ASE 2025 (Table 1, 3-Stufen: normal/mild/moderat-schwer), TAPSE/sPAP und RA-Area als PH-Risikomarker nach ESC/ERS 2022. Linksherz (E/e', LAVI) nach aktuellem ASE-Diastole-Konsens. Hinweis: reine Orientierung, Kontext und Bildqualität beachten.</div>"
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


def build_echo_section(add) -> Dict[str, Any]:
    """Build Echo section UI."""
    gr.Markdown("### Echokardiographie")

    # --- Import block ---------------------------------------------------------
    with gr.Accordion("Echo Import (PDF oder Screenshot)", open=True):
        gr.Markdown(
            "Datei hochladen. Unterstützt werden Textlayer PDFs sowie Screenshots als Bilddatei (PNG, JPG, WEBP, BMP, TIF). Wenn kein Textlayer vorhanden ist oder ein Screenshot genutzt wird, erfolgt die Extraktion per OCR, sofern Tesseract verfügbar ist.\n\nHinweis: Für Screenshot OCR muss Tesseract installiert sein. Falls Tesseract nicht im PATH ist, setze TESSERACT_CMD auf den Pfad zur tesseract.exe.",
        )

        with gr.Row():
            import_pdf_cur = gr.File(
                label="Echo Datei (aktuell)",
                file_types=[".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"],
                type="filepath",
                file_count="single",
            )
            import_pdf_prev = gr.File(
                label="Vor Echo Datei (optional)",
                file_types=[".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"],
                type="filepath",
                file_count="single",
            )

        with gr.Row():
            btn_apply = gr.Button("Werte übernehmen (nur leere Felder)", variant="primary")
            btn_clear_cur = gr.Button("Import löschen", variant="secondary")
            btn_clear_prev = gr.Button("Vor-Echo löschen", variant="secondary")

        # state
        state_echo_cur = gr.State(value={"parsed": {}, "meta": {}, "has_file": False})
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
        "import_preview_cur_html": import_preview_cur_html,
        "import_preview_prev_html": import_preview_prev_html,
        "compare_html": compare_html,
        "details_html": details_html,
        "state_echo_cur": state_echo_cur,
        "state_echo_prev": state_echo_prev,
        "btn_apply": btn_apply,
        "btn_clear_cur": btn_clear_cur,
        "btn_clear_prev": btn_clear_prev,
    }


def bind_echo_import(echo_ui: Dict[str, Any], *,
                    field_components: Dict[str, Any]) -> Dict[str, Any]:
    """Bind callbacks for echo PDF imports (current + previous).

    - Aktuelles Echo: nach Import werden Werte automatisch in die manuellen Felder uebernommen
      (nur wenn dort noch leer/0/keine Angabe steht).
    - Vor-Echo: bleibt unabhaengig; dient v.a. dem Vergleich.
    """

    import_pdf_cur = echo_ui["import_pdf_cur"]
    import_pdf_prev = echo_ui["import_pdf_prev"]
    preview_cur = echo_ui["import_preview_cur_html"]
    preview_prev = echo_ui["import_preview_prev_html"]
    compare_html = echo_ui["compare_html"]
    details_html = echo_ui["details_html"]
    state_cur = echo_ui["state_echo_cur"]
    state_prev = echo_ui["state_echo_prev"]
    btn_apply = echo_ui["btn_apply"]
    btn_clear_cur = echo_ui["btn_clear_cur"]
    btn_clear_prev = echo_ui["btn_clear_prev"]

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

    def _is_empty(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            s = v.strip().lower()
            return (not s) or (s in ("keine angabe", "n/a", "na", "-"))
        if isinstance(v, (int, float)):
            try:
                x = float(v)
                if x != x:  # NaN
                    return True
                return x == 0.0
            except Exception:
                return False
        return False

    def _apply_values(state_cur_in, state_prev_in, *current_vals):
        """Fill only empty fields from available parsed values.

        Priority: current import, then prev import (if current missing).
        """
        stc = state_cur_in or {}
        stp = state_prev_in or {}
        parsed_cur = stc.get("parsed") or {}
        parsed_prev = stp.get("parsed") or {}

        parsed = parsed_cur if parsed_cur else parsed_prev

        cur_map = {k: v for k, v in zip(apply_keys, current_vals)}

        out_updates: List[Any] = []
        for k in apply_keys:
            cur = cur_map.get(k)
            val = parsed.get(k)

            # Radios erwarten Strings (keine Angabe, ja, nein)
            if k in ('ivc_collapse', 'pericardial_effusion', 'rvot_notch', 'ivc_respiratory') and (val is not None):
                val = _normalize_radio_value(k, val)

            # handle radios: only set when empty or "keine Angabe"
            if isinstance(cur, str) and (cur.strip().lower() == "keine angabe") and (val is not None):
                out_updates.append(val)
                continue

            # handle checkboxes: only set True from parsed evidence
            if isinstance(cur, bool):
                if (cur is False) and (val is True):
                    out_updates.append(True)
                else:
                    out_updates.append(cur)
                continue

            if _is_empty(cur) and (val is not None):
                out_updates.append(val)
            else:
                out_updates.append(cur)

        # Ensure echo_done true when we actually parsed something
        if "echo_done" in apply_keys:
            try:
                i = apply_keys.index("echo_done")
                if (cur_map.get("echo_done") is False) and any(
                    k for k in parsed.keys() if k not in ("height_cm", "weight_kg", "bsa_m2")
                ):
                    out_updates[i] = True
            except Exception:
                pass

        return out_updates

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

    def _parse_cur(file_obj, prev_state, *current_vals):
        """Parse current echo and auto-apply into manual fields."""
        cur_state = _parse_file_to_state(file_obj)
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)

        # Auto-apply only if we got parsed values from current import
        updated_vals = list(current_vals)
        try:
            if (cur_state.get("parsed") or {}):
                updated_vals = _apply_values(cur_state, prev_state, *current_vals)
        except Exception:
            updated_vals = list(current_vals)

        return (cur_state, cur_html, cmp_html, d, btnu, *updated_vals)

    def _parse_prev(file_obj, cur_state):
        import json
        prev_state = _parse_file_to_state(file_obj)
        cur_state = cur_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state)
        prev_json = json.dumps(prev_state.get("parsed") or {}, ensure_ascii=False)
        prev_meta_json = json.dumps(prev_state.get("meta") or {}, ensure_ascii=False)
        return prev_state, prev_html, cmp_html, d, btnu, prev_json, prev_meta_json

    # Bind upload/change for both (independent)
    out_cur = [state_cur, preview_cur, compare_html, details_html, btn_apply] + apply_components
    in_cur = [import_pdf_cur, state_prev] + apply_components

    try:
        import_pdf_cur.change(_parse_cur, inputs=in_cur, outputs=out_cur, queue=False)
    except Exception:
        pass
    try:
        import_pdf_prev.change(
            _parse_prev,
            inputs=[import_pdf_prev, state_cur],
            outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
            queue=False,
        )
    except Exception:
        pass

    # Some Gradio versions prefer `.upload()`
    try:
        import_pdf_cur.upload(_parse_cur, inputs=in_cur, outputs=out_cur, queue=False)
    except Exception:
        pass
    try:
        import_pdf_prev.upload(
            _parse_prev,
            inputs=[import_pdf_prev, state_cur],
            outputs=[state_prev, preview_prev, compare_html, details_html, btn_apply, prev_json_comp, prev_meta_comp],
            queue=False,
        )
    except Exception:
        pass

    # Wire apply button: outputs are all echo fields that are present
    btn_apply.click(
        _apply_values,
        inputs=[state_cur, state_prev] + apply_components,
        outputs=apply_components,
        queue=False,
    )

    # Clear buttons: clear only that side (independent) + update compare
    def _clear_cur(prev_state):
        cur_state_new = {"parsed": {}, "meta": {}, "has_file": False}
        prev_state = prev_state or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state, cur_state_new)
        return None, cur_state_new, cur_html, cmp_html, d, btnu

    def _clear_prev(cur_state_in):
        prev_state_new = {"parsed": {}, "meta": {}, "has_file": False}
        cur_state_in = cur_state_in or {"parsed": {}, "meta": {}, "has_file": False}
        cur_html, prev_html, cmp_html, d, btnu = _update_all(prev_state_new, cur_state_in)
        return None, prev_state_new, prev_html, cmp_html, d, btnu, "", ""
    btn_clear_cur.click(
        _clear_cur,
        inputs=[state_prev],
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
