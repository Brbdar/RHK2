#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Echo Report Builder – Patient*innenbericht (Echo-Teil).

WICHTIG
- Patient*innenfreundlich, keine Überdiagnose, keine Rohwertliste als Haupttext.
- Nutzt ausschließlich bereits erfasste Werte. Fehlende Werte werden ausgelassen oder als nicht beurteilbar markiert.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from rhk_echo_guidelines import fmt_value, severity, unit_for

ECHO_PATIENT_MODE_LAY = "laienbefund"
ECHO_PATIENT_MODE_SHORT = "kurzfassung"

_ECHO_MODE_ALIASES = {
    "laienbefund": ECHO_PATIENT_MODE_LAY,
    "laie": ECHO_PATIENT_MODE_LAY,
    "lay": ECHO_PATIENT_MODE_LAY,
    "patient": ECHO_PATIENT_MODE_LAY,
    "default": ECHO_PATIENT_MODE_LAY,
    "kurzfassung": ECHO_PATIENT_MODE_SHORT,
    "kurz": ECHO_PATIENT_MODE_SHORT,
    "short": ECHO_PATIENT_MODE_SHORT,
    "compact": ECHO_PATIENT_MODE_SHORT,
    "summary": ECHO_PATIENT_MODE_SHORT,
}

_ECHO_JARGON_EXPLANATIONS: List[Tuple[str, str]] = [
    ("KM", "Kontrastmittel"),
    ("DD", "Differentialdiagnose (andere mögliche Erklärung)"),
    ("RR", "Blutdruck"),
    ("LWS", "Lendenwirbelsäule"),
    ("IV", "über die Vene"),
    ("Ödem", "Wassereinlagerung"),
    ("Infiltrat", "verdichtetes Gewebe, oft als Entzündungszeichen"),
    ("Läsion", "Gewebeveränderung"),
    ("benigne", "gutartig"),
    ("maligne", "bösartig"),
    ("Echokardiographie", "Herzultraschall"),
    ("TR Vmax", "Geschwindigkeit des Rückflusses über die Trikuspidalklappe"),
    ("TAPSE", "Messwert für die Beweglichkeit der rechten Herzkammer"),
    ("PAAT", "Zeit bis zum Flussgipfel in der Lungenschlagader"),
    ("Perikarderguss", "Flüssigkeit im Herzbeutel"),
    ("LVEF", "Messwert für die Pumpkraft der linken Herzkammer"),
    ("RVFAC", "Messwert für die Pumpfunktion der rechten Herzkammer"),
    ("Strain", "Dehnungsmessung des Herzmuskels"),
    ("VCI", "untere Hohlvene"),
    ("E/e", "Hinweiswert auf den Füllungsdruck des linken Herzens"),
]

_ECHO_AUTO_GLOSSARY: Dict[str, str] = {
    "KM": "Kontrastmittel: Substanz, die Strukturen in der Bildgebung besser sichtbar macht.",
    "DD": "Differentialdiagnose: andere mögliche Erklärung für einen Befund.",
    "RR": "Blutdruck (Riva-Rocci).",
    "LWS": "Lendenwirbelsäule (unterer Rücken).",
    "IV": "Intravenös: Gabe über die Vene.",
    "Ödem": "Wassereinlagerung im Gewebe.",
    "Infiltrat": "Verdichtetes Gewebe, häufig als Hinweis auf Entzündung.",
    "Läsion": "Gewebeveränderung; kann gutartig oder bösartig sein.",
    "benigne": "Gutartig.",
    "maligne": "Bösartig.",
    "Echokardiographie": "Ultraschalluntersuchung des Herzens.",
    "LVEF": "Anteil des Blutes, den die linke Herzkammer pro Schlag auswirft.",
    "TAPSE": "Messwert für die Beweglichkeit der rechten Herzkammer.",
    "TR Vmax": "Geschwindigkeit eines Rückflusssignals über der Trikuspidalklappe.",
    "sPAP": "Im Echo geschätzter Druck in der Lungenschlagader (Schätzwert).",
    "E/e": "Verhältnis zweier Echo-Messungen als Hinweis auf linken Füllungsdruck.",
    "LAVI": "Volumen des linken Vorhofs bezogen auf die Körperoberfläche.",
    "RVFAC": "Flächenänderung der rechten Herzkammer als Funktionshinweis.",
    "Strain": "Dehnungsmessung des Herzmuskels.",
    "PAAT": "Zeit bis zum Flussgipfel in der Lungenschlagader.",
    "VCI": "Untere Hohlvene; Größe/Kollaps geben Hinweise auf Druckverhältnisse.",
    "Perikarderguss": "Flüssigkeitsansammlung im Herzbeutel.",
}

