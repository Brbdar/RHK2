#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOCX Importer für RHK-Befunde (GE MacLab Word Export).

Designziele:
- Nur Tabellen werden ausgewertet (Fließtext wird ignoriert).
- Base 2 ist die einzige Quelle für die in der App zu berechnenden Hämodynamik-Ruhewerte.
  Es werden niemals Ruhewerte aus Base 1 in berechnungsrelevante Felder übernommen.
- Unterstützt zusätzliche Phasen: Ergometrie, Post-Intervention (z.B. Volumenchallenge), NO/O2 (falls als Spalte vorhanden).
- Vollständige Rohdaten (Tabellen) werden gespeichert, UI wird jedoch nur schlank befüllt.
- Hohe Robustheit bei Dezimaltrennzeichen (Komma/Punkt) und leicht variierenden Tabellen.

Rückgabeformat:
{
  "ui": {...},                 # direkt in die App-Felder mappbar (Teilmenge)
  "payload": {...},            # vollständige strukturierte Extraktion
  "quality": {...},            # Ampel + Gründe + Warnungen
}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import re
from datetime import datetime

try:
    from docx import Document  # type: ignore
except ModuleNotFoundError:
    Document = None  # type: ignore

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _clean(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("\xa0", " ").strip()

def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", _clean(s))

def _lower_key(s: str) -> str:
    return re.sub(r"\s+", " ", _clean(s)).lower()

def _parse_float(s: Any) -> Optional[float]:
    txt = _clean(s)
    if txt == "":
        return None
    # remove units and parentheses content unless it's a pure number inside parentheses handled elsewhere
    txt = txt.strip()
    # keep digits, comma, dot, minus
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
        return float(txt2)
    except Exception:
        return None

def _parse_int(s: Any) -> Optional[int]:
    f = _parse_float(s)
    if f is None:
        return None
    try:
        return int(round(f))
    except Exception:
        return None

def _parse_date_to_ddmmyyyy(s: Any) -> Optional[str]:
    txt = _clean(s)
    if txt == "":
        return None
    txt = txt.replace("/", ".")
    # find a date like dd.mm.yyyy
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", txt)
    if not m:
        return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if len(y) == 2:
        y = "20" + y
    try:
        dt = datetime(int(y), int(mo), int(d))
        return dt.strftime("%d.%m.%Y")
    except Exception:
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
    except Exception:
        return -1


def _split_label_value(cell_text: str) -> Tuple[str, str]:
    """Return (label, value) from a MacLab cell, usually 'Label\\nValue'."""
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
    hh = hh.replace("post intervention", "post-intervention")
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
    if "no" == hh or "ino" in hh:
        return "no"
    if "o2" == hh or "oxygen" in hh:
        return "o2"
    # fallback slug
    hh = hh.replace(" ", "_").replace("-", "_")
    return hh or "phase"

def _parse_sys_dia_mean(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 54/23 (33) or 177/80/115
    s = _clean(txt)
    out = {"sys": None, "dia": None, "mean": None}
    if s == "":
        return out
    # patterns with parentheses
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    # patterns with 3 slash numbers
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    # patterns with 2 slash numbers
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        return out
    # single
    out["mean"] = _parse_float(s)
    return out

def _parse_a_v_mean(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 24/22 (18)
    s = _clean(txt)
    out = {"a": None, "v": None, "mean": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["a"] = _parse_float(m.group(1))
        out["v"] = _parse_float(m.group(2))
        out["mean"] = _parse_float(m.group(3))
        return out
    # sometimes mean only
    out["mean"] = _parse_float(s)
    return out

def _parse_rv_sys_dia_edp(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 55/1/9
    s = _clean(txt)
    out = {"sys": None, "dia": None, "edp": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*/\s*([\-0-9\.,]+)\s*$", s)
    if m:
        out["sys"] = _parse_float(m.group(1))
        out["dia"] = _parse_float(m.group(2))
        out["edp"] = _parse_float(m.group(3))
        return out
    # fallback
    out["sys"] = _parse_float(s)
    return out

def _parse_resistance_dyn_wu(txt: str) -> Dict[str, Optional[float]]:
    # e.g. 287,93 (3,6)
    s = _clean(txt)
    out = {"dyn": None, "wu": None}
    if s == "":
        return out
    m = re.match(r"\s*([\-0-9\.,]+)\s*\(\s*([\-0-9\.,]+)\s*\)\s*$", s)
    if m:
        out["dyn"] = _parse_float(m.group(1))
        out["wu"] = _parse_float(m.group(2))
        return out
    # if only one number, store as wu (most user facing)
    val = _parse_float(s)
    out["wu"] = val
    return out


# ---------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------

def _table_matrix(t) -> List[List[str]]:
    return [[_clean(c.text) for c in row.cells] for row in t.rows]

def _is_vitals_header(row: List[str]) -> bool:
    header = " ".join(row)
    h = _lower_key(header)
    return ("spo2" in h) and ("hf" in h) and ("bd" in h) and ("zeit" in h)

def _is_bloodgas_header(row: List[str]) -> bool:
    header = " ".join(row)
    h = _lower_key(header)
    return ("hb" in h) and ("sätt" in h or "satt" in h) and ("po2" in h) and ("zeit" in h) and ("ort" in h)

def _is_pressure_header(row: List[str]) -> bool:
    header = " ".join(row)
    h = _lower_key(header)
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
    """
    Returns phases + mapping[row_label][phase_key] = raw_cell
    Expects mat[0] = [title, phase1, phase2, ...]
    """
    header = mat[0]
    phases: List[str] = []
    col_keys: List[str] = []
    for h in header[1:]:
        if _clean(h) == "":
            continue
        pk = _to_phase_key(h)
        phases.append(pk)
        col_keys.append(pk)
    rows: Dict[str, Dict[str, str]] = {}
    for r in mat[1:]:
        if not r:
            continue
        row_label = _clean(r[0])
        if row_label == "":
            continue
        row_map: Dict[str, str] = {}
        # iterate through same number of columns; ignore trailing empties
        for j, pk in enumerate(col_keys, start=1):
            if j < len(r):
                row_map[pk] = _clean(r[j])
        rows[row_label] = row_map
    return phases, rows


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def parse_maclab_docx(path: str) -> Dict[str, Any]:
    # Lazy dependency guard: keep the app usable even if python-docx is not installed.
    if Document is None:
        # Dependency guard: keep the app usable even if python-docx is not installed.
        # The frontend can still run; DOCX import will show an actionable error.
        return {
            "ok": False,
            "error": "python-docx fehlt. Bitte `pip install -r requirements.txt` ausführen (oder `pip install python-docx`).",
            "source": {"path": path},
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
                "status": "red",
                "reasons": ["python-docx fehlt (Import nicht möglich)."],
            },
        }

    doc = Document(path)
    tables = [_table_matrix(t) for t in doc.tables]

    # Keep ALL tables for auditability and to ensure nothing is "lost".
    # Each entry contains the original matrix plus a best-effort title (first cell).
    all_tables = []
    for i, mat in enumerate(tables):
        title = mat[0][0] if (mat and mat[0]) else ""
        all_tables.append({"index": i, "title": title, "matrix": mat})
    
    payload: Dict[str, Any] = {
        "source": {"path": path},
        "patient": {},
        "timeseries": {"vitals": [], "bloodgas": [], "pressures": []},
        "phases": {},
        "raw_tables": {},
    }

    payload["raw_tables"]["all_tables"] = all_tables

    # 1) Patient info (prefer structured 2x6 table)
    patient_tbl = None
    for mat in tables:
        if len(mat) == 2 and len(mat[0]) >= 6:
            flat0 = " ".join(mat[0])
            if ("Patientenname" in flat0) and ("Untersuch" in flat0):
                patient_tbl = mat
                break
    if patient_tbl:
        payload["raw_tables"]["patient_info"] = patient_tbl
        row = patient_tbl[1]
        def _cell_val(i) -> str:
            return _split_label_value(row[i])[1] if i < len(row) else ""
        dob = _parse_date_to_ddmmyyyy(_cell_val(0))
        age_txt = _cell_val(1)
        age = _parse_int(age_txt)
        sex_raw = _cell_val(2)
        sex = None
        sxl = _lower_key(sex_raw)
        if "weib" in sxl or "female" in sxl:
            sex = "weiblich"
        elif "männ" in sxl or "mann" in sxl or "male" in sxl:
            sex = "männlich"
        elif "div" in sxl:
            sex = None  # divers nicht unterstützt
        # height/weight cells may contain imperial units in parentheses; take first numeric token
        height = _parse_float(re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", _cell_val(3)).group(1)) if re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", _cell_val(3)) else _parse_float(_cell_val(3))
        weight = _parse_float(re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", _cell_val(4)).group(1)) if re.search(r"([0-9]{2,3}[\.,]?[0-9]*)", _cell_val(4)) else _parse_float(_cell_val(4))
        bsa = _parse_float(_cell_val(5))
        # exam date in header row cell 2 (index 2)
        exam_date = _parse_date_to_ddmmyyyy(patient_tbl[0][2] if len(patient_tbl[0]) > 2 else "")
        # identifiers
        patient_name = _cell_val(1)  # table often duplicates; safer from cell 1? but here it's age; so fallback below
        # extract patient name from header row cell 1 (index 1)
        # In examples: header[1] is "Patientenname" label only, value is in row[1]? Actually row[1] is "Alter..".
        # So we parse name from row0 cell1? If present.
        name_cell = patient_tbl[0][1] if len(patient_tbl[0]) > 1 else ""
        # Often not containing value. There may be another single-cell patient-info table. We'll fill later.
        payload["patient"] = {
            "dob": dob,
            "age_years": age,
            "sex": sex,
            "height_cm": height,
            "weight_kg": weight,
            "bsa_m2": bsa,
            "exam_date": exam_date,
        }

        # IDs
        pat_record = _split_label_value(patient_tbl[0][3])[1] if len(patient_tbl[0]) > 3 else ""
        study_nr = _split_label_value(patient_tbl[0][4])[1] if len(patient_tbl[0]) > 4 else ""
        admission = _split_label_value(patient_tbl[0][5])[1] if len(patient_tbl[0]) > 5 else ""
        payload["patient"].update({
            "pat_record_id": pat_record or None,
            "study_id": study_nr or None,
            "admission_id": admission or None,
        })

    # Fallback: single-cell patient info
    if not payload["patient"].get("exam_date"):
        for mat in tables:
            if mat and len(mat[0]) == 1 and "Patienteninformationen" in mat[0][0]:
                # second row contains multi-line text
                blob = " ".join(mat[1]) if len(mat) > 1 else ""
                ex = _parse_date_to_ddmmyyyy(blob)
                payload["patient"]["exam_date"] = payload["patient"].get("exam_date") or ex

                # Demografie aus Textblock (robust gegen variable Whitespace/Tabulatoren)
                db = _parse_date_to_ddmmyyyy(re.search(r"Geburtsdatum\s*([0-9./]+)", blob).group(1)) if re.search(r"Geburtsdatum\s*([0-9./]+)", blob) else None
                payload["patient"]["dob"] = payload["patient"].get("dob") or db

                # Alter (Jahre)
                age = _parse_int(re.search(r"Alter\s*([0-9]{1,3})", blob).group(1)) if re.search(r"Alter\s*([0-9]{1,3})", blob) else None
                if payload["patient"].get("age_years") is None and age is not None:
                    payload["patient"]["age_years"] = age

                # Geschlecht
                sex_raw = re.search(r"Geschlecht\s*([A-Za-zÄÖÜäöüß]+)", blob)
                sex = None
                if sex_raw:
                    sxl = _lower_key(sex_raw.group(1))
                    if "weib" in sxl or "female" in sxl:
                        sex = "weiblich"
                    elif "männ" in sxl or "mann" in sxl or "male" in sxl:
                        sex = "männlich"
                    elif "div" in sxl:
                        sex = None  # divers nicht unterstützt
                if payload["patient"].get("sex") is None and sex is not None:
                    payload["patient"]["sex"] = sex

                # Größe / Gewicht / KOF
                h = _parse_float(re.search(r"Größe\s*([0-9]{2,3}[\.,]?[0-9]*)\s*cm", blob).group(1)) if re.search(r"Größe\s*([0-9]{2,3}[\.,]?[0-9]*)\s*cm", blob) else None
                w = _parse_float(re.search(r"Gewicht\s*([0-9]{2,3}[\.,]?[0-9]*)\s*kg", blob).group(1)) if re.search(r"Gewicht\s*([0-9]{2,3}[\.,]?[0-9]*)\s*kg", blob) else None
                bsa = _parse_float(re.search(r"KOF\s*([0-9]{1,2}[\.,]?[0-9]*)\s*m2", blob).group(1)) if re.search(r"KOF\s*([0-9]{1,2}[\.,]?[0-9]*)\s*m2", blob) else None
                if payload["patient"].get("height_cm") is None and h is not None:
                    payload["patient"]["height_cm"] = h
                if payload["patient"].get("weight_kg") is None and w is not None:
                    payload["patient"]["weight_kg"] = w
                if payload["patient"].get("bsa_m2") is None and bsa is not None:
                    payload["patient"]["bsa_m2"] = bsa

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
                payload["timeseries"]["vitals"].append({
                    "time": time, "spo2": spo2, "hr": hr,
                    "bp_sys": bd.get("sys"), "bp_dia": bd.get("dia"), "bp_mean": bd.get("mean"),
                    "af": af,
                })

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
                payload["timeseries"]["bloodgas"].append({
                    "time": time, "site": ort, "hb_g_dl": hb, "sat_pct": sat, "po2_mmhg": po2,
                    "content_ml_dl": content, "group": group or None,
                })

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
                payload["timeseries"]["pressures"].append({
                    "time": time, "site": site, "sys": sysv, "dia": diasv, "end": endv,
                    "mean": meanv, "a_wave": a_wave, "v_wave": v_wave, "max_dpdt": maxdpdt, "hr": hr,
                })

    # 3) Phase summary tables
    def _parse_pressure_summary():
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
                    # generic attempt
                    payload["phases"][pk]["pressures"][lab.lower()] = {"raw": raw}
    def _parse_co():
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
    def _parse_resistance():
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
    def _parse_flow():
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
                elif "vo2 quelle" in lab or "vo2 quelle" in lab:
                    payload["phases"][pk]["flow"]["vo2_source"] = _clean(raw) or None
                elif "a-vo2" in lab or "a vo2" in lab:
                    payload["phases"][pk]["flow"]["avo2diff_ml_dl"] = _parse_float(raw)
                elif "fick-hzv" in lab:
                    payload["phases"][pk]["flow"]["fick_co_repeat"] = _parse_float(raw)
                else:
                    payload["phases"][pk]["flow"][lab] = raw
    def _parse_work():
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
                if lab.startswith("rvsw-i") or "rvsw-i" in lab:
                    payload["phases"][pk]["work"]["rvswi_gm_m2"] = _parse_float(raw)
                elif lab.startswith("rvsw") or "rvsw" in lab:
                    payload["phases"][pk]["work"]["rvsw_gm"] = _parse_float(raw)
                else:
                    payload["phases"][pk]["work"][lab] = raw

    _parse_pressure_summary()
    _parse_co()
    _parse_resistance()
    _parse_work()
    _parse_flow()

    # 4) Derive a few canonical fields for UI mapping
    # IMPORTANT: For patient safety and reproducibility, the app's calculable rest hemodynamics
    # MUST come from Base 2 only (never from Base 1). Base 1 is kept in payload for transparency.
    rest_pk = "base2"

    def _get_phase(pk: str) -> Dict[str, Any]:
        return payload["phases"].get(pk) or {}
    base1 = _get_phase("base1")
    base2 = _get_phase("base2")

    # helper to get a key from Base 2 ONLY (no fallback)
    def _pick_base2(obj_path: Tuple[str, ...]) -> Optional[float]:
        def _dig(phase_obj):
            cur = phase_obj
            for k in obj_path:
                if not isinstance(cur, dict) or k not in cur:
                    return None
                cur = cur[k]
            return cur
        return _dig(base2)

    # canonical rest values
    pa_sys = _pick_base2(("pressures","pa","sys"))
    pa_dia = _pick_base2(("pressures","pa","dia"))
    pa_mean = _pick_base2(("pressures","pa","mean"))
    pcw_mean = _pick_base2(("pressures","pcw","mean"))
    ra_mean = _pick_base2(("pressures","ra","mean"))

    co_td = _pick_base2(("co","td_co"))
    ci_td = _pick_base2(("co","td_ci"))
    co_fick = _pick_base2(("co","fick_co"))
    ci_fick = _pick_base2(("co","fick_ci"))
    pvr_wu = None
    pvr_dyn = None
    def _pick_res(key: str) -> Tuple[Optional[float], Optional[float]]:
        r = base2.get("resistance", {}).get(key) if "base2" in payload["phases"] else None
        if not isinstance(r, dict):
            r = None
        if r and (r.get("wu") is not None or r.get("dyn") is not None):
            return r.get("wu"), r.get("dyn")
        return None, None
    pvr_wu, pvr_dyn = _pick_res("pvr")

    payload["canonical"] = {
        "rest_phase": rest_pk,
        "rest": {
            "spap": pa_sys, "dpap": pa_dia, "mpap": pa_mean,
            "pawp": pcw_mean, "rap": ra_mean,
            "co_td": co_td, "ci_td": ci_td,
            "co_fick": co_fick, "ci_fick": ci_fick,
            "pvr_wu": pvr_wu, "pvr_dyn": pvr_dyn,
        }
    }

    # 5) Quality checks (kept minimal; UI decides how to display)
    quality: Dict[str, Any] = {"status": "green", "reasons": [], "warnings": []}

    # Base 2 policy (never backfill from Base 1)
    if not ("base2" in payload.get("phases", {}) and (payload["phases"].get("base2") or {}).get("pressures")):
        quality["status"] = "yellow"
        quality["reasons"].append(
            "Base 2 nicht gefunden oder unvollständig; es werden keine Hämodynamik-Ruhewerte aus Base 1 übernommen."
        )

    # essential: mpap, pawp, co
    if payload["canonical"]["rest"]["mpap"] is None or payload["canonical"]["rest"]["pawp"] is None:
        quality["status"] = "yellow"
        quality["reasons"].append("Ruhe Druckwerte unvollständig (mPAP oder PAWP fehlt).")
    if payload["canonical"]["rest"]["co_td"] is None and payload["canonical"]["rest"]["co_fick"] is None:
        quality["status"] = "yellow"
        quality["reasons"].append("HZV fehlt (TD und Fick nicht gefunden).")

    # pvr check if available
    mpap = payload["canonical"]["rest"]["mpap"]
    pawp = payload["canonical"]["rest"]["pawp"]
    co_for_calc = payload["canonical"]["rest"]["co_td"] or payload["canonical"]["rest"]["co_fick"]
    if mpap is not None and pawp is not None and co_for_calc:
        pvr_calc = (mpap - pawp) / co_for_calc if co_for_calc != 0 else None
        if pvr_calc is not None and payload["canonical"]["rest"]["pvr_wu"] is not None:
            if abs(pvr_calc - payload["canonical"]["rest"]["pvr_wu"]) > 0.5 and abs(pvr_calc - payload["canonical"]["rest"]["pvr_wu"]) / max(payload["canonical"]["rest"]["pvr_wu"], 0.1) > 0.15:
                quality["status"] = "yellow"
                quality["warnings"].append("PVR Kontrollrechnung weicht auffällig von Dokumentwert ab.")
                quality["reasons"].append("Kontrollrechnung PVR Abweichung.")

    payload["quality"] = quality
    return payload


def map_payload_to_ui(payload: Dict[str, Any], target: str = "current") -> Dict[str, Any]:
    """
    Map extracted payload to existing UI keys.
    target:
      - "current": fill main fields (mpap_rest, pawp_rest, ...)
      - "prev": fill prev_* fields for Vergleich
    """
    ui: Dict[str, Any] = {}
    pat = payload.get("patient") or {}
    can = payload.get("canonical") or {}
    rest = (can.get("rest") or {})

    # Demografie und Meta
    if target == "current":
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
            last = [v for v in vitals if v.get("bp_sys") is not None or v.get("hr") is not None]
            last = last[-1] if last else vitals[-1]
            if last.get("bp_sys") is not None:
                ui["bp_sys"] = last.get("bp_sys")
            if last.get("bp_dia") is not None:
                ui["bp_dia"] = last.get("bp_dia")
            if last.get("bp_mean") is not None:
                ui["bp_mean"] = last.get("bp_mean")
            if last.get("hr") is not None and 20 <= float(last.get("hr")) <= 220:
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

        # Untersuchung: rhk_date
        if pat.get("exam_date"):
            ui["rhk_date"] = pat.get("exam_date")

        # Hämodynamik Ruhe
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

        # CO CI PVR (primär TD, sonst Fick)
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

        # Stufenoxymetrie / Sättigungen (aus Blutgas-Timeseries; letzter verfügbarer Wert je Ort)
        try:
            bg = (payload.get("timeseries") or {}).get("bloodgas") or []
            if isinstance(bg, list) and bg:
                def _tmin(hhmm: str) -> int:
                    try:
                        if not hhmm:
                            return -1
                        h, m = hhmm.split(":")
                        return int(h) * 60 + int(m)
                    except Exception:
                        return -1
                best = {}  # key -> (tmin, sat)
                for row in bg:
                    if not isinstance(row, dict):
                        continue
                    site = str(row.get("site") or "").strip()
                    sat = row.get("sat_pct") if row.get("sat_pct") is not None else row.get("sat")
                    if sat is None:
                        continue
                    t = _tmin(str(row.get("time") or ""))
                    k = _lower_key(site)
                    # normalize site keys
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
                # PA bevorzugt aus 'pa', sonst 'mv'
                if "pa" in best:
                    ui["sat_pa"] = best["pa"][1]
                elif "mv" in best:
                    ui["sat_pa"] = best["mv"][1]
                if "ao" in best:
                    ui["sat_ao"] = best["ao"][1]
        except Exception:
            pass

        # Zusatzphasen
        phases = payload.get("phases") or {}
        if "exercise" in phases and phases["exercise"].get("pressures"):
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

        if "post" in phases and phases["post"].get("pressures"):
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
        if rest.get("mpap") is not None:
            ui["prev_mpap"] = rest.get("mpap")
        if rest.get("pawp") is not None:
            ui["prev_pawp"] = rest.get("pawp")
        if rest.get("rap") is not None:
            ui["prev_rap"] = rest.get("rap")
        ci = rest.get("ci_td") if rest.get("ci_td") is not None else rest.get("ci_fick")
        if rest.get("co_td") is not None:
            ui["co_method"] = "Thermodilution"
        elif rest.get("co_fick") is not None:
            ui["co_method"] = "Fick"
        if ci is not None:
            ui["prev_ci"] = ci
        if rest.get("pvr_wu") is not None:
            ui["prev_pvr"] = rest.get("pvr_wu")
    # small import meta (for UI status)
    q = payload.get("quality") or {}
    ui["docx_import_status"] = q.get("status")
    ui["docx_import_reasons"] = "; ".join(q.get("reasons") or [])
    return ui
