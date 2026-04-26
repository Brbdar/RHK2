#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Study checks for RHK Befundassistent.

Ziele
- Konservative, reproduzierbare Studien Pre Screen Hinweise.
- Nur auf Basis dokumentierter Felder aus der UI und abgeleiteter Werte.
- Fehlende Daten werden nicht imputiert.

Wichtig
- Es wird nie "geeignet" ausgegeben.
- Positivhinweis nur, wenn alle im Tool abbildbaren Kriterien erfuellt sind.
- Ausschluss wird nur bei dokumentierten Ausschlusskriterien ausgegeben.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rhk_validation import safe_float as _safe_float

# Reuse existing clinical helper logic if available.
_infer_anemia_base: Optional[Callable[[Optional[str], Optional[float]], Optional[bool]]]
try:
    from rhk_base import _infer_anemia as _infer_anemia_base
except Exception:  # pragma: no cover
    _infer_anemia_base = None


def _calc_bmi(height_cm: Optional[float], weight_kg: Optional[float]) -> Optional[float]:
    try:
        if height_cm is None or weight_kg is None:
            return None
        if height_cm <= 0 or weight_kg <= 0:
            return None
        h_m = height_cm / 100.0
        return float(weight_kg) / (h_m * h_m)
    except Exception:
        return None


def _infer_anemia(sex: Optional[str], hb_g_dl: Optional[float]) -> Optional[bool]:
    """Return True/False if inferable, else None.

    Wichtig
    - Es werden keine neuen Grenzwerte eingefuehrt.
    - Wenn der app weite Helper nicht verfuegbar ist oder Daten fehlen, None.
    """
    if hb_g_dl is None:
        return None
    if _infer_anemia_base is None:
        return None
    try:
        return bool(_infer_anemia_base(sex, hb_g_dl))
    except Exception:
        return None


def _tri_state(v: Any) -> str:
    """Map UI Auswahl auf yes/no/unk.

    Erwartete Werte (Dropdown)
    - "Unklar / nicht erhoben"
    - "Nein"
    - "Ja"
    """
    try:
        if v is None:
            return "unk"
        if isinstance(v, bool):
            return "yes" if v else "no"
        s = str(v).strip().lower()
        if s == "":
            return "unk"
        if "unklar" in s or "nicht erhoben" in s or "nicht bestimmt" in s:
            return "unk"
        if s.startswith("ja") or s == "ja":
            return "yes"
        if s.startswith("nein") or s == "nein":
            return "no"
        # Fallback
        return "unk"
    except Exception:
        return "unk"