_ECHO_PANIC_WORD_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bgefährlich\s+wirkend\b", "ernst zu nehmen"),
    (r"\bschlimm(?:e|er|es|en)?\b", "ausgeprägt"),
    (r"\bgefährlich(?:e|er|es|en)?\b", "ernst zu nehmen"),
    (r"\bbedrohlich(?:e|er|es|en)?\b", "ernst zu nehmen"),
    (r"\bdramatisch(?:e|er|es|en)?\b", "deutlich"),
]
_ECHO_PARAGRAPH_CONNECTORS = ("Außerdem,", "Zusätzlich,", "Darüber hinaus,", "Gleichzeitig,", "Im nächsten Schritt")
_ECHO_PROTECTED_PREFIX_WORDS = {
    "PH",
    "PAH",
    "CTEPH",
    "BNP",
    "NT-proBNP",
    "NT",
    "WHO",
    "ESC",
    "ERS",
    "RAP",
    "PAWP",
    "PVR",
    "mPAP",
    "sPAP",
    "dPAP",
    "CI",
    "CO",
    "TRV",
    "TR",
    "TAPSE",
    "PAAT",
    "RVFAC",
    "LVEF",
    "VCI",
}


def _normalize_echo_patient_mode(mode: Any) -> Optional[str]:
    if mode is None:
        return None
    token = str(mode or "").strip().lower()
    if not token:
        return None
    token = token.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    token = re.sub(r"[\s_-]+", "", token)
    return _ECHO_MODE_ALIASES.get(token)


def _replace_echo_jargon_once(line: str, term: str, explanation: str) -> str:
    if not line:
        return line
    if explanation.lower() in line.lower():
        return line
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)
    if not pattern.search(line):
        return line
    return pattern.sub(lambda m: f"{explanation} ({m.group(0)})", line, count=1)


def _inline_explanation_from_glossary_text(explanation: str) -> str:
    txt = re.sub(r"\s+", " ", str(explanation or "").strip())
    if not txt:
        return ""
    if ":" in txt:
        txt = txt.split(":", 1)[0].strip()
    elif "." in txt:
        txt = txt.split(".", 1)[0].strip()
    if len(txt) > 72:
        txt = txt[:69].rstrip() + "..."
    return txt


def _build_echo_inline_terms(glossary: Optional[Dict[str, str]] = None) -> List[Tuple[str, str]]:
    terms: List[Tuple[str, str]] = list(_ECHO_JARGON_EXPLANATIONS)
    seen = {str(term).casefold() for term, _ in terms}
    src = glossary or _ECHO_AUTO_GLOSSARY
    for term, expl in (src or {}).items():
        key = str(term or "").strip()
        if not key or key.casefold() in seen:
            continue
        short = _inline_explanation_from_glossary_text(str(expl or ""))
        if not short:
            continue
        terms.append((key, short))
        seen.add(key.casefold())
    return terms


