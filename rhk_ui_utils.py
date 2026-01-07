#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI helper functions for RHK Befundassistent.

Split out of rhk_ui.py to keep the main UI module focused on building the Gradio layout
and wiring callbacks.
"""

from __future__ import annotations

import html as _html

from rhk_base import *  # noqa: F401,F403
from rhk_viz import svg_mpap_pawp_vs_co, svg_series_over_phases, svg_delta_bars, svg_compare_bars  # noqa: F401

# NOTE: Everything below is copied from the original monolithic rhk_ui.py.
def _gradio_major_version() -> int:
    """Best-effort: parse gradio.__version__ major number.

    Gradio 6 moved app-level params (theme/css/js/head) from Blocks() to launch().
    We support both so the project runs with gradio>=5,<7.
    """
    try:
        v = getattr(gr, "__version__", "0")
        return int(str(v).split(".")[0])
    except Exception:
        return 0


def _fmt_or_dash(v: Any, nd: int = 0) -> str:
    try:
        if v is None or v == "":
            return "–"
        fv = float(v)
        if nd <= 0:
            return f"{fv:.0f}"
        return f"{fv:.{nd}f}"
    except Exception:
        return "–"


def load_rulebook_meta(path: str) -> Dict[str, Any]:
    """Read meta info (version/updated) from YAML rulebook without changing rule loading."""
    try:
        if not path or not os.path.exists(path):
            return {}
        if yaml is None:
            return {}
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        meta = doc.get("meta") if isinstance(doc, dict) else {}
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def html_escape(s: Any) -> str:
    """HTML-escape helper (quote-safe)."""
    try:
        return _html.escape(str(s), quote=True)
    except Exception:
        return ""


def compute_egfr(creatinine_mg_dl: Any, age_years: Any, sex: Any) -> Optional[float]:
    """Compute eGFR (CKD-EPI 2021, race-free) in ml/min/1.73m².

    creatinine_mg_dl: serum creatinine in mg/dl
    age_years: age in years
    sex: UI value ("m"/"w" or "male/female" style strings)
    """

    try:
        scr = float(creatinine_mg_dl)
        age = float(age_years)
    except Exception:
        return None

    if scr <= 0 or age <= 0:
        return None

    s = str(sex or "").strip().lower()
    is_female = s in {"w", "weiblich", "female", "f"}

    # CKD-EPI 2021 constants
    k = 0.7 if is_female else 0.9
    a = -0.241 if is_female else -0.302
    sex_factor = 1.012 if is_female else 1.0

    x = scr / k
    mn = min(x, 1.0)
    mx = max(x, 1.0)

    egfr = 142.0 * (mn ** a) * (mx ** -1.200) * (0.9938 ** age) * sex_factor
    if egfr != egfr or egfr <= 0:  # NaN/invalid
        return None
    return float(egfr)



def build_sticky_summary_html(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]] = None) -> str:
    """Concise, always-visible live preview of key values."""
    if not case:
        status = ""
        if flags:
            # Minimal status even without case
            dirty = bool(flags.get("dirty"))
            saved_at = flags.get("saved_at")
            has_report = bool(flags.get("has_report"))
            stale = bool(flags.get("report_stale"))
            if has_report:
                status += "<span class='rhk-schip rhk-schip--warn'>Befund veraltet</span>" if stale else "<span class='rhk-schip rhk-schip--good'>Befund aktuell</span>"
            if dirty:
                status += "<span class='rhk-schip rhk-schip--warn'>Änderungen nicht gespeichert</span>"
            elif saved_at:
                status += "<span class='rhk-schip rhk-schip--good'>Gespeichert</span>"
        return (
            "<div class='rhk-summarybar'>"
            "<span class='rhk-schip rhk-schip--info'>Hämodynamik: –</span>"
            "<span class='rhk-schip'>RAP: –</span>"
            "<span class='rhk-schip'>mPAP: –</span>"
            "<span class='rhk-schip'>PAWP: –</span>"
            "<span class='rhk-schip'>PVR: –</span>"
            "<span class='rhk-schip'>CI: –</span>"
            "<span class='rhk-schip rhk-schip--warn'>Risiko: –</span>"
            f"{status}"
            "</div>"
        )

    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    scores = case.get("scores") or {}

    # Warnungen (nicht blockierend)
    warns = case.get("warnings") or []
    wcnt = len(warns) if isinstance(warns, list) else 0
    wtone = "warn"
    if wcnt:
        try:
            sev = {str(w.get("severity")) for w in warns if isinstance(w, dict)}
            wtone = "bad" if "error" in sev else "warn"
        except Exception:
            wtone = "warn"
    wchip = ""
    if wcnt:
        # Tooltip with full warning list
        w_msgs = []
        try:
            for w in warns:
                if isinstance(w, dict) and str(w.get("message") or "").strip():
                    w_msgs.append(str(w.get("message")).strip())
        except Exception:
            w_msgs = []
        tooltip = "\n".join([f"- {m}" for m in w_msgs]) if w_msgs else ""
        tattr = f" title='{html_escape(tooltip)}'" if tooltip else ""
        wchip = f"<span class='rhk-schip rhk-schip--{wtone}'{tattr}>Warnungen: {wcnt}</span>"

    hemo_cat = str(der.get("hemo_category") or "unknown")
    hemo_map = {
        "precap": "präkapillär",
        "ipcph": "iPcPH",
        "cpcph": "cPcPH",
        "no_ph": "keine PH",
        "unknown": "unklar",
    }
    hemo_txt = hemo_map.get(hemo_cat, hemo_cat)

    mpap = der.get("mpap_rest")
    pawp = der.get("pawp_rest")
    rap = der.get("rap_rest")
    pvr = der.get("pvr_rest")
    ci = der.get("ci_rest")
    # Risk badge: prioritize ESC/ERS 4-strata if present, else REVEAL Lite 2
    esc4 = scores.get("esc_ers_4s")
    rl2 = scores.get("reveal_lite2")
    risk_txt = "–"
    risk_tone = "warn"
    if isinstance(esc4, str) and esc4:
        risk_txt = f"ESC/ERS 4-Strata: {esc4}"
        risk_tone = "good" if esc4 == "low" else ("bad" if esc4 == "high" else "warn")
    elif isinstance(rl2, str) and rl2:
        risk_txt = f"REVEAL Lite 2: {rl2}"
        _l = rl2.strip().lower()
        risk_tone = "good" if _l.startswith("nied") else ("bad" if _l.startswith("hoch") else "warn")

    # Optional compare hint
    prev_mpap = ui.get("prev_mpap")
    prev_pvr = ui.get("prev_pvr")
    cmp_hint = ""
    try:
        if prev_mpap not in (None, "") and mpap not in (None, ""):
            d = float(mpap) - float(prev_mpap)
            arrow = "↑" if d > 1 else ("↓" if d < -1 else "±")
            cmp_hint = f"<span class='rhk-schip rhk-schip--info'>ΔmPAP: {arrow} {d:+.0f}</span>"
        elif prev_pvr not in (None, "") and pvr not in (None, ""):
            d = float(pvr) - float(prev_pvr)
            arrow = "↑" if d > 0.5 else ("↓" if d < -0.5 else "±")
            cmp_hint = f"<span class='rhk-schip rhk-schip--info'>ΔPVR: {arrow} {d:+.1f}</span>"
    except Exception:
        cmp_hint = ""

    # Status chips (saved/dirty/stale)
    status_chips = ""
    if flags:
        try:
            has_report = bool(flags.get("has_report"))
            stale = bool(flags.get("report_stale"))
            dirty = bool(flags.get("dirty"))
            saved_at = flags.get("saved_at")

            if has_report:
                status_chips += "<span class='rhk-schip rhk-schip--warn'>Befund veraltet</span>" if stale else "<span class='rhk-schip rhk-schip--good'>Befund aktuell</span>"
            if dirty:
                status_chips += "<span class='rhk-schip rhk-schip--warn'>Änderungen nicht gespeichert</span>"
            elif saved_at:
                status_chips += "<span class='rhk-schip rhk-schip--good'>Gespeichert</span>"
        except Exception:
            status_chips = ""

    return (
        "<div class='rhk-summarybar'>"
        f"<span class='rhk-schip rhk-schip--info'>Hämodynamik: {html_escape(hemo_txt)}</span>"
        f"<span class='rhk-schip'>RAP: {_fmt_or_dash(rap,0)}</span>"
        f"<span class='rhk-schip'>mPAP: {_fmt_or_dash(mpap,0)}</span>"
        f"<span class='rhk-schip'>PAWP: {_fmt_or_dash(pawp,0)}</span>"
        f"<span class='rhk-schip'>PVR: {_fmt_or_dash(pvr,1)}</span>"
        f"<span class='rhk-schip'>CI: {_fmt_or_dash(ci,2)}</span>"
        f"<span class='rhk-schip rhk-schip--{risk_tone}'>Risiko: {html_escape(risk_txt)}</span>"
        f"{wchip}"
        f"{cmp_hint}"
        f"{status_chips}"
        "</div>"
    )


def build_compare_overview_html(case: Optional[Dict[str, Any]]) -> str:
    if not case:
        return ""
    ui = case.get("ui") or {}
    der = case.get("derived") or {}

    rows = [
        ("RAP (mmHg)", ui.get("prev_rap"), der.get("rap_rest"), 0, 1.0),
        ("mPAP (mmHg)", ui.get("prev_mpap"), der.get("mpap_rest"), 0, 1.0),
        ("PAWP (mmHg)", ui.get("prev_pawp"), der.get("pawp_rest"), 0, 1.0),
        ("CI (l/min/m²)", ui.get("prev_ci"), der.get("ci_rest"), 2, 0.15),
        ("PVR (WU)", ui.get("prev_pvr"), der.get("pvr_rest"), 1, 0.5),
    ]

    def _delta_cell(prev, cur, nd, thr):
        try:
            if prev in (None, "") or cur in (None, ""):
                return "<span class='cmp-delta-flat'>–</span>"
            d = float(cur) - float(prev)
            if d > thr:
                cls = "cmp-delta-up"
                arrow = "↑"
            elif d < -thr:
                cls = "cmp-delta-down"
                arrow = "↓"
            else:
                cls = "cmp-delta-flat"
                arrow = "±"
            fmt = f"{{:{'+.'}{nd}f}}" if nd > 0 else "{:+.0f}"
            val = fmt.format(d)
            return f"<span class='{cls}'>{arrow} {val}</span>"
        except Exception:
            return "<span class='cmp-delta-flat'>–</span>"

    any_prev = any((p not in (None, "") for (_n, p, _c, _nd, _thr) in rows))
    if not any_prev:
        return ""

    prev_date = str(ui.get("prev_rhk_date") or "").strip()
    cur_date = str(ui.get("rhk_date") or "").strip()
    note = "Vorher/Nachher basierend auf Vor-RHK Feldern und aktuellen Ruhewerten."
    if prev_date and cur_date:
        note = f"Zeitraum: {html_escape(prev_date)} → {html_escape(cur_date)}. {note}"
    elif prev_date:
        note = f"Referenz: Vor-RHK {html_escape(prev_date)}. {note}"
    elif cur_date:
        note = f"Aktueller RHK: {html_escape(cur_date)}. {note}"

    tr = []
    for name, prev, cur, nd, thr in rows:
        tr.append(
            "<tr>"
            f"<td>{html_escape(name)}</td>"
            f"<td>{_fmt_or_dash(prev,nd)}</td>"
            f"<td>{_fmt_or_dash(cur,nd)}</td>"
            f"<td>{_delta_cell(prev,cur,nd,thr)}</td>"
            "</tr>"
        )

    return (
        "<div class='cmp-wrap'>"
        "<div class='cmp-head'>"
        "<div class='cmp-title'>Vergleich Vorher vs Jetzt</div>"
        f"<div class='cmp-note'>{note}</div>"
        "</div>"
        "<table>"
        "<thead><tr>""<th>Parameter</th>" + (f"<th>Vorher<br><span class='cmp-date'>{html_escape(prev_date)}</span></th>" if prev_date else "<th>Vorher</th>") + (f"<th>Jetzt<br><span class='cmp-date'>{html_escape(cur_date)}</span></th>" if cur_date else "<th>Jetzt</th>") + "<th>Δ</th></tr></thead>"
        f"<tbody>{''.join(tr)}</tbody>"
        "</table>"
        "</div>"
    )




def build_docx_status_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    def _phases(payload: dict | None) -> str:
        if not payload:
            return ""
        ph = payload.get("phases") or {}
        order = ["base1", "base2", "exercise", "post", "no", "o2"]
        seen = [p for p in order if p in ph]
        for k in ph.keys():
            if k not in seen:
                seen.append(k)
        name = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergometrie",
            "post": "Post Intervention",
            "no": "NO",
            "o2": "O2",
        }
        return ", ".join([name.get(k, k) for k in seen]) if seen else ""

    def _date(payload: dict | None) -> str:
        try:
            return (payload or {}).get("patient", {}).get("exam_date") or ""
        except Exception:
            return ""

    def _quality(payload: dict | None) -> tuple[str, str]:
        q = (payload or {}).get("quality") or {}
        return (q.get("status") or "", "; ".join(q.get("reasons") or []))

    cur_ph = _phases(docx_cur)
    prev_ph = _phases(docx_prev)
    cur_date = _date(docx_cur)
    prev_date = _date(docx_prev)

    cur_status, cur_reasons = _quality(docx_cur)
    prev_status, prev_reasons = _quality(docx_prev)

    def chip(label: str, value: str) -> str:
        if not value:
            return ""
        return f"<span class='chip'><span class='chip-lab'>{_html.escape(label)}</span> {_html.escape(value)}</span>"

    def block(title: str, date: str, ph: str, status: str, reasons: str) -> str:
        if not (date or ph or status or reasons):
            return ""
        warn = " warn" if status and status not in ("ok", "green") else ""
        rs = f"<div class='small'>{_html.escape(reasons)}</div>" if reasons else ""
        return (
            f"<div class='docx-box{warn}'>"
            f"<div class='docx-title'>{_html.escape(title)}</div>"
            f"<div class='docx-row'>"
            f"{chip('Datum', date)}{chip('Phasen', ph)}{chip('Qualität', status)}"
            f"</div>"
            f"{rs}"
            f"</div>"
        )

    html = (
        "<div class='docx-status'>"
        + block("Aktueller RHK Import", cur_date, cur_ph, cur_status, cur_reasons)
        + block("Vor-RHK Import", prev_date, prev_ph, prev_status, prev_reasons)
        + "</div>"
    )

    # Tabellenübersicht: immer direkt sichtbar (kompakt), damit nichts "versteckt" ist.
    # Die Risikoklassen-Tabelle aus dem Dokument wird in der Übersicht bewusst ausgeblendet.
    try:
        tables_html = build_docx_tables_overview_html(docx_cur, docx_prev)
    except Exception:
        tables_html = ""
    if tables_html:
        html += (
            "<div class='docx-muted'>Hinweis: Die Risikoklassen-Tabelle aus dem Dokument wird absichtlich ausgeblendet.</div>"
            + tables_html
        )

    return "" if "docx-box" not in html else html




def build_docx_tables_overview_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    """Compact, source-of-truth overview (tables only, no narrative).

    Shows what was extracted from DOCX so nothing is "hidden" in the UI. The
    risk-class table (if present) is intentionally skipped.
    """

    import re

    def fmt(x: object) -> str:
        if x is None:
            return ""
        try:
            # keep readable; MacLab often has 1-2 decimals
            if isinstance(x, float):
                return f"{x:.2f}".rstrip("0").rstrip(".")
            if isinstance(x, int):
                return str(x)
            # numeric strings
            sx = str(x)
            return sx
        except Exception:
            return ""

    def mk_table(headers: list[str], rows: list[list[object]], *, cls: str = "rhk-tbl") -> str:
        th = "".join([f"<th>{_html.escape(h)}</th>" for h in headers])
        body_rows = []
        for r in rows:
            tds = "".join([f"<td>{_html.escape(fmt(c))}</td>" for c in r])
            body_rows.append(f"<tr>{tds}</tr>")
        tbody = "".join(body_rows)
        return f"<table class='{cls}'><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>"

    def get_nested(d: dict, path: list[str]):
        cur = d
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    def render(payload: dict, label: str) -> str:
        phases = (payload or {}).get("phases") or {}
        if not phases:
            return ""

        # Spaltenreihenfolge wie im klinischen Denken:
        # Base 1 -> Base 2 -> Ergometrie bzw. Intervention
        order = ["base1", "base2", "exercise", "post"]
        keys = [k for k in order if k in phases]
        if not keys:
            keys = list(phases.keys())

        name_map = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergometrie",
            "post": "Intervention",
        }
        cols = [name_map.get(k, k) for k in keys]

        def p(ph: str, *path: str):
            return get_nested(phases.get(ph) or {}, list(path))

        rows_core: list[list[object]] = []
        def add_row(name: str, vals: list[object]):
            rows_core.append([name] + vals)


        # Pressures (aus der Druckzusammenfassung, ohne Fließtext-Inferenz)
        add_row("RAP A/V/mean [mmHg]", [
            "/".join([fmt(p(k, "pressures", "ra", "a")), fmt(p(k, "pressures", "ra", "v")), fmt(p(k, "pressures", "ra", "mean"))]).strip("/")
            for k in keys
        ])
        add_row("RV s/d/EDP [mmHg]", [
            "/".join([fmt(p(k, "pressures", "rv", "sys")), fmt(p(k, "pressures", "rv", "dia")), fmt(p(k, "pressures", "rv", "edp"))]).strip("/")
            for k in keys
        ])
        add_row("PAP s/d/m [mmHg]", [
            "/".join([fmt(p(k, "pressures", "pa", "sys")), fmt(p(k, "pressures", "pa", "dia")), fmt(p(k, "pressures", "pa", "mean"))]).strip("/")
            for k in keys
        ])
        add_row("PCWP A/V/mean [mmHg]", [
            "/".join([fmt(p(k, "pressures", "pcw", "a")), fmt(p(k, "pressures", "pcw", "v")), fmt(p(k, "pressures", "pcw", "mean"))]).strip("/")
            for k in keys
        ])

        # CO/CI

        # CO/CI
        add_row("CO TD [L/min]", [p(k, "co", "td_co") for k in keys])
        add_row("CI TD [L/min/m²]", [p(k, "co", "td_ci") for k in keys])
        add_row("CO Fick [L/min]", [p(k, "co", "fick_co") for k in keys])
        add_row("CI Fick [L/min/m²]", [p(k, "co", "fick_ci") for k in keys])


        # Resistance (Dokumentwerte; keine Interpretation)
        add_row("PVR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "pvr", "wu")), fmt(p(k, "resistance", "pvr", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("PVRI [WU·m²] / [dyn·s·cm⁻⁵·m²]", [
            "/".join([fmt(p(k, "resistance", "pvri", "wu")), fmt(p(k, "resistance", "pvri", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TPR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "tpr", "wu")), fmt(p(k, "resistance", "tpr", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TPRI [WU·m²] / [dyn·s·cm⁻⁵·m²]", [
            "/".join([fmt(p(k, "resistance", "tpri", "wu")), fmt(p(k, "resistance", "tpri", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TVR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "tvr", "wu")), fmt(p(k, "resistance", "tvr", "dyn"))]).strip("/")
            for k in keys
        ])

        # Derived gradients

        # Derived gradients (from pressures)
        def tpg_for(ph: str):
            mpap = p(ph, "pressures", "pa", "mean")
            pcw = p(ph, "pressures", "pcw", "mean")
            try:
                if mpap is None or pcw is None:
                    return None
                return float(mpap) - float(pcw)
            except Exception:
                return None

        def dpg_for(ph: str):
            d = p(ph, "pressures", "pa", "dia")
            pcw = p(ph, "pressures", "pcw", "mean")
            try:
                if d is None or pcw is None:
                    return None
                return float(d) - float(pcw)
            except Exception:
                return None

        add_row("TPG [mmHg]", [tpg_for(k) for k in keys])
        add_row("DPG [mmHg]", [dpg_for(k) for k in keys])

        def papi_for(ph: str):
            try:
                s = p(ph, "pressures", "pa", "sys")
                d = p(ph, "pressures", "pa", "dia")
                ra = p(ph, "pressures", "ra", "mean")
                if s is None or d is None or ra in (None, 0):
                    return None
                return (float(s) - float(d)) / float(ra)
            except Exception:
                return None

        def sv_for(ph: str):
            try:
                co = p(ph, "co", "td_co") or p(ph, "co", "fick_co")
                hr = p(ph, "co", "fick_hr")
                if co is None or hr in (None, 0):
                    return None
                return float(co) * 1000.0 / float(hr)
            except Exception:
                return None

        add_row("PAPI", [papi_for(k) for k in keys])
        add_row("SV [ml] (CO/HR)", [sv_for(k) for k in keys])

        core_html = mk_table(["Parameter"] + cols, rows_core, cls="rhk-tbl")

        # Blood gas / oximetry (raw)
        bg = ((payload or {}).get("timeseries") or {}).get("bloodgas") or []
        bg_rows: list[list[object]] = []
        for r in bg[:80]:
            if not isinstance(r, dict):
                continue
            bg_rows.append([
                r.get("time"),
                r.get("site"),
                r.get("group"),
                r.get("hb_g_dl"),
                r.get("sat_pct"),
                r.get("po2_mmhg"),
                r.get("content_ml_dl"),
            ])
        bg_html = ""
        if bg_rows:
            bg_html = mk_table([
                "Zeit", "Ort", "Gruppe", "Hb [g/dl]", "Sättigung [%]", "pO₂ [mmHg]", "O₂-Content [ml/dl]",
            ], bg_rows, cls="rhk-tbl")

        def _is_risk_like_table(title: str, matrix: list[list[object]]) -> bool:
            # Das gesamte ESC/ERS Risiko-Range-Kapitel ist nicht patient*innenspezifisch.
            # Es soll weder extrahiert noch als "roh" angezeigt werden.
            t = (title or "").strip()
            if re.search(r"risiko|risk", t, flags=re.IGNORECASE):
                return True
            # Viele dieser Range-Tabellen haben keinen klaren Titel in der ersten Zelle.
            # Deshalb zusätzlich auf Inhalte prüfen (nur wenige Zeilen scannen).
            try:
                sample = " ".join([" ".join([str(c) for c in row]) for row in (matrix or [])[:4]])
            except Exception:
                sample = ""
            if re.search(r"WHO\-Funktionsklasse|REVEAL|COMPERA|Geringes\s+R|Intermedi|Hohes\s+R", sample, flags=re.IGNORECASE):
                return True
            if re.search(r"Biomarker", sample, flags=re.IGNORECASE) and re.search(r"NT\-?proBNP|BNP\b", sample, flags=re.IGNORECASE) and re.search(r"<|>", sample):
                return True
            return False

        # All extracted tables (except risk-like tables)
        all_tables = ((payload or {}).get("raw_tables") or {}).get("all_tables") or []
        tbl_html_parts: list[str] = []
        for t in all_tables:
            try:
                title = (t.get("title") or "").strip()
                matrix = t.get("matrix") or []
                if _is_risk_like_table(title, matrix):
                    continue
                if not matrix:
                    continue
                # "Max.Last" Spalte: In manchen MacLab-Tabellen ist die letzte Kopfzelle leer.
                # Wenn eine Ergometrie-Spalte existiert, füllen wir "Max.Last" mit den Ergo-Werten
                # (rein für Transparenz in der Rohdarstellung).
                try:
                    header = list(matrix[0]) if matrix and matrix[0] else []
                    if header and len(header) >= 5:
                        ergo_idx = None
                        for j, h in enumerate(header):
                            if isinstance(h, str) and re.search(r"ergometrie", h, flags=re.IGNORECASE):
                                ergo_idx = j
                                break
                        if (ergo_idx is not None) and (str(header[-1]).strip() == ""):
                            header[-1] = "Max.Last"
                            # copy matrix for display only
                            patched = [header]
                            for rr in matrix[1:]:
                                r = list(rr)
                                # ensure length
                                if len(r) < len(header):
                                    r = r + [""] * (len(header) - len(r))
                                if str(r[-1]).strip() == "" and ergo_idx < len(r):
                                    r[-1] = r[ergo_idx]
                                patched.append(r)
                            matrix = patched
                except Exception:
                    pass
                # limit extremely large tables to keep UI snappy
                max_rows = 120
                matrix_show = matrix[:max_rows]
                headers = [str(x) for x in matrix_show[0]]
                rows = [list(row) for row in matrix_show[1:]]
                tbl = mk_table(headers, rows, cls="rhk-tbl")
                more = "" if len(matrix) <= max_rows else f"<div class='docx-muted'>… {len(matrix)-max_rows} weitere Zeilen ausgeblendet</div>"
                tbl_html_parts.append(
                    f"<details class='docx-details'><summary>{_html.escape(title or 'Tabelle')}</summary>{tbl}{more}</details>"
                )
            except Exception:
                continue

        tables_html = "".join(tbl_html_parts)

        qual = (payload or {}).get("quality") or {}
        qual_status = _html.escape(str(qual.get("status") or ""))
        qual_reasons = qual.get("reasons") or []
        qual_html = ""
        if qual_status:
            reasons = "".join([f"<li>{_html.escape(str(x))}</li>" for x in qual_reasons])
            qual_html = f"<div class='docx-muted'>Import-Qualität: {qual_status}</div>" + (f"<ul class='docx-list'>{reasons}</ul>" if reasons else "")

        parts = [
            f"<div class='docx-title'>{_html.escape(label)} – Tabellenübersicht (Quelle: DOCX)</div>",
            qual_html,
            core_html,
        ]
        if bg_html:
            parts.append(f"<details class='docx-details'><summary>Oximetrie und BGA (roh)</summary>{bg_html}</details>")
        if tables_html:
            parts.append(f"<details class='docx-details'><summary>Alle extrahierten Tabellen (roh)</summary>{tables_html}</details>")

        return "<div class='docx-box'>" + "".join(parts) + "</div>"

    html_parts = []
    if docx_cur:
        html_parts.append(render(docx_cur, "Aktueller RHK"))
    if docx_prev:
        html_parts.append(render(docx_prev, "Vor-RHK"))

    return "".join([p for p in html_parts if p])

def build_rhk_plots_html(case: dict, docx_cur: dict | None, docx_prev: dict | None) -> str:
    if not isinstance(case, dict):
        return ""
    der = case.get("derived") or {}
    raw = case.get("raw") or {}

    charts: list[str] = []

    # 1) Phasen-Verlauf aus Docx (Base 1/2/Ergo/Post)
    if isinstance(docx_cur, dict) and (docx_cur.get("phases") or {}):
        ph = docx_cur.get("phases") or {}
        order = ["base1", "base2", "exercise", "post", "no", "o2"]
        phase_keys = [k for k in order if k in ph]
        for k in ph.keys():
            if k not in phase_keys:
                phase_keys.append(k)
        label_map = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergo",
            "post": "Post",
            "no": "NO",
            "o2": "O2",
        }
        labels = [label_map.get(k, k) for k in phase_keys]

        def _get_val(k: str, path: tuple[str, ...]) -> float | None:
            try:
                cur = ph.get(k) or {}
                for p in path:
                    cur = cur.get(p) if isinstance(cur, dict) else None
                return cur if isinstance(cur, (int, float)) else None
            except Exception:
                return None

        mpap = [_get_val(k, ("pressures", "pa", "mean")) for k in phase_keys]
        pawp = [_get_val(k, ("pressures", "pcw", "mean")) for k in phase_keys]
        rap = [_get_val(k, ("pressures", "ra", "mean")) for k in phase_keys]

        co_td = [_get_val(k, ("co", "td_co")) for k in phase_keys]
        co_fk = [_get_val(k, ("co", "fick_co")) for k in phase_keys]
        ci_td = [_get_val(k, ("co", "td_ci")) for k in phase_keys]
        ci_fk = [_get_val(k, ("co", "fick_ci")) for k in phase_keys]

        pvr = [_get_val(k, ("resistance", "pvr", "wu")) for k in phase_keys]
        pvri = [_get_val(k, ("resistance", "pvri", "wu")) for k in phase_keys]

        if any(v is not None for v in mpap + pawp + rap):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"mPAP": mpap, "PAWP": pawp, "RAP": rap},
                    "Zentrale Drücke (Phasen)",
                    "mmHg",
                )
            )

        if any(v is not None for v in co_td + co_fk):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"HZV TD": co_td, "HZV Fick": co_fk},
                    "HZV Verlauf (Phasen)",
                    "l/min",
                )
            )

        if any(v is not None for v in ci_td + ci_fk):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"CI TD": ci_td, "CI Fick": ci_fk},
                    "CI Verlauf (Phasen)",
                    "l/min/m²",
                )
            )

        if any(v is not None for v in pvr + pvri):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"PVR": pvr, "PVRI": pvri},
                    "Widerstände (Phasen)",
                    "WU",
                )
            )

    # 2) mPAP/PAWP gegen HZV (Rest -> Peak)
    if bool(raw.get("exercise_done")):
        charts.append(svg_mpap_pawp_vs_co(
            der.get("mpap"), der.get("pawp"), der.get("co"),
            der.get("mpap_peak"), der.get("pawp_peak"), der.get("co_peak"),
            title="Ergometrie: Druck gegen HZV"
        ))

    # 3) Vorher vs Jetzt (Delta-Bars) – fokussiert auf Basis-Hämodynamik
    prev = {
        "mPAP": raw.get("prev_mpap"),
        "PAWP": raw.get("prev_pawp"),
        "RAP": raw.get("prev_rap"),
        "CI": raw.get("prev_ci"),
        "PVR": raw.get("prev_pvr"),
    }
    cur = {
        "mPAP": der.get("mpap"),
        "PAWP": der.get("pawp"),
        "RAP": der.get("rap"),
        "CI": der.get("ci"),
        "PVR": der.get("pvr"),
    }
    delta_items = []
    for k in ("mPAP", "PAWP", "RAP", "CI", "PVR"):
        try:
            if prev.get(k) is None or cur.get(k) is None:
                continue
            delta_items.append((k, float(cur[k]) - float(prev[k])))
        except Exception:
            continue
    if delta_items:
        charts.append(svg_delta_bars(delta_items, "Vorher vs Jetzt (Differenz)", "Delta", note="Delta = Jetzt minus Vorher"))

    # 3b) Vorher vs Jetzt (Absolute Werte) – eigene, schnelle Übersicht
    try:
        press_items = []
        if prev.get("mPAP") is not None and cur.get("mPAP") is not None:
            press_items.append(("mPAP", float(prev["mPAP"]), float(cur["mPAP"])))
        if prev.get("PAWP") is not None and cur.get("PAWP") is not None:
            press_items.append(("PAWP", float(prev["PAWP"]), float(cur["PAWP"])))
        if prev.get("RAP") is not None and cur.get("RAP") is not None:
            press_items.append(("RAP", float(prev["RAP"]), float(cur["RAP"])))
        if press_items:
            charts.append(svg_compare_bars(press_items, "Vorher vs Jetzt (Drücke)", "mmHg"))

        ci_items = []
        if prev.get("CI") is not None and cur.get("CI") is not None:
            ci_items.append(("CI", float(prev["CI"]), float(cur["CI"])))
        if ci_items:
            charts.append(svg_compare_bars(ci_items, "Vorher vs Jetzt (Cardiac Index)", "l/min/m²"))

        pvr_items = []
        if prev.get("PVR") is not None and cur.get("PVR") is not None:
            pvr_items.append(("PVR", float(prev["PVR"]), float(cur["PVR"])))
        if pvr_items:
            charts.append(svg_compare_bars(pvr_items, "Vorher vs Jetzt (PVR)", "WU"))
    except Exception:
        pass

    # 4) Volumenchallenge (Pre -> Post)
    if bool(raw.get("volume_challenge_done")):
        try:
            pawp_pre = raw.get("pawp_pre")
            pawp_post = raw.get("pawp_post")
            mpap_pre = raw.get("mpap_pre")
            mpap_post = raw.get("mpap_post")
            items = []
            if pawp_pre is not None and pawp_post is not None:
                items.append(("PAWP", float(pawp_post) - float(pawp_pre)))
            if mpap_pre is not None and mpap_post is not None:
                items.append(("mPAP", float(mpap_post) - float(mpap_pre)))
            if items:
                charts.append(svg_delta_bars(items, "Volumenchallenge (Post minus Pre)", "mmHg"))
        except Exception:
            pass

    if not charts:
        return ""

    return "<div class='rhk-viz-grid'>" + "".join([f"<div class='rhk-viz-item'>{c}</div>" for c in charts if c]) + "</div>"

def build_p_module_cards_html(blocks: Dict[str, Any], case: Optional[Dict[str, Any]]) -> str:
    if not case:
        return ""
    der = case.get("derived") or {}
    decision = case.get("decision") or {}
    ui = case.get("ui") or {}

    policy = der.get("p_module_policy") or {}
    levels = policy.get("levels") or {}
    disabled = policy.get("disabled") or {}

    auto_mods = _normalize_module_ids(decision.get("modules") or [])
    sel_mods = _normalize_module_ids(ui.get("modules") or [])
    # Keep selection order stable (auto first)
    sel_mods = list(dict.fromkeys(auto_mods + sel_mods))

    def lvl_chip(lvl: int) -> str:
        if lvl == 1:
            return "<span class='pmod-chip pmod-chip--lvl1'>Level I</span>"
        if lvl == 2:
            return "<span class='pmod-chip pmod-chip--lvl2'>Level II</span>"
        return "<span class='pmod-chip pmod-chip--lvl3'>Level III</span>"

    # Reduce visual overload: show primarily Level I/II + currently selected modules.
    # Locked modules are displayed separately via `build_disabled_p_modules_html()`.
    allowed = set(policy.get("allowed") or [])
    pids_to_show: List[str] = []
    for pid in _ALL_P_MODULE_IDS:
        if pid in disabled:
            continue
        if allowed and pid not in allowed:
            continue
        try:
            lvl = int(levels.get(pid, 3) or 3)
        except Exception:
            lvl = 3
        if lvl <= 2 or pid in sel_mods or pid in auto_mods:
            pids_to_show.append(pid)

    cards = []
    for pid in pids_to_show:
        b = blocks.get(pid)
        title = b.title if b else pid
        subtitle = ""
        try:
            subtitle = b.subtitle if b and getattr(b, "subtitle", None) else ""
        except Exception:
            subtitle = ""

        lvl = int(levels.get(pid, 3) or 3)
        locked_reason = None
        is_locked = False

        is_auto = pid in auto_mods
        is_selected = pid in sel_mods
        is_manual = (is_selected and not is_auto)

        meta = [lvl_chip(lvl)]
        if is_auto:
            meta.append("<span class='pmod-chip pmod-chip--auto'>Auto</span>")
        elif is_manual:
            meta.append("<span class='pmod-chip pmod-chip--manual'>Manuell</span>")

        tip = ""
        if is_locked and locked_reason:
            tip = html_escape(str(locked_reason))

        cards.append(
            f"<div class='pmod-card' title='{tip}'>"
            f"<div class='pmod-title'>{pid} – {html_escape(str(title))}</div>"
            f"<div class='pmod-sub'>{html_escape(str(subtitle))}</div>"
            f"<div class='pmod-meta'>{''.join(meta)}</div>"
            "</div>"
        )

    auto_n = len(auto_mods)
    manual_n = len([m for m in sel_mods if (m not in auto_mods)])
    locked_n = len(disabled)

    shown_n = len(pids_to_show)
    header = (
        "<div class='rhk-summarybar' style='margin: 4px 0 8px;'>"
        f"<span class='rhk-schip rhk-schip--info'>Module: Auto {auto_n}</span>"
        f"<span class='rhk-schip'>Manuell {manual_n}</span>"
        f"<span class='rhk-schip rhk-schip--warn'>Gesperrt {locked_n}</span>"
        f"<span class='rhk-schip'>Anzeige: {shown_n}/{len(_ALL_P_MODULE_IDS)} (Level I–II + ausgewählt)</span>"
        "</div>"
    )

    if not cards:
        return header
    return header + "<div class='pmod-grid'>" + "".join(cards) + "</div>"


# ---------------------------------------------------------------------
# Pre-Cath Safety Header (Ampel) – HTML renderer
# ---------------------------------------------------------------------
def build_pre_cath_header_html(ui: dict | None) -> str:
    """Render a compact, chip-based Pre-Cath Safety header.

    Expected ui keys (best-effort):
    - consent_done: bool
    - access_route: str
    - inr: float
    - ptt_s: float
    - platelets_g_l: float
    - anticoag_status: str
    - anticoag_paused: bool
    - crp_mg_l: float
    """

    ui = ui or {}

    def _safe_float(x):
        try:
            if x is None or x == "":
                return None
            return float(x)
        except Exception:
            return None

    def _chip(text: str, cls: str = "", title: str = "") -> str:
        c = "rhk-schip" + (f" {cls}" if cls else "")
        tattr = f" title='{html_escape(title)}'" if title else ""
        return f"<span class='{c}'{tattr}>" + html_escape(text) + "</span>"

    # 1) Aufklärung
    consent_done = bool(ui.get("consent_done") is True)
    consent_chip = _chip(
        "Aufklärung: erfolgt" if consent_done else "Aufklärung: fehlt",
        "rhk-schip--good" if consent_done else "rhk-schip--bad",
    )

    # 1b) Zugangsweg
    access_route = (ui.get("access_route") or "").strip()
    access_chip = _chip(
        f"Zugang: {access_route}" if access_route else "Zugang: –",
        "rhk-schip--info",
    )

    # 2) Gerinnung
    inr = _safe_float(ui.get("inr"))
    ptt = _safe_float(ui.get("ptt_s"))
    plts = _safe_float(ui.get("platelets_g_l"))

    # Schwellen: praxisnah/konservativ
    # - INR hoch: > 1.5
    # - PTT hoch: > 40 s
    # - Thrombos niedrig: < 100 G/l
    warns = []
    if inr is not None and inr > 1.5:
        warns.append(f"INR {inr:g}")
    if ptt is not None and ptt > 40:
        warns.append(f"PTT {ptt:g}")
    if plts is not None and plts < 100:
        warns.append(f"Thrombos {plts:g}")

    if warns:
        coag_chip = _chip("Gerinnung: Warnung (" + ", ".join(warns) + ")", "rhk-schip--warn")
    else:
        # Wenn alles fehlt: neutral (info), sonst grün
        any_val = (inr is not None) or (ptt is not None) or (plts is not None)
        coag_chip = _chip("Gerinnung: OK" if any_val else "Gerinnung: (keine Daten)", "rhk-schip--good" if any_val else "rhk-schip--info")

    # 3) Antikoagulation
    anticoag_status_raw = str(ui.get("anticoag_status") or "").strip()
    anticoag_status = anticoag_status_raw.strip().lower()
    anticoag_paused_flag = bool(ui.get("anticoag_paused") is True)

    # Normalize common variants
    is_yes = anticoag_status in ("ja", "yes", "true")
    is_no = anticoag_status in ("nein", "no", "false")
    is_paused_text = ("paus" in anticoag_status)  # matches "pausiert", "ja, aber pausiert"
    is_unknown = anticoag_status in ("unklar", "")

    if is_no:
        # In this context: no anticoagulation = OK (green)
        antico_chip = _chip("Antikoagulation: nein", "rhk-schip--good")
    elif is_yes:
        # Yes without pause = attention (red), paused = OK (green)
        if anticoag_paused_flag or is_paused_text:
            antico_chip = _chip("Antikoagulation: ja (pausiert)", "rhk-schip--good")
        else:
            antico_chip = _chip("Antikoagulation: ja", "rhk-schip--bad")
    elif is_paused_text:
        antico_chip = _chip("Antikoagulation: ja (pausiert)", "rhk-schip--good")
    elif is_unknown:
        antico_chip = _chip("Antikoagulation: unklar", "rhk-schip--warn")
    else:
        # e.g. "keine Angabe"
        antico_chip = _chip("Antikoagulation: " + (anticoag_status_raw or "keine Angabe"), "rhk-schip--info")

    # 4) Nierenfunktion (Kreatinin / eGFR)
    crea = _safe_float(ui.get("creatinine_mg_dl"))
    egfr_v = _safe_float(ui.get("egfr_ml_min_1_73"))
    if egfr_v is None:
        egfr_v = _safe_float(ui.get("egfr"))

    renal_tone = "rhk-schip--info"
    if egfr_v is not None:
        if egfr_v >= 60:
            renal_tone = "rhk-schip--good"
        elif egfr_v >= 30:
            renal_tone = "rhk-schip--warn"
        else:
            renal_tone = "rhk-schip--bad"
    elif crea is not None:
        if crea < 1.3:
            renal_tone = "rhk-schip--good"
        elif crea <= 1.8:
            renal_tone = "rhk-schip--warn"
        else:
            renal_tone = "rhk-schip--bad"

    renal_tip = ""
    try:
        if egfr_v is not None:
            renal_tip = f"eGFR {_fmt_or_dash(egfr_v,0)} ml/min/1.73m²"
    except Exception:
        renal_tip = ""

    renal_chip = _chip(f"Krea: {_fmt_or_dash(crea,2)}", renal_tone, renal_tip)

    # 4)

    # 4) Infekt (CRP)
    crp = _safe_float(ui.get("crp_mg_l"))
    if crp is not None and crp > 20:
        infect_chip = _chip(f"Infekt: CRP {crp:g}", "rhk-schip--bad")
    elif crp is not None:
        infect_chip = _chip(f"Infekt: CRP {crp:g}", "rhk-schip--good")
    else:
        infect_chip = _chip("Infekt: (kein CRP)", "rhk-schip--info")

    return (
        "<div class='rhk-summarybar'>"
        + consent_chip
        + access_chip
        + coag_chip
        + antico_chip
        + infect_chip
        + renal_chip
        + "</div>"
    )