def _novartis_hv_assess(case: Dict[str, Any]) -> Dict[str, Any]:
    """Assess Novartis healthy volunteer protocol based on captured fields.

    Rueckgabe
    - reasons: List[str] mit dokumentierten Ausschlussgruenden
    - eligible_hint: bool (nur wenn alle im Tool abbildbaren Kriterien erfuellt)

    Hinweis
    - Viele Protokollkriterien (z.B. QTc, Virologie) werden hier bewusst nicht
      bewertet, wenn sie separat geprueft werden.
    """
    ui = (case or {}).get("ui") or {}
    der = (case or {}).get("derived") or {}

    sex = (ui.get("sex") or "").strip().lower()

    age = _safe_float(ui.get("age"))
    height_cm = _safe_float(ui.get("height_cm"))
    weight_kg = _safe_float(ui.get("weight_kg"))

    bp_sys = _safe_float(ui.get("bp_sys"))
    bp_dia = _safe_float(ui.get("bp_dia"))
    hr = _safe_float(ui.get("hr"))

    bmi = _safe_float(der.get("bmi"))
    if bmi is None:
        bmi = _safe_float(ui.get("bmi"))
    if bmi is None:
        bmi = _calc_bmi(height_cm, weight_kg)

    egfr = _safe_float(der.get("egfr_ml_min_1_73"))
    if egfr is None:
        egfr = _safe_float(ui.get("egfr_ml_min_1_73"))

    hb = _safe_float(ui.get("hb_g_dl"))
    anemia = _infer_anemia(sex, hb)

    # Study specific click fields
    other_trial = _tri_state(ui.get("study_other_trial_recent"))
    blood_donation = _tri_state(ui.get("study_blood_donation_8w"))
    nicotine = _tri_state(ui.get("study_nicotine_active"))
    caffeine = _tri_state(ui.get("study_caffeine_gt800"))
    meds = _tri_state(ui.get("study_meds_supp_4w"))
    cannabis = _tri_state(ui.get("study_cannabis_4w"))
    misuse = _tri_state(ui.get("study_alcohol_substance_misuse_1y"))
    test_or_unwilling = _tri_state(ui.get("study_alcohol_drug_test_or_unwilling_72h"))
    cruciferous = _tri_state(ui.get("study_cruciferous_7d"))
    grapefruit = _tri_state(ui.get("study_grapefruit_14d"))
    pregnancy = _tri_state(ui.get("study_pregnancy_lactation"))

    liver_path = _tri_state(ui.get("study_liver_pathologic"))
    renal_path = _tri_state(ui.get("study_renal_pathologic"))

    childbearing_raw = (ui.get("study_childbearing_potential") or "").strip().lower()

    reasons: List[str] = []

    # Exclusions based on documented fields
    if other_trial == "yes":
        reasons.append("andere klinische Studie aktuell oder innerhalb 30 Tage")
    if nicotine == "yes":
        reasons.append("aktiver Nikotin oder Tabakkonsum")
    if blood_donation == "yes":
        reasons.append("Blut oder Plasmaspende in den letzten 8 Wochen")

    if meds == "yes":
        reasons.append("Medikamente Supplemente oder Vitamine in den letzten 4 Wochen")
    if cannabis == "yes":
        reasons.append("Cannabis in den letzten 4 Wochen")

    if misuse == "yes":
        reasons.append("Alkohol oder Substanzmissbrauch im letzten Jahr")
    if test_or_unwilling == "yes":
        reasons.append("positiver Alkohol oder Drogentest oder fehlende Abstinenzbereitschaft")

    if caffeine == "yes":
        reasons.append("Koffein >800 mg pro Tag")
    if cruciferous == "yes":
        reasons.append("Kreuzbluetler innerhalb 7 Tage")
    if grapefruit == "yes":
        reasons.append("Grapefruitsaft innerhalb 14 Tage")

    if pregnancy == "yes":
        reasons.append("Schwangerschaft oder Stillzeit")

    # Female specific exclusion: childbearing potential
    if sex == "weiblich":
        if "gebaerfaehig" in childbearing_raw and "nicht" not in childbearing_raw:
            reasons.append("gebärfähig")

    # Existing app flags (healthy volunteer context)
    if bool(ui.get("ph_known")) or bool(ui.get("ph_suspected")):
        reasons.append("bekannte oder vermutete pulmonale Hypertonie")
    if bool(ui.get("chd_pos")):
        reasons.append("kardiale Erkrankung oder EKG Auffaelligkeit dokumentiert")

    # Numeric based exclusions where protocol uses clear thresholds
    if age is not None and not (18.0 <= age <= 55.0):
        reasons.append("Alter ausserhalb 18 bis 55 Jahre")
    if weight_kg is not None and weight_kg < 50.0:
        reasons.append("Koerpergewicht <50 kg")
    if bmi is not None and not (18.0 <= bmi <= 29.9):
        reasons.append("BMI ausserhalb 18 bis 29,9")

    # Vitals: if documented and outside target range
    vitals_out = False
    if bp_sys is not None and not (90.0 <= bp_sys <= 139.0):
        vitals_out = True
    if bp_dia is not None and not (50.0 <= bp_dia <= 89.0):
        vitals_out = True
    if hr is not None and not (50.0 <= hr <= 90.0):
        vitals_out = True
    if vitals_out:
        reasons.append("sitzende Vitalparameter ausserhalb Zielbereich")

    # Kidney function (either derived eGFR or screening click)
    if egfr is not None and egfr < 60.0:
        reasons.append("eGFR <60")
    if renal_path == "yes":
        reasons.append("Nierenfunktion klinisch relevant eingeschraenkt")

    # Liver
    if liver_path == "yes":
        reasons.append("Leberwerte pathologisch")

    # Hb based (using existing helper)
    if anemia is True:
        reasons.append("Anämie nach Hb")

    # Eligible hint only if all checkable required fields are explicitly ok
    eligible_hint = False

    # Required basics
    basics_ok = (
        sex in ("männlich", "weiblich")
        and age is not None and 18.0 <= age <= 55.0
        and weight_kg is not None and weight_kg >= 50.0
        and bmi is not None and 18.0 <= bmi <= 29.9
        and bp_sys is not None and 90.0 <= bp_sys <= 139.0
        and bp_dia is not None and 50.0 <= bp_dia <= 89.0
        and hr is not None and 50.0 <= hr <= 90.0
        and egfr is not None and egfr >= 60.0
        and anemia is False
        and not bool(ui.get("ph_known")) and not bool(ui.get("ph_suspected"))
        and not bool(ui.get("chd_pos"))
    )

    # Required study click fields: must be explicitly "Nein" to allow the hint
    clicks_ok = (
        other_trial == "no"
        and blood_donation == "no"
        and nicotine == "no"
        and meds == "no"
        and cannabis == "no"
        and misuse == "no"
        and test_or_unwilling == "no"
        and caffeine == "no"
        and cruciferous == "no"
        and grapefruit == "no"
        and liver_path == "no"
        and renal_path == "no"
    )

    female_ok = True
    if sex == "weiblich":
        # pregnancy must be documented as no
        female_ok = (pregnancy == "no")
        # childbearing must be documented as not of childbearing potential
        cb = childbearing_raw
        if not cb:
            female_ok = False
        else:
            if "nicht" in cb and "gebaerfaehig" in cb:
                pass
            elif "nicht gebaerfaehig" in cb:
                pass
            elif "postmenopausal" in cb or "oophorekt" in cb or "hysterekt" in cb:
                pass
            else:
                # unklar or gebaerfaehig
                female_ok = False

    if basics_ok and clicks_ok and female_ok and not reasons:
        eligible_hint = True

    return {"reasons": reasons, "eligible_hint": eligible_hint}