def _clean_glossary_map(data: Optional[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in (data or {}).items():
        kk = str(k or "").strip()
        vv = str(v or "").strip()
        if kk and vv:
            out[kk] = vv
    return out


def _load_echo_runtime_glossary() -> Dict[str, str]:
    try:
        mod = __import__("rhk_textdb_echo_patient")
        db = getattr(mod, "ECHO_PATIENT_GLOSSARY", {}) or {}
        if isinstance(db, dict):
            return _clean_glossary_map(db)
    except Exception:
        return {}
    return {}


def _merge_echo_glossary(base_glossary: Dict[str, str]) -> Dict[str, str]:
    merged = dict(_ECHO_AUTO_GLOSSARY)
    merged.update(_clean_glossary_map(base_glossary))
    return merged


def _find_echo_glossary_term_idx(line: str, term: str) -> Optional[int]:
    hay = str(line or "")
    needle = str(term or "")
    if not hay or not needle:
        return None
    hay_l = hay.lower()
    needle_l = needle.lower()
    term_has_non_alnum = any(not ch.isalnum() for ch in needle_l)
    start = 0
    while True:
        idx = hay_l.find(needle_l, start)
        if idx == -1:
            return None
        if term_has_non_alnum:
            return idx
        end = idx + len(needle_l)
        left_ok = (idx == 0) or (not hay_l[idx - 1].isalnum())
        right_ok = (end >= len(hay_l)) or (not hay_l[end].isalnum())
        if left_ok and right_ok:
            return idx
        start = idx + 1


def _collect_used_echo_glossary_terms(lines: List[str], glossary: Dict[str, str], *, max_terms: int = 24) -> List[str]:
    if not glossary or not lines:
        return []
    terms = list(glossary.keys())
    found: List[str] = []
    for line in lines:
        txt = str(line or "")
        for term in terms:
            if term in found:
                continue
            if _find_echo_glossary_term_idx(txt, term) is not None:
                found.append(term)
                if len(found) >= max_terms:
                    return found
    return found


def _append_echo_glossary_section(lines: List[str], glossary: Dict[str, str], *, max_terms: int = 24) -> None:
    used_terms = _collect_used_echo_glossary_terms(lines, glossary, max_terms=max_terms)
    if not used_terms:
        return
    lines.append("### Begriffe kurz erklärt")
    for term in used_terms:
        expl = str(glossary.get(term) or "").strip()
        if expl:
            one_sent = _echo_glossary_one_sentence(expl)
            if one_sent:
                lines.append(f"- **{term}:** {one_sent}")
    lines.append("")


def _echo_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9ÄÖÜäöüß]+(?:/[A-Za-z0-9ÄÖÜäöüß]+)?", str(text or "")))


def _echo_truncate_words(text: str, max_words: int) -> str:
    tokens = re.findall(r"\S+", str(text or "").strip())
    if max_words <= 0:
        return ""
    if not tokens:
        return ""
    out_tokens: List[str] = []
    wc = 0
    for tok in tokens:
        tw = _echo_word_count(tok)
        if tw <= 0:
            tw = 1
        if wc + tw > max_words:
            break
        out_tokens.append(tok)
        wc += tw
    if wc <= 0:
        return ""
    out = " ".join(out_tokens).rstrip(" ,;:")
    if out and not out.endswith((".", "!", "?")):
        out += "."
    return out


def _echo_split_sentences(text: str) -> List[str]:
    s = str(text or "").strip()
    if not s:
        return []
    parts = re.split(r"(?<=[.!?])\s+", s)
    return [p.strip() for p in parts if p.strip()]


def _echo_limit_sentences(text: str, *, max_sentences: int = 2) -> str:
    sents = _echo_split_sentences(text)
    if not sents:
        return ""
    out = " ".join(sents[:max_sentences]).strip()
    if out and out[-1] not in ".!?":
        out += "."
    return out


def _echo_has_transition_prefix(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    return bool(re.match(r"(?i)^(außerdem|zusätzlich|darüber hinaus|gleichzeitig|im nächsten schritt|wichtig)\b", t))


def _echo_lowercase_chunk_start(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    m = re.match(r"^([A-Za-zÄÖÜäöüß]+)", t)
    if not m:
        return t
    word = m.group(1)
    if word in _ECHO_PROTECTED_PREFIX_WORDS:
        return t
    if word[0].islower():
        return t
    return word[0].lower() + word[1:] + t[m.end() :]


_ECHO_LABEL_CHUNK_RE = re.compile(r"^[A-ZÄÖÜ][\wÄÖÜäöüß\- ]{0,40}:\s")


def _echo_chunk_with_transition(chunk: str, idx: int) -> str:
    """Join a chunk with a soft transition connector (grammar-safe).

    See ``rhk_reports._patient_paragraph_chunk_with_transition`` for the
    rationale. In short: German V2 inversion means "Außerdem X" requires X to
    start with a finite verb. If X starts with a capitalized noun/article,
    prepending the connector produces ungrammatical prose, so we keep the
    chunk standalone.
    """
    text = str(chunk or "").strip()
    if not text:
        return ""
    if idx <= 0 or _echo_has_transition_prefix(text):
        return text
    if _ECHO_LABEL_CHUNK_RE.match(text):
        return text
    if re.match(r"^[A-ZÄÖÜ]", text):
        return text
    connector = _ECHO_PARAGRAPH_CONNECTORS[(idx - 1) % len(_ECHO_PARAGRAPH_CONNECTORS)]
    return f"{connector} {_echo_lowercase_chunk_start(text)}"


def _echo_build_layered_paragraph(
    candidates: List[str],
    *,
    min_words: int = 80,
    max_words: int = 120,
) -> str:
    chunks = [_echo_limit_sentences(c, max_sentences=2) for c in candidates if str(c or "").strip()]
    chunks = [c for c in chunks if c]
    if not chunks:
        return ""

    out_parts: List[str] = []
    for ch in chunks:
        candidate = _echo_chunk_with_transition(ch, len(out_parts))
        trial = " ".join(out_parts + [candidate]).strip()
        wc = _echo_word_count(trial)
        if wc <= max_words:
            out_parts.append(candidate)
            continue
        remain = max_words - _echo_word_count(" ".join(out_parts))
        if remain > 6:
            out_parts.append(_echo_truncate_words(candidate, remain))
        break

    out = " ".join(out_parts).strip()
    filler = (
        "Wichtig ist die Gesamtschau aus Beschwerden, Verlauf und ergänzenden Untersuchungen. "
        "Bitte besprechen Sie die Ergebnisse in Ruhe mit dem Behandlungsteam."
    )
    while out and _echo_word_count(out) < min_words:
        trial = (out + " " + filler).strip()
        if _echo_word_count(trial) <= max_words:
            out = trial
            continue
        out = _echo_truncate_words(trial, max_words)
        break

    if out and _echo_word_count(out) > max_words:
        out = _echo_truncate_words(out, max_words)
    return out


def _echo_glossary_one_sentence(explanation: str) -> str:
    txt = re.sub(r"\s+", " ", str(explanation or "").strip())
    if not txt:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", txt)
    first = parts[0].strip() if parts else txt
    if first and first[-1] not in ".!?":
        first += "."
    return first


def _echo_find_header_bounds(lines: List[str], header: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        start = lines.index(header)
    except ValueError:
        return None, None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("### "):
            end = i
            break
    return start, end


def _enforce_echo_layered_constraints(lines: List[str]) -> List[str]:
    out = list(lines or [])

    s0, s1 = _echo_find_header_bounds(out, "### Kurzfazit (Schnellüberblick)")
    if s0 is not None and s1 is not None:
        payload = [ln.strip() for ln in out[s0 + 1 : s1] if ln.strip()]
        summary_txt = " ".join(payload).strip()
        if summary_txt:
            if _echo_word_count(summary_txt) > 120:
                summary_txt = _echo_truncate_words(summary_txt, 120)
            filler = (
                "Wichtig ist die Gesamtschau aus Beschwerden, Verlauf und ergänzenden Untersuchungen. "
                "Bitte besprechen Sie die Ergebnisse in Ruhe mit dem Behandlungsteam."
            )
            while _echo_word_count(summary_txt) < 80:
                trial = (summary_txt + " " + filler).strip()
                if _echo_word_count(trial) <= 120:
                    summary_txt = trial
                else:
                    summary_txt = _echo_truncate_words(trial, 120)
                    break
            out = out[: s0 + 1] + [summary_txt, ""] + out[s1:]

    b0, b1 = _echo_find_header_bounds(out, "### Wichtigste Punkte")
    if b0 is not None and b1 is not None:
        fixed: List[str] = []
        for ln in out[b0 + 1 : b1]:
            s = str(ln or "")
            if s.strip().startswith("- "):
                content = s.strip()[2:].strip()
                content = _echo_limit_sentences(content, max_sentences=2)
                if content:
                    fixed.append(f"- {content}")
            else:
                fixed.append(s)
        out = out[: b0 + 1] + fixed + out[b1:]

    return out


def _normalize_echo_certainty_line(line: str) -> str:
    txt = str(line or "")
    if not txt or txt.lstrip().startswith("#"):
        return txt

    out = txt
    out = re.sub(
        r"(?i)\b(?:es\s+wurde\s+)?kein(?:e|en)?\s+hinweis\s+auf\b",
        "Es gibt keinen Hinweis auf",
        out,
    )
    out = re.sub(r"(?i)\bregelrecht\b", "unauffällig", out)
    # Match only the real medical shorthand (requires first dot) so we do not
    # strip the "Va"/"Vas" prefix of words like Vasoreaktivität or Vaskulitis.
    out = re.sub(r"(?i)\bV\.\s*a\.?\s*", "Verdacht auf ", out)
    out = re.sub(r"(?i)\bDD\s*:\s*", "Andere mögliche Erklärung: ", out)
    out = re.sub(r"(?i)\bvereinbar mit\b", "kann vereinbar sein mit", out)
    out = re.sub(r"(?i)\bEs gibt keinen Hinweis auf ([^.]+?)\s+gesehen\b", r"Es gibt keinen Hinweis auf \1", out)
    out = re.sub(
        r"(?i)^(\s*[-*]?\s*)verdacht\s+auf\b",
        r"\1Es besteht ein Verdacht auf",
        out,
        count=1,
    )
    out = re.sub(
        r"(?i)(^|[.!?]\s+)\s*verdacht\s+auf\b",
        r"\1Es besteht ein Verdacht auf",
        out,
    )
    out = re.sub(
        r"(?i)(:\s*)verdacht\s+auf\b",
        r"\1Es besteht ein Verdacht auf",
        out,
        count=1,
    )
    out = re.sub(
        r"(?i)(^|[.!?]\s+)\s*hinweise\s+auf\b",
        r"\1Es gibt Hinweise auf",
        out,
    )
    out = re.sub(
        r"(?i)(:\s*)hinweise\s+auf\b",
        r"\1Es gibt Hinweise auf",
        out,
    )
    return out


def _sanitize_echo_tone(line: str) -> str:
    out = str(line or "")
    if not out:
        return out
    for pattern, replacement in _ECHO_PANIC_WORD_REPLACEMENTS:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    out = re.sub(r"(?i)\bernst zu nehmen\s+wirkend\b", "ernst zu nehmen", out)
    return out


def _rewrite_echo_line_for_lay_mode(
    line: str,
    *,
    inline_terms: Optional[List[Tuple[str, str]]] = None,
) -> str:
    txt = str(line or "")
    if not txt or txt.lstrip().startswith("#"):
        return txt
    out = _normalize_echo_certainty_line(txt)
    for term, explanation in (inline_terms or _ECHO_JARGON_EXPLANATIONS):
        out = _replace_echo_jargon_once(out, term, explanation)
    out = _sanitize_echo_tone(out)
    return out


def _finalize_echo_report_lines(lines: List[str], glossary: Optional[Dict[str, str]] = None) -> str:
    inline_terms = _build_echo_inline_terms(glossary)
    rewritten = [
        _rewrite_echo_line_for_lay_mode(str(ln or ""), inline_terms=inline_terms)
        for ln in (lines or [])
    ]
    rewritten = _enforce_echo_layered_constraints(rewritten)
    _append_echo_glossary_section(rewritten, glossary or {}, max_terms=24)
    return "\n".join(rewritten).strip() + "\n"


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        x = float(v)
        if x != x:
            return None
        # Echo: 0/0.0 wird als fehlend behandelt (kein stilles "0")
        if abs(x) < 1e-12:
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


def _echo_clarity_sentence(color: str) -> str:
    token = str(color or "").strip().lower()
    if token == "rot":
        return "Gesamteinordnung: Die erhobenen Messzeichen sind eher auffällig."
    if token == "gelb":
        return "Gesamteinordnung: Die erhobenen Messzeichen sind teils auffällig, teils grenzwertig."
    if token == "grün":
        return "Gesamteinordnung: Die erhobenen Messzeichen sind überwiegend unauffällig."
    return "Gesamteinordnung: Eine eindeutige Einordnung (unauffällig/auffällig) ist derzeit nicht sicher möglich."


def _echo_relevance_line(kind: str) -> str:
    k = str(kind or "").strip().lower()
    if k == "main":
        return "Relevanz im Bericht: Hauptbefund."
    if k == "side":
        return "Relevanz im Bericht: Nebenbefund; keine akute Maßnahme wird erwähnt."
    return "Relevanz im Bericht: Im Bericht steht keine Dringlichkeit."


def _echo_relevance_from_color(color: str) -> str:
    token = str(color or "").strip().lower()
    if token == "rot":
        return "main"
    if token == "grün":
        return "side"
    return "neutral"


def _echo_relevance_from_msg(msg: str) -> str:
    txt = str(msg or "").strip().lower()
    if not txt:
        return "neutral"
    if (
        ("deutliche hinweise" in txt)
        or ("vermindert" in txt)
        or ("perikarderguss" in txt and "kein" not in txt)
        or ("auffällig" in txt and "unauffällig" not in txt)
    ):
        return "main"
    if ("unauffällig" in txt) or ("kein perikarderguss" in txt) or ("keine eindeutigen hinweise" in txt):
        return "side"
    return "neutral"


def _append_echo_relevance_section(out: List[str], *, color: str, summary: str, msgs: List[str]) -> None:
    out.append("### Relevanz: Hauptbefunde und Nebenbefunde")
    ampel = _echo_limit_sentences(f"Ampel-Einordnung: {str(color or '').upper()} – {summary}", max_sentences=2)
    if ampel:
        out.append(f"- **Gesamtecho-Einordnung:** {ampel} {_echo_relevance_line(_echo_relevance_from_color(color))}")

    for msg in (msgs or [])[:4]:
        detail = _echo_limit_sentences(msg, max_sentences=2)
        if detail:
            out.append(f"- **Befunddetail:** {detail} {_echo_relevance_line(_echo_relevance_from_msg(detail))}")

    if out and out[-1] == "### Relevanz: Hauptbefunde und Nebenbefunde":
        out.append(
            f"- **Gesamteinschätzung:** Eine Priorisierung ist anhand der vorliegenden Angaben nur eingeschränkt möglich. {_echo_relevance_line('neutral')}"
        )
    out.append("")


def _append_echo_layered_summary(
    out: List[str],
    *,
    color: str,
    summary: str,
    clarity: str,
    msgs: List[str],
    followup: str,
    reason: str,
    story: str,
    primary_dx: str,
) -> None:
    candidates: List[str] = [
        f"Die aktuelle Echo-Einordnung zeigt eine {color}-Ampel: {summary}",
        clarity,
        (
            "Der Herzultraschall liefert wichtige Hinweise auf Druckbelastung und Pumpfunktion, "
            "ersetzt aber bei unklaren Situationen nicht die direkte Druckmessung im Rechtsherzkatheter."
        ),
        f"Anlass war: {reason}." if reason else (f"Dokumentierte Beschwerden: {story}." if story else ""),
        f"Medizinische Einordnung: {primary_dx}." if primary_dx else "",
        f"Geplante Verlaufskontrolle: in {followup}." if followup else "Der genaue Zeitpunkt der Kontrolle wird individuell festgelegt.",
    ]
    quick_text = _echo_build_layered_paragraph(candidates, min_words=80, max_words=120)
    out.append("### Kurzfazit (Schnellüberblick)")
    if quick_text:
        out.append(quick_text)
    else:
        out.append("Eine kompakte Einordnung ist derzeit nicht sicher möglich, weil zentrale Angaben fehlen.")
    out.append("")

    out.append("### Wichtigste Punkte")
    bullets: List[str] = [
        f"Ampel-Einordnung: {color.upper()} – {summary}",
        clarity,
    ]
    if msgs:
        bullets.extend(msgs[:3])
    if followup:
        bullets.append(f"Empfohlene klinische Verlaufskontrolle: in {followup}.")
    for bullet in bullets:
        btxt = _echo_limit_sentences(bullet, max_sentences=2)
        if btxt:
            out.append(f"- {btxt}")
    out.append("")

    out.append("### Details und Erklärungen")
    out.append("Die folgenden Abschnitte erklären die einzelnen Befunde ausführlicher.")
    out.append("")


def build_echo_patient_report(case: Dict[str, Any], *, mode: Optional[str] = None) -> str:
    ui: Dict[str, Any] = case.get("ui", {}) or {}
    dec: Dict[str, Any] = case.get("decision", {}) or {}
    env: Dict[str, Any] = case.get("env", {}) or {}
    glossary = _merge_echo_glossary(_load_echo_runtime_glossary())
    report_mode = (
        _normalize_echo_patient_mode(mode)
        or _normalize_echo_patient_mode(ui.get("patient_report_mode"))
        or ECHO_PATIENT_MODE_LAY
    )

    if not ui.get("echo_done") and not ui.get("cmr_done"):
        if report_mode == ECHO_PATIENT_MODE_SHORT:
            return "## Echo Kurzfassung (Patient*innen)\n\nAktuell sind keine Echo Werte dokumentiert.\n"
        return "## Echo Bericht (Patient*innen)\n\nAktuell sind keine Echo Werte dokumentiert.\n"

    first = str(ui.get("firstname") or "").strip()
    last = str(ui.get("name") or "").strip()
    pname = (first + " " + last).strip()
    salutation = f"Guten Tag {pname}," if pname else "Guten Tag,"
    story = str(ui.get("story") or "").strip()
    reason = str(ui.get("ph_reason_rhk") or "").strip()
    if reason.lower() == "keine angabe":
        reason = ""
    followup = str(env.get("followup_timing_desc") or "").strip()

    out: List[str] = []
    out.append("## Echo Bericht (Patient*innen)")
    out.append("")
    out.append("### Einordnung und Transparenz")
    out.append(salutation)
    out.append(
        "Dieser Bericht erklärt die Echo-Befunde in einfacher Sprache. "
        "Er ergänzt den medizinischen Fachbericht und ersetzt nicht das persönliche Arztgespräch."
    )
    out.append(
        "Ein Ultraschall des Herzens (Echokardiographie) zeigt Herzgröße und Pumpfunktion gut. "
        "Druckwerte im Lungenkreislauf sind im Echo jedoch Schätzwerte und können vom Rechtsherzkatheter abweichen."
    )
    out.append("")
    out.append("### Anlass der Untersuchung")
    if reason and story:
        out.append(f"Anlass laut Dokumentation: {reason}.")
        out.append(f"Kurz-Anamnese/Beschwerden: {story}")
    elif reason:
        out.append(f"Anlass laut Dokumentation: {reason}.")
    elif story:
        out.append(f"Kurz-Anamnese/Beschwerden: {story}")
    else:
        out.append("Ein konkreter Anlass wurde im Datensatz nicht strukturiert hinterlegt.")
    out.append("")

    color, summary = _ampel(ui)
    clarity = _echo_clarity_sentence(color)
    primary_dx = str(dec.get("primary_dx") or "").strip()

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

    if report_mode == ECHO_PATIENT_MODE_SHORT:
        short: List[str] = []
        short.append("## Echo Kurzfassung (Patient*innen)")
        short.append("")
        short.append(f"**Ampel: {color.upper()}** – {summary}")
        short.append(clarity)
        if reason:
            short.append(f"Anlass: {reason}.")
        elif story:
            short.append(f"Dokumentierte Beschwerden: {story}")
        if msgs:
            short.append("")
            short.append("### Kernaussagen")
            short.extend([f"- {m}" for m in msgs[:3]])
        short.append("")
        short.append("### Nächste Schritte")
        if color == "rot":
            short.append("- Zeitnahe Rücksprache und engmaschige Verlaufskontrollen sind besonders wichtig.")
            short.append("- Das kann belastend sein; wir besprechen mit Ihnen die nächsten Schritte klar und ohne unnötige Dramatisierung.")
        elif color == "gelb":
            short.append("- Verlaufskontrollen sind sinnvoll, um Veränderungen früh zu erkennen.")
        elif color == "grün":
            short.append("- Häufig reicht eine reguläre Verlaufskontrolle gemäß Behandlungsplan.")
        else:
            short.append("- Für die Planung werden zusätzliche Messwerte oder Verlaufsdaten benötigt.")
        if followup:
            short.append(f"- Empfohlene klinische Verlaufskontrolle: in {followup}.")
        short.append("- Bei deutlicher neuer Luftnot, Ohnmacht oder Brustschmerz bitte sofort Rücksprache halten.")
        return _finalize_echo_report_lines(short, glossary)

    _append_echo_layered_summary(
        out,
        color=color,
        summary=summary,
        clarity=clarity,
        msgs=msgs,
        followup=followup,
        reason=reason,
        story=story,
        primary_dx=primary_dx,
    )
    _append_echo_relevance_section(out, color=color, summary=summary, msgs=msgs)

    if msgs:
        out.append("### Was wurde gesehen")
        out.extend([f"- {m}" for m in msgs])
        out.append("")
    else:
        out.append("### Was wurde gesehen")
        out.append("- Es liegen derzeit zu wenige Messwerte vor, um eine verständliche Einordnung zu geben.")
        out.append("")

    refs: List[str] = []
    if _as_float(tapse) is not None:
        refs.append("- **TAPSE:** ab etwa 17 mm meist unauffällig (Orientierungswert).")
    if _as_float(trv) is not None:
        refs.append("- **TR Vmax:** unter etwa 2,8 m/s meist unauffällig (Orientierungswert).")
    if _as_float(paat) is not None:
        refs.append("- **PAAT:** über etwa 105 ms spricht eher gegen eine ausgeprägte Druckbelastung (Orientierungswert).")
    if refs:
        out.append("### Vergleich mit Orientierungswerten")
        out.extend(refs)
        out.append("")

    out.append("### Wie geht es weiter?")
    if color == "rot":
        out.append("- Bei roter Ampel sind zeitnahe Rücksprache und engere Verlaufskontrollen besonders wichtig.")
        out.append("- Das kann belastend sein; wir gehen die nächsten Schritte mit Ihnen ruhig und transparent durch.")
    elif color == "gelb":
        out.append("- Bei gelber Ampel sind Verlaufskontrollen sinnvoll, um die Entwicklung früh zu erkennen.")
    elif color == "grün":
        out.append("- Bei grüner Ampel reicht häufig eine reguläre Verlaufskontrolle gemäß Behandlungsplan.")
    else:
        out.append("- Für die nächste Planung werden zusätzliche Messwerte oder Verlaufsdaten benötigt.")
    if followup:
        out.append(f"- Empfohlene klinische Verlaufskontrolle: in {followup}.")
    out.append(
        "- Wichtig für den nächsten Termin: neue Luftnot, Schwindel/Ohnmacht, Schwellungen oder deutliche Leistungsabnahme dokumentieren."
    )
    out.append("")

    out.append("### Ansprechpartner und Kontakt")
    gp = str(ui.get("hausarzt") or ui.get("hausarzt_name") or "").strip()
    cardio = str(ui.get("kardiologe") or ui.get("kardiologe_name") or ui.get("ph_center_contact") or "").strip()
    phone = str(ui.get("contact_phone") or ui.get("telefon") or "").strip()
    if gp:
        out.append(f"- Hausärztliche Ansprechperson: {gp}")
    if cardio:
        out.append(f"- Kardiologie/PH-Team: {cardio}")
    if phone:
        out.append(f"- Telefon: {phone}")
    if not (gp or cardio or phone):
        out.append("- Hausärztin/Hausarzt: zeitnahe Befundbesprechung vereinbaren.")
        out.append("- Kardiologie/PH-Team: bei Warnzeichen noch am selben Tag Rücksprache halten.")
        out.append("- Bei akuter schwerer Luftnot, Brustschmerz oder Ohnmacht sofort Notruf 112.")
    out.append("")

    out.append("### Wann Rücksprache sinnvoll ist")
    out.append("- Wenn neue oder zunehmende Atemnot, Brustschmerzen, Ohnmacht, deutliche Wassereinlagerungen oder schnelle Leistungsabnahme auftreten.")
    out.append("- Wenn im Bericht eine gelbe oder rote Ampel steht oder wenn Ihr Behandlungsteam eine Katheteruntersuchung zur Druckmessung empfiehlt.")
    out.append("")
    out.append("Hinweis: Einzelwerte hängen von Bildqualität und Messbedingungen ab. Am wichtigsten ist die Gesamtschau aus Beschwerden, Untersuchung, Labor/Belastungstests und Verlauf.")
    out.append("")

    return _finalize_echo_report_lines(out, glossary)
