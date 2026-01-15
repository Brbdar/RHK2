#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo Report Builder – Patient*innenbericht (Echo-Teil).

WICHTIG
- Patient*innenfreundlich, keine Überdiagnose, keine Rohwertliste als Haupttext.
- Nutzt ausschließlich bereits erfasste Werte. Fehlende Werte werden ausgelassen oder als nicht beurteilbar markiert.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List, Tuple

from rhk_echo_guidelines import severity, fmt_value, unit_for


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        x = float(v)
        if x != x:
            return None
        return x
    except Exception:
        return None


def _fmt(key: str, v: Any, digits: int = 0) -> str:
    u = unit_for(key)
    s = fmt_value(v, digits=digits)
    return (f"{s} {u}".strip()) if u else s


def _ampel(ui: Dict[str, Any]) -> Tuple[str, str]:
    """Return (color_word, one_line_summary)."""
    keys = [
        "trv_ms", "pasp_echo", "paat_ms",
        "tapse_mm", "rvfac_pct", "s_prime_cm_s",
        "ivc_diam_mm", "ivc_collapse_index_pct", "ivc_collapse",
        "pericardial_effusion", "rvot_notch"
    ]
    sev = []
    for k in keys:
        if k in ui and ui.get(k) is not None:
            s = severity(k, ui.get(k))
            if s:
                sev.append(s)
    if not sev:
        return "grau", "Nicht beurteilbar, weil wichtige Messwerte fehlen."
    if "r" in sev:
        return "rot", "Mehrere Messzeichen sind auffällig. Das ist ein Hinweis, aber keine endgültige Diagnose."
    if "y" in sev:
        return "gelb", "Es gibt grenzwertige Hinweise. Oft hilft ein Verlauf oder eine ergänzende Abklärung."
    return "grün", "Die dokumentierten Messzeichen sind insgesamt unauffällig."


def build_echo_patient_report(case: Dict[str, Any]) -> str:
    ui: Dict[str, Any] = case.get("ui", {}) or {}

    if not ui.get("echo_done") and not ui.get("cmr_done"):
        return "## Echo Bericht (Patient*innen)\n\nAktuell sind keine Echo Werte dokumentiert.\n"

    out: List[str] = []
    out.append("## Echo Bericht (Patient*innen)")
    out.append("")
    out.append("Ein Ultraschall des Herzens (Echokardiographie) zeigt die Herzgröße, die Pumpfunktion und indirekte Hinweise auf Druckbelastung. Er kann Druckwerte aber nur schätzen und ersetzt keine Messung im Herzkatheter.")
    out.append("")
    color, summary = _ampel(ui)
    out.append(f"**Zusammenfassung (Ampel): {color.upper()}** – {summary}")
    out.append("")
    # Key messages based on available data (very limited list)
    msgs: List[str] = []

    tapse = ui.get("tapse_mm")
    if _as_float(tapse) is not None:
        s = severity("tapse_mm", tapse)
        if s == "r":
            msgs.append(f"Die Beweglichkeit der rechten Herzkammer ist vermindert (TAPSE { _fmt('tapse_mm', tapse) }).")
        elif s == "y":
            msgs.append(f"Die Beweglichkeit der rechten Herzkammer ist grenzwertig (TAPSE { _fmt('tapse_mm', tapse) }).")
        else:
            msgs.append(f"Die Beweglichkeit der rechten Herzkammer ist unauffällig (TAPSE { _fmt('tapse_mm', tapse) }).")

    trv = ui.get("trv_ms")
    if _as_float(trv) is not None:
        s = severity("trv_ms", trv)
        if s == "r":
            msgs.append(f"Es gibt deutliche Hinweise auf erhöhten Druck im Lungenkreislauf (TR Vmax { _fmt('trv_ms', trv, digits=2) }).")
        elif s == "y":
            msgs.append(f"Es gibt grenzwertige Hinweise auf erhöhten Druck im Lungenkreislauf (TR Vmax { _fmt('trv_ms', trv, digits=2) }).")
        else:
            msgs.append(f"Es gibt keine eindeutigen Hinweise auf erhöhten Druck im Lungenkreislauf anhand des gemessenen TR-Jets (TR Vmax { _fmt('trv_ms', trv, digits=2) }).")

    paat = ui.get("paat_ms")
    if _as_float(paat) is not None:
        s = severity("paat_ms", paat)
        if s in {"y", "r"}:
            msgs.append(f"Die Flusszeit in der Lungenschlagader ist verkürzt (PAAT { _fmt('paat_ms', paat) }); das kann zu einer Druckbelastung passen.")
        else:
            msgs.append(f"Die Flusszeit in der Lungenschlagader ist unauffällig (PAAT { _fmt('paat_ms', paat) }).")

    peric = ui.get("pericardial_effusion")
    if peric is not None:
        s = severity("pericardial_effusion", peric)
        if s == "r":
            msgs.append("Es wurde ein Perikarderguss (Flüssigkeit um das Herz) beschrieben.")
        else:
            msgs.append("Es wurde kein Perikarderguss beschrieben.")

    if msgs:
        out.append("### Was wurde gesehen")
        out.extend([f"- {m}" for m in msgs])
        out.append("")
    else:
        out.append("### Was wurde gesehen")
        out.append("- Es liegen derzeit zu wenige Messwerte vor, um eine verständliche Einordnung zu geben.")
        out.append("")
    out.append("### Wann Rücksprache sinnvoll ist")
    out.append("- Wenn neue oder zunehmende Atemnot, Brustschmerzen, Ohnmacht, deutliche Wassereinlagerungen oder schnelle Leistungsabnahme auftreten.")
    out.append("- Wenn im Bericht eine gelbe oder rote Ampel steht oder wenn Ihr Behandlungsteam eine Katheteruntersuchung zur Druckmessung empfiehlt.")
    out.append("")
    out.append("Hinweis: Einzelwerte hängen von Bildqualität und Messbedingungen ab. Am wichtigsten ist die Gesamtschau aus Beschwerden, Untersuchung, Labor/Belastungstests und Verlauf.")
    out.append("")

    return "\n".join(out).strip() + "\n"