def get_study_hints(case: Dict[str, Any]) -> List[str]:
    """Return additional clinician hints related to study pre screening."""
    hints: List[str] = []

    try:
        ui = (case or {}).get("ui") or {}
        res = _novartis_hv_assess(case)
        reasons = res.get("reasons") or []
        if isinstance(reasons, list) and reasons:
            # deduplicate, keep order
            dedup = list(dict.fromkeys([str(x).strip() for x in reasons if str(x).strip()]))
            if dedup:
                hints.append("Nicht geeignet für Novartis Studie, weil: " + "; ".join(dedup) + ".")
        else:
            if bool(res.get("eligible_hint")):
                hints.append("Studienevaluation für Novartis Studie erwägen")
            else:
                # If the user started documenting the study screening items but the criteria are not
                # sufficiently documented for a conservative assessment, show a short hint (no inference).
                try:
                    tri_keys = [
                        "study_other_trial_recent",
                        "study_blood_donation_8w",
                        "study_nicotine_active",
                        "study_caffeine_gt800",
                        "study_meds_supp_4w",
                        "study_cannabis_4w",
                        "study_alcohol_substance_misuse_1y",
                        "study_alcohol_drug_test_or_unwilling_72h",
                        "study_cruciferous_7d",
                        "study_grapefruit_14d",
                        "study_pregnancy_lactation",
                        "study_liver_pathologic",
                        "study_renal_pathologic",
                    ]
                    engaged = any(_tri_state(ui.get(k)) != "unk" for k in tri_keys)
                    cb = str(ui.get("study_childbearing_potential") or "").strip().lower()
                    if cb and ("unklar" not in cb and "nicht erhoben" not in cb):
                        engaged = True
                    if engaged:
                        hints.append("Novartis Studie: Studienevaluation derzeit nicht möglich, weil Angaben unvollständig.")
                except Exception:
                    pass
    except Exception:
        pass

    return hints
