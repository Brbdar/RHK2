#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PH Therapie – robuste Erfassung als Episoden.

Dieses Modul bündelt:
- UI Choices (Medikamente, Status, Gründe)
- Parsing/Serialisierung der Gradio-Tabellenrepräsentation (list[list])
- Ableitung von Klassen-Tags für das Regelwerk (ohne UI-Überschreiben)

Design-Prinzipien
- Keine stillen Datenübernahmen: Legacy -> Episoden nur auf explizite Aktion.
- Fehlende Angaben bleiben leer (keine Imputation).
- Unbekannte Medikamente werden nicht klassifiziert.
"""

from __future__ import annotations

from typing import Any, Dict, List

# -----------------------------------------------------------------------------
# UI Choices
# -----------------------------------------------------------------------------

# Statuswerte sind bewusst kurz und eindeutig.
PH_TX_STATUS_CHOICES: List[str] = [
    "aktuell",
    "geplant",
    "pausiert",
    "abgesetzt",
    "früher",
    "unklar",
]

PH_TX_STOP_REASON_CHOICES: List[str] = [
    "keine Angabe",
    "Unverträglichkeit/Nebenwirkung",
    "Kontraindikation",
    "Ineffektivität",
    "Patient*innenwunsch",
    "Andere/unklar",
]


# Medikamentenliste (Praxis orientiert, Eigennamen bevorzugt).
# Hinweis: Bei Bedarf können weitere Namen ergänzt werden, ohne die Logik zu brechen.
PH_DRUG_CHOICES: List[str] = [
    # ERA
    "Opsumit (Macitentan)",
    "Tracleer (Bosentan)",
    "Volibris (Ambrisentan)",
    # PDE5
    "Sildenafil",
    "Tadalafil",
    # sGC
    "Adempas (Riociguat)",
    "Riociguat",
    # IP-Rezeptoragonist
    "Uptravi (Selexipag)",
    "Selexipag",
    # Prostazyklin
    "Ventavis (Iloprost)",
    "Iloprost",
    "Treprostinil",
    "Remodulin (Treprostinil)",
    "Tyvaso (Treprostinil)",
    "Veletri (Epoprostenol)",
    "Flolan (Epoprostenol)",
    "Epoprostenol",
    # Sonstiges / supportive
    "Kalziumantagonist",
    "Diuretikum",
    "Sauerstoff",
    # 4. Pfad
    "Sotatercept",
    # Freitext
    "Sonstiges",
]


# Table columns (Gradio Dataframe)
PH_TX_TABLE_HEADERS: List[str] = [
    "Medikament",
    "Status",
    "seit (MM/JJJJ)",
    "bis (MM/JJJJ)",
    "Grund (optional)",
    "Kommentar (optional)",
]


# -----------------------------------------------------------------------------
# Mapping to rulebook class tags (must match rhk_rules.yaml string literals)
# -----------------------------------------------------------------------------

_TAG_PDE5 = "PDE-5-Hemmer"
_TAG_SGC = "sGC-Stimulator (Riociguat)"
_TAG_ERA = "Endothelin-Rezeptorantagonist (ERA)"
_TAG_PROST = "Prostazyklin-Therapie / -Analogon"
_TAG_IP = "IP-Rezeptoragonist (z.B. Selexipag)"
_TAG_CCB = "Kalziumantagonist (bei Vasoreaktivität)"
_TAG_DIUR = "Diuretikum"
_TAG_O2 = "Sauerstofftherapie"
_TAG_SOTA = "Sotatercept (BMPR2/Activin-Pfad)"
_TAG_OTHER = "Sonstiges"


PH_DRUG_TO_CLASS_TAGS: Dict[str, List[str]] = {
    # ERA
    "opsumit (macitentan)": [_TAG_ERA],
    "macitentan": [_TAG_ERA],
    "tracleer (bosentan)": [_TAG_ERA],
    "bosentan": [_TAG_ERA],
    "volibris (ambrisentan)": [_TAG_ERA],
    "ambrisentan": [_TAG_ERA],

    # PDE5
    "sildenafil": [_TAG_PDE5],
    "tadalafil": [_TAG_PDE5],

    # sGC
    "adempas (riociguat)": [_TAG_SGC],
    "riociguat": [_TAG_SGC],

    # IP agonist
    "uptravi (selexipag)": [_TAG_IP],
    "selexipag": [_TAG_IP],

    # Prostacyclin pathway
    "ventavis (iloprost)": [_TAG_PROST],
    "iloprost": [_TAG_PROST],
    "treprostinil": [_TAG_PROST],
    "remodulin (treprostinil)": [_TAG_PROST],
    "tyvaso (treprostinil)": [_TAG_PROST],
    "veletri (epoprostenol)": [_TAG_PROST],
    "flolan (epoprostenol)": [_TAG_PROST],
    "epoprostenol": [_TAG_PROST],

    # Supportive
    "kalziumantagonist": [_TAG_CCB],
    "diuretikum": [_TAG_DIUR],
    "sauerstoff": [_TAG_O2],

    # Sotatercept
    "sotatercept": [_TAG_SOTA],

    # Other
    "sonstiges": [_TAG_OTHER],
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _s(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _norm_key(name: str) -> str:
    return _s(name).lower()


def _parse_ph_tx_text(text: str) -> List[Dict[str, str]]:
    """Parse fallback text editor content into episode dicts.

    A single line represents one episode...
    """

    def _split_cols(line: str) -> List[str]:
        if "\t" in line:
            cols = line.split("\t")
        elif "|" in line:
            cols = line.split("|")
        elif ";" in line:
            cols = line.split(";")
        else:
            cols = line.split(",")
        return [c.strip() for c in cols]

    out: List[Dict[str, str]] = []
    for raw in (text or "").splitlines():
        line = str(raw).strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        low = line.lower()
        # header row tolerance
        if "medikament" in low and "status" in low:
            continue

        cols = _split_cols(line)
        cols = cols + [""] * (6 - len(cols))
        drug = _s(cols[0])
        status = _s(cols[1]).lower()
        if not drug or not status:
            continue
        out.append({
            "drug": drug,
            "status": status,
            "since": _s(cols[2]),
            "until": _s(cols[3]),
            "reason": _s(cols[4]),
            "note": _s(cols[5]),
        })
    return out


def parse_ph_tx_table_rows(rows: Any) -> List[Dict[str, str]]:
    """Parse Gradio Dataframe value -> list of episode dicts.

    Expected input:
    - list[list] where each row matches PH_TX_TABLE_HEADERS order
    - empty/None yields []

    Episode keys:
    - drug, status, since, until, reason, note
    """
    if rows is None:
        return []

    # Fallback-Editor (Textbox): eine Zeile = eine Episode
    # Format bevorzugt: Tab-getrennt (6 Spalten) in PH_TX_TABLE_HEADERS Reihenfolge.
    # Alternative Delimiter werden toleriert: "|" oder ";".
    if isinstance(rows, str):
        text = rows.strip()
        if not text:
            return []
        return _parse_ph_tx_text(text)
    if isinstance(rows, dict):
        # defensive: some integrations store already as episodes
        # treat as single episode dict if shape fits
        drug = _s(rows.get("drug"))
        status = _s(rows.get("status"))
        if drug and status:
            return [{
                "drug": drug,
                "status": status,
                "since": _s(rows.get("since")),
                "until": _s(rows.get("until")),
                "reason": _s(rows.get("reason")),
                "note": _s(rows.get("note")),
            }]
        return []
    if not isinstance(rows, list):
        return []

    out: List[Dict[str, str]] = []
    for r in rows:
        if not isinstance(r, (list, tuple)):
            continue
        # Pad to 6 cols
        rr = list(r) + [""] * (6 - len(r))
        drug = _s(rr[0])
        status = _s(rr[1]).lower()
        if not drug or not status:
            continue
        out.append({
            "drug": drug,
            "status": status,
            "since": _s(rr[2]),
            "until": _s(rr[3]),
            "reason": _s(rr[4]),
            "note": _s(rr[5]),
        })
    return out


def episodes_to_ph_tx_table_rows(episodes: Any) -> List[List[str]]:
    """Serialize episodes list -> Gradio Dataframe rows."""
    if not isinstance(episodes, list):
        return []
    rows: List[List[str]] = []
    for e in episodes:
        if not isinstance(e, dict):
            continue
        drug = _s(e.get("drug"))
        status = _s(e.get("status"))
        if not drug or not status:
            continue
        rows.append([
            drug,
            status,
            _s(e.get("since")),
            _s(e.get("until")),
            _s(e.get("reason")),
            _s(e.get("note")),
        ])
    return rows


def episodes_to_ph_tx_text(episodes: Any) -> str:
    """Serialize episodes list -> text lines (tab-delimited)."""
    rows = episodes_to_ph_tx_table_rows(episodes)
    if not rows:
        return ""
    lines: List[str] = []
    for r in rows:
        rr = [str(x or "").strip() for x in (r or [])]
        rr = rr + [""] * (6 - len(rr))
        lines.append("\t".join(rr[:6]))
    return "\n".join(lines)


def legacy_lists_to_episodes(ui: Dict[str, Any]) -> List[Dict[str, str]]:
    """Legacy compatibility: build episodes from old PH therapy list fields.

    IMPORTANT: This does NOT write back into ui.
    It is intended for explicit conversion button and for report fallback.
    """
    u = ui or {}
    stop_reason = _s(u.get("ph_stop_reason"))
    stop_reason_txt = _s(u.get("ph_stop_reason_text"))
    stop_bits = ", ".join([x for x in [stop_reason, stop_reason_txt] if x and x.lower() != "keine angabe"]).strip()

    def _as_list(v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        if isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]
        return [str(v).strip()] if str(v).strip() else []

    cur = _as_list(u.get("ph_current_meds"))
    prev = _as_list(u.get("ph_prev_meds"))
    planned = _as_list(u.get("ph_new_meds"))
    stopped = _as_list(u.get("ph_stopped_meds"))

    eps: List[Dict[str, str]] = []
    for d in prev:
        eps.append({"drug": d, "status": "früher", "since": "", "until": "", "reason": "", "note": ""})
    for d in stopped:
        eps.append({"drug": d, "status": "abgesetzt", "since": "", "until": "", "reason": stop_bits, "note": ""})
    for d in cur:
        eps.append({"drug": d, "status": "aktuell", "since": "", "until": "", "reason": "", "note": ""})
    for d in planned:
        eps.append({"drug": d, "status": "geplant", "since": "", "until": "", "reason": "", "note": ""})
    return eps


def derive_rulebook_class_lists_from_episodes(episodes: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Derive ph_current_meds/ph_new_meds/... as rulebook class tags.

    Output keys match legacy UI field names so they can override in env via derived.
    """
    cur: List[str] = []
    prev: List[str] = []
    stopped: List[str] = []
    new: List[str] = []

    def _add_unique(lst: List[str], item: str) -> None:
        if item and item not in lst:
            lst.append(item)

    for e in episodes or []:
        if not isinstance(e, dict):
            continue
        drug = _s(e.get("drug"))
        status = _s(e.get("status")).lower()
        if not drug or not status:
            continue
        tags = PH_DRUG_TO_CLASS_TAGS.get(_norm_key(drug)) or []
        # Unknown drug -> do not classify (safe, conservative)
        if not tags:
            continue

        if status == "aktuell":
            for t in tags:
                _add_unique(cur, t)
        elif status == "geplant":
            for t in tags:
                _add_unique(new, t)
        elif status in ("abgesetzt", "pausiert"):
            for t in tags:
                _add_unique(stopped, t)
        elif status == "früher":
            for t in tags:
                _add_unique(prev, t)

    return {
        "ph_current_meds": cur,
        "ph_prev_meds": prev,
        "ph_stopped_meds": stopped,
        "ph_new_meds": new,
    }


def format_ph_tx_episode_line(e: Dict[str, str]) -> str:
    """Compact single-line representation for reports (German, deterministic)."""
    drug = _s(e.get("drug"))
    status = _s(e.get("status")).lower()
    since = _s(e.get("since"))
    until = _s(e.get("until"))
    reason = _s(e.get("reason"))
    note = _s(e.get("note"))

    if not drug or not status:
        return ""

    bits: List[str] = []
    # time window
    if since and until:
        bits.append(f"{since} bis {until}")
    elif since:
        bits.append(f"seit {since}")
    elif until:
        bits.append(f"bis {until}")

    if reason:
        bits.append(reason)
    if note:
        bits.append(note)

    tail = "; ".join([b for b in bits if b])
    if tail:
        return f"{drug} ({status}, {tail})"
    return f"{drug} ({status})"
