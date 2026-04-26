#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.31: rhk_import_docx.py - Performance: python-docx lazy import (faster cold-start), API unverändert
# Refactor v1.28: rhk_import_docx.py - Robust DOCX parse (safe errors, deterministic schema), kein File-Pfad in Payload, UI-Mapping sanitisiert
"""DOCX Importer für RHK-Befunde (GE MacLab Word Export).

Klinische Leitplanken (STRICT):
- **Fehlende Werte ≠ 0**: Es wird niemals ``None`` als 0 interpretiert.
- **Manuelle Eingaben werden nicht überschrieben**: Diese Policy wird in der UI-Merge-Logik
  umgesetzt (siehe ``rhk_import_merge.py``). Dieses Modul liefert ausschließlich Updates.
- **Plausibilität**: Unphysiologische Werte gelten als *nicht vorhanden* (siehe Sanitization).

Designziele:
- Nur Tabellen werden ausgewertet (Fließtext wird ignoriert).
- Base 2 ist die einzige Quelle für berechnungsrelevante Ruhewerte.
  Ruhewerte aus Base 1 werden **niemals** in berechnungsrelevante Felder übernommen.
- Unterstützt zusätzliche Phasen: Ergometrie, Post-Intervention (z.B. Volumenchallenge),
  NO/O2 (falls als Spalte vorhanden).
- Hohe Robustheit bei Dezimaltrennzeichen (Komma/Punkt) und leicht variierenden Tabellen.
- Deterministische Ausgabe: gleicher Input → gleicher Output.

Rückgabeformat (stabil):
{
  "ok": bool,
  "error": str|None,                 # nur bei ok=False gesetzt
  "source": {"filename": str},
  "patient": {...},
  "timeseries": {"vitals": [], "bloodgas": [], "pressures": []},
  "phases": {...},
  "canonical": {...},                # Base-2-basierte Ruhewerte
  "raw_tables": {...},               # Tabellen für Audit/Übersicht (UI filtert streng)
  "quality": {"status": "green|yellow|red", "reasons": [...], "warnings": [...]},
}
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple


@lru_cache(maxsize=1)
def _load_docx_document_cls():
    """Lazy import wrapper for python-docx.

    Performance rationale:
    - python-docx import can noticeably slow down cold-starts.
    - DOCX import is optional in many clinical workflows.
    """
    try:
        from docx import Document
        return Document
    except ModuleNotFoundError:
        return None

from rhk_validation import sanitize_ui_numbers

# UI defaults for fields that the DOCX importer is allowed to auto-fill.
# These are reused by the merge/undo logic so importer output and reset policy
# cannot silently drift apart.
DOCX_CURRENT_WIPE_DEFAULTS: Dict[str, Any] = {
    # Demography / meta
    "age": None,
    "sex": "keine Angabe",
    "height_cm": None,
    "weight_kg": None,
    "hb_g_dl": None,
    "rhk_date": "",
    # Rest hemodynamics
    "spap_rest": None,
    "dpap_rest": None,
    "mpap_rest": None,
    "pawp_rest": None,
    "rap_rest": None,
    "co_rest": None,
    "ci_rest": None,
    "pvr_rest": None,
    "co_method": "keine Angabe",
    # Oximetry + vitals
    "sat_svc": None,
    "sat_ivc": None,
    "sat_ra": None,
    "sat_rv": None,
    "sat_pa": None,
    "sat_ao": None,
    "bp_sys": None,
    "bp_dia": None,
    "bp_mean": None,
    "hr": None,
    "spo2": None,
    # Exercise / additional phases
    "exercise_done": False,
    "spap_peak": None,
    "dpap_peak": None,
    "mpap_peak": None,
    "pawp_peak": None,
    "co_peak": None,
    "ci_peak": None,
    "volume_challenge_done": False,
    "pawp_pre": None,
    "pawp_post": None,
    "mpap_pre": None,
    "mpap_post": None,
    "vaso_test_done": False,
    "vaso_agent": "",
    "vaso_response_desc": "",
    "vaso_mpap_pre": None,
    "vaso_co_pre": None,
    "vaso_mpap_post": None,
    "vaso_co_post": None,
}

DOCX_PREV_WIPE_DEFAULTS: Dict[str, Any] = {
    "prev_rhk_date": "",
    "prev_spap": None,
    "prev_dpap": None,
    "prev_mpap": None,
    "prev_pawp": None,
    "prev_rap": None,
    "prev_co": None,
    "prev_ci": None,
    "prev_pvr": None,
}


# ---------------------------------------------------------------------
# Helpers (Parsing)
# ---------------------------------------------------------------------

def _clean(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("\xa0", " ").strip()


def _lower_key(s: str) -> str:
    return re.sub(r"\s+", " ", _clean(s)).lower()


def _parse_float(s: Any) -> Optional[float]:
    """Parse a float from MacLab cell text.

    Supports:
    - German decimal comma
    - Thousands separators (best effort): 1.049,25 -> 1049.25
    - Values with units or extra text (units stripped)
    """
    txt = _clean(s)
    if txt == "":
        return None

    # Keep digits, comma, dot, minus; strip units/words.
    txt2 = re.sub(r"[^0-9,\.\-]", "", txt)
    if txt2 in ("", "-", ".", ","):
        return None

    # German formats:
    # 1.049,25  -> 1049.25
    # 287,93    -> 287.93
    # 147.96    -> 147.96
    if "." in txt2 and "," in txt2:
        txt2 = txt2.replace(".", "").replace(",", ".")
    else:
        txt2 = txt2.replace(",", ".")
    try:
        v = float(txt2)
    except (TypeError, ValueError):
        return None
    # NaN/Inf should not propagate
    if not (v == v) or v in (float("inf"), float("-inf")):
        return None
    return v


def _parse_int(s: Any) -> Optional[int]:
    f = _parse_float(s)
    if f is None:
        return None
    try:
        return int(round(float(f)))
    except (TypeError, ValueError):
        return None


def _parse_date_to_ddmmyyyy(s: Any) -> Optional[str]:
    txt = _clean(s)
    if txt == "":
        return None
    txt = txt.replace("/", ".")
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", txt)
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    try:
        dt = datetime(int(y), int(mo), int(d))
        return dt.strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return None


def _parse_time_hhmm(s: Any) -> Optional[str]:
    txt = _clean(s)
    m = re.search(r"(\d{1,2})[:.](\d{2})", txt)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return None


def _hhmm_to_minutes(s: Any) -> int:
    """Best-effort convert HH:MM to minutes since 00:00. Unknown -> -1."""
    t = _parse_time_hhmm(s)
    if not t:
        return -1
    try:
        hh, mm = t.split(":", 1)
        return int(hh) * 60 + int(mm)
    except (TypeError, ValueError, AttributeError):
        return -1


def _split_label_value(cell_text: str) -> Tuple[str, str]:
    """Return (label, value) from a MacLab cell, usually 'Label\nValue'."""
    txt = _clean(cell_text)
    if "\n" in txt:
        parts = [p.strip() for p in txt.split("\n") if p.strip() != ""]
        if len(parts) >= 2:
            return parts[0], parts[1]
    return txt, ""


def _to_phase_key(h: str) -> str:
    hh = _lower_key(h)
    hh = hh.replace("–", "-").replace("—", "-")
    hh = hh.replace("post intervention", "post-intervention")
    hh = hh.replace("postintervention", "post-intervention")
    hh = re.sub(r"[^a-z0-9\- ]", "", hh)
    hh = re.sub(r"\s+", " ", hh).strip()

    # Robust Base-Phasen-Erkennung (MacLab Varianten):
    # - akzeptiert Zusätze wie 'Base 2 (Ruhe)', 'Baseline 2', 'Basis 2', etc.
    # - niemals Base 1 als Base 2 mappen
    if re.search(r"\b(base|baseline|basis)\s*1\b", hh):
        return "base1"
    if re.search(r"\b(base|baseline|basis)\s*2\b", hh):
        return "base2"
    # Roman numerals occasionally occur
    if re.search(r"\b(base|baseline|basis)\s*i\b", hh):
        return "base1"
    if re.search(r"\b(base|baseline|basis)\s*ii\b", hh):
        return "base2"

    if "ergometrie" in hh or "exercise" in hh or "belast" in hh:
        return "exercise"
    if "post-intervention" in hh or "volumen" in hh or "fluid" in hh:
        return "post"
    if hh in ("no",) or "ino" in hh:
        return "no"
    if hh in ("o2",) or "oxygen" in hh:
        return "o2"

    # fallback slug
    hh = hh.replace(" ", "_").replace("-", "_")
    return hh or "phase"


def _parse_sys_dia_mean(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 54/23 (33) or 177/80/115
    s = _clean(txt)
    out: Dict[str, Optional[float]] = {"sys": None, "dia": None, "mean": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        return out
    out["mean"] = _parse_float(s)
    return out


def _parse_a_v_mean(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 24/22 (18)
    s = _clean(txt)
    out: Dict[str, Optional[float]] = {"a": None, "v": None, "mean": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["a"] = _parse_float(m.group(1))
        out["v"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    out["mean"] = _parse_float(s)
    return out


def _parse_rv_sys_dia_edp(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 55/1/9
    s = _clean(txt)
    out: Dict[str, Optional[float]] = {"sys": None, "dia": None, "edp": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["edp"] = _parse_float(m.group(3))
        return out
    out["sys"] = _parse_float(s)
    return out


def _parse_resistance_dyn_wu(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 287,93 (3,6)
    s = _clean(txt)
    out: Dict[str, Optional[float]] = {"dyn": None, "wu": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["dyn"] = _parse_float(m.group(1))
        out["wu"] = _parse_float(m.group(2))
        return out
    # If only one number, store as WU (most user-facing)
    out["wu"] = _parse_float(s)
    return out


# ---------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------

def _table_matrix(t: Any) -> List[List[str]]:
    return [[_clean(c.text) for c in row.cells] for row in t.rows]


def _is_vitals_header(row: List[str]) -> bool:
    h = _lower_key(" ".join(row))
    return ("spo2" in h) and ("hf" in h or "herzfrequ" in h) and ("bd" in h or "blutdruck" in h) and ("zeit" in h)


def _is_bloodgas_header(row: List[str]) -> bool:
    h = _lower_key(" ".join(row))
    return ("hb" in h) and ("sätt" in h or "satt" in h) and ("po2" in h) and ("zeit" in h) and ("ort" in h)


def _is_pressure_header(row: List[str]) -> bool:
    h = _lower_key(" ".join(row))
    return ("sys" in h) and ("dias" in h) and ("mittel" in h) and ("a-welle" in h or "a welle" in h) and ("zeit" in h)


def _find_table_by_title(tables: List[List[List[str]]], title_sub: str) -> Optional[List[List[str]]]:
    key = _lower_key(title_sub)
    for mat in tables:
        if not mat or not mat[0]:
            continue
        first = _lower_key(mat[0][0])
        if key in first:
            return mat
    return None


def _extract_phase_table(mat: List[List[str]]) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    """Extract a phase-summary table.

    Returns:
        phases: list of unique phase keys (e.g. base1, base2, exercise, ...)
        rows: mapping[label][phase_key] = raw_cell_text

    Expects mat[0] = [title, phase1, phase2, ...]
    """
    header = mat[0]

    # 1) Anchors = non-empty header cells (excluding title column 0)
    anchors: List[Tuple[int, str]] = []  # (anchor_col_idx, phase_key)
    phases: List[str] = []
    used: Dict[str, int] = {}
    for col_idx in range(1, len(header)):
        h = _clean(header[col_idx])
        if h == "":
            continue
        base_pk = _to_phase_key(h)
        n = used.get(base_pk, 0)
        used[base_pk] = n + 1
        pk = base_pk if n == 0 else f"{base_pk}_{n+1}"
        phases.append(pk)
        anchors.append((col_idx, pk))

    min_phase_idx = min([c for c, _ in anchors], default=1)

    # 2) Candidate columns around each anchor (fixes shifted values into blank neighbor columns)
    phase_candidates: List[Tuple[str, int, List[int]]] = []  # (phase_key, anchor_idx, candidate_cols)
    for anchor_idx, pk in anchors:
        cols = {anchor_idx}
        # expand left over empty headers
        j = anchor_idx - 1
        while j >= 1:
            if _clean(header[j]) != "":
                break
            cols.add(j)
            j -= 1
        # expand right over empty headers
        j = anchor_idx + 1
        while j < len(header):
            if _clean(header[j]) != "":
                break
            cols.add(j)
            j += 1
        phase_candidates.append((pk, anchor_idx, sorted(cols)))

    def _pick_row_label(row: List[str]) -> str:
        # Prefer textual labels in columns left of the first phase anchor.
        for i in range(0, min(min_phase_idx, len(row))):
            v = _clean(row[i])
            if v and re.search(r"[A-Za-zÄÖÜäöüß]", v):
                return v
        for i in range(0, min(min_phase_idx, len(row))):
            v = _clean(row[i])
            if v:
                return v
        for v in row:
            vv = _clean(v)
            if vv:
                return vv
        return ""

    rows: Dict[str, Dict[str, str]] = {}
    for r in mat[1:]:
        if not r:
            continue
        row_label = _pick_row_label(r)
        if row_label == "":
            continue
        row_map: Dict[str, str] = {}
        for pk, anchor_idx, cand_cols in phase_candidates:
            val = ""
            if anchor_idx < len(r):
                val = _clean(r[anchor_idx])
            if val == "":
                for c in sorted(cand_cols, reverse=True):
                    if c < len(r):
                        vv = _clean(r[c])
                        if vv != "":
                            val = vv
                            break
            row_map[pk] = val
        rows[row_label] = row_map
    return phases, rows


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def _empty_result(filename: str, *, ok: bool, error: Optional[str], status: str, reasons: List[str]) -> Dict[str, Any]:
    return {
        "ok": bool(ok),
        "error": error,
        "source": {"filename": filename},
        "patient": {},
        "timeseries": {"vitals": [], "bloodgas": [], "pressures": []},
        "phases": {},
        "canonical": {},
        "raw_tables": {
            "all_tables": [],
            "bloodgas_tables": [],
            "pressure_tables": [],
            "pressure_summary": [],
            "co_table": [],
            "flow_table": [],
            "work_table": [],
            "resistance_table": [],
        },
        "quality": {
            "status": status,
            "reasons": reasons,
            "warnings": [],
        },
    }


def parse_maclab_docx(path: str) -> Dict[str, Any]:
    """Parse a GE MacLab DOCX export.

    This function never raises; errors are mapped into a stable output dict.
    """
    path_str = str(path or "")
    filename = os.path.basename(path_str) or "upload.docx"

    Document = _load_docx_document_cls()
    if Document is None:
        return _empty_result(
            filename,
            ok=False,
            error="python-docx fehlt",
            status="red",
            reasons=["python-docx fehlt (Import nicht möglich)."],
        )

    try:
        doc = Document(path_str)
    except Exception as e:
        return _empty_result(
            filename,
            ok=False,
            error="DOCX konnte nicht geöffnet werden",
            status="red",
            reasons=[f"DOCX Import fehlgeschlagen ({type(e).__name__})."],
        )

    try:
        tables = [_table_matrix(t) for t in doc.tables]
    except Exception as e:
        return _empty_result(
            filename,
            ok=False,
            error="DOCX Tabellen konnten nicht gelesen werden",
            status="red",
            reasons=[f"DOCX Tabellen-Parsing fehlgeschlagen ({type(e).__name__})."],
        )

    payload: Dict[str, Any] = {
        "ok": True,
        "error": None,
        "source": {"filename": filename},
        "patient": {},
        "timeseries": {"vitals": [], "bloodgas": [], "pressures": []},
        "phases": {},
        "canonical": {},
        "raw_tables": {},
        "quality": {"status": "green", "reasons": [], "warnings": []},
    }

    # Keep ALL tables for auditability and to ensure nothing is "lost".
    all_tables = []
    for i, mat in enumerate(tables):
        title = mat[0][0] if (mat and mat[0]) else ""
        all_tables.append({"index": i, "title": title, "matrix": mat})
    payload["raw_tables"]["all_tables"] = all_tables

    # 1) Patient info (prefer structured 2x6 table)
    patient_tbl: Optional[List[List[str]]] = None
    for mat in tables:
        if len(mat) == 2 and len(mat[0]) >= 6:
            flat0 = " ".join(mat[0])
            if ("Patientenname" in flat0) and ("Untersuch" in flat0):
                patient_tbl = mat
                break

    if patient_tbl:
        payload["raw_tables"]["patient_info"] = patient_tbl
        row = patient_tbl[1]

        def _cell_val(i: int) -> str:
            return _split_label_value(row[i])[1] if i < len(row) else ""

        dob = _parse_date_to_ddmmyyyy(_cell_val(0))
        age = _parse_int(_cell_val(1))
        sex_raw = _cell_val(2)
        sex: Optional[str] = None
        sxl = _lower_key(sex_raw)
        if sxl in ("m", "mann", "männlich", "male"):
            sex = "männlich"
        elif sxl in ("w", "weib", "weiblich", "female"):
            sex = "weiblich"
        elif "männ" in sxl or "male" in sxl:
            sex = "männlich"
        elif "weib" in sxl or "female" in sxl:
            sex = "weiblich"

        # height/weight cells may contain units in parentheses; take first numeric token
        h_txt = _cell_val(3)
        w_txt = _cell_val(4)
        h_match = re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", h_txt)
        w_match = re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", w_txt)
        height = _parse_float(h_match.group(1) if h_match else h_txt)
        weight = _parse_float(w_match.group(1) if w_match else w_txt)
        bsa = _parse_float(_cell_val(5))

        # exam date best-effort from header row
        exam_date = _parse_date_to_ddmmyyyy(" ".join(patient_tbl[0])) or _parse_date_to_ddmmyyyy(patient_tbl[0][2] if len(patient_tbl[0]) > 2 else "")

        payload["patient"] = {
            "dob": dob,
            "age_years": age,
            "sex": sex,
            "height_cm": height,
            "weight_kg": weight,
            "bsa_m2": bsa,
            "exam_date": exam_date,
        }

    # Fallback: single-cell patient info
    if not (payload.get("patient") or {}).get("exam_date"):
        for mat in tables:
            if mat and len(mat[0]) == 1 and "Patienteninformationen" in mat[0][0]:
                blob = " ".join(mat[1]) if len(mat) > 1 else ""
                payload.setdefault("patient", {})
                payload["patient"]["exam_date"] = payload["patient"].get("exam_date") or _parse_date_to_ddmmyyyy(blob)

                # Demografie aus Textblock (robust gegen variable Whitespace)
                m = re.search(r"Geburtsdatum\s*([0-9./]+)", blob)
                if payload["patient"].get("dob") is None and m:
                    payload["patient"]["dob"] = _parse_date_to_ddmmyyyy(m.group(1))

                m = re.search(r"Alter\s*([0-9]{1,3})", blob)
                if payload["patient"].get("age_years") is None and m:
                    payload["patient"]["age_years"] = _parse_int(m.group(1))

                m = re.search(r"Geschlecht\s*([A-Za-zÄÖÜäöüß]+)", blob)
                if payload["patient"].get("sex") is None and m:
                    sxl = _lower_key(m.group(1))
                    if sxl in ("m", "männlich", "mann"):
                        payload["patient"]["sex"] = "männlich"
                    elif sxl in ("w", "weiblich", "weib"):
                        payload["patient"]["sex"] = "weiblich"

                m = re.search(r"Größe\s*([0-9]{2,3}[\.,]?[0-9]*)\s*cm", blob)
                if payload["patient"].get("height_cm") is None and m:
                    payload["patient"]["height_cm"] = _parse_float(m.group(1))
                m = re.search(r"Gewicht\s*([0-9]{2,3}[\.,]?[0-9]*)\s*kg", blob)
                if payload["patient"].get("weight_kg") is None and m:
                    payload["patient"]["weight_kg"] = _parse_float(m.group(1))
                m = re.search(r"KOF\s*([0-9]{1,2}[\.,]?[0-9]*)\s*m2", blob)
                if payload["patient"].get("bsa_m2") is None and m:
                    payload["patient"]["bsa_m2"] = _parse_float(m.group(1))
                break

    # 2) Timeseries tables
    for mat in tables:
        if not mat:
            continue
        header = mat[0]
        if _is_vitals_header(header):
            payload["raw_tables"].setdefault("vitals_tables", []).append(mat)
            for r in mat[1:]:
                if len(r) < 4:
                    continue
                time = _parse_time_hhmm(r[0])
                spo2 = _parse_float(r[1])
                hr = _parse_float(r[2])
                bd = _parse_sys_dia_mean(r[3])
                af = _parse_float(r[4]) if len(r) > 4 else None
                payload["timeseries"]["vitals"].append(
                    {
                        "time": time,
                        "spo2": spo2,
                        "hr": hr,
                        "bp_sys": bd.get("sys"),
                        "bp_dia": bd.get("dia"),
                        "bp_mean": bd.get("mean"),
                        "af": af,
                    }
                )

        elif _is_bloodgas_header(header):
            payload["raw_tables"].setdefault("bloodgas_tables", []).append(mat)
            for r in mat[1:]:
                if len(r) < 6:
                    continue
                time = _parse_time_hhmm(r[0])
                ort = _clean(r[1]).upper()
                hb = _parse_float(r[2])
                sat = _parse_float(r[3])
                po2 = _parse_float(r[4])
                content = _parse_float(r[5])
                group = _clean(r[6]) if len(r) > 6 else ""
                payload["timeseries"]["bloodgas"].append(
                    {
                        "time": time,
                        "site": ort,
                        "hb_g_dl": hb,
                        "sat_pct": sat,
                        "po2_mmhg": po2,
                        "content_ml_dl": content,
                        "group": group or None,
                    }
                )

        elif _is_pressure_header(header):
            payload["raw_tables"].setdefault("pressure_tables", []).append(mat)
            for r in mat[1:]:
                if len(r) < 6:
                    continue
                time = _parse_time_hhmm(r[0])
                site = _clean(r[1]).upper()
                sysv = _parse_float(r[2])
                diasv = _parse_float(r[3])
                endv = _parse_float(r[4])
                meanv = _parse_float(r[5])
                a_wave = _parse_float(r[6]) if len(r) > 6 else None
                v_wave = _parse_float(r[7]) if len(r) > 7 else None
                maxdpdt = _parse_float(r[8]) if len(r) > 8 else None
                hr = _parse_float(r[9]) if len(r) > 9 else None
                payload["timeseries"]["pressures"].append(
                    {
                        "time": time,
                        "site": site,
                        "sys": sysv,
                        "dia": diasv,
                        "end": endv,
                        "mean": meanv,
                        "a_wave": a_wave,
                        "v_wave": v_wave,
                        "max_dpdt": maxdpdt,
                        "hr": hr,
                    }
                )

    # 3) Phase summary tables
    def _parse_pressure_summary() -> None:
        mat = _find_table_by_title(tables, "Für Berechnung benutzte Druckwerte")
        if not mat:
            return
        payload["raw_tables"]["pressure_summary"] = mat
        phases, rows = _extract_phase_table(mat)
        for pk in phases:
            payload["phases"].setdefault(pk, {})["pressures"] = {}
        for label, colmap in rows.items():
            lab = _clean(label).upper()
            for pk, raw in colmap.items():
                if pk not in payload["phases"]:
                    continue
                if lab == "RA":
                    payload["phases"][pk]["pressures"]["ra"] = _parse_a_v_mean(raw)
                elif lab in ("PCW", "PAWP", "PCWP", "WEDGE"):
                    payload["phases"][pk]["pressures"]["pcw"] = _parse_a_v_mean(raw)
                elif lab == "PA":
                    payload["phases"][pk]["pressures"]["pa"] = _parse_sys_dia_mean(raw)
                elif lab == "RV":
                    payload["phases"][pk]["pressures"]["rv"] = _parse_rv_sys_dia_edp(raw)
                else:
                    payload["phases"][pk]["pressures"][lab.lower()] = {"raw": raw}

    def _parse_co() -> None:
        mat = _find_table_by_title(tables, "Herzzeitvolumen")
        if not mat:
            return
        payload["raw_tables"]["co_table"] = mat
        phases, rows = _extract_phase_table(mat)
        for pk in phases:
            payload["phases"].setdefault(pk, {})["co"] = {}
        for label, colmap in rows.items():
            lab = _lower_key(label)
            for pk, raw in colmap.items():
                if pk not in payload["phases"]:
                    continue
                if "tdhzv" in lab:
                    payload["phases"][pk]["co"]["td_co"] = _parse_float(raw)
                elif "tdci" in lab:
                    payload["phases"][pk]["co"]["td_ci"] = _parse_float(raw)
                elif "fick-hzv" in lab or ("fick" in lab and "hzv" in lab):
                    payload["phases"][pk]["co"]["fick_co"] = _parse_float(raw)
                elif "fick-ci" in lab or ("fick" in lab and "ci" in lab):
                    payload["phases"][pk]["co"]["fick_ci"] = _parse_float(raw)
                elif "fick-hf" in lab:
                    payload["phases"][pk]["co"]["fick_hr"] = _parse_float(raw)
                elif (("td" in lab) and ("hf" in lab) and ("fick" not in lab)) or ("td-hf" in lab) or ("tdhf" in lab):
                    payload["phases"][pk]["co"]["td_hr"] = _parse_float(raw)
                elif (("td" in lab) and ("sv" in lab) and ("fick" not in lab)) or ("td-sv" in lab) or ("tdsv" in lab):
                    payload["phases"][pk]["co"]["td_sv_ml"] = _parse_float(raw)
                elif (("td" in lab) and ("svi" in lab) and ("fick" not in lab)) or ("td-svi" in lab) or ("tdsvi" in lab):
                    payload["phases"][pk]["co"]["td_svi_ml_m2"] = _parse_float(raw)
                elif ("kof" in lab) or ("bsa" in lab) or ("körperoberfläche" in lab) or ("koerperoberflaeche" in lab):
                    payload["phases"][pk]["co"]["bsa_m2"] = _parse_float(raw)
                elif ("fick" in lab and "sv" in lab):
                    payload["phases"][pk]["co"]["fick_sv_ml"] = _parse_float(raw)
                elif ("fick" in lab and "svi" in lab):
                    payload["phases"][pk]["co"]["fick_svi_ml_m2"] = _parse_float(raw)

    def _parse_resistance() -> None:
        mat = _find_table_by_title(tables, "Widerstandsergebnisse")
        if not mat:
            return
        payload["raw_tables"]["resistance_table"] = mat
        phases, rows = _extract_phase_table(mat)
        for pk in phases:
            payload["phases"].setdefault(pk, {})["resistance"] = {}
        for label, colmap in rows.items():
            lab = _lower_key(label)
            for pk, raw in colmap.items():
                if pk not in payload["phases"]:
                    continue
                if lab.startswith("pvr-i") or "pvr-i" in lab:
                    payload["phases"][pk]["resistance"]["pvri"] = _parse_resistance_dyn_wu(raw)
                elif lab.startswith("pvr"):
                    payload["phases"][pk]["resistance"]["pvr"] = _parse_resistance_dyn_wu(raw)
                elif lab.startswith("tpr-i") or "tpr-i" in lab:
                    payload["phases"][pk]["resistance"]["tpri"] = _parse_resistance_dyn_wu(raw)
                elif lab.startswith("tpr"):
                    payload["phases"][pk]["resistance"]["tpr"] = _parse_resistance_dyn_wu(raw)
                elif lab.startswith("tvr"):
                    payload["phases"][pk]["resistance"]["tvr"] = _parse_resistance_dyn_wu(raw)
                else:
                    payload["phases"][pk]["resistance"][lab] = {"raw": raw}

    def _parse_flow() -> None:
        mat = _find_table_by_title(tables, "Blutfluss")
        if not mat:
            return
        payload["raw_tables"]["flow_table"] = mat
        phases, rows = _extract_phase_table(mat)
        for pk in phases:
            payload["phases"].setdefault(pk, {})["flow"] = {}
        for label, colmap in rows.items():
            lab = _lower_key(label)
            for pk, raw in colmap.items():
                if pk not in payload["phases"]:
                    continue
                if lab.startswith("vo2"):
                    payload["phases"][pk]["flow"]["vo2_ml_min"] = _parse_float(raw)
                elif "vo2 quelle" in lab:
                    payload["phases"][pk]["flow"]["vo2_source"] = _clean(raw) or None
                elif "a-vo2" in lab or "a vo2" in lab:
                    payload["phases"][pk]["flow"]["avo2diff_ml_dl"] = _parse_float(raw)
                elif "fick-hzv" in lab:
                    payload["phases"][pk]["flow"]["fick_co_repeat"] = _parse_float(raw)
                elif "qp/qs" in lab or "qpqs" in lab:
                    payload["phases"][pk]["flow"]["qp_qs"] = _parse_float(raw)
                elif lab.strip() == "qp" or lab.startswith("qp "):
                    payload["phases"][pk]["flow"]["qp_l_min"] = _parse_float(raw)
                elif lab.strip() == "qs" or lab.startswith("qs "):
                    payload["phases"][pk]["flow"]["qs_l_min"] = _parse_float(raw)
                else:
                    payload["phases"][pk]["flow"][lab] = raw

    def _parse_work() -> None:
        mat = _find_table_by_title(tables, "Schlagarbeit")
        if not mat:
            return
        payload["raw_tables"]["work_table"] = mat
        phases, rows = _extract_phase_table(mat)
        for pk in phases:
            payload["phases"].setdefault(pk, {})["work"] = {}
        for label, colmap in rows.items():
            lab = _lower_key(label)
            for pk, raw in colmap.items():
                if pk not in payload["phases"]:
                    continue
                if lab.startswith("rvsw-i") or "rvsw-i" in lab or lab.startswith("rvswi") or "rvswi" in lab:
                    payload["phases"][pk]["work"]["rvswi_gm_m2"] = _parse_float(raw)
                elif lab.startswith("rvsw") or "rvsw" in lab:
                    payload["phases"][pk]["work"]["rvsw_gm"] = _parse_float(raw)
                elif lab.startswith("lvsw-i") or "lvsw-i" in lab or lab.startswith("lvswi") or "lvswi" in lab:
                    payload["phases"][pk]["work"]["lvswi_gm_m2"] = _parse_float(raw)
                elif lab.startswith("lvsw") or "lvsw" in lab:
                    payload["phases"][pk]["work"]["lvsw_gm"] = _parse_float(raw)
                else:
                    payload["phases"][pk]["work"][lab] = raw

    _parse_pressure_summary()
    _parse_co()
    _parse_resistance()
    _parse_work()
    _parse_flow()

    # 4) Canonical rest values (Base 2 only)
    base2 = payload["phases"].get("base2") or {}

    def _dig(phase_obj: Any, obj_path: Tuple[str, ...]) -> Optional[float]:
        cur = phase_obj
        for k in obj_path:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur if isinstance(cur, (int, float)) else None

    pa_sys = _dig(base2, ("pressures", "pa", "sys"))
    pa_dia = _dig(base2, ("pressures", "pa", "dia"))
    pa_mean = _dig(base2, ("pressures", "pa", "mean"))
    pcw_mean = _dig(base2, ("pressures", "pcw", "mean"))
    ra_mean = _dig(base2, ("pressures", "ra", "mean"))

    co_td = _dig(base2, ("co", "td_co"))
    ci_td = _dig(base2, ("co", "td_ci"))
    co_fick = _dig(base2, ("co", "fick_co"))
    ci_fick = _dig(base2, ("co", "fick_ci"))

    pvr_wu: Optional[float] = None
    pvr_dyn: Optional[float] = None
    pvr_node = (base2.get("resistance", {}) or {}).get("pvr") if isinstance(base2, dict) else None
    if isinstance(pvr_node, dict):
        pvr_wu = pvr_node.get("wu") if isinstance(pvr_node.get("wu"), (int, float)) else None
        pvr_dyn = pvr_node.get("dyn") if isinstance(pvr_node.get("dyn"), (int, float)) else None

    payload["canonical"] = {
        "rest_phase": "base2",
        "rest": {
            "spap": pa_sys,
            "dpap": pa_dia,
            "mpap": pa_mean,
            "pawp": pcw_mean,
            "rap": ra_mean,
            "co_td": co_td,
            "ci_td": ci_td,
            "co_fick": co_fick,
            "ci_fick": ci_fick,
            "pvr_wu": pvr_wu,
            "pvr_dyn": pvr_dyn,
        },
    }

    # 5) Quality checks
    q = payload["quality"]
    if not (payload["phases"].get("base2") or {}).get("pressures"):
        q["status"] = "yellow"
        q["reasons"].append(
            "Base 2 nicht gefunden oder unvollständig; es werden keine Hämodynamik-Ruhewerte aus Base 1 übernommen."
        )

    if payload["canonical"]["rest"]["mpap"] is None or payload["canonical"]["rest"]["pawp"] is None:
        q["status"] = "yellow"
        q["reasons"].append("Ruhe Druckwerte unvollständig (mPAP oder PAWP fehlt).")

    if payload["canonical"]["rest"]["co_td"] is None and payload["canonical"]["rest"]["co_fick"] is None:
        q["status"] = "yellow"
        q["reasons"].append("HZV fehlt (TD und Fick nicht gefunden).")

    # PVR check if available
    mpap = payload["canonical"]["rest"]["mpap"]
    pawp = payload["canonical"]["rest"]["pawp"]
    co_for_calc = payload["canonical"]["rest"]["co_td"]
    if co_for_calc is None:
        co_for_calc = payload["canonical"]["rest"]["co_fick"]

    if mpap is not None and pawp is not None and co_for_calc is not None and co_for_calc != 0:
        pvr_calc = (mpap - pawp) / co_for_calc
        pvr_doc = payload["canonical"]["rest"]["pvr_wu"]
        if (pvr_doc is not None) and isinstance(pvr_doc, (int, float)):
            try:
                pvr_doc_f = float(pvr_doc)
                if pvr_doc_f > 0 and abs(pvr_calc - pvr_doc_f) > 0.5 and abs(pvr_calc - pvr_doc_f) / max(pvr_doc_f, 0.1) > 0.15:
                    q["status"] = "yellow"
                    q["warnings"].append("PVR Kontrollrechnung weicht auffällig von Dokumentwert ab.")
                    q["reasons"].append("Kontrollrechnung PVR Abweichung.")
            except Exception:
                pass

    return payload


def map_payload_to_ui(payload: Dict[str, Any], target: str = "current") -> Dict[str, Any]:
    """Map extracted payload to existing UI keys.

    target:
      - "current": fill main fields (mpap_rest, pawp_rest, ...)
      - "prev": fill prev_* fields for Vergleich
    """
    ui: Dict[str, Any] = {}
    pat = payload.get("patient") or {}
    can = payload.get("canonical") or {}
    rest = (can.get("rest") or {})

    if target == "current":
        # Demography / meta
        if pat.get("age_years") is not None:
            ui["age"] = pat.get("age_years")
        if pat.get("sex"):
            ui["sex"] = pat.get("sex")
        if pat.get("height_cm") is not None:
            ui["height_cm"] = pat.get("height_cm")
        if pat.get("weight_kg") is not None:
            ui["weight_kg"] = pat.get("weight_kg")

        # Best effort: BP + HR from last vitals row
        vitals = (payload.get("timeseries") or {}).get("vitals") or []
        if vitals:
            last_candidates = [v for v in vitals if v.get("bp_sys") is not None or v.get("hr") is not None]
            last = last_candidates[-1] if last_candidates else vitals[-1]
            if last.get("bp_sys") is not None:
                ui["bp_sys"] = last.get("bp_sys")
            if last.get("bp_dia") is not None:
                ui["bp_dia"] = last.get("bp_dia")
            if last.get("bp_mean") is not None:
                ui["bp_mean"] = last.get("bp_mean")
            if last.get("hr") is not None:
                ui["hr"] = last.get("hr")
            if last.get("spo2") is not None:
                ui["spo2"] = last.get("spo2")

        # Hb: prefer arterial (ART/AO). If multiple exist, take the latest timestamp.
        bgs = (payload.get("timeseries") or {}).get("bloodgas") or []
        hb = None
        best_t = -1
        for r in bgs:
            site = (r.get("site") or "").upper()
            if site in ("ART", "AO", "AORTA"):
                t = _hhmm_to_minutes(r.get("time"))
                if r.get("hb_g_dl") is not None and t >= best_t:
                    hb = r.get("hb_g_dl")
                    best_t = t
        if hb is None:
            for r in bgs:
                t = _hhmm_to_minutes(r.get("time"))
                if r.get("hb_g_dl") is not None and t >= best_t:
                    hb = r.get("hb_g_dl")
                    best_t = t
        if hb is not None:
            ui["hb_g_dl"] = hb

        if pat.get("exam_date"):
            ui["rhk_date"] = pat.get("exam_date")

        # Hemodynamics rest (Base 2 only)
        if rest.get("spap") is not None:
            ui["spap_rest"] = rest.get("spap")
        if rest.get("dpap") is not None:
            ui["dpap_rest"] = rest.get("dpap")
        if rest.get("mpap") is not None:
            ui["mpap_rest"] = rest.get("mpap")
        if rest.get("pawp") is not None:
            ui["pawp_rest"] = rest.get("pawp")
        if rest.get("rap") is not None:
            ui["rap_rest"] = rest.get("rap")

        # CO/CI/PVR (prefer TD, else Fick)
        co = rest.get("co_td") if rest.get("co_td") is not None else rest.get("co_fick")
        ci = rest.get("ci_td") if rest.get("ci_td") is not None else rest.get("ci_fick")
        if rest.get("co_td") is not None:
            ui["co_method"] = "Thermodilution"
        elif rest.get("co_fick") is not None:
            ui["co_method"] = "Fick"
        if co is not None:
            ui["co_rest"] = co
        if ci is not None:
            ui["ci_rest"] = ci
        if rest.get("pvr_wu") is not None:
            ui["pvr_rest"] = rest.get("pvr_wu")

        # Step-up / saturations from bloodgas (latest per site)
        try:
            bg = (payload.get("timeseries") or {}).get("bloodgas") or []
            if isinstance(bg, list) and bg:
                def _tmin(hhmm: str) -> int:
                    try:
                        if not hhmm:
                            return -1
                        h, m = hhmm.split(":")
                        return int(h) * 60 + int(m)
                    except (TypeError, ValueError, AttributeError):
                        return -1

                best: Dict[str, Tuple[int, Any]] = {}
                for row in bg:
                    if not isinstance(row, dict):
                        continue
                    site = str(row.get("site") or "").strip()
                    sat = row.get("sat_pct") if row.get("sat_pct") is not None else row.get("sat")
                    if sat is None:
                        continue
                    t = _tmin(str(row.get("time") or ""))
                    k = _lower_key(site)

                    if k in ("svc", "vcs", "vc"):
                        key = "svc"
                    elif k in ("ivc", "vci"):
                        key = "ivc"
                    elif k in ("ra",):
                        key = "ra"
                    elif k in ("rv",):
                        key = "rv"
                    elif k in ("pa", "a. pulmonalis", "pulmonalarterie"):
                        key = "pa"
                    elif k in ("art", "ao", "aorta", "arteriell"):
                        key = "ao"
                    elif k in ("ven", "mv", "mixed", "mixed venous"):
                        key = "mv"
                    else:
                        continue

                    prev = best.get(key)
                    if prev is None or t >= prev[0]:
                        best[key] = (t, sat)

                if "svc" in best:
                    ui["sat_svc"] = best["svc"][1]
                if "ivc" in best:
                    ui["sat_ivc"] = best["ivc"][1]
                if "ra" in best:
                    ui["sat_ra"] = best["ra"][1]
                if "rv" in best:
                    ui["sat_rv"] = best["rv"][1]
                if "pa" in best:
                    ui["sat_pa"] = best["pa"][1]
                elif "mv" in best:
                    ui["sat_pa"] = best["mv"][1]
                if "ao" in best:
                    ui["sat_ao"] = best["ao"][1]
        except Exception:
            pass

        # Additional phases
        phases = payload.get("phases") or {}
        if "exercise" in phases and (phases["exercise"] or {}).get("pressures"):
            ui["exercise_done"] = True
            pa = phases["exercise"].get("pressures", {}).get("pa") or {}
            pcw = phases["exercise"].get("pressures", {}).get("pcw") or {}
            if pa.get("sys") is not None:
                ui["spap_peak"] = pa.get("sys")
            if pa.get("dia") is not None:
                ui["dpap_peak"] = pa.get("dia")
            if pa.get("mean") is not None:
                ui["mpap_peak"] = pa.get("mean")
            if pcw.get("mean") is not None:
                ui["pawp_peak"] = pcw.get("mean")

            co_ex = phases["exercise"].get("co", {}).get("td_co") or phases["exercise"].get("co", {}).get("fick_co")
            ci_ex = phases["exercise"].get("co", {}).get("td_ci") or phases["exercise"].get("co", {}).get("fick_ci")
            if co_ex is not None:
                ui["co_peak"] = co_ex
            if ci_ex is not None:
                ui["ci_peak"] = ci_ex

        if "post" in phases and (phases["post"] or {}).get("pressures"):
            ui["volume_challenge_done"] = True
            # pre from rest, post from post
            if rest.get("pawp") is not None:
                ui["pawp_pre"] = rest.get("pawp")
            if rest.get("mpap") is not None:
                ui["mpap_pre"] = rest.get("mpap")
            pcw = phases["post"].get("pressures", {}).get("pcw") or {}
            pa = phases["post"].get("pressures", {}).get("pa") or {}
            if pcw.get("mean") is not None:
                ui["pawp_post"] = pcw.get("mean")
            if pa.get("mean") is not None:
                ui["mpap_post"] = pa.get("mean")

    else:
        # prev mapping: use Base 2 only (never Base 1)
        if pat.get("exam_date"):
            ui["prev_rhk_date"] = pat.get("exam_date")

        if rest.get("spap") is not None:
            ui["prev_spap"] = rest.get("spap")
        if rest.get("dpap") is not None:
            ui["prev_dpap"] = rest.get("dpap")
        if rest.get("mpap") is not None:
            ui["prev_mpap"] = rest.get("mpap")
        if rest.get("pawp") is not None:
            ui["prev_pawp"] = rest.get("pawp")
        if rest.get("rap") is not None:
            ui["prev_rap"] = rest.get("rap")

        co = rest.get("co_td") if rest.get("co_td") is not None else rest.get("co_fick")
        ci = rest.get("ci_td") if rest.get("ci_td") is not None else rest.get("ci_fick")
        if co is not None:
            ui["prev_co"] = co
        if ci is not None:
            ui["prev_ci"] = ci
        if rest.get("pvr_wu") is not None:
            ui["prev_pvr"] = rest.get("pvr_wu")

    # Import meta (for UI status)
    q = payload.get("quality") or {}
    ui["docx_import_status"] = q.get("status")
    ui["docx_import_reasons"] = "; ".join(q.get("reasons") or [])

    # Final: sanitize numeric keys (fehlend≠0, unphys→None) without touching strings/flags.
    ui = sanitize_ui_numbers(ui)
    return ui
