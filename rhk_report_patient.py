"""Patient-report builder family extracted from ``rhk_reports``.

Owns the entire patient-facing report path:
- Mode constants (PATIENT_REPORT_MODE_LAY / PATIENT_REPORT_MODE_SHORT)
- Jargon explanations and auto-glossary tables (DE / EN / ZH)
- Glossary handling, inline jargon explanations
- Archetype-driven narrative selection
- Measurement-block writers
- The top-level ``build_patient_report`` / ``_build_patient_report_content``
  entry points

K_* section keys are duplicated locally to keep the dependency graph
acyclic; if those rename in rhk_reports, update here too.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import random
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from rhk_base import (
    _ALL_P_MODULE_IDS,
    APP_VERSION,
    SafeDict,
    TextBlock,
    _compare_rhk_trend,
    _fmt,
    _normalize_module_ids,
    _safe_float,
    fmt_float,
    pmods_apply_overrides,
    pmods_get_force_optional,
)
from rhk_case_schema import CaseLike, CaseSection
from rhk_logging import log_exception
from rhk_ph_tx import format_ph_tx_episode_line
from rhk_report_cache import _cache_get, _cache_set, _case_fingerprint
from rhk_report_summary import (
    _get_ph_tx_episodes,
)


def _build_relevante_vorerkrankungen_line(ui: Dict[str, Any]) -> str:
    """Lazy import shim — function lives in rhk_reports."""
    from rhk_reports import _build_relevante_vorerkrankungen_line as _impl
    return _impl(ui)


def _report_db_text(case: CaseLike, audience: str, section: str) -> str:
    """Lazy import shim — function lives in rhk_reports."""
    from rhk_reports import _report_db_text as _impl
    return _impl(case, audience, section)

# Section keys mirrored from rhk_reports.
K_UI = "ui"
K_DERIVED = "derived"
K_SCORES = "scores"
K_DECISION = "decision"
K_ENV = "env"
K_HFPEF = "hfpef"
K_BUNDLE = "bundle"
K_MODULES = "modules"
K_STORY = "story"
K_CHD_POS = "chd_pos"
K_STATUS = "status"
K_RISK_CATEGORY = "risk_category"
K_PH_ETIOLOGY = "ph_etiology"
K_CANDIDATES = "candidates"
K_SEVERITY = "severity"

_REPORT_RECOVERABLE_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    TypeError,
    ValueError,
    ImportError,
    ModuleNotFoundError,
)


PATIENT_REPORT_MODE_LAY = "laienbefund"
PATIENT_REPORT_MODE_SHORT = "kurzfassung"

_PATIENT_REPORT_MODE_ALIASES: Dict[str, str] = {
    "laienbefund": PATIENT_REPORT_MODE_LAY,
    "laie": PATIENT_REPORT_MODE_LAY,
    "lay": PATIENT_REPORT_MODE_LAY,
    "patient": PATIENT_REPORT_MODE_LAY,
    "default": PATIENT_REPORT_MODE_LAY,
    "verstaendlich": PATIENT_REPORT_MODE_LAY,
    "verständlich": PATIENT_REPORT_MODE_LAY,
    "kurzfassung": PATIENT_REPORT_MODE_SHORT,
    "kurz": PATIENT_REPORT_MODE_SHORT,
    "short": PATIENT_REPORT_MODE_SHORT,
    "compact": PATIENT_REPORT_MODE_SHORT,
    "summary": PATIENT_REPORT_MODE_SHORT,
}

_PATIENT_JARGON_EXPLANATIONS: List[Tuple[str, str]] = [
    ("KM", "Kontrastmittel"),
    ("DD", "Differentialdiagnose (andere mögliche Erklärung)"),
    ("RR", "Blutdruck"),
    ("LWS", "Lendenwirbelsäule"),
    ("BWS", "Brustwirbelsäule"),
    ("HWS", "Halswirbelsäule"),
    ("IV", "über die Vene"),
    ("i.v.", "über die Vene"),
    ("i.m.", "in den Muskel"),
    ("s.c.", "unter die Haut"),
    ("Ödem", "Wassereinlagerung"),
    ("Infiltrat", "verdichtetes Gewebe, oft als Entzündungszeichen"),
    ("Läsion", "Gewebeveränderung"),
    ("benigne", "gutartig"),
    ("maligne", "bösartig"),
    ("Stenose", "Engstelle"),
    ("Insuffizienz", "Funktionseinschränkung"),
    ("Embolie", "Gefäßverschluss, meist durch ein Blutgerinnsel"),
    ("Thrombose", "Blutgerinnsel in einem Gefäß"),
    ("Fibrose", "narbiger Umbau von Gewebe"),
    ("Ischämie", "Minderdurchblutung"),
    ("Dilatation", "Erweiterung eines Gefäßes oder Hohlraums"),
    ("Hypertrophie", "Verdickung/Vergrößerung von Gewebe"),
    ("ESC/ERS-Risikoeinstufung", "Risikoeinschätzung nach europäischen Fachleitlinien"),
    ("WHO-Funktionsklasse", "Einteilung Ihrer Alltags-Belastbarkeit"),
    ("ICD-10", "medizinische Diagnose-Codes"),
    ("Volumenchallenge", "Flüssigkeitsbelastungstest"),
    ("Vasoreaktivität", "Test, wie gut sich die Lungengefäße unter einem Kurzzeit-Medikament entspannen"),
    ("mPAP", "mittlerer Druck in den Lungengefäßen"),
    ("PAWP", "Druck vor der linken Herzhälfte"),
    ("PVR", "Widerstand in den Lungengefäßen"),
    ("RAP", "Druck im rechten Vorhof"),
    ("CI", "Pumpleistung des Herzens bezogen auf die Körperoberfläche"),
    ("CO", "Blutmenge, die das Herz pro Minute pumpt"),
    ("WU", "Einheit für den Gefäßwiderstand"),
    ("sPAP", "oberer Druckwert in der Lungenarterie"),
    ("dPAP", "unterer Druckwert in der Lungenarterie"),
    ("präkapillär", "Druckerhöhung eher in den Lungengefäßen selbst"),
    ("postkapillär", "Druckerhöhung eher durch die linke Herzseite"),
    ("IpcPH", "Form mit Druckübertragung vor allem von der linken Herzseite"),
    ("CpcPH", "kombinierte Form mit linker Herzseite und Lungengefäßen"),
    ("CTEPH", "Lungenhochdruck durch ältere Blutgerinnsel"),
    ("WHO-FC", "WHO-Funktionsklasse (Alltags-Belastbarkeit)"),
    ("6MWD", "Strecke im 6-Minuten-Gehtest"),
    ("BNP", "Blutwert als Hinweis auf Herzbelastung"),
    ("NT-proBNP", "Blutwert als Hinweis auf Herzbelastung"),
    ("NT pro BNP", "Blutwert als Hinweis auf Herzbelastung"),
]

# Auto-glossary — general-medical shortcuts that can appear in a patient report
# and are NOT already covered by PATIENT_GLOSSARY. PH-specific terms
# (PH, PAH, CTEPH, CO, WU, sPAP, …) are deliberately *not* listed here to avoid
# split-brain definitions; PATIENT_GLOSSARY is the single source of truth for
# those. Ambiguous 2-letter abbreviations like "IV" are excluded because they
# collide with Roman numerals (e.g. "Funktionsklasse IV").
#
# At report time, ``_collect_used_glossary_terms`` filters this list down to
# terms that actually appear in the rendered text, so listing many entries here
# does not bloat output — it only widens the safety net for patient-visible
# jargon.
_PATIENT_AUTO_GLOSSARY: Dict[str, str] = {
    # Standard clinical shortcuts
    "KM": "Kontrastmittel: Substanz, die bestimmte Strukturen in der Bildgebung besser sichtbar macht.",
    "DD": "Differentialdiagnose: andere mögliche Erklärung für einen Befund.",
    "RR": "Blutdruck (Riva-Rocci).",
    "i.v.": "Intravenös: Gabe über die Vene.",
    "i.m.": "Intramuskulär: Gabe in den Muskel.",
    "s.c.": "Subkutan: Gabe unter die Haut.",
    # Anatomy abbreviations (spine)
    "LWS": "Lendenwirbelsäule (unterer Rücken).",
    "BWS": "Brustwirbelsäule (mittlerer Rücken).",
    "HWS": "Halswirbelsäule (oberer Rücken/Nacken).",
    # Imaging / pathology language
    "Läsion": "Eine umschriebene Veränderung im Gewebe — kann harmlos oder krankhaft sein.",
    "benigne": "Gutartig.",
    "maligne": "Bösartig.",
    "Nodulus": "Knötchen: kleine rundliche Gewebeveränderung.",
    "Tumor": "Schwellung oder Gewebeneubildung — sagt noch nichts über Gut- oder Bösartigkeit aus.",
    "Atelektase": "Nicht belüfteter Lungenabschnitt.",
    "Konsolidierung": "Lungenabschnitt mit Flüssigkeit oder Gewebeverdichtung (z. B. bei Entzündung).",
    "Infiltrat": "Einlagerung von Flüssigkeit oder Zellen im Gewebe — oft bei Entzündungen.",
    "Ödem": "Wasseransammlung im Gewebe.",
    # Vessels / heart
    "Stenose": "Engstelle in einem Gefäß oder Hohlorgan.",
    "Insuffizienz": "Funktionseinschränkung eines Organs oder einer Struktur.",
    "Embolie": "Gefäßverschluss, meist durch eingeschwemmtes Gerinnsel.",
    "Thrombose": "Blutgerinnsel in einem Gefäß.",
    "Fibrose": "Narbiger Umbau von Gewebe.",
    "Ischämie": "Minderdurchblutung eines Gewebes.",
    "Dilatation": "Erweiterung eines Gefäßes oder Hohlraums.",
    "Hypertrophie": "Verdickung/Vergrößerung von Gewebe.",
    "Erguss": "Flüssigkeitsansammlung in einem Körperraum.",
    # Imaging modalities
    "MRT": "Magnetresonanztomographie: bildgebende Untersuchung ohne Röntgenstrahlung.",
    "CMR": "Kardio-MRT: Herzuntersuchung im MRT.",
    "Echo": "Echokardiographie: Ultraschalluntersuchung des Herzens.",
}

_PATIENT_JARGON_EXPLANATIONS_EN: List[Tuple[str, str]] = [
    ("KM", "contrast agent"),
    ("DD", "differential diagnosis (other possible explanation)"),
    ("RR", "blood pressure"),
    ("LWS", "lumbar spine"),
    ("BWS", "thoracic spine"),
    ("HWS", "cervical spine"),
    ("IV", "intravenous"),
    ("i.v.", "intravenous"),
    ("i.m.", "intramuscular"),
    ("s.c.", "subcutaneous"),
    ("Ödem", "fluid retention"),
    ("Infiltrat", "consolidated tissue, often a sign of inflammation"),
    ("Läsion", "tissue change"),
    ("benigne", "benign"),
    ("maligne", "malignant"),
    ("Stenose", "narrowing"),
    ("Insuffizienz", "functional impairment"),
    ("Embolie", "vessel blockage, usually by a blood clot"),
    ("Thrombose", "blood clot in a vessel"),
    ("Fibrose", "scarring of tissue"),
    ("Ischämie", "reduced blood flow"),
    ("Dilatation", "widening of a vessel or cavity"),
    ("Hypertrophie", "thickening/enlargement of tissue"),
    ("ESC/ERS-Risikoeinstufung", "risk classification per European guidelines"),
    ("WHO-Funktionsklasse", "classification of your everyday exercise capacity"),
    ("ICD-10", "medical diagnosis codes"),
    ("Volumenchallenge", "fluid challenge test"),
    ("Vasoreaktivität", "test of how well the pulmonary vessels relax with a short-acting medication"),
    ("mPAP", "mean pulmonary artery pressure"),
    ("PAWP", "pressure before the left heart"),
    ("PVR", "pulmonary vascular resistance"),
    ("RAP", "right atrial pressure"),
    ("CI", "cardiac output relative to body surface area"),
    ("CO", "amount of blood the heart pumps per minute"),
    ("WU", "unit for vascular resistance"),
    ("sPAP", "upper pressure value in the pulmonary artery"),
    ("dPAP", "lower pressure value in the pulmonary artery"),
    ("präkapillär", "pressure increase mainly in the pulmonary vessels themselves"),
    ("postkapillär", "pressure increase mainly from the left side of the heart"),
    ("IpcPH", "form with pressure mainly from the left side of the heart"),
    ("CpcPH", "combined form involving both the left heart and pulmonary vessels"),
    ("CTEPH", "pulmonary hypertension from older blood clots"),
    ("WHO-FC", "WHO functional class (everyday exercise capacity)"),
    ("6MWD", "distance walked in the 6-minute walk test"),
    ("BNP", "blood marker indicating cardiac strain"),
    ("NT-proBNP", "blood marker indicating cardiac strain"),
    ("NT pro BNP", "blood marker indicating cardiac strain"),
]

_PATIENT_JARGON_EXPLANATIONS_ZH: List[Tuple[str, str]] = [
    ("KM", "造影剂"),
    ("DD", "鉴别诊断（其他可能的解释）"),
    ("RR", "血压"),
    ("LWS", "腰椎"),
    ("BWS", "胸椎"),
    ("HWS", "颈椎"),
    ("IV", "静脉给药"),
    ("i.v.", "静脉给药"),
    ("i.m.", "肌肉注射"),
    ("s.c.", "皮下注射"),
    ("Ödem", "水肿"),
    ("Infiltrat", "组织浸润，常为炎症征象"),
    ("Läsion", "组织病变"),
    ("benigne", "良性"),
    ("maligne", "恶性"),
    ("Stenose", "狭窄"),
    ("Insuffizienz", "功能障碍"),
    ("Embolie", "血管栓塞，通常由血栓引起"),
    ("Thrombose", "血管内血栓"),
    ("Fibrose", "组织纤维化"),
    ("Ischämie", "缺血"),
    ("Dilatation", "血管或腔室扩张"),
    ("Hypertrophie", "组织增厚/增大"),
    ("ESC/ERS-Risikoeinstufung", "依据欧洲指南的风险分级"),
    ("WHO-Funktionsklasse", "日常活动耐量分级"),
    ("ICD-10", "医学诊断编码"),
    ("Volumenchallenge", "液体负荷试验"),
    ("Vasoreaktivität", "肺血管对短效药物的舒张反应测试"),
    ("mPAP", "平均肺动脉压"),
    ("PAWP", "左心前压力"),
    ("PVR", "肺血管阻力"),
    ("RAP", "右心房压力"),
    ("CI", "相对于体表面积的心输出量"),
    ("CO", "心脏每分钟泵出的血量"),
    ("WU", "血管阻力单位"),
    ("sPAP", "肺动脉收缩压"),
    ("dPAP", "肺动脉舒张压"),
    ("präkapillär", "压力升高主要源于肺血管本身"),
    ("postkapillär", "压力升高主要源于左心"),
    ("IpcPH", "以左心因素为主的类型"),
    ("CpcPH", "左心与肺血管共同参与的混合类型"),
    ("CTEPH", "由陈旧性血栓引起的肺动脉高压"),
    ("WHO-FC", "WHO功能分级（日常活动耐量）"),
    ("6MWD", "6分钟步行试验距离"),
    ("BNP", "提示心脏负荷的血液标志物"),
    ("NT-proBNP", "提示心脏负荷的血液标志物"),
    ("NT pro BNP", "提示心脏负荷的血液标志物"),
]

_PATIENT_AUTO_GLOSSARY_EN: Dict[str, str] = {
    "KM": "Contrast agent: substance that makes certain structures more visible in imaging.",
    "DD": "Differential diagnosis: another possible explanation for a finding.",
    "RR": "Blood pressure (Riva-Rocci).",
    "LWS": "Lumbar spine (lower back).",
    "BWS": "Thoracic spine (mid back).",
    "HWS": "Cervical spine (neck area).",
    "IV": "Intravenous: administered through a vein.",
    "i.v.": "Intravenous: administered through a vein.",
    "i.m.": "Intramuscular: administered into the muscle.",
    "s.c.": "Subcutaneous: administered under the skin.",
    "Ödem": "Fluid retention in the tissue.",
    "Infiltrat": "Consolidated tissue, often indicating inflammation.",
    "Läsion": "Tissue change; may be benign or malignant.",
    "benigne": "Benign (not cancerous).",
    "maligne": "Malignant (cancerous).",
    "Stenose": "Narrowing of a vessel or hollow organ.",
    "Insuffizienz": "Impaired function of an organ or structure.",
    "Embolie": "Vessel blockage, usually from a dislodged blood clot.",
    "Thrombose": "Blood clot inside a vessel.",
    "Fibrose": "Scarring of tissue.",
    "Ischämie": "Reduced blood supply to a tissue.",
    "Dilatation": "Widening of a vessel or cavity.",
    "Hypertrophie": "Thickening or enlargement of tissue.",
    "Konsolidierung": "Consolidation of lung tissue (e.g., from inflammation).",
    "Atelektase": "Incompletely aerated section of lung.",
    "Erguss": "Fluid collection in a body cavity.",
    "Nodulus": "Small nodule.",
    "Tumor": "Tissue growth; may be benign or malignant.",
    "CT": "Computed tomography: imaging with cross-sectional images.",
    "MRT": "Magnetic resonance imaging: imaging without radiation.",
    "CMR": "Cardiac MRI: heart examination using MRI.",
    "Echo": "Echocardiography: ultrasound examination of the heart.",
    "PH": "Pulmonary hypertension (high blood pressure in the lungs).",
    "PAH": "Pulmonary arterial hypertension, a subtype of pulmonary hypertension.",
    "CTEPH": "Chronic thromboembolic pulmonary hypertension: pulmonary hypertension from older blood clots.",
    "CO": "Cardiac output: amount of blood the heart pumps per minute.",
    "WU": "Wood Units: measurement unit for pulmonary vascular resistance.",
    "sPAP": "Systolic pressure in the pulmonary artery.",
    "dPAP": "Diastolic pressure in the pulmonary artery.",
    "präkapillär": "Pattern where the pressure increase mainly originates in the pulmonary vessels themselves.",
    "postkapillär": "Pattern where the left side of the heart contributes to the pressure increase.",
    "IpcPH": "Isolated post-capillary pulmonary hypertension (pressure mainly from the left heart).",
    "CpcPH": "Combined post- and pre-capillary pulmonary hypertension (left heart plus pulmonary vessel changes).",
    "WHO-FC": "WHO functional class: classification of everyday exercise capacity in heart/lung disease.",
    "6MWD": "6-minute walk test distance: distance walked in six minutes.",
    "NT-proBNP": "Blood marker that can indicate cardiac strain.",
    "NT pro BNP": "Alternative spelling of NT-proBNP.",
}

_PATIENT_AUTO_GLOSSARY_ZH: Dict[str, str] = {
    "KM": "造影剂：使成像中某些结构更清晰可见的物质。",
    "DD": "鉴别诊断：对某一发现的其他可能解释。",
    "RR": "血压（Riva-Rocci法）。",
    "LWS": "腰椎（下背部）。",
    "BWS": "胸椎（中背部）。",
    "HWS": "颈椎（颈部区域）。",
    "IV": "静脉注射：通过静脉给药。",
    "i.v.": "静脉注射：通过静脉给药。",
    "i.m.": "肌肉注射：注入肌肉。",
    "s.c.": "皮下注射：注入皮下。",
    "Ödem": "组织中的水肿。",
    "Infiltrat": "组织浸润，常提示炎症。",
    "Läsion": "组织病变；可为良性或恶性。",
    "benigne": "良性。",
    "maligne": "恶性。",
    "Stenose": "血管或空腔器官的狭窄。",
    "Insuffizienz": "器官或结构的功能障碍。",
    "Embolie": "血管栓塞，通常由脱落的血栓引起。",
    "Thrombose": "血管内的血栓。",
    "Fibrose": "组织纤维化。",
    "Ischämie": "组织供血不足。",
    "Dilatation": "血管或腔室扩张。",
    "Hypertrophie": "组织增厚或增大。",
    "Konsolidierung": "肺组织实变（如炎症所致）。",
    "Atelektase": "肺部未充分通气的区域。",
    "Erguss": "体腔内的积液。",
    "Nodulus": "小结节。",
    "Tumor": "组织新生物；可为良性或恶性。",
    "CT": "计算机断层扫描：横断面成像检查。",
    "MRT": "磁共振成像：无辐射的成像检查。",
    "CMR": "心脏磁共振：利用MRI进行的心脏检查。",
    "Echo": "超声心动图：心脏超声检查。",
    "PH": "肺动脉高压（肺部血压升高）。",
    "PAH": "肺动脉性高压，肺动脉高压的一种亚型。",
    "CTEPH": "慢性血栓栓塞性肺动脉高压：由陈旧性血栓引起的肺动脉高压。",
    "CO": "心输出量：心脏每分钟泵出的血量。",
    "WU": "Wood单位：肺血管阻力的计量单位。",
    "sPAP": "肺动脉收缩压。",
    "dPAP": "肺动脉舒张压。",
    "präkapillär": "压力升高主要源于肺血管本身的模式。",
    "postkapillär": "左心参与导致压力升高的模式。",
    "IpcPH": "孤立性毛细血管后肺动脉高压（压力主要来自左心）。",
    "CpcPH": "混合性毛细血管后和毛细血管前肺动脉高压（左心因素加肺血管病变）。",
    "WHO-FC": "WHO功能分级：心肺疾病患者日常活动耐量的分级。",
    "6MWD": "6分钟步行试验距离：6分钟内行走的距离。",
    "NT-proBNP": "可提示心脏负荷的血液标志物。",
    "NT pro BNP": "NT-proBNP的另一种写法。",
}


def _get_patient_jargon_explanations(lang: str = "de") -> List[Tuple[str, str]]:
    """Return the jargon-to-lay-explanation list for the given language."""
    if lang == "en":
        return _PATIENT_JARGON_EXPLANATIONS_EN
    if lang == "zh":
        return _PATIENT_JARGON_EXPLANATIONS_ZH
    return _PATIENT_JARGON_EXPLANATIONS


def _get_patient_auto_glossary(lang: str = "de") -> Dict[str, str]:
    """Return the auto-glossary dict for the given language."""
    if lang == "en":
        return _PATIENT_AUTO_GLOSSARY_EN
    if lang == "zh":
        return _PATIENT_AUTO_GLOSSARY_ZH
    return _PATIENT_AUTO_GLOSSARY


_PATIENT_PANIC_WORD_REPLACEMENTS: List[Tuple[str, str]] = [
    (r"\bgefährlich\s+wirkend\b", "ernst zu nehmen"),
    (r"\bschlimm(?:e|er|es|en)?\b", "ausgeprägt"),
    (r"\bgefährlich(?:e|er|es|en)?\b", "ernst zu nehmen"),
    (r"\bbedrohlich(?:e|er|es|en)?\b", "ernst zu nehmen"),
    (r"\bdramatisch(?:e|er|es|en)?\b", "deutlich"),
    (r"\bkatastrophal(?:e|er|es|en)?\b", "ausgeprägt"),
]


def _normalize_patient_report_mode(mode: Any) -> Optional[str]:
    if mode is None:
        return None
    token = str(mode or "").strip().lower()
    if not token:
        return None
    token = token.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    token = re.sub(r"[\s_-]+", "", token)
    return _PATIENT_REPORT_MODE_ALIASES.get(token)


def _resolve_patient_report_mode(case: CaseLike, mode: Optional[str] = None) -> str:
    explicit = _normalize_patient_report_mode(mode)
    if explicit:
        return explicit
    if isinstance(case, dict):
        ui = case.get(K_UI) or {}
        if isinstance(ui, dict):
            ui_mode = _normalize_patient_report_mode(ui.get("patient_report_mode"))
            if ui_mode:
                return ui_mode
    return PATIENT_REPORT_MODE_LAY


def _replace_patient_jargon_once(line: str, term: str, explanation: str) -> str:
    """Inject a lay-language explanation exactly once per term in a line.

    Clinical-UX guardrails (v27.4.24+):
    - Never expand terms whose explanation is already present in the line.
    - Never expand terms that appear **inside parentheses** — those are already
      glossary hints and a second expansion creates nested ``((...))`` clutter.
    - Never expand terms that fall inside a previous expansion (sentinel-marked)
      — this prevents chain reactions such as "Sotatercept" expanding to text
      containing "BMPR2", which would then also be expanded.
    - Skip the expansion when the preceding word duplicates the first word of
      the explanation (e.g. "Blutwert BNP" + explanation "Blutwert als Hinweis …"
      → avoids doubled "Blutwert Blutwert …").
    """
    if not line:
        return line
    # Strip sentinels only for the "already present" comparison.
    bare_line = _strip_expansion_sentinels(line)
    if explanation.lower() in bare_line.lower():
        return line
    # The (?<![\w-]) boundary also excludes matches that are *sub-parts* of a
    # hyphenated compound term (e.g. "Funktionsklasse" inside "WHO-Funktionsklasse").
    # Without this, a shorter glossary key like "Funktionsklasse" would inject
    # its own explanation in the middle of a longer, already-canonical term.
    pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", flags=re.IGNORECASE)
    # Walk all matches and pick the first one that is not inside a protected region.
    chosen = None
    for match in pattern.finditer(line):
        start, end = match.span()
        before = line[:start]
        after = line[end:]
        # Skip matches inside a prior expansion (between \u0002 … \u0003).
        last_open_sentinel = before.rfind(_EXPANSION_SENTINEL_OPEN)
        last_close_sentinel = before.rfind(_EXPANSION_SENTINEL_CLOSE)
        if last_open_sentinel > last_close_sentinel:
            continue
        # Skip matches inside an unclosed literal parenthesis.
        last_open = before.rfind("(")
        last_close = before.rfind(")")
        if last_open > last_close:
            continue
        # Skip if the term is immediately followed by a parenthetical annotation
        # (e.g. "RAP (9 mmHg)") — adding a glossary expansion there would produce
        # unsightly doubled parentheses like "RAP (Druck im rechten Vorhof) (9 mmHg)".
        # Markdown emphasis markers (``**``, ``__``, ``*``, ``_``) between the
        # term and the opening paren are ignored for this check, so that
        # ``**NT-proBNP** (Blutwert bei Herzbelastung)`` is also recognised as
        # "already annotated" and the inline glossary skips the bold label.
        if re.match(r"(?:\*{1,3}|_{1,3})?\s*\(", after or ""):
            continue
        # Avoid "Blutwert Blutwert …" duplication.
        first_word_of_explanation = re.split(r"\s+", explanation.strip(), maxsplit=1)[0].casefold()
        preceding_words = re.findall(r"\w+", before)
        if preceding_words and preceding_words[-1].casefold() == first_word_of_explanation:
            continue
        chosen = match
        break
    if not chosen:
        return line
    s, e = chosen.span()
    # Defensive: if the explanation itself contains parentheticals, strip them
    # before wrapping — otherwise we produce clutter like
    # ``DD (Differentialdiagnose (andere mögliche Erklärung))``. The inline
    # form should always be a clean noun phrase; the full definition still
    # lives in the glossary section.
    safe_explanation = re.sub(r"\s*\([^()]*\)", "", str(explanation))
    safe_explanation = re.sub(r"\s{2,}", " ", safe_explanation).strip(" ,;:-–—")
    if not safe_explanation:
        safe_explanation = str(explanation)
    # UX: keep the original medical term as the primary noun and add the
    # lay-language explanation in parentheses. Flipping the order (explanation
    # first, term in parens) broke drug names and German grammar, e.g.
    #   "Bei der Vasoreaktivität" → "Bei der Test, wie gut sich …"   (ungrammatical)
    #   "Sotatercept (aktuell …)"  → "Neueres Medikament … (Sotatercept) (aktuell …)"
    wrapped = (
        f"{line[s:e]} "
        f"({_EXPANSION_SENTINEL_OPEN}{safe_explanation}{_EXPANSION_SENTINEL_CLOSE})"
    )
    return line[:s] + wrapped + line[e:]


def _inline_explanation_from_glossary_text(explanation: str) -> str:
    """Return a short, grammatically well-formed inline explanation.

    Used when expanding a medical term inline (e.g. "mPAP" →
    "mittlerer Druck in den Lungengefäßen (mPAP)"). Keeps only the first
    sentence/clause and falls back to a word-boundary cut — never in the
    middle of a word — so we do not produce artefacts like ``"BMPR2)/A..."``.

    Clinical-UX guardrails:
    - Strip **nested parentheticals** from the short form so the inline
      expansion never produces clutter like ``"Antikoagulation (Blutverdünnung
      (Gerinnungshemmung), um …)"``. Nested ``((…))`` reads like a parser bug.
    - Cut at the first comma after a clean noun phrase: ``"Blutverdünnung,
      um Blutgerinnsel zu verhindern"`` → ``"Blutverdünnung"``. The full
      explanation remains available in the glossary section.
    """
    txt = re.sub(r"\s+", " ", str(explanation or "").strip())
    if not txt:
        return ""
    # Remove nested parentheticals (non-greedy) — defines a safe short form
    # that cannot re-introduce ``(inner)`` clutter when inlined into parens.
    stripped_parens = re.sub(r"\s*\([^()]*\)", "", txt)
    stripped_parens = re.sub(r"\s{2,}", " ", stripped_parens).strip()
    if stripped_parens:
        txt = stripped_parens
    # Prefer the first clause before a colon; otherwise the first sentence.
    if ":" in txt:
        txt = txt.split(":", 1)[0].strip()
    elif "." in txt:
        txt = txt.split(".", 1)[0].strip()
    # For short noun-phrase definitions a trailing relative clause is noise.
    # Prefer the first comma-bounded clause when it is long enough to stand
    # alone ("Blutverdünnung, um …" → "Blutverdünnung").
    head = txt.split(",", 1)[0].strip()
    if len(head) >= 12:
        txt = head
    max_len = 90
    if len(txt) > max_len:
        cut = txt[:max_len]
        # Back up to the last space to avoid cutting mid-word.
        space_idx = cut.rfind(" ")
        if space_idx >= 30:  # keep at least a usable chunk
            cut = cut[:space_idx]
        txt = cut.rstrip(" ,;:-–—") + "…"
    return txt


def _build_patient_inline_terms(glossary: Optional[Dict[str, str]] = None, lang: str = "de") -> List[Tuple[str, str]]:
    terms: List[Tuple[str, str]] = list(_get_patient_jargon_explanations(lang))
    seen = {str(term).casefold() for term, _ in terms}
    src = glossary or _get_patient_auto_glossary(lang)
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


def _normalize_patient_certainty_line(line: str) -> str:
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
    # Expand the medical shorthand "V.a." / "V. a." / "V.A." → "Verdacht auf ".
    # Require the first dot so we never chew off the "Va" prefix of words like
    # "Vasoreaktivität", "Vaskulär", "Variante" etc. Examples that still match:
    #   "V.a. PAH"          → "Verdacht auf PAH"
    #   "V. a. Sarkoidose"  → "Verdacht auf Sarkoidose"
    # Examples that are now correctly preserved:
    #   "Vasoreaktivität"   → "Vasoreaktivität"  (no change)
    #   "Vaskulitis"        → "Vaskulitis"       (no change)
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


def _sanitize_patient_tone(line: str) -> str:
    out = str(line or "")
    if not out:
        return out
    for pattern, replacement in _PATIENT_PANIC_WORD_REPLACEMENTS:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    out = re.sub(r"(?i)\bernst zu nehmen\s+wirkend\b", "ernst zu nehmen", out)
    return out


_PATIENT_META_LINE_RE = re.compile(
    r"^\s*\*{0,2}\s*(?:Name|Datum|Date|Version|Patient|Fallnummer|Case|Versionsstand)\s*:",
    re.IGNORECASE,
)
# Paired sentinels used to mark a freshly-inserted lay explanation so that
# subsequent jargon expansions in the same line do not chain into it
# (e.g. expanding "BMPR2" inside a text that was just added as the
# explanation for "Sotatercept").
_EXPANSION_SENTINEL_OPEN = "\u0002"
_EXPANSION_SENTINEL_CLOSE = "\u0003"


def _strip_expansion_sentinels(text: str) -> str:
    if not text:
        return text
    return text.replace(_EXPANSION_SENTINEL_OPEN, "").replace(_EXPANSION_SENTINEL_CLOSE, "")


def _rewrite_patient_line_for_lay_mode(
    line: str,
    *,
    inline_terms: Optional[List[Tuple[str, str]]] = None,
    lang: str = "de",
) -> str:
    txt = str(line or "")
    if not txt or txt.lstrip().startswith("#"):
        return txt
    # Skip metadata / header lines (Name, Datum, Version …). These carry
    # identifying information that must NOT be rewritten by the lay-language
    # glossary — otherwise patient names that happen to contain medical
    # abbreviations (e.g. test cases like "PAH Restart …") get mangled.
    if _PATIENT_META_LINE_RE.match(txt):
        return txt
    out = _normalize_patient_certainty_line(txt) if lang == "de" else txt
    for term, explanation in (inline_terms or _get_patient_jargon_explanations(lang)):
        out = _replace_patient_jargon_once(out, term, explanation)
    out = _strip_expansion_sentinels(out)
    out = _sanitize_patient_tone(out)
    return out


def _rewrite_patient_lines_for_lay_mode(
    lines: List[str],
    glossary: Optional[Dict[str, str]] = None,
    lang: str = "de",
) -> List[str]:
    inline_terms = _build_patient_inline_terms(glossary, lang=lang)
    return [
        _rewrite_patient_line_for_lay_mode(str(ln or ""), inline_terms=inline_terms, lang=lang)
        for ln in (lines or [])
    ]

def _stable_patient_seed(case: CaseLike) -> int:
    """Deterministic seed for patient text variants.

    Goal: different cases → different wording, but same case → stable wording
    across repeated generations.
    """
    ui = case.get(K_UI) or {}
    der = case.get(K_DERIVED) or {}
    dec = case.get(K_DECISION) or {}

    # Select stable, clinically relevant discriminators for variant diversity.
    # More discriminators → more text variety across different patients.
    _age_raw = _safe_float(ui.get("age"))
    _age_bucket = "young" if (_age_raw and _age_raw < 40) else "elderly" if (_age_raw and _age_raw > 70) else "adult"
    key = {
        "bundle": dec.get(K_BUNDLE),
        "primary_dx": dec.get("primary_dx"),
        "hemo_category": der.get("hemo_category"),
        "exercise_done": bool(der.get("exercise_done")),
        "exercise_pattern": der.get("exercise_pattern"),
        "step_up_present": bool(der.get("step_up_present")),
        "ct_ild": bool(ui.get("ct_ild")),
        "ct_emphysema": bool(ui.get("ct_emphysema")),
        "vq_defect": bool(ui.get("vq_defect")),
        "hfpef_category": der.get("hfpef_category"),
        "anemia": bool(der.get("anemia")),
        "congestion": bool(der.get("congestion_likely")),
        # v27.5: additional discriminators for richer individualisation
        "age_bucket": _age_bucket,
        "sex": str(ui.get("sex") or "").strip().lower(),
        "who_fc": str(ui.get("who_fc") or "").strip(),
        "diabetes": bool(ui.get("diabetes")),
        "copd": bool(ui.get("copd") or ui.get("ct_emphysema")),
        "renal": bool(der.get("renal_impairment") or (_safe_float(ui.get("krea")) and _safe_float(ui.get("krea")) > 1.5)),
        "obesity": bool(der.get("bmi") and _safe_float(der.get("bmi")) and _safe_float(der.get("bmi")) > 30),
        "has_prior_rhk": bool(ui.get("prior_mpap") or ui.get("prior_pawp")),
    }
    s = json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _patient_name(ui: Dict[str, Any]) -> str:
    # Support multiple possible UI key names (historic variants)
    first = ""
    for k in ("firstname", "first_name", "vorname", "first"):
        v = ui.get(k)
        if isinstance(v, str) and v.strip():
            first = v.strip()
            break

    last = ""
    for k in ("name", "lastname", "last_name", "nachname", "surname"):
        v = ui.get(k)
        if isinstance(v, str) and v.strip():
            last = v.strip()
            break

    full = (first + " " + last).strip()
    return full



def _patient_salutation(ui: Dict[str, Any], rng: random.Random, lang: str = "de") -> str:
    """Returns a stable, formal salutation.

    Patient-facing report templates predominantly use formal address (Sie/Ihre).
    Randomly switching between "Hallo" and "Guten Tag" caused an inconsistent
    register (Hallo + Sie), which is confusing for patients.
    """
    name = _patient_name(ui)
    if lang == "en":
        return f"Dear {name}," if name else "Dear Patient,"
    if lang == "zh":
        return f"尊敬的{name}：" if name else "尊敬的患者："
    if name:
        return f"Guten Tag {name},"
    return "Guten Tag,"


def _load_patient_textdb(lang: str = "de") -> Tuple[Dict[str, Any], Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """Loads patient-facing text blocks if available (flat file, no folders).

    When *lang* is ``"en"`` or ``"zh"``, the corresponding localised module
    (e.g. ``rhk_textdb_patient_en``) is tried first; it falls back to the
    German default so that missing translations never crash the report.
    """
    import sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # Build ordered candidate list: lang-specific first, then German fallback.
    # v27.4.25+: the ``rhk_textdb_patient_v7`` shim was removed — its extra
    # ``_add()`` calls would overwrite the now-richer 6-variant blocks with
    # the 2-variant legacy versions, which hurts individualization.
    candidates: list[str] = []
    if lang and lang != "de":
        candidates.append(f"rhk_textdb_patient_{lang}")
    candidates.append("rhk_textdb_patient")

    for mod_name in candidates:
        try:
            mod = __import__(mod_name)
            blocks = getattr(mod, "PATIENT_BLOCKS", None)
            bundles = getattr(mod, "PATIENT_BUNDLES", None)
            module_summary = getattr(mod, "PATIENT_MODULE_SUMMARY", {}) or {}
            glossary = getattr(mod, "PATIENT_GLOSSARY", {}) or {}
            if isinstance(blocks, dict) and isinstance(bundles, dict):
                if not isinstance(module_summary, dict):
                    module_summary = {}
                if not isinstance(glossary, dict):
                    glossary = {}
                return blocks, bundles, module_summary, glossary
        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_REP_IMPORT_PATIENT_TEXTDB", "Patient text database import variant failed.", exc, module=mod_name)
            continue
    return {}, {}, {}, {}


def _load_echo_patient_textdb() -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Loads echo patient-facing text blocks if available (flat file, no folders)."""
    import sys
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    for mod_name in ("rhk_textdb_echo_patient",):
        try:
            mod = __import__(mod_name)
            blocks = getattr(mod, "ECHO_PATIENT_BLOCKS", None)
            glossary = getattr(mod, "ECHO_PATIENT_GLOSSARY", {}) or {}
            if isinstance(blocks, dict):
                if not isinstance(glossary, dict):
                    glossary = {}
                return blocks, glossary
        except (ImportError, ModuleNotFoundError, AttributeError, TypeError, ValueError) as exc:
            log_exception("RHK_REP_IMPORT_ECHO_PATIENT_TEXTDB", "Echo patient text database import failed.", exc, module=mod_name)
            continue
    return {}, {}


_REPORT_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "# Patientenbericht zum Rechtsherzkatheter": "# Patient Report — Right Heart Catheterization",
        "**Name:**": "**Name:**",
        "**Datum:**": "**Date:**",
        "**Version:**": "**Version:**",
        "## Einordnung und Transparenz": "## Context and Transparency",
        "Dieser Patientenbericht ist eine laienfreundliche Ergänzung zum medizinischen Fachbericht. Er soll das Gespräch mit Ihrer Hausärztin/Ihrem Hausarzt und dem Kardiologie-Team erleichtern.": "This patient report is a plain-language supplement to the medical report. It is meant to help you discuss your results with your primary care physician and cardiology team.",
        "Wichtig: Die Einordnung basiert auf den hinterlegten Messwerten und Angaben. Nicht alle Informationen liegen immer als strukturierte Codes vor; deshalb bleibt das persönliche Arztgespräch entscheidend.": "Important: This summary is based on the recorded measurements and data. Not all information is always available in structured form; therefore your personal consultation with your physician remains essential.",
        "## Anlass der Untersuchung": "## Reason for the Examination",
        "## Diagnosen und Einordnung": "## Diagnoses and Classification",
        "## Kurzfazit (Schnellüberblick)": "## Summary (Quick Overview)",
        "## Details und Erklärungen": "## Details and Explanations",
        "## Was wurde bei Ihnen gemessen – und warum ist das wichtig?": "## What Was Measured — and Why Does It Matter?",
        "## Was bedeutet das für Sie?": "## What Does This Mean for You?",
        "## Wichtige Werte zur Orientierung": "## Key Values for Reference",
        "## Persönliche Risikoeinschätzung": "## Personal Risk Assessment",
        "## Wie geht es weiter?": "## What Happens Next?",
        "## Therapie und Medikamente": "## Treatment and Medication",
        "## Alltag und Sicherheit": "## Daily Life and Safety",
        "## Ansprechpartner und Kontakt": "## Contact Information",
        "## Fragen für das Arztgespräch": "## Questions for Your Doctor",
        "## Wann sollten Sie sich sofort melden?": "## When Should You Seek Immediate Help?",
        "## Begriffe kurz erklärt": "## Glossary of Terms",
        "## Ihre Angaben zur Belastbarkeit im Alltag": "## Your Reported Exercise Tolerance",
        "## Anlass": "## Reason",
        "## Kernbotschaft": "## Key Message",
        "## Nächste Schritte": "## Next Steps",
        "## Warnzeichen": "## Warning Signs",
        "## Persönliche Belastbarkeit im Alltag": "## Personal Exercise Tolerance",
        "## Spiroergometrie (Belastungstest mit Atemgas-Messung)": "## Cardiopulmonary Exercise Test (exercise test with gas analysis)",
        "### Relevanz: Hauptbefunde und Nebenbefunde": "### Relevance: Main Findings and Secondary Findings",
        "### Wichtigste Punkte": "### Key Points",
        "### Ergänzende Einordnung": "### Supplementary Assessment",
        "## Zusatztest: Volumenchallenge (Flüssigkeitsbelastung)": "## Additional Test: Volume Challenge (Fluid Loading)",
        "## Zusatztest: Vasoreaktivität": "## Additional Test: Vasoreactivity",
        "## Nicht gemessene oder nicht verwertbare Kernwerte": "## Missing or Unusable Core Values",
        "## Wenn Werte und Beschwerden nicht gut zusammenpassen": "## When Values and Symptoms Don't Match Well",
        "## Verlauf im Vergleich": "## Comparison Over Time",
        "### Nachsorge und Kontrolltermine": "### Follow-Up and Check-Up Appointments",
        "### Aktuell dokumentierte Therapie": "### Currently Documented Treatment",
        "### Geplante/erwogene Therapie": "### Planned/Considered Treatment",
        "### Frühere oder pausierte Therapie": "### Previous or Paused Treatment",
        "### Evidenzbasierte Alltagshinweise": "### Evidence-Based Daily Life Tips",
        "### Alltag bei erhöhtem Risiko": "### Daily Life at Elevated Risk",
        "# Kurzfassung zum Rechtsherzkatheter": "# Summary — Right Heart Catheterization",
    },
    "zh": {
        "# Patientenbericht zum Rechtsherzkatheter": "# 患者报告 — 右心导管检查",
        "**Name:**": "**姓名：**",
        "**Datum:**": "**日期：**",
        "**Version:**": "**版本：**",
        "## Einordnung und Transparenz": "## 背景说明",
        "Dieser Patientenbericht ist eine laienfreundliche Ergänzung zum medizinischen Fachbericht. Er soll das Gespräch mit Ihrer Hausärztin/Ihrem Hausarzt und dem Kardiologie-Team erleichtern.": "本患者报告是医学专业报告的通俗补充，旨在帮助您与主治医师和心内科团队沟通。",
        "Wichtig: Die Einordnung basiert auf den hinterlegten Messwerten und Angaben. Nicht alle Informationen liegen immer als strukturierte Codes vor; deshalb bleibt das persönliche Arztgespräch entscheidend.": "重要提示：本报告基于已记录的检测数据。并非所有信息都以结构化形式存在，因此与医生的当面沟通至关重要。",
        "## Anlass der Untersuchung": "## 检查原因",
        "## Diagnosen und Einordnung": "## 诊断与分类",
        "## Kurzfazit (Schnellüberblick)": "## 简要总结",
        "## Details und Erklärungen": "## 详细解释",
        "## Was wurde bei Ihnen gemessen – und warum ist das wichtig?": "## 检测了什么——为什么这很重要？",
        "## Was bedeutet das für Sie?": "## 这对您意味着什么？",
        "## Wichtige Werte zur Orientierung": "## 重要参考数值",
        "## Persönliche Risikoeinschätzung": "## 个人风险评估",
        "## Wie geht es weiter?": "## 下一步计划",
        "## Therapie und Medikamente": "## 治疗与药物",
        "## Alltag und Sicherheit": "## 日常生活与安全",
        "## Ansprechpartner und Kontakt": "## 联系方式",
        "## Fragen für das Arztgespräch": "## 与医生沟通时的问题",
        "## Wann sollten Sie sich sofort melden?": "## 何时应立即就医？",
        "## Begriffe kurz erklärt": "## 术语简释",
        "## Ihre Angaben zur Belastbarkeit im Alltag": "## 您描述的日常活动耐受情况",
        "## Anlass": "## 原因",
        "## Kernbotschaft": "## 核心信息",
        "## Nächste Schritte": "## 下一步",
        "## Warnzeichen": "## 警示信号",
        "## Persönliche Belastbarkeit im Alltag": "## 个人日常活动耐受情况",
        "## Spiroergometrie (Belastungstest mit Atemgas-Messung)": "## 心肺运动试验（含气体分析的运动测试）",
        "### Relevanz: Hauptbefunde und Nebenbefunde": "### 相关性：主要发现与次要发现",
        "### Wichtigste Punkte": "### 要点",
        "### Ergänzende Einordnung": "### 补充评估",
        "## Zusatztest: Volumenchallenge (Flüssigkeitsbelastung)": "## 附加检查：容量负荷试验",
        "## Zusatztest: Vasoreaktivität": "## 附加检查：血管反应性试验",
        "## Nicht gemessene oder nicht verwertbare Kernwerte": "## 缺失或不可用的核心数值",
        "## Wenn Werte und Beschwerden nicht gut zusammenpassen": "## 当数值与症状不太吻合时",
        "## Verlauf im Vergleich": "## 随时间变化对比",
        "### Nachsorge und Kontrolltermine": "### 随访与复查安排",
        "### Aktuell dokumentierte Therapie": "### 目前记录的治疗方案",
        "### Geplante/erwogene Therapie": "### 计划/考虑中的治疗方案",
        "### Frühere oder pausierte Therapie": "### 既往或已暂停的治疗方案",
        "### Evidenzbasierte Alltagshinweise": "### 基于循证医学的日常建议",
        "### Alltag bei erhöhtem Risiko": "### 高风险状态下的日常生活",
        "# Kurzfassung zum Rechtsherzkatheter": "# 右心导管检查摘要",
    },
}


def _tr(text: str, lang: str) -> str:
    """Translate a report structural string.  Falls back to original (German)."""
    if lang == "de" or not lang:
        return text
    return _REPORT_STRINGS.get(lang, {}).get(text, text)


def _pick_echo_patient_template(block: Any, rng: random.Random) -> str:
    """Pick a template variant for echo patient blocks."""
    if block is None:
        return ""
    if isinstance(block, dict):
        temps = block.get("templates")
        if isinstance(temps, (list, tuple)) and temps:
            return str(rng.choice(list(temps)))
        if isinstance(temps, str) and temps.strip():
            return str(temps)
        if isinstance(block.get("template"), str):
            return str(block.get("template"))
        return ""

    temps = getattr(block, "templates", None)
    if isinstance(temps, (list, tuple)) and temps:
        return str(rng.choice(list(temps)))
    if isinstance(temps, str) and temps.strip():
        return temps
    templ = getattr(block, "template", None)
    if isinstance(templ, str):
        return templ
    return ""


def _safe_format_text_template(template: str, ctx: Dict[str, Any]) -> str:
    """Render a text template safely.

    Patient/Echo text blocks are editable and can occasionally contain malformed
    placeholders. Report generation must remain robust and never crash because of
    a single template typo.
    """
    t = str(template or "")
    if not t:
        return ""
    try:
        return t.format_map(SafeDict(ctx))
    except (KeyError, TypeError, ValueError) as exc:
        log_exception("RHK_REP_TEMPLATE_FORMAT", "Template formatting failed; using placeholder-stripped fallback.", exc)
        # Fallback: keep literal content and drop common placeholder tokens.
        # This avoids exposing Python format errors to clinicians/patients.
        try:
            return re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", "", t)
        except (TypeError, re.error) as inner_exc:
            log_exception("RHK_REP_TEMPLATE_FALLBACK", "Regex placeholder stripping fallback failed.", inner_exc)
            return t


def _render_echo_patient_text(block_id: str, blocks: Dict[str, Any], ctx: Dict[str, Any], rng: random.Random) -> str:
    block = blocks.get(block_id)
    templ = _pick_echo_patient_template(block, rng)
    if not templ:
        return ""
    txt = _safe_format_text_template(templ, ctx).strip()
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


# =============================================================================
# Doctor report for Word/Clipboard (compact, ordered)
# =============================================================================

def build_doctor_report_for_copy(case: CaseLike, blocks: Dict[str, TextBlock]) -> str:
    """Return doctor report for clipboard/DOCX export (delegates to build_doctor_report)."""
    # Lazy import to avoid circular dependency: build_doctor_report lives in
    # rhk_reports, which imports from this module.
    from rhk_reports import build_doctor_report
    fp = _case_fingerprint(case)
    cached = _cache_get('doctor_report_copy', fp)
    if cached is not None:
        return cached
    _res = build_doctor_report(case, blocks)
    _cache_set('doctor_report_copy', fp, _res)
    return _res
def build_echo_patient_report(case: CaseLike, *, mode: Optional[str] = None) -> str:
    """Patient*innenbericht Echokardiographie (strukturierte Interpretation).

    Implementierung liegt in `rhk_echo_report_patient.py` und wird hier nur
    gecached/wrapped, um etablierte Schnittstellen stabil zu halten.
    """
    report_mode = _resolve_patient_report_mode(case, mode)
    fp = _case_fingerprint(case)
    cache_kind = f"echo_patient_report::{report_mode}"
    cached = _cache_get(cache_kind, fp)
    if cached is not None:
        return cached

    from rhk_echo_report_patient import build_echo_patient_report as _impl
    try:
        out = _impl(dict(case), mode=report_mode)
    except TypeError:
        # Backward compatibility if an older local echo module is in use.
        out = _impl(dict(case))

    _cache_set(cache_kind, fp, out)
    return out

def _pick_patient_template(block: Any, rng: random.Random) -> str:
    """Pick a block template variant.

    Supports:
    - dataclass with .templates: list[str] or tuple[str]
    - dataclass with .template: str
    - dict-like entries
    """
    if block is None:
        return ""

    # dict-like
    if isinstance(block, dict):
        temps = block.get("templates")
        if isinstance(temps, (list, tuple)) and temps:
            return str(rng.choice(list(temps)))
        if isinstance(temps, str) and temps.strip():
            return temps
        if isinstance(block.get("template"), str):
            return str(block.get("template"))
        return ""

    temps = getattr(block, "templates", None)
    if isinstance(temps, (list, tuple)) and temps:
        return str(rng.choice(list(temps)))
    if isinstance(temps, str) and temps.strip():
        return temps

    templ = getattr(block, "template", None)
    if isinstance(templ, str):
        return templ

    return ""


def _render_patient_text(block_id: str, blocks: Dict[str, Any], ctx: Dict[str, Any], rng: random.Random) -> str:
    block = blocks.get(block_id)
    templ = _pick_patient_template(block, rng)
    if not templ:
        return ""
    txt = _safe_format_text_template(templ, ctx).strip()

    # Normalize whitespace a bit
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    return txt.strip()


def _patient_variant_or_fallback(
    block_id: str,
    blocks: Dict[str, Any],
    ctx: Dict[str, Any],
    rng: random.Random,
    *,
    lang: str,
    de: str,
    en: str = "",
    zh: str = "",
) -> str:
    """Render a patient text block with variants, falling back to a fixed string.

    Rationale
    ---------
    Many measurement sentences in the patient report were hardcoded as a single
    German/English/Chinese string triple. That leaves zero room for
    individualization. This helper lets call-sites migrate incrementally:

    - For German (``lang == "de"``) we first try the variant pool from
      ``blocks[block_id]`` and fill it with the supplied ``ctx`` (numbers,
      qualitative labels, etc.). If no block exists or no template is chosen,
      the German fallback ``de`` is returned verbatim.
    - For EN/ZH we always return the language-specific fallback, since
      translated variant pools are not yet implemented.

    Call-sites can migrate to more variety simply by adding the matching
    ``PX_*`` block to :mod:`rhk_textdb_patient` with 4+ templates — no code
    change required.

    v27.4.25+: Since ``rhk_textdb_patient_en`` and ``rhk_textdb_patient_zh``
    now carry matching block IDs for several ``PX_*`` keys, we first try the
    language-specific variant pool supplied by the caller (``blocks`` is
    expected to be loaded via :func:`_load_patient_textdb` for ``lang``).
    The language-specific fallback is used only when the pool is empty.
    """
    lang = str(lang or "de").strip().lower()
    # Always prefer the variant pool — ``blocks`` is language-specific when
    # the caller used :func:`_load_patient_textdb` with the same ``lang``.
    text = _render_patient_text(block_id, blocks, ctx, rng)
    if text:
        return text
    if lang == "en" and en:
        return en
    if lang == "zh" and zh:
        return zh
    return de


def _load_patient_variant_context(
    case: CaseLike, *, lang: str = "de"
) -> Tuple[Dict[str, Any], Dict[str, Any], random.Random]:
    """Return ``(blocks, ctx, rng)`` for patient variant rendering.

    The short-report code path and other helpers need the same ``(blocks,
    ctx, rng)`` triple that the main report builds inline. This helper
    centralizes the construction so call-sites can render variants without
    duplicating the setup.
    """
    blocks, _bundles, _mods, _gloss = _load_patient_textdb(lang=lang)
    ctx: Dict[str, Any] = {
        "name": _patient_name(case.get(K_UI, {}) or {}),
    }
    rng = random.Random(_stable_patient_seed(case))
    return blocks, ctx, rng


def _find_glossary_term_idx(line: str, term: str) -> Optional[int]:
    """Return the index of a clean glossary-term match inside a line, or None.

    Uses proper word boundaries so short abbreviations like "IV" don't leak
    into Roman numerals (e.g. "Funktionsklasse IV") or word fragments.
    Terms containing symbols ("/", "+", "-", ".", " ") fall back to substring
    matching because Python's ``\\w`` boundary would otherwise reject valid
    occurrences like "V/Q" or "NT pro BNP".
    """
    if not term:
        return None
    if any(ch in term for ch in ("/", "+", "-", ".", " ")):
        idx = line.find(term)
        return idx if idx >= 0 else None
    m = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", line)
    return m.start() if m else None


def _collect_glossary_line_hits(line: str, terms: List[str], found: List[str]) -> List[str]:
    hits: List[Tuple[int, str]] = []
    for term in terms:
        if term in found:
            continue
        idx = _find_glossary_term_idx(line, term)
        if idx is not None:
            hits.append((idx, term))
    hits.sort(key=lambda x: x[0])
    return [term for _, term in hits]



def _collect_used_glossary_terms(lines: List[str], glossary: Dict[str, str], *, max_terms: int = 12) -> List[str]:
    """Return glossary terms in first-appearance order based on report lines.

    Notes
    -----
    - We keep this lightweight and deterministic.
    - We intentionally avoid fuzzy matching to prevent false positives.
    - Special terms containing symbols (e.g. "V/Q") are matched as substring.
    """
    if not glossary or not lines:
        return []

    terms = list(glossary.keys())
    found: List[str] = []

    for ln in lines:
        line_hits = _collect_glossary_line_hits(str(ln), terms, found)
        for term in line_hits:
            found.append(term)
            if len(found) >= max_terms:
                return found

    return found


def _merge_patient_glossary(base_glossary: Dict[str, str]) -> Dict[str, str]:
    merged: Dict[str, str] = dict(_PATIENT_AUTO_GLOSSARY)
    for k, v in (base_glossary or {}).items():
        kk = str(k or "").strip()
        vv = str(v or "").strip()
        if kk and vv:
            merged[kk] = vv
    return merged


def _append_patient_glossary_section(
    lines: List[str],
    glossary: Dict[str, str],
    *,
    max_terms: int = 40,
    lang: str = "de",
) -> None:
    used_terms = _collect_used_glossary_terms(lines, glossary, max_terms=max_terms)
    if not used_terms:
        return
    lines.append(_tr("## Begriffe kurz erklärt", lang))
    for term in used_terms:
        expl = str(glossary.get(term) or "").strip()
        if expl:
            one_sent = _glossary_one_sentence(expl)
            if one_sent:
                lines.append(f"- **{term}:** {one_sent}")
    lines.append("")


def _word_count(text: str) -> int:
    t = str(text or "")
    latin = len(re.findall(r"[A-Za-z0-9ÄÖÜäöüß]+(?:/[A-Za-z0-9ÄÖÜäöüß]+)?", t))
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", t))
    return latin + cjk


def _truncate_words(text: str, max_words: int, *, require_clean_end: bool = False) -> str:
    """Truncate text at a word count but preserve the last *complete* sentence.

    Clinical-UX rationale: a mid-sentence cut ending in ``"Als nächstes."`` is
    worse than a slightly shorter paragraph. When we must truncate, we back up
    to the last sentence boundary so the result always reads like finished
    prose — never like a broken stub.

    Abbreviation-aware: common German abbreviations such as ``u.a.``, ``ggf.``,
    ``z.B.`` are masked before the back-off regex looks for ``[.!?]\\s``. This
    prevents pathological truncations like
    ``"Abklärung präkapillärer Ursachen (u.a. Autoimmunität, HIV/Leber, ggf."``
    where the important tail "Genetik) und die PH-spezifische Therapie…" would
    otherwise be silently dropped.

    When ``require_clean_end`` is True and no complete sentence fits within the
    budget, the function returns the empty string rather than emitting a
    mid-sentence fragment with a trailing period (which reads as a parser bug,
    e.g. "…PH-spezifische Therapie nach." in a Kurzfazit).
    """
    tokens = re.findall(r"\S+", str(text or "").strip())
    if max_words <= 0:
        return ""
    if not tokens:
        return ""
    out_tokens: List[str] = []
    wc = 0
    for tok in tokens:
        tw = _word_count(tok)
        if tw <= 0:
            tw = 1
        if wc + tw > max_words:
            break
        out_tokens.append(tok)
        wc += tw
    if wc <= 0:
        return ""
    out = " ".join(out_tokens).rstrip(" ,;:")
    # Mask abbreviation dots before searching for the last sentence boundary,
    # then restore them — so "u.a." / "ggf." / "z.B." are not misread as ends.
    masked = out
    for abbr in _SENTENCE_ABBREVIATIONS:
        masked_abbr = abbr.replace(".", _ABBREV_PLACEHOLDER)
        masked = re.sub(
            rf"(?i)(?<!\w){re.escape(abbr)}",
            masked_abbr,
            masked,
        )
    # Back off to the last completed sentence so we never leave a stub like
    # "Als nächstes." dangling at the end of the paragraph.
    m = re.search(r"(?s)^(.*[.!?])\s", masked + " ")
    if m and m.group(1).strip():
        trimmed = m.group(1).replace(_ABBREV_PLACEHOLDER, ".").rstrip()
        if _word_count(trimmed) >= max(10, max_words // 2):
            return trimmed
    if require_clean_end:
        return ""
    out = masked.replace(_ABBREV_PLACEHOLDER, ".")
    if out and not out.endswith((".", "!", "?")):
        out += "."
    return out


# Common German (+ a few English) abbreviations whose trailing period must NOT
# be treated as a sentence boundary. Without this, "u.a. Autoimmunität" gets
# split after "u.a." and downstream sentence-limiters drop the rest, producing
# truncated patient-facing text such as "…, HIV/Leber, ggf." (the important
# content "Genetik) und die PH-spezifische Therapie" is lost).
_SENTENCE_ABBREVIATIONS: Tuple[str, ...] = (
    "u.a.", "u. a.", "z.B.", "z. B.", "ggf.", "bzw.", "i.v.", "i. v.",
    "p.o.", "p. o.", "s.c.", "s. c.", "d.h.", "d. h.", "o.ä.", "o. ä.",
    "o.a.", "o. a.", "s.o.", "s. o.", "s.u.", "s. u.", "ca.", "etc.",
    "vs.", "ev.", "evtl.", "sog.", "max.", "min.", "inkl.", "exkl.",
    "ggü.", "Mio.", "Mrd.", "Nr.", "Abs.", "Art.", "Abb.", "Tab.",
    "St.", "Jh.", "Dr.", "Prof.", "Fr.", "Hr.", "bspw.",
    "e.g.", "i.e.",
)
_ABBREV_PLACEHOLDER = "\u0001"  # SOH – never appears in user content


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences while respecting common abbreviations.

    The patient-facing report uses ``_limit_sentences`` to cap output size; a
    naive period-based split would prematurely end a sentence on "u.a.", "z.B.",
    "ggf." etc. and silently drop everything after — a clinical-UX defect.
    """
    s = str(text or "").strip()
    if not s:
        return []
    # Mask abbreviation dots so the regex split cannot see them as sentence ends.
    for abbr in _SENTENCE_ABBREVIATIONS:
        masked = abbr.replace(".", _ABBREV_PLACEHOLDER)
        # Replace only standalone occurrences (case-insensitive).
        s = re.sub(
            rf"(?i)(?<!\w){re.escape(abbr)}",
            masked,
            s,
        )
    parts = re.split(r"(?<=[.!?])\s+", s)
    return [p.replace(_ABBREV_PLACEHOLDER, ".").strip() for p in parts if p.strip()]


def _limit_sentences(text: str, *, max_sentences: int = 2) -> str:
    sents = _split_sentences(text)
    if not sents:
        return ""
    out = " ".join(sents[:max_sentences]).strip()
    if out and out[-1] not in ".!?":
        out += "."
    return out


_PATIENT_PARAGRAPH_CONNECTORS: Dict[str, Tuple[str, ...]] = {
    "de": ("Außerdem", "Zusätzlich", "Darüber hinaus", "Gleichzeitig"),
    "en": ("Additionally", "Furthermore", "Moreover", "At the same time"),
    "zh": ("此外", "另外", "而且", "同时"),
}


def _has_patient_transition_prefix(text: str) -> bool:
    t = str(text or "").strip()
    if not t:
        return False
    return bool(
        re.match(
            r"(?i)^(außerdem|zusätzlich|darüber hinaus|gleichzeitig|im nächsten schritt|wichtig)\b",
            t,
        )
    )


def _lowercase_patient_chunk_start(text: str) -> str:
    t = str(text or "").strip()
    if not t:
        return ""
    m = re.match(r"^([A-Za-zÄÖÜäöüß]+)", t)
    if not m:
        return t
    word = m.group(1)
    protected = {
        "PH",
        "PAH",
        "CTEPH",
        "BNP",
        "NT-proBNP",
        "NT",
        "ICD",
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
        "V/Q",
    }
    if word in protected:
        return t
    if word[0].islower():
        return t
    return word[0].lower() + word[1:] + t[m.end() :]


_LABEL_CHUNK_RE = re.compile(r"^[A-ZÄÖÜ][\wÄÖÜäöüß\- ]{0,40}:\s")


def _patient_paragraph_chunk_with_transition(chunk: str, idx: int, lang: str = "de") -> str:
    """Return a chunk joined with a soft transition connector.

    Grammar notes (German):
    - "Außerdem X" triggers V2 inversion, so X should start with a finite verb.
      If the chunk starts with a *noun* label like "Gesamteinordnung:" or an
      NP like "Die Werte sprechen…", the connector breaks grammar.
    - We therefore skip the connector for label-style chunks ("Foo: …") and
      for chunks whose first word is a capitalized noun/article (rough
      heuristic: starts with "Die/Der/Das/… " + NP or a colon-label).
    """
    text = str(chunk or "").strip()
    if not text:
        return ""
    if idx <= 0:
        return text
    if _has_patient_transition_prefix(text):
        return text
    # Never prefix label-style chunks (e.g. "Gesamteinordnung: …").
    if _LABEL_CHUNK_RE.match(text):
        return text
    # Skip the connector for German chunks that start with any capitalized
    # word — prepending "Außerdem" in front of a full sentence almost always
    # breaks V2 inversion or sounds ungrammatical. Separating with a sentence
    # boundary (the caller joins chunks with a space) reads far more natural.
    if lang == "de" and re.match(r"^[A-ZÄÖÜ]", text):
        return text
    connectors = _PATIENT_PARAGRAPH_CONNECTORS.get(lang, _PATIENT_PARAGRAPH_CONNECTORS["de"])
    connector = connectors[(idx - 1) % len(connectors)]
    return f"{connector} {_lowercase_patient_chunk_start(text)}"


def _build_layered_paragraph(
    candidates: List[str],
    *,
    min_words: int = 80,
    max_words: int = 120,
    lang: str = "de",
) -> str:
    chunks = [_limit_sentences(c, max_sentences=2) for c in candidates if str(c or "").strip()]
    chunks = [c for c in chunks if c]
    if not chunks:
        return ""

    out_parts: List[str] = []
    for ch in chunks:
        candidate = _patient_paragraph_chunk_with_transition(ch, len(out_parts), lang=lang)
        trial = " ".join(out_parts + [candidate]).strip()
        wc = _word_count(trial)
        if wc <= max_words:
            out_parts.append(candidate)
            continue
        remain = max_words - _word_count(" ".join(out_parts))
        if remain > 6:
            # Strict mode: drop the chunk entirely if no complete sentence fits.
            # Better to fall short (filler tops up to min_words) than to leave a
            # mid-sentence fragment like "…PH-spezifische Therapie nach."
            cut = _truncate_words(candidate, remain, require_clean_end=True)
            if cut:
                out_parts.append(cut)
        break

    out = " ".join(out_parts).strip()
    filler = {
        "en": "What matters most is the overall picture — symptoms, measurements, and trends over time. Please discuss the findings with your care team at your own pace.",
        "zh": "最重要的是综合考虑症状、检测数值和随时间的变化趋势。请在方便时与您的医疗团队详细讨论这些结果。",
    }.get(lang, (
        "Wichtig ist die Gesamtschau aus Beschwerden, Messwerten und Verlauf. "
        "Bitte besprechen Sie die Befunde in Ruhe mit Ihrem Behandlungsteam."
    ))
    _filler_rounds = 0
    while out and _word_count(out) < min_words:
        _filler_rounds += 1
        if _filler_rounds > 5:
            break
        trial = (out + " " + filler).strip()
        if _word_count(trial) <= max_words:
            out = trial
            continue
        out = _truncate_words(trial, max_words)
        break

    if out and _word_count(out) > max_words:
        out = _truncate_words(out, max_words)
    return out


def _glossary_one_sentence(explanation: str) -> str:
    """Return the first sentence of a glossary definition.

    Uses the abbreviation-aware splitter so definitions that contain ``z.B.``,
    ``u.a.``, ``ggf.`` etc. are not truncated mid-sentence. A naive period-based
    split produced patient-facing artefacts like
    ``"CT: Computertomographie: Schnittbild-Untersuchung, z.B."`` — the
    important content after the abbreviation was silently dropped.
    """
    txt = re.sub(r"\s+", " ", str(explanation or "").strip())
    if not txt:
        return ""
    sents = _split_sentences(txt)
    first = sents[0].strip() if sents else txt
    if first and first[-1] not in ".!?":
        first += "."
    return first


def _find_header_bounds(lines: List[str], header: str) -> Tuple[Optional[int], Optional[int]]:
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


def _enforce_patient_layered_constraints(lines: List[str]) -> List[str]:
    out = list(lines or [])

    # Kurzfazit: enforce 80-120 words after all rewrites.
    s0, s1 = _find_header_bounds(out, "## Kurzfazit (Schnellüberblick)")
    if s0 is not None and s1 is not None:
        payload = [ln.strip() for ln in out[s0 + 1 : s1] if ln.strip()]
        summary_txt = " ".join(payload).strip()
        if summary_txt:
            if _word_count(summary_txt) > 120:
                summary_txt = _truncate_words(summary_txt, 120)
            filler = (
                "Wichtig ist die Gesamtschau aus Beschwerden, Messwerten und Verlauf. "
                "Bitte besprechen Sie die Befunde in Ruhe mit Ihrem Behandlungsteam."
            )
            while _word_count(summary_txt) < 80:
                trial = (summary_txt + " " + filler).strip()
                if _word_count(trial) <= 120:
                    summary_txt = trial
                else:
                    summary_txt = _truncate_words(trial, 120)
                    break
            out = out[: s0 + 1] + [summary_txt, ""] + out[s1:]

    # Bulletpoints: max 1-2 sentences per bullet.
    b0, b1 = _find_header_bounds(out, "### Wichtigste Punkte")
    if b0 is not None and b1 is not None:
        fixed: List[str] = []
        for ln in out[b0 + 1 : b1]:
            s = str(ln or "")
            if s.strip().startswith("- "):
                content = s.strip()[2:].strip()
                content = _limit_sentences(content, max_sentences=2)
                if content:
                    fixed.append(f"- {content}")
            else:
                fixed.append(s)
        out = out[: b0 + 1] + fixed + out[b1:]

    return out


def _patient_to_bool(v: Any, truthy: set[str]) -> bool:
    """Robust bool parser for mixed UI payloads (bool/str/int)."""
    if v is None:
        return False
    if isinstance(v, bool):
        return bool(v)
    s = str(v).strip().lower()
    return s in truthy


def _patient_norm(x: Any) -> str:
    return str(x).strip() if x is not None else ""


def _patient_clean_choice(x: Any) -> str:
    s = _patient_norm(x)
    if not s:
        return ""
    if s.lower() in {"keine angabe", "unbekannt", "nicht dokumentiert"}:
        return ""
    return s


def _patient_first_nonempty(src: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        v = _patient_clean_choice(src.get(k))
        if v:
            return v
    return ""


def _patient_risk_txt(cat: Optional[str], lang: str = "de") -> Optional[str]:
    if not cat:
        return None
    c = str(cat).strip().lower()
    if c.startswith("low") or c.startswith("niedrig"):
        return {
            "en": (
                "The overall assessment currently appears rather stable. "
                "If your symptoms are also stable, check-ups every few months are often sufficient."
            ),
            "zh": (
                "目前的总体评估看起来比较稳定。"
                "如果您的症状也保持稳定，通常每隔几个月复查即可。"
            ),
        }.get(lang, (
            "Die Gesamt-Einordnung wirkt derzeit eher stabil. "
            "Wenn Ihre Beschwerden ebenfalls stabil sind, reichen häufig Kontrollen im Abstand von einigen Monaten."
        ))
    if c.startswith("inter") or "mittel" in c:
        return {
            "en": (
                "The overall assessment suggests a moderate need for monitoring. "
                "Check-ups in weeks to a few months are often advisable to review your progress and treatment together."
            ),
            "zh": (
                "总体评估提示需要中等程度的监测。"
                "通常建议在数周至数月内复查，以便共同评估病情进展和治疗效果。"
            ),
        }.get(lang, (
            "Die Gesamt-Einordnung spricht für einen mittleren Kontrollbedarf. "
            "Oft sind Kontrollen in Wochen bis wenigen Monaten sinnvoll, um Verlauf und Therapie gemeinsam zu überprüfen."
        ))
    if c.startswith("high") or "hoch" in c:
        return {
            "en": (
                "The overall assessment suggests a high need for monitoring. "
                "Close follow-up and potentially more intensive treatment options at a specialized PH center are important."
            ),
            "zh": (
                "总体评估提示需要高度监测。"
                "在专业肺动脉高压中心进行密切随访以及可能更积极的治疗方案非常重要。"
            ),
        }.get(lang, (
            "Die Gesamt-Einordnung spricht für einen hohen Kontrollbedarf. "
            "Engmaschige Betreuung und ggf. intensivere Therapieoptionen im spezialisierten PH-Zentrum sind wichtig."
        ))
    return None


def _patient_bundle_patient_blocks(bundle_id: str, bundles: Dict[str, Any], blocks: Dict[str, Any]) -> List[str]:
    bids = bundles.get(bundle_id) or []
    return [bid for bid in bids if bid in blocks]


def _patientize_cause_text(txt: str) -> str:
    t = str(txt or "").strip()
    if not t:
        return ""
    low = t.lower()
    if ("gruppe 2" in low) or ("linkskard" in low) or ("hfpef" in low):
        return "Hinweise, dass die linke Herzhälfte mitbeteiligt ist (Rückstau in die Lunge)."
    if ("gruppe 3" in low) or ("copd" in low) or ("ild" in low) or ("fibrose" in low) or ("hypox" in low):
        return "Hinweise, dass eine Lungenerkrankung/Atemwegsproblematik mitbeteiligt sein könnte."
    if ("gruppe 4" in low) or ("cteph" in low) or ("embol" in low) or ("thrombo" in low):
        return "Hinweise, dass ältere Blutgerinnsel in den Lungengefäßen eine Rolle spielen könnten."
    if ("gruppe 1" in low) or ("pah" in low) or ("pulmonal-arter" in low):
        return "Hinweise, dass vor allem die Lungengefäße selbst betroffen sind (pulmonal-arterielle Form)."
    return re.sub(r"\s*\(.*grupp(e)?\s*\d.*?\)\s*", " ", t, flags=re.IGNORECASE).strip()


def _patient_hf_text(der: Dict[str, Any], hf: Dict[str, Any], lang: str = "de") -> Optional[str]:
    hf_cat = _patient_norm(der.get("hfpef_category") or hf.get("hfpef_category") or "")
    hf_prob = _safe_float(der.get("hfpef_prob") or hf.get("hfpef_prob"))
    if not hf_cat:
        return None
    c = hf_cat.lower()
    if "high" in c or "likely" in c:
        txt = {
            "en": "There are signs that the left side of the heart does not fill optimally during exertion (this can contribute to fluid backing up into the lungs).",
            "zh": "有迹象表明左心在运动时充盈不够理想（这可能导致液体回流至肺部）。",
        }.get(lang, "Es gibt Hinweise, dass die linke Herzhälfte sich unter Belastung nicht optimal füllt (das kann zu einem Rückstau in die Lunge beitragen).")
    elif "inter" in c or "mid" in c:
        txt = {
            "en": "There are some indications that the left side of the heart may be involved during exertion.",
            "zh": "有一些迹象表明左心在运动时可能也参与其中。",
        }.get(lang, "Es gibt gewisse Hinweise, dass die linke Herzhälfte unter Belastung mitbeteiligt sein könnte.")
    elif "low" in c or "unlikely" in c:
        txt = {
            "en": "There are no clear indications that the left side of the heart is the primary cause.",
            "zh": "目前没有明确迹象表明左心是主要原因。",
        }.get(lang, "Es gibt eher keine klaren Hinweise, dass die linke Herzhälfte die Hauptursache ist.")
    else:
        return None
    if hf_prob is not None:
        _approx = {"en": "Approximate", "zh": "大约"}.get(lang, "Orientierend")
        txt = txt + f" ({_approx}: {int(round(hf_prob))}%)."
    return txt


def _patient_warn_lines(ui: Dict[str, Any], lang: str = "de") -> List[str]:
    anticoag_status = str(ui.get("anticoag_status") or "").strip().lower()
    clot_hint = bool(ui.get("vq_defect") or ui.get("ct_pe") or ui.get("pe_history"))
    ild = bool(ui.get("ct_ild"))
    antifib_status = str(ui.get("antifib_status") or "").strip().lower()
    warn_lines: List[str] = []
    if clot_hint and anticoag_status and anticoag_status not in {"ja", "yes", "true"}:
        warn_lines.append({
            "en": (
                "There are findings that could be consistent with older blood clots in the pulmonary vessels. "
                "Please discuss with your care team promptly whether blood thinning (anticoagulation) is necessary."
            ),
            "zh": (
                "有一些发现可能与肺血管中的陈旧血栓有关。"
                "请尽快与您的医疗团队讨论是否需要抗凝（血液稀释）治疗。"
            ),
        }.get(lang, (
            "Es gibt Hinweise, die (auch) zu älteren Gerinnseln in den Lungengefäßen passen könnten. "
            "Bitte klären Sie zeitnah mit Ihrem Behandlungsteam, ob eine Blutverdünnung (Antikoagulation) notwendig ist."
        )))
    if ild and antifib_status in {"", "nein", "unklar"}:
        warn_lines.append({
            "en": (
                "With signs of pulmonary fibrosis, specialized co-management is important. "
                "Please clarify whether antifibrotic therapy may be appropriate in your case."
            ),
            "zh": (
                "在有肺纤维化迹象的情况下，专科协同管理非常重要。"
                "请咨询抗纤维化治疗是否适合您的情况。"
            ),
        }.get(lang, (
            "Bei Hinweisen auf eine Lungenfibrose ist eine spezialisierte Mitbetreuung wichtig. "
            "Bitte klären Sie, ob eine antifibrotische Therapie in Ihrem Fall sinnvoll ist."
        )))
    return warn_lines


def _patient_cpet_lines(ui: Dict[str, Any], lang: str = "de") -> List[str]:
    """Short, plain-language CPET summary for the patient report.

    Purpose: give the patient a simple, honest read-out of what the test
    showed — no jargon, no diagnosis labels, just what the key numbers
    suggest and what happens next.

    Returns an empty list if CPET was not done.
    """
    if not ui.get("cpet_done"):
        return []

    vo2 = _safe_float(ui.get("cpet_peak_vo2_ml_kg_min"))
    vo2_pct = _safe_float(ui.get("cpet_peak_vo2_pct_pred"))
    ve_slope = _safe_float(ui.get("cpet_ve_vco2_slope"))
    pet_vt1 = _safe_float(ui.get("cpet_petco2_vt1_mmhg"))
    rer = _safe_float(ui.get("cpet_rer_peak"))

    out: List[str] = []

    intro = {
        "en": "During the exercise test we measured how efficiently your body takes up oxygen and releases carbon dioxide while cycling.",
        "zh": "在此运动测试中，我们测量了您在骑行时身体摄取氧气与排出二氧化碳的效率。",
    }.get(lang, "Bei der Spiroergometrie haben wir gemessen, wie gut Ihr Körper unter Belastung Sauerstoff aufnimmt und Kohlendioxid wieder abgibt.")
    out.append(intro)

    # Effort line — essential for honest interpretation.
    if rer is not None and rer >= 1.10:
        effort = {
            "en": "You reached a good level of exertion during the test, so the values are reliable.",
            "zh": "您在测试中达到了良好的运动强度，因此这些数值是可靠的。",
        }.get(lang, "Sie haben während des Tests eine gute Ausbelastung erreicht — die Werte sind aussagekräftig.")
        out.append(effort)
    elif rer is not None:
        effort = {
            "en": "The test ended before full peak exertion; the values should therefore be interpreted with this in mind.",
            "zh": "测试在达到最大用力前结束，因此解读时需考虑这一点。",
        }.get(lang, "Der Test wurde vor der maximalen Ausbelastung beendet — die Werte sollten mit dieser Einschränkung betrachtet werden.")
        out.append(effort)

    # Peak VO2 — the headline number.
    if vo2 is not None:
        if vo2 > 15:
            vo2_msg = {
                "en": f"Your peak oxygen uptake was {vo2:.1f} mL/min/kg — a value in the normal range.",
                "zh": f"您的峰值摄氧量为 {vo2:.1f} mL/min/kg，属正常范围。",
            }.get(lang, f"Ihre maximale Sauerstoffaufnahme lag bei {vo2:.1f} mL/min/kg — ein Wert im normalen Bereich.")
        elif vo2 >= 11:
            vo2_msg = {
                "en": f"Your peak oxygen uptake was {vo2:.1f} mL/min/kg — moderately reduced compared to the healthy range.",
                "zh": f"您的峰值摄氧量为 {vo2:.1f} mL/min/kg，较健康范围中度降低。",
            }.get(lang, f"Ihre maximale Sauerstoffaufnahme lag bei {vo2:.1f} mL/min/kg — im Vergleich zum gesunden Bereich mäßig vermindert.")
        else:
            vo2_msg = {
                "en": f"Your peak oxygen uptake was {vo2:.1f} mL/min/kg — clearly reduced. This is important information for treatment planning.",
                "zh": f"您的峰值摄氧量为 {vo2:.1f} mL/min/kg，明显降低。这对治疗规划有重要意义。",
            }.get(lang, f"Ihre maximale Sauerstoffaufnahme lag bei {vo2:.1f} mL/min/kg — deutlich vermindert. Das ist für die Therapieplanung eine wichtige Information.")
        if vo2_pct is not None:
            vo2_msg += {
                "en": f" That corresponds to about {vo2_pct:.0f}% of the value expected for your age and sex.",
                "zh": f" 这约相当于您同年龄、同性别健康人群预期值的 {vo2_pct:.0f}%。",
            }.get(lang, f" Das entspricht etwa {vo2_pct:.0f} % des für Ihr Alter und Geschlecht erwarteten Wertes.")
        out.append(vo2_msg)

    # Ventilation pattern — PH signature
    ph_like = (ve_slope is not None and ve_slope >= 35) and (pet_vt1 is not None and pet_vt1 < 30)
    if ph_like:
        out.append({
            "en": "The breathing pattern during exercise suggests that the pulmonary vessels may be contributing to your shortness of breath — this fits the overall assessment.",
            "zh": "运动中的呼吸模式提示肺血管可能在您气短症状中起作用，这与整体评估相符。",
        }.get(lang, "Das Atemmuster unter Belastung passt dazu, dass die Lungengefäße zu Ihrer Atemnot beitragen können — das ordnet sich in das Gesamtbild ein."))
    elif ve_slope is not None and ve_slope >= 35:
        out.append({
            "en": "The breathing pattern during exercise showed reduced efficiency — this can occur with heart or lung disease and will be considered in the further plan.",
            "zh": "运动中呼吸效率下降，这可能与心脏或肺部疾病相关，将在后续方案中加以考虑。",
        }.get(lang, "Das Atemmuster zeigte unter Belastung eine verminderte Effizienz — das kann bei Herz- oder Lungenerkrankungen vorkommen und fließt in die weitere Planung ein."))

    out.append({
        "en": "_Note:_ Exercise testing complements the cardiac catheterization — it helps us understand your symptoms under real-life exertion.",
        "zh": "_提示：_ 运动测试是对心导管检查的补充，可以帮助我们理解您在日常负荷下的症状。",
    }.get(lang, "_Hinweis:_ Die Spiroergometrie ergänzt den Rechtsherzkatheter — sie hilft uns zu verstehen, was unter Belastung mit Ihrem Körper passiert."))

    return out


def _patient_functional_context_lines(ui: Dict[str, Any], lang: str = "de") -> List[str]:
    """Build short patient-facing context lines from functional/symptom fields."""
    out: List[str] = []

    if ui.get("exertional_dyspnea") is True:
        out.append({"en": "Shortness of breath during exertion was documented.", "zh": "运动时气短已被记录在案。"}.get(lang, "Belastungs-Luftnot wurde in den Angaben dokumentiert."))

    syn = _patient_to_bool(ui.get("syncope"), {"ja", "yes", "true", "1", "gelegentlich", "manchmal", "wiederholt"})
    diz = _patient_to_bool(ui.get("dizziness"), {"ja", "yes", "true", "1"})
    if syn:
        out.append({"en": "Fainting or near-fainting was reported.", "zh": "曾报告有晕厥或接近晕厥的情况。"}.get(lang, "Ohnmacht/Beinahe-Ohnmacht wurde angegeben."))
    elif diz:
        out.append({"en": "Dizziness was reported as a symptom.", "zh": "头晕已被报告为一种症状。"}.get(lang, "Schwindel wurde als Symptom angegeben."))

    stairs = _safe_float(ui.get("stairs_flights"))
    if stairs is not None:
        out.append({
            "en": f"In daily life, approximately {_fmt(stairs,0)} flights of stairs were documented as the current exercise limit.",
            "zh": f"在日常生活中，约{_fmt(stairs,0)}层楼梯被记录为当前的运动极限。",
        }.get(lang, f"Im Alltag wurden etwa {_fmt(stairs,0)} Etagen als aktuelle Belastungsgrenze dokumentiert."))

    six = _safe_float(ui.get("six_mwd_m"))
    if six is not None:
        six_dt = _patient_clean_choice(ui.get("six_mwd_date"))
        if six_dt:
            out.append({
                "en": f"In the 6-minute walk test, {_fmt(six,0)} m were most recently achieved ({six_dt}).",
                "zh": f"在六分钟步行测试中，最近达到了{_fmt(six,0)}米（{six_dt}）。",
            }.get(lang, f"Im 6-Minuten-Gehtest wurden zuletzt {_fmt(six,0)} m erreicht ({six_dt})."))
        else:
            out.append({
                "en": f"In the 6-minute walk test, {_fmt(six,0)} m were most recently achieved.",
                "zh": f"在六分钟步行测试中，最近达到了{_fmt(six,0)}米。",
            }.get(lang, f"Im 6-Minuten-Gehtest wurden zuletzt {_fmt(six,0)} m erreicht."))

    if ui.get("hemoptysis") is True:
        out.append({"en": "Coughing up blood was documented; please contact your care team immediately if new episodes occur.", "zh": "咯血已被记录；如有新发作，请立即联系您的医疗团队。"}.get(lang, "Blutiger Auswurf wurde dokumentiert; bei neuen Episoden bitte sofort Rücksprache halten."))

    return out


def _patient_conversation_questions(
    *,
    ui: Dict[str, Any],
    has_ph: bool,
    followup_timing_desc: str,
    lang: str = "de",
) -> List[str]:
    """Return conversation prompts tailored to available patient context."""
    _q = {
        "cause": {
            "en": "What is the most likely cause of the elevated pressure in my case?",
            "zh": "在我的情况下，压力升高最可能的原因是什么？",
            "de": "Was ist in meinem Fall die wahrscheinlichste Ursache der Druckerhöhung?",
        },
        "tests": {
            "en": "What further tests are planned – and what should they clarify?",
            "zh": "还计划做哪些检查——这些检查要明确什么问题？",
            "de": "Welche Untersuchungen sind noch geplant – und was soll dadurch geklärt werden?",
        },
        "treatment": {
            "en": "What treatment is currently planned (or being considered) – and how will we know if it's helping?",
            "zh": "目前计划（或正在考虑）哪种治疗方案——我们如何知道它是否有效？",
            "de": "Welche Behandlung ist aktuell geplant (oder wird erwogen) – und woran merken wir, ob sie hilft?",
        },
        "warning": {
            "en": "What warning signs should prompt me to contact you quickly?",
            "zh": "哪些警示症状应该让我尽快与您联系？",
            "de": "Welche Warnzeichen sollten mich zu schneller Rücksprache veranlassen?",
        },
        "comorb": {
            "en": "Which of my pre-existing conditions most strongly influences the treatment decision right now?",
            "zh": "我的哪些既往疾病目前对治疗决策的影响最大？",
            "de": "Welche meiner Vorerkrankungen beeinflusst die Therapieentscheidung aktuell am stärksten?",
        },
        "exercise_goal": {
            "en": "What realistic personal exercise goal (e.g., walking distance or flights of stairs) is appropriate until the next check-up?",
            "zh": "在下次复查之前，什么样的个人运动目标（例如步行距离或楼层数）是合理的？",
            "de": "Welches realistische persönliche Belastungsziel (z. B. Gehstrecke oder Etagen) passt bis zur nächsten Kontrolle?",
        },
        "syncope_safety": {
            "en": "What safety rules apply to me regarding dizziness/fainting in daily life (e.g., stairs, exercise, driving)?",
            "zh": "关于日常生活中的头晕/晕厥，我需要遵循哪些安全规则（例如爬楼梯、运动、驾车）？",
            "de": "Welche Sicherheitsregeln gelten für mich bei Schwindel/Ohnmacht im Alltag (z. B. Treppen, Sport, Autofahren)?",
        },
        "followup": {
            "en": "By when should my next follow-up appointment take place specifically?",
            "zh": "我的下一次复查预约具体应该在什么时候之前进行？",
            "de": "Bis wann sollte mein nächster Kontrolltermin konkret stattfinden?",
        },
        "exertional": {
            "en": "What steps make sense if symptoms mainly occur during exertion?",
            "zh": "如果症状主要在活动时出现，应该采取哪些措施？",
            "de": "Welche Schritte sind sinnvoll, wenn Beschwerden vor allem unter Belastung auftreten?",
        },
    }

    def _t(key: str) -> str:
        return _q[key].get(lang, _q[key]["de"])

    questions: List[str] = [
        _t("cause"),
        _t("tests"),
        _t("treatment"),
        _t("warning"),
    ]

    comorb = _patient_clean_choice(ui.get("comorbidities"))
    if comorb:
        questions.append(_t("comorb"))

    if (_safe_float(ui.get("six_mwd_m")) is not None) or (_safe_float(ui.get("stairs_flights")) is not None):
        questions.append(_t("exercise_goal"))

    syn = _patient_to_bool(ui.get("syncope"), {"ja", "yes", "true", "1", "gelegentlich", "manchmal", "wiederholt"})
    diz = _patient_to_bool(ui.get("dizziness"), {"ja", "yes", "true", "1"})
    if syn or diz:
        questions.append(_t("syncope_safety"))

    if not followup_timing_desc:
        questions.append(_t("followup"))
    if not has_ph:
        questions.append(_t("exertional"))

    out: List[str] = []
    seen: set[str] = set()
    for q in questions:
        key = q.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out[:8]


def _patient_arch_blocks() -> Dict[str, Dict[str, str]]:
    return {
        "H1": {"measured": "PX_ARCH_H1_FOCUS_MEASURED", "meaning": "PX_ARCH_H1_FOCUS_MEANING"},
        "H2": {"measured": "PX_ARCH_H2_FOCUS_MEASURED", "meaning": "PX_ARCH_H2_FOCUS_MEANING"},
        "H3": {"measured": "PX_ARCH_H3_FOCUS_MEASURED", "meaning": "PX_ARCH_H3_FOCUS_MEANING"},
        "H4": {"measured": "PX_ARCH_H4_FOCUS_MEASURED", "meaning": "PX_ARCH_H4_FOCUS_MEANING"},
        "H5": {"measured": "PX_ARCH_H5_FOCUS_MEASURED", "meaning": "PX_ARCH_H5_FOCUS_MEANING"},
        "H6": {"measured": "PX_ARCH_H6_FOCUS_MEASURED", "meaning": "PX_ARCH_H6_FOCUS_MEANING"},
    }


def _patient_rest_hemo_values(der: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return {
        "mpap": _safe_float(der.get("mpap_rest") if der.get("mpap_rest") is not None else der.get("mpap")),
        "pawp": _safe_float(der.get("pawp_rest") if der.get("pawp_rest") is not None else der.get("pawp")),
        "pvr": _safe_float(der.get("pvr_rest") if der.get("pvr_rest") is not None else der.get("pvr")),
        "ci": _safe_float(der.get("ci_rest") if der.get("ci_rest") is not None else der.get("ci")),
        "rap": _safe_float(der.get("rap_rest") if der.get("rap_rest") is not None else der.get("rap")),
    }


def _patient_arch_text(
    *,
    kind: str,
    archetype_id: str,
    blocks: Dict[str, Any],
    ctx: Dict[str, Any],
    rng: random.Random,
) -> str:
    bid = (_patient_arch_blocks().get(archetype_id) or {}).get(kind)
    if not bid:
        return ""
    return _render_patient_text(bid, blocks, ctx, rng)


def _patient_hemo_qual(label: str, v: Optional[float], lang: str = "de") -> Optional[str]:
    """Patient-friendly qualitative bucket for key hemodynamic metrics."""
    if v is None:
        return None
    _q = {
        "niedrig": {"en": "low", "zh": "偏低"}.get(lang, "niedrig"),
        "grenzwertig": {"en": "borderline", "zh": "临界"}.get(lang, "grenzwertig"),
        "normal": {"en": "normal", "zh": "正常"}.get(lang, "normal"),
        "leicht erhöht": {"en": "mildly elevated", "zh": "轻度升高"}.get(lang, "leicht erhöht"),
        "erhöht": {"en": "elevated", "zh": "升高"}.get(lang, "erhöht"),
        "deutlich erhöht": {"en": "significantly elevated", "zh": "明显升高"}.get(lang, "deutlich erhöht"),
    }
    if label == "CI":
        if v < 2.2:
            return _q["niedrig"]
        if v < 2.5:
            return _q["grenzwertig"]
        return _q["normal"]
    thresholds: Dict[str, List[Tuple[float, str]]] = {
        "mPAP": [(20.0, "normal"), (30.0, "erhöht"), (float("inf"), "deutlich erhöht")],
        "PAWP": [(15.0, "normal"), (20.0, "erhöht"), (float("inf"), "deutlich erhöht")],
        "PVR": [(2.0, "normal"), (3.0, "leicht erhöht"), (5.0, "erhöht"), (float("inf"), "deutlich erhöht")],
        "RAP": [(7.0, "normal"), (12.0, "erhöht"), (float("inf"), "deutlich erhöht")],
    }
    bounds = thresholds.get(label)
    if not bounds:
        return None
    for limit, text in bounds:
        if v <= limit:
            return _q[text]
    return None


# ---------------------------------------------------------------------------
# Severity-tier dispatch helpers for PX_MEASURE_* blocks.
# Thresholds mirror _patient_hemo_qual; dispatch picks one of three tiered
# text blocks (MILD/MOD/SEV) so the patient report adapts its tone to the
# measured severity instead of reusing a single boilerplate per metric.
# ---------------------------------------------------------------------------

def _patient_mpap_block_key(mpap: Optional[float]) -> str:
    """Pick severity-graded mPAP block key. Falls back to the single-tier key."""
    if mpap is None:
        return "PX_MEASURE_MPAP_ELEVATED"
    if mpap > 45.0:
        return "PX_MEASURE_MPAP_SEV"
    if mpap > 30.0:
        return "PX_MEASURE_MPAP_MOD"
    if mpap > 20.0:
        return "PX_MEASURE_MPAP_MILD"
    return "PX_MEASURE_MPAP_ELEVATED"


def _patient_pawp_block_key(pawp: Optional[float]) -> str:
    """Pick severity-graded PAWP block key (post-cap pattern)."""
    if pawp is None:
        return "PX_MEASURE_POSTCAP_PAWP_HIGH"
    if pawp > 25.0:
        return "PX_MEASURE_PAWP_SEV"
    if pawp > 20.0:
        return "PX_MEASURE_PAWP_MOD"
    if pawp > 15.0:
        return "PX_MEASURE_PAWP_MILD"
    return "PX_MEASURE_POSTCAP_PAWP_HIGH"


def _patient_pvr_severity_key(pvr: Optional[float]) -> Optional[str]:
    """Return a severity-graded PVR key, or None if PVR is not elevated."""
    if pvr is None or pvr <= 2.0:
        return None
    if pvr > 5.0:
        return "PX_MEASURE_PVR_SEV"
    if pvr > 3.0:
        return "PX_MEASURE_PVR_MOD"
    return "PX_MEASURE_PVR_MILD"


def _patient_rap_severity_key(rap: Optional[float]) -> Optional[str]:
    """Return a severity-graded RAP key for elevated values, else None."""
    if rap is None or rap <= 7.0:
        return None
    if rap > 15.0:
        return "PX_MEASURE_RAP_SEV"
    if rap > 12.0:
        return "PX_MEASURE_RAP_MOD"
    return "PX_MEASURE_RAP_MILD"


def _patient_ci_low_severity_key(ci: Optional[float]) -> Optional[str]:
    """Return a severity-graded CI-low key, or None if CI is adequate."""
    if ci is None or ci >= 2.5:
        return None
    if ci < 1.8:
        return "PX_MEASURE_CI_LOW_SEV"
    if ci < 2.2:
        return "PX_MEASURE_CI_LOW_MOD"
    return "PX_MEASURE_CI_BORDERLINE"


# ---------------------------------------------------------------------------
# Patient-report transitions ("bridges")
# ---------------------------------------------------------------------------
#
# Goal: keep the patient report from reading as a staccato list of findings.
# Each bridge is a short connective sentence (6 variants per kind, per
# language) drawn from the ``PX_BRIDGE_*`` pool in the patient textdbs. The
# helper below returns a stable-but-varied bridge for a given "kind", which
# caller sites can splice between measurement or section paragraphs so the
# overall text flows instead of jumping.
#
# The set of supported ``kind`` values mirrors the blocks defined in
# :mod:`rhk_textdb_patient` / ``_en`` / ``_zh``:
#
#   add          – parallel / additive finding (same direction)
#   contrast     – a contrasting or complementary finding
#   consequence  – causal / downstream inference from the previous sentence
#   pump_focus   – shift to the pump side (CI/CO)
#   right_heart  – shift to the venous / right-heart side (RAP)
#   biomarker    – shift to the lab / biomarker side (BNP)
#   section_close– closing / summarizing sentence for a paragraph
#   to_causes    – transition into the "possible causes" / etiology section
#   to_therapy   – transition into the therapy section
#   to_everyday  – transition into the everyday-life / self-care section
#
_PATIENT_BRIDGE_KINDS: Tuple[str, ...] = (
    "add",
    "contrast",
    "consequence",
    "pump_focus",
    "right_heart",
    "biomarker",
    "section_close",
    "to_causes",
    "to_therapy",
    "to_everyday",
)


def _patient_bridge(
    kind: str,
    blocks: Dict[str, Any],
    rng: random.Random,
    *,
    ctx: Optional[Dict[str, Any]] = None,
) -> str:
    """Return one short connective sentence for patient-report flow.

    The chosen sentence comes from ``PX_BRIDGE_<KIND>`` in ``blocks`` (the
    patient textdb loaded for the active language). If the block is missing
    or empty, the empty string is returned — callers are expected to treat
    an empty bridge as "skip" rather than error out.

    Bridges are stateless: every call gets a fresh pick from the pool. To
    avoid repetition the caller can simply choose not to insert a bridge
    before every paragraph (e.g. only between closely related lines).
    """
    k = (kind or "").strip().lower()
    if k not in _PATIENT_BRIDGE_KINDS:
        return ""
    key = f"PX_BRIDGE_{k.upper()}"
    return _render_patient_text(key, blocks, ctx or {}, rng)


def _append_patient_bridge(
    lines: List[str],
    kind: str,
    blocks: Dict[str, Any],
    rng: random.Random,
    *,
    ctx: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a bridge sentence to ``lines`` if one is available."""
    t = _patient_bridge(kind, blocks, rng, ctx=ctx)
    if t:
        lines.append(t)


def _patient_medication_goal(drug_name: str, lang: str = "de") -> str:
    """Return a short patient-facing therapy goal sentence for a drug class."""
    d = str(drug_name or "").strip().lower()
    if not d:
        return ""
    rules: List[Tuple[Tuple[str, ...], Dict[str, str]]] = [
        (("sildenafil", "tadalafil", "pde"), {
            "de": "Ziel: Entlastung der Lungengefäße und oft bessere Belastbarkeit.",
            "en": "Goal: Relieving pressure on the lung vessels and often improving exercise capacity.",
            "zh": "目标：减轻肺血管压力，通常可改善运动耐量。",
        }),
        (("riociguat", "adempas", "sgc"), {
            "de": "Ziel: Senkung des Gefäßwiderstands in der Lunge; besonders relevant bei bestimmten PH-Formen.",
            "en": "Goal: Lowering vascular resistance in the lungs; especially relevant for certain forms of PH.",
            "zh": "目标：降低肺血管阻力；对某些类型的肺动脉高压尤为重要。",
        }),
        (("macitentan", "bosentan", "ambrisentan", "era"), {
            "de": "Ziel: Blockade von Endothelin-Signalen, um die Lungengefäße zu entlasten.",
            "en": "Goal: Blocking endothelin signals to relieve pressure on the lung vessels.",
            "zh": "目标：阻断内皮素信号以减轻肺血管负担。",
        }),
        (("selexipag", "uptravi", "ip-rezeptor"), {
            "de": "Ziel: Erweiterung der Lungengefäße und Unterstützung der Belastbarkeit.",
            "en": "Goal: Widening the lung vessels and supporting exercise tolerance.",
            "zh": "目标：扩张肺血管并支持运动耐量。",
        }),
        (("iloprost", "treprostinil", "epoprostenol", "prost"), {
            "de": "Ziel: starke Gefäßentlastung bei fortgeschritteneren Verläufen.",
            "en": "Goal: Strong vascular relief in more advanced disease.",
            "zh": "目标：在病情较重时提供强效血管减压。",
        }),
        (("diuret", "entwässer"), {
            "de": "Ziel: Entlastung bei Rückstau und Wassereinlagerungen.",
            "en": "Goal: Relieving fluid buildup and swelling.",
            "zh": "目标：减轻体液潴留和水肿。",
        }),
        (("sauerstoff",), {
            "de": "Ziel: stabile Sauerstoffversorgung in Ruhe, Belastung und ggf. nachts.",
            "en": "Goal: Stable oxygen supply at rest, during activity, and if needed at night.",
            "zh": "目标：在休息、活动及必要时夜间保持稳定的氧气供应。",
        }),
        (("sotatercept",), {
            "de": "Ziel: Therapie des BMPR2/Activin-Signalwegs zur Senkung der Krankheitsaktivität.",
            "en": "Goal: Targeting the BMPR2/activin signaling pathway to reduce disease activity.",
            "zh": "目标：靶向BMPR2/激活素信号通路以降低疾病活动性。",
        }),
        (("kalzium",), {
            "de": "Ziel: Gefäßentlastung in ausgewählten Konstellationen, z. B. nach positivem Vasoreaktivitätstest.",
            "en": "Goal: Vascular relief in selected situations, e.g., after a positive vasoreactivity test.",
            "zh": "目标：在特定情况下（如血管反应性试验阳性后）减轻血管负担。",
        }),
    ]
    for needles, texts in rules:
        if any(n in d for n in needles):
            return texts.get(lang, texts["de"])
    return ""


def _patient_symptom_profile(ui: Dict[str, Any]) -> Dict[str, Any]:
    """Return a lightweight symptom profile from patient-facing UI fields."""
    who = str(ui.get("who_fc") or "").strip().upper()
    syn = _patient_to_bool(ui.get("syncope"), {"ja", "yes", "true", "1", "gelegentlich", "manchmal"})
    diz = _patient_to_bool(ui.get("dizziness"), {"ja", "yes", "true", "1"})
    stairs = _safe_float(ui.get("stairs_flights"))

    sev = "unknown"
    if who in {"III", "IV"}:
        sev = "high"
    elif who in {"II"}:
        sev = "moderate"
    elif who in {"I"}:
        sev = "low"
    elif stairs is not None:
        if stairs <= 1:
            sev = "low"
        elif stairs <= 2:
            sev = "moderate"
        else:
            sev = "high"

    return {
        "who_fc": who,
        "syncope": syn,
        "dizziness": diz,
        "stairs_flights": stairs,
        "severity": sev,
    }


def _patient_discordance_flags(
    *,
    symp: Dict[str, Any],
    mpap: Optional[float],
    bio_qual: Optional[str],
    ui: Dict[str, Any],
) -> Dict[str, bool]:
    """Detect common patient-facing discordance patterns for explanation blocks."""
    d1 = bool((mpap is not None and mpap > 30) and (bio_qual == "niedrig"))
    strong_symp = bool(symp.get(K_SEVERITY) == "high" or symp.get("syncope"))
    d2 = bool((mpap is not None and mpap <= 25) and strong_symp)

    pasp_echo = _safe_float(ui.get("pasp_echo"))
    trv = _safe_float(ui.get("trv_ms"))
    echo_low = bool((pasp_echo is not None and pasp_echo < 40) or (trv is not None and trv < 2.8))
    d3 = bool(echo_low and (mpap is not None and mpap > 30))

    return {
        "high_mpap_low_bnp": d1,
        "low_pressure_high_symptoms": d2,
        "echo_ok_cath_high": d3,
    }


def _patient_bio_qual(kind: str, v: Optional[float], lang: str = "de") -> Optional[str]:
    """Soft patient-facing biomarker qualifier for BNP/NT-proBNP."""
    if v is None:
        return None
    _q = {
        "niedrig": {"en": "low", "zh": "偏低"}.get(lang, "niedrig"),
        "erhöht": {"en": "elevated", "zh": "升高"}.get(lang, "erhöht"),
        "deutlich erhöht": {"en": "significantly elevated", "zh": "明显升高"}.get(lang, "deutlich erhöht"),
    }
    k = (kind or "").upper()
    if "NT" in k:
        if v < 300:
            return _q["niedrig"]
        if v < 1400:
            return _q["erhöht"]
        return _q["deutlich erhöht"]
    if v < 100:
        return _q["niedrig"]
    if v < 300:
        return _q["erhöht"]
    return _q["deutlich erhöht"]


def _patient_is_high_risk(cat: str) -> bool:
    c = str(cat or "").strip().lower()
    if not c:
        return False
    return (
        c.startswith("high")
        or "high" in c
        or "hoch" in c
        or "intermediate-high" in c
        or "intermediate high" in c
        or "intermediatehigh" in c
    )


def _patient_module_level(levels_map: Dict[str, int], mid: str) -> int:
    try:
        lvl = int(levels_map.get(mid, 3))
    except (TypeError, ValueError) as exc:
        log_exception(
            "RHK_REP_MODULE_LEVEL_PARSE",
            "Module level parsing failed; defaulting to level 3.",
            exc,
            module_id=mid,
        )
        lvl = 3
    return lvl if lvl in (1, 2, 3) else 3


def _patient_module_reason(
    mid: str,
    *,
    der: Dict[str, Any],
    ui: Dict[str, Any],
    eti_groups: List[int],
    pawp: Optional[float],
    risk_cat_local: str,
    congestion: bool,
    lang: str = "de",
) -> str:
    """Short, patient-friendly reason (only when applicable)."""
    _reasons_de: Dict[str, Tuple[str, bool]] = {
        "P02": ("weil es Hinweise auf Wassereinlagerungen bzw. Rückstau gibt", congestion),
        "P13": ("weil die Blutwerte auf eine Blutarmut hindeuten können", bool(der.get("anemia"))),
        "P17": ("weil bestimmte Autoimmun-/Rheuma-Erkrankungen Lungenhochdruck mit verursachen können", bool(ui.get("immunology_pos"))),
        "P18": ("weil bestimmte Virusinfektionen in seltenen Fällen mit Lungenhochdruck zusammenhängen", bool(ui.get("virology_pos"))),
        "P20": ("weil genetische Faktoren bei manchen Formen von Lungenhochdruck eine Rolle spielen können", bool(ui.get("mutation_pos"))),
    }
    _reasons_en: Dict[str, Tuple[str, bool]] = {
        "P02": ("because there are signs of fluid retention or congestion", congestion),
        "P13": ("because blood values may indicate anemia", bool(der.get("anemia"))),
        "P17": ("because certain autoimmune/rheumatic conditions can contribute to pulmonary hypertension", bool(ui.get("immunology_pos"))),
        "P18": ("because certain viral infections can, in rare cases, be associated with pulmonary hypertension", bool(ui.get("virology_pos"))),
        "P20": ("because genetic factors can play a role in some forms of pulmonary hypertension", bool(ui.get("mutation_pos"))),
    }
    _reasons_zh: Dict[str, Tuple[str, bool]] = {
        "P02": ("因为有液体潴留或淤积的迹象", congestion),
        "P13": ("因为血液检查可能提示贫血", bool(der.get("anemia"))),
        "P17": ("因为某些自身免疫性/风湿性疾病可能促发肺动脉高压", bool(ui.get("immunology_pos"))),
        "P18": ("因为某些病毒感染在极少数情况下可能与肺动脉高压相关", bool(ui.get("virology_pos"))),
        "P20": ("因为遗传因素可能在某些类型的肺动脉高压中起作用", bool(ui.get("mutation_pos"))),
    }
    simple_reason = {"en": _reasons_en, "zh": _reasons_zh}.get(lang, _reasons_de)
    reason_pair = simple_reason.get(mid)
    if reason_pair and reason_pair[1]:
        return reason_pair[0]

    lung_hint = bool(der.get("ct_ild")) or bool(der.get("ct_emphysema")) or bool(der.get("lufu_restrictive")) or bool(der.get("lufu_obstructive")) or bool(der.get("lufu_diffusion"))
    if mid in ("P08", "P12") and lung_hint:
        return {"en": "because lung/airway findings may be abnormal and we want to evaluate this more closely", "zh": "因为肺部/气道检查结果可能异常，我们希望进一步评估"}.get(lang, "weil Befunde an Lunge/Atemwegen auffällig sein können und wir das genauer einordnen möchten")
    if mid == "P09" and (2 in eti_groups or (pawp is not None and pawp > 15)):
        return {"en": "because there may be indications that the left side of the heart is involved", "zh": "因为可能有迹象表明左心参与其中"}.get(lang, "weil es Hinweise auf eine Beteiligung der linken Herzseite geben kann")

    thrombo_hint = 4 in eti_groups or bool(der.get("vq_defect")) or bool(der.get("ct_embolie")) or bool(der.get("ct_pe"))
    if mid in ("P05", "P10") and thrombo_hint:
        if mid == "P10" and str(ui.get("anticoag_status") or "").lower() in ("nein", "unklar", ""):
            return {"en": "because in this context the question of blood thinning therapy is particularly important", "zh": "因为在这种情况下，抗凝治疗的问题尤为重要"}.get(lang, "weil in diesem Zusammenhang die Frage nach einer Blutverdünnung besonders wichtig ist")
        return {"en": "because indications of (older) blood clots or embolisms may be relevant", "zh": "因为可能存在（陈旧性）血栓/栓塞的相关线索"}.get(lang, "weil Hinweise auf (ältere) Blutgerinnsel/Embolien eine Rolle spielen könnten")
    if mid == "P25" and (risk_cat_local.startswith("high") or "hoch" in risk_cat_local):
        return {"en": "because in a more severe overall situation we proactively consider advanced options at a specialist center", "zh": "因为在较为严重的整体情况下，我们会提前考虑专科中心的进一步治疗选项"}.get(lang, "weil wir bei einer eher schweren Gesamtsituation frühzeitig auch weiterführende Optionen im Spezialzentrum mitdenken")
    return ""


def _patient_episode_patient_bullet(e: Dict[str, Any], lang: str = "de") -> str:
    one = format_ph_tx_episode_line(e)
    if not one:
        return ""
    goal = _patient_medication_goal(str(e.get("drug") or ""), lang=lang)
    if goal:
        return f"- {one}: {goal}"
    return f"- {one}"


def _append_patient_intro_meta(
    lines: List[str],
    ctx: Dict[str, Any],
    reason_rhk: str,
    story: str,
    lang: str = "de",
    *,
    blocks: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> None:
    pname = str(ctx.get("name") or "")
    salutation = str(ctx.get("salutation") or "")
    lines.append(_tr("# Patientenbericht zum Rechtsherzkatheter", lang))
    meta: List[str] = []
    if pname:
        meta.append(f"{_tr('**Name:**', lang)} {pname}")
    meta.append(f"{_tr('**Datum:**', lang)} {_dt.date.today().strftime('%d.%m.%Y')}")
    meta.append(f"{_tr('**Version:**', lang)} {APP_VERSION}")
    lines.append(" · ".join(meta))
    lines.append("")

    lines.append(_tr("## Einordnung und Transparenz", lang))
    lines.append(salutation)
    _blocks = blocks if blocks is not None else {}
    _rng = rng if rng is not None else random.Random(0)
    lines.append(_patient_variant_or_fallback(
        "PX_TRANSPARENCY_INTRO",
        _blocks,
        ctx,
        _rng,
        lang=lang,
        de=(
            "Dieser Patientenbericht ist eine laienfreundliche Ergänzung zum medizinischen Fachbericht. "
            "Er soll das Gespräch mit Ihrer Hausärztin/Ihrem Hausarzt und dem Kardiologie-Team erleichtern."
        ),
        en=(
            "This patient report is a plain-language supplement to the medical report. "
            "It is meant to support your conversation with your primary care doctor and cardiology team."
        ),
        zh="本患者报告是医学报告的通俗易懂的补充。旨在方便您与家庭医生及心内科团队的沟通。",
    ))
    lines.append(_patient_variant_or_fallback(
        "PX_TRANSPARENCY_DATA_NOTE",
        _blocks,
        ctx,
        _rng,
        lang=lang,
        de=(
            "Wichtig: Die Einordnung basiert auf den hinterlegten Messwerten und Angaben. "
            "Nicht alle Informationen liegen immer als strukturierte Codes vor; deshalb bleibt das persönliche Arztgespräch entscheidend."
        ),
        en=(
            "Important: The assessment is based on the recorded values and information. "
            "Not all information is available as structured codes; that is why the personal consultation remains crucial."
        ),
        zh="重要提示：本评估基于记录的数值和信息。并非所有信息都以结构化代码形式存在，因此面对面的问诊至关重要。",
    ))
    lines.append("")

    lines.append(_tr("## Anlass der Untersuchung", lang))
    if reason_rhk and story:
        _txt = {"en": f"Reason per documentation: {reason_rhk}.", "zh": f"根据文档记录的检查原因：{reason_rhk}。"}.get(lang, f"Anlass laut Dokumentation: {reason_rhk}.")
        lines.append(_txt)
        _txt = {"en": f"Brief history/symptoms: {story}", "zh": f"简要病史/症状：{story}"}.get(lang, f"Kurz-Anamnese/Beschwerden: {story}")
        lines.append(_txt)
    elif reason_rhk:
        _txt = {"en": f"Reason per documentation: {reason_rhk}.", "zh": f"根据文档记录的检查原因：{reason_rhk}。"}.get(lang, f"Anlass laut Dokumentation: {reason_rhk}.")
        lines.append(_txt)
    elif story:
        _txt = {"en": f"Brief history/symptoms: {story}", "zh": f"简要病史/症状：{story}"}.get(lang, f"Kurz-Anamnese/Beschwerden: {story}")
        lines.append(_txt)
    else:
        lines.append(_patient_variant_or_fallback(
            "PX_REASON_MISSING",
            _blocks,
            ctx,
            _rng,
            lang=lang,
            de="Ein konkreter Untersuchungsanlass wurde im Datensatz nicht strukturiert hinterlegt.",
            en="No specific reason for the examination was recorded in a structured format in the dataset.",
            zh="数据集中未以结构化形式记录具体的检查原因。",
        ))
    lines.append("")


def _patient_overview_core_sentence(has_ph: bool, mpap: Optional[float], lang: str = "de") -> str:
    if has_ph and mpap is not None:
        if lang == "en":
            return f"The mean pressure in your pulmonary vessels (mPAP) is {_fmt(mpap,0)} mmHg, which is clearly elevated (pulmonary hypertension starts at >20 mmHg)."
        if lang == "zh":
            return f"您肺血管的平均压力（mPAP）为 {_fmt(mpap,0)} mmHg，明显升高（肺动脉高压标准为 >20 mmHg）。"
        return f"Der mittlere Druck in Ihren Lungengefäßen (mPAP) liegt bei {_fmt(mpap,0)} mmHg und ist damit deutlich erhöht (Lungenhochdruck ab >20 mmHg)."
    if has_ph:
        if lang == "en":
            return "The measurements indicate elevated pressure in the pulmonary vessels (pulmonary hypertension)."
        if lang == "zh":
            return "检测结果显示肺血管压力升高（肺动脉高压）。"
        return "Die Messwerte sprechen für eine Druckerhöhung in den Lungengefäßen (Lungenhochdruck)."
    if lang == "en":
        return "The measurements show no signs of significant pressure elevation in the pulmonary vessels."
    if lang == "zh":
        return "检测结果未发现肺血管压力明显升高的迹象。"
    return "In der Messung finden sich keine Hinweise auf eine relevante Druckerhöhung in den Lungengefäßen."


def _ensure_clarity_label(text: str, lang: str) -> str:
    """Ensure the patient overall-classification sentence carries the label prefix.

    The report structure expects an explicit "Gesamteinordnung:" (DE) /
    "Overall assessment:" (EN) / "总体评估：" (ZH) marker on this sentence so
    downstream readers (and tests) can always locate the classification.
    Variant pools may return natural prose without that exact prefix; we
    therefore prepend the label when the colon-labelled form isn't already
    present in the opening of the sentence.
    """
    t = str(text or "").lstrip()
    if not t:
        return t
    label = {"en": "Overall assessment:", "zh": "总体评估："}.get(lang, "Gesamteinordnung:")
    head = t[:60]
    if label in head:
        return t
    # Prepend the label. Use the sentence as-is so the reader sees
    # "Gesamteinordnung: Die Messwerte …" or "Gesamteinordnung: Die Gesamteinordnung spricht …"
    # rather than stripping words from the variant.
    if lang == "zh":
        return f"{label}{t}"
    return f"{label} {t}"


def _patient_overview_clarity_sentence(
    *,
    has_ph: bool,
    hemo_cat: str,
    mpap: Optional[float],
    pvr: Optional[float],
    pawp: Optional[float],
    lang: str = "de",
    blocks: Optional[Dict[str, Any]] = None,
    ctx: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> str:
    _blocks = blocks if blocks is not None else {}
    _ctx = ctx if ctx is not None else {}
    _rng = rng if rng is not None else random.Random(0)
    if mpap is None and pvr is None and pawp is None:
        return _patient_variant_or_fallback(
            "PX_CLARITY_MISSING_VALUES",
            _blocks,
            _ctx,
            _rng,
            lang=lang,
            de="Eine eindeutige Einordnung (unauffällig/auffällig) ist aktuell nicht möglich, weil zentrale Messwerte fehlen.",
            en="A clear assessment is currently not possible because key measurements are missing.",
            zh="由于缺少关键检测数据，目前无法做出明确评估。",
        )
    if not has_ph:
        raw = _patient_variant_or_fallback(
            "PX_CLARITY_NO_PH",
            _blocks,
            _ctx,
            _rng,
            lang=lang,
            de="Gesamteinordnung: Die Messwerte in Ruhe sind überwiegend unauffällig und eher untypisch für einen Lungenhochdruck in Ruhe.",
            en="Overall assessment: The resting values are largely normal and not typical for pulmonary hypertension at rest.",
            zh="总体评估：静息状态下的数值基本正常，不符合静息性肺动脉高压的典型表现。",
        )
        return _ensure_clarity_label(raw, lang)
    if hemo_cat == "precap":
        raw = _patient_variant_or_fallback(
            "PX_CLARITY_PRECAP",
            _blocks,
            _ctx,
            _rng,
            lang=lang,
            de="Gesamteinordnung: Die Messwerte sind auffällig und eher typisch für eine Druckerhöhung in den Lungengefäßen selbst.",
            en="Overall assessment: The values are abnormal and typical for pressure elevation originating in the pulmonary vessels themselves.",
            zh="总体评估：数值异常，符合肺血管本身压力升高的典型表现。",
        )
        return _ensure_clarity_label(raw, lang)
    if hemo_cat in {"ipcph", "cpcph"}:
        raw = _patient_variant_or_fallback(
            "PX_CLARITY_POSTCAP",
            _blocks,
            _ctx,
            _rng,
            lang=lang,
            de="Gesamteinordnung: Die Messwerte sind auffällig und eher typisch für eine Mitbeteiligung der linken Herzseite.",
            en="Overall assessment: The values are abnormal and typical for involvement of the left side of the heart.",
            zh="总体评估：数值异常，符合左心参与的典型表现。",
        )
        return _ensure_clarity_label(raw, lang)
    raw = _patient_variant_or_fallback(
        "PX_CLARITY_AMBIGUOUS",
        _blocks,
        _ctx,
        _rng,
        lang=lang,
        de="Gesamteinordnung: Die Messwerte sind auffällig; die genaue Zuordnung ist noch nicht sicher und wird weiter abgeklärt.",
        en="Overall assessment: The values are abnormal; the precise classification is not yet certain and will be further investigated.",
        zh="总体评估：数值异常；精确分类尚不确定，将进一步检查。",
    )
    return _ensure_clarity_label(raw, lang)


def _patient_overview_pattern_sentence(has_ph: bool, hemo_cat: str, pvr: Optional[float], pawp: Optional[float], lang: str = "de") -> str:
    if not (has_ph and hemo_cat):
        return ""
    if hemo_cat == "precap":
        if pvr is not None:
            if lang == "en":
                return f"The values suggest that resistance in the pulmonary vessels is elevated (PVR {_fmt(pvr,1)} WU; elevated above >2 WU)."
            if lang == "zh":
                return f"数值表明肺血管阻力升高（PVR {_fmt(pvr,1)} WU；>2 WU为升高）。"
            return f"Die Werte sprechen eher dafür, dass der Widerstand in den Lungengefäßen selbst erhöht ist (PVR {_fmt(pvr,1)} WU; erhöht ab >2 WU)."
        if lang == "en":
            return "The values suggest that resistance in the pulmonary vessels themselves is elevated."
        if lang == "zh":
            return "数值表明肺血管本身的阻力升高。"
        return "Die Werte sprechen eher dafür, dass der Widerstand in den Lungengefäßen selbst erhöht ist."
    if hemo_cat in {"ipcph", "cpcph"}:
        if pawp is not None:
            if lang == "en":
                return f"There are indications that the left side of the heart may be involved (PAWP {_fmt(pawp,0)} mmHg, often elevated above >15 mmHg)."
            if lang == "zh":
                return f"有迹象表明左心可能参与其中（PAWP {_fmt(pawp,0)} mmHg，>15 mmHg为常见升高值）。"
            return f"Es gibt Hinweise, dass die linke Herzseite mitbeteiligt sein könnte (PAWP {_fmt(pawp,0)} mmHg, häufig erhöht ab >15 mmHg)."
        if lang == "en":
            return "There are indications that the left side of the heart may be involved."
        if lang == "zh":
            return "有迹象表明左心可能参与其中。"
        return "Es gibt Hinweise, dass die linke Herzseite mitbeteiligt sein könnte."
    return ""


def _patient_overview_bnp_sentence(bnp_kind: str, bnp_val: Optional[float], ci: Optional[float], lang: str = "de") -> str:
    if bnp_val is None:
        if ci is not None and _patient_hemo_qual("CI", ci) in {"niedrig", "grenzwertig"}:
            if lang == "en":
                return f"Cardiac output is rather reduced (CI {_fmt(ci,2)} l/min/m²)."
            if lang == "zh":
                return f"心输出量偏低（CI {_fmt(ci,2)} l/min/m²）。"
            return f"Die Pumpleistung ist eher reduziert (CI {_fmt(ci,2)} l/min/m²)."
        return ""
    q = _patient_bio_qual(str(bnp_kind), bnp_val)
    q_display = _patient_bio_qual(str(bnp_kind), bnp_val, lang=lang) if lang != "de" else q
    q_txt = f" ({q_display})" if q_display else ""
    if q == "niedrig":
        if lang == "en":
            return f"The blood marker {bnp_kind} is {_fmt(bnp_val,0)} pg/ml (low). This argues against a currently severe cardiac overload, though the value is also influenced by age, kidney function, and acute infections."
        if lang == "zh":
            return f"血液标志物 {bnp_kind} 为 {_fmt(bnp_val,0)} pg/ml（偏低）。这不太支持目前存在严重心脏负荷过重，但该数值也受年龄、肾功能和急性感染的影响。"
        return f"Der Blutwert {bnp_kind} liegt bei {_fmt(bnp_val,0)} pg/ml{q_txt}. Das spricht eher gegen eine aktuell stark erhöhte Herzbelastung (der Wert wird aber auch von Alter, Nierenfunktion und akuten Infekten beeinflusst)."
    if q in {"erhöht", "deutlich erhöht"}:
        _q_en = {"erhöht": "elevated", "deutlich erhöht": "significantly elevated"}.get(q, q)
        _q_zh = {"erhöht": "升高", "deutlich erhöht": "明显升高"}.get(q, q)
        if lang == "en":
            return f"The blood marker {bnp_kind} is {_fmt(bnp_val,0)} pg/ml ({_q_en}). This is consistent with the heart being under increased strain and will be monitored over time."
        if lang == "zh":
            return f"血液标志物 {bnp_kind} 为 {_fmt(bnp_val,0)} pg/ml（{_q_zh}）。这与心脏承受更大负荷一致，将在随访中持续监测。"
        return f"Der Blutwert {bnp_kind} liegt bei {_fmt(bnp_val,0)} pg/ml{q_txt}. Das passt dazu, dass das Herz derzeit stärker belastet ist und wird im Verlauf als wichtiger Orientierungspunkt genutzt."
    if lang == "en":
        return f"The blood marker {bnp_kind} is {_fmt(bnp_val,0)} pg/ml. We use this value together with symptoms and exercise tolerance to assess the course."
    if lang == "zh":
        return f"血液标志物 {bnp_kind} 为 {_fmt(bnp_val,0)} pg/ml。我们将结合症状和运动耐量来综合评估。"
    return f"Der Blutwert {bnp_kind} liegt bei {_fmt(bnp_val,0)} pg/ml. Wir nutzen diesen Wert zusammen mit Symptomen und Belastbarkeit, um den Verlauf besser einzuordnen."


def _patient_overview_next_step_sentence(der: Dict[str, Any], leading_action: str, lang: str = "de") -> str:
    eti = der.get(K_PH_ETIOLOGY) if isinstance(der, dict) else None
    cand_n = len(eti.get(K_CANDIDATES) or []) if isinstance(eti, dict) else 0
    ambiguous = bool(cand_n > 1)
    if ambiguous and leading_action:
        if lang == "en":
            return f"Which cause contributes most is not yet certain from the available data. Next, we will specifically investigate {leading_action} so that we can tailor the treatment accordingly."
        if lang == "zh":
            return f"根据现有数据，哪种原因贡献最大尚不确定。下一步我们将重点调查{leading_action}，以便制定合适的治疗方案。"
        return f"Welche Ursache am meisten beiträgt, ist anhand der bisherigen Daten noch nicht sicher. Als nächstes klären wir gezielt {leading_action}, damit wir die Behandlung passend ausrichten können."
    if ambiguous:
        if lang == "en":
            return "Which cause contributes most is not yet certain. We will conduct additional tests to identify the main cause and plan targeted treatment."
        if lang == "zh":
            return "哪种原因贡献最大尚不确定。我们将进行进一步检查以明确主要原因并制定针对性治疗方案。"
        return "Welche Ursache am meisten beiträgt, ist anhand der bisherigen Daten noch nicht sicher. Deshalb ergänzen wir weitere Untersuchungen, um die Hauptursache zu klären und die Behandlung gezielt auszurichten."
    if leading_action:
        if lang == "en":
            return f"As the next step, we will specifically address {leading_action} so that we can plan the most suitable treatment."
        if lang == "zh":
            return f"下一步我们将重点处理{leading_action}，以便制定最合适的治疗方案。"
        return f"Als nächster Schritt klären wir gezielt {leading_action}, damit wir die Behandlung passend ausrichten können."
    return ""


def _patient_relevance_line(kind: str, lang: str = "de") -> str:
    k = str(kind or "").strip().lower()
    if k == "main":
        return {"en": "Report relevance: main finding.", "zh": "报告相关性：主要发现。"}.get(lang, "Relevanz im Bericht: Hauptbefund.")
    if k == "side":
        return {"en": "Report relevance: incidental finding; no acute action mentioned.", "zh": "报告相关性：次要发现；未提及急性处理措施。"}.get(lang, "Relevanz im Bericht: Nebenbefund; keine akute Maßnahme wird erwähnt.")
    return {"en": "Report relevance: no urgency noted in the report.", "zh": "报告相关性：报告中未提及紧急性。"}.get(lang, "Relevanz im Bericht: Im Bericht steht keine Dringlichkeit.")


def _patient_relevance_from_esc4(esc4: Any) -> str:
    val = str(esc4 or "").strip().lower()
    if not val:
        return "neutral"
    if "high" in val or "hoch" in val:
        return "main"
    if "intermediate-high" in val or "intermediate high" in val:
        return "main"
    return "neutral"


def _append_patient_relevance_section(
    *,
    lines: List[str],
    has_ph: bool,
    mpap: Optional[float],
    hemo_cat: str,
    pvr: Optional[float],
    pawp: Optional[float],
    bnp_kind: str,
    bnp_val: Optional[float],
    ci: Optional[float],
    bio_qual: Optional[str],
    esc4: Any,
    der: Dict[str, Any],
    leading_action: str,
    lang: str = "de",
) -> None:
    lines.append(_tr("### Relevanz: Hauptbefunde und Nebenbefunde", lang))

    _lbl_pressure = {"en": "Pulmonary pressure", "zh": "肺动脉压力"}.get(lang, "Drucklage im Lungenkreislauf")
    _lbl_pattern = {"en": "Measurement pattern", "zh": "检测模式"}.get(lang, "Messmuster")
    _lbl_biomarker = {"en": "Biomarker assessment", "zh": "生物标志物评估"}.get(lang, "Blutwert-Einordnung")
    _lbl_risk = {"en": "Risk assessment", "zh": "风险评估"}.get(lang, "Risikoeinschätzung")
    _lbl_next = {"en": "Next steps", "zh": "后续步骤"}.get(lang, "Weiteres Vorgehen")
    _lbl_overall = {"en": "Overall assessment", "zh": "总体评估"}.get(lang, "Gesamteinschätzung")

    core = _limit_sentences(_patient_overview_core_sentence(has_ph, mpap, lang=lang), max_sentences=2)
    if core:
        lines.append(f"- **{_lbl_pressure}:** {core} {_patient_relevance_line('main' if has_ph else 'neutral', lang=lang)}")

    pattern = _limit_sentences(_patient_overview_pattern_sentence(has_ph, hemo_cat, pvr, pawp, lang=lang), max_sentences=2)
    if pattern:
        lines.append(f"- **{_lbl_pattern}:** {pattern} {_patient_relevance_line('main' if has_ph else 'neutral', lang=lang)}")

    bnp_text = _limit_sentences(_patient_overview_bnp_sentence(bnp_kind, bnp_val, ci, lang=lang), max_sentences=2)
    if bnp_text:
        bnp_rel = "neutral"
        if str(bio_qual or "").strip().lower() in {"erhöht", "deutlich erhöht"}:
            bnp_rel = "main"
        elif str(bio_qual or "").strip().lower() == "niedrig":
            bnp_rel = "side"
        lines.append(f"- **{_lbl_biomarker}:** {bnp_text} {_patient_relevance_line(bnp_rel, lang=lang)}")

    if esc4:
        _risk_tpl = {
            "en": f"The current risk classification is {esc4}.",
            "zh": f"目前的风险分级为{esc4}。",
        }.get(lang, f"Die Risikoeinstufung liegt aktuell bei {esc4}.")
        risk_txt = _limit_sentences(_risk_tpl, max_sentences=2)
        lines.append(f"- **{_lbl_risk}:** {risk_txt} {_patient_relevance_line(_patient_relevance_from_esc4(esc4), lang=lang)}")

    next_step = _limit_sentences(_patient_overview_next_step_sentence(der, leading_action, lang=lang), max_sentences=2)
    if next_step:
        _uncertain = {"en": "not certain", "zh": "不确定"}.get(lang, "nicht sicher")
        rel = "main" if _uncertain in next_step.lower() else "neutral"
        lines.append(f"- **{_lbl_next}:** {next_step} {_patient_relevance_line(rel, lang=lang)}")

    _header_check = _tr("### Relevanz: Hauptbefunde und Nebenbefunde", lang)
    if lines and lines[-1] == _header_check:
        _fallback_txt = {
            "en": f"A prioritization is only partially possible based on the available data. {_patient_relevance_line('neutral', lang='en')}",
            "zh": f"根据现有数据，仅能进行有限的优先排序。 {_patient_relevance_line('neutral', lang='zh')}",
        }.get(lang, f"Eine Priorisierung ist anhand der vorliegenden Angaben nur eingeschränkt möglich. {_patient_relevance_line('neutral', lang=lang)}")
        lines.append(f"- **{_lbl_overall}:** {_fallback_txt}")

    lines.append("")


def _append_patient_diagnosis_block(
    *,
    lines: List[str],
    ui: Dict[str, Any],
    known_dx: str,
    known_subtype: str,
    first_dx: str,
    primary_dx: str,
    cause_patient: str,
    bundle: str,
    bundle_patient_blocks: Callable[[str], List[str]],
    blocks: Dict[str, Any],
    ctx: Dict[str, Any],
    rng: random.Random,
    lang: str = "de",
) -> None:
    lines.append(_tr("## Diagnosen und Einordnung", lang))
    if known_dx:
        dx_line = known_dx
        if known_subtype:
            dx_line = f"{dx_line} – {known_subtype}"
        if first_dx:
            _first_doc = {"en": "first documented", "zh": "首次记录"}.get(lang, "erstmals dokumentiert")
            dx_line = f"{dx_line} ({_first_doc}: {first_dx})"
        _lbl_known = {"en": "Known diagnosis (medical)", "zh": "已知诊断（医学）"}.get(lang, "Bekannte Diagnose (medizinisch)")
        lines.append(f"- **{_lbl_known}:** {dx_line}")
    if primary_dx:
        _lbl_current = {"en": "Current classification from this examination", "zh": "本次检查的当前分类"}.get(lang, "Aktuelle Einordnung dieser Untersuchung")
        lines.append(f"- **{_lbl_current}:** {primary_dx}")
    if cause_patient:
        _lbl_simple = {"en": "In simple terms", "zh": "通俗解释"}.get(lang, "Einfach erklärt")
        lines.append(f"- **{_lbl_simple}:** {cause_patient}")
    comorb_line = _build_relevante_vorerkrankungen_line(ui)
    if comorb_line and comorb_line != "-":
        _lbl_comorb = {"en": "Relevant pre-existing conditions (per documentation)", "zh": "相关既往病史（根据文档记录）"}.get(lang, "Relevante Vorerkrankungen (laut Dokumentation)")
        lines.append(f"- **{_lbl_comorb}:** {comorb_line}")
    if not (known_dx or primary_dx or cause_patient):
        _no_dx = {"en": "A structured diagnosis is currently not recorded; classification is based on measurements, symptoms, and clinical course.", "zh": "目前尚未记录结构化诊断；分类基于测量值、症状和临床病程。"}.get(lang, "Eine strukturierte Diagnosebezeichnung ist aktuell nicht hinterlegt; die Einordnung erfolgt über Messwerte, Beschwerden und Verlauf.")
        lines.append(f"- {_no_dx}")
    _icd10 = {"en": "**ICD-10 codes:** No structured ICD-10 codes are recorded in this dataset.", "zh": "**ICD-10编码：**本数据集中未记录结构化的ICD-10编码。"}.get(lang, "**ICD-10-Codes:** In diesem Datensatz sind keine strukturierten ICD-10-Codes hinterlegt.")
    lines.append(f"- {_icd10}")

    bundle_texts = _collect_patient_bundle_texts(bundle, bundle_patient_blocks, blocks, ctx, rng)
    if bundle_texts:
        _lbl_bundle = {"en": "Supplementary standardized classification", "zh": "补充标准化分类"}.get(lang, "Ergänzende standardisierte Einordnung")
        # Render as a bold paragraph header (not a bullet with no content)
        # so we never emit the awkward "- **Label:**" empty-bullet line.
        lines.append("")
        lines.append(f"**{_lbl_bundle}:**")
        for t in bundle_texts:
            lines.append(f"- {t}")
    lines.append("")


def _collect_patient_bundle_texts(
    bundle: str,
    bundle_patient_blocks: Callable[[str], List[str]],
    blocks: Dict[str, Any],
    ctx: Dict[str, Any],
    rng: random.Random,
) -> List[str]:
    out: List[str] = []
    for bid in bundle_patient_blocks(bundle):
        t = _render_patient_text(bid, blocks, ctx, rng)
        if t and (t not in out):
            out.append(t)
    return out

def _append_patient_intro_sections(
    *,
    lines: List[str],
    case: CaseLike,
    ui: Dict[str, Any],
    der: Dict[str, Any],
    blocks: Dict[str, Any],
    rng: random.Random,
    ctx: Dict[str, Any],
    bundle: str,
    bundle_patient_blocks: Callable[[str], List[str]],
    reason_rhk: str,
    story: str,
    has_ph: bool,
    mpap: Optional[float],
    hemo_cat: str,
    pvr: Optional[float],
    pawp: Optional[float],
    ci: Optional[float],
    bnp_kind: str,
    bnp_val: Optional[float],
    bio_qual: Optional[str],
    esc4: Any,
    leading_action: str,
    known_dx: str,
    known_subtype: str,
    first_dx: str,
    primary_dx: str,
    cause_patient: str,
    lang: str = "de",
) -> None:
    _append_patient_intro_meta(lines, ctx, reason_rhk, story, lang=lang, blocks=blocks, rng=rng)
    _esc4_line = ""
    if esc4:
        _esc4_line = {
            "en": f"The current risk classification is {esc4}. This influences how closely we plan therapy and follow-up.",
            "zh": f"目前的风险分级为{esc4}。这将影响我们对治疗和随访的安排。",
        }.get(lang, f"Die Risikoeinstufung liegt aktuell bei {esc4}. Das beeinflusst, wie eng wir Therapie und Kontrollen planen.")
    overview = [
        _patient_overview_core_sentence(has_ph, mpap, lang=lang),
        _patient_overview_clarity_sentence(
            has_ph=has_ph,
            hemo_cat=hemo_cat,
            mpap=mpap,
            pvr=pvr,
            pawp=pawp,
            lang=lang,
            blocks=blocks,
            ctx=ctx,
            rng=rng,
        ),
        _patient_overview_pattern_sentence(has_ph, hemo_cat, pvr, pawp, lang=lang),
        _patient_overview_bnp_sentence(bnp_kind, bnp_val, ci, lang=lang),
        _esc4_line,
        _patient_overview_next_step_sentence(der, leading_action, lang=lang),
    ]

    summary_text = _build_layered_paragraph(overview, min_words=80, max_words=120, lang=lang)
    lines.append(_tr("## Kurzfazit (Schnellüberblick)", lang))
    if summary_text:
        lines.append(summary_text)
    else:
        lines.append(_patient_variant_or_fallback(
            "PX_SUMMARY_MISSING",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Eine kompakte Einordnung ist derzeit nicht sicher möglich, weil zentrale Angaben fehlen.",
            en="A concise assessment is currently not possible because key data is missing.",
            zh="由于缺少关键数据，目前无法进行简要评估。",
        ))
    lines.append("")

    lines.append(_tr("### Wichtigste Punkte", lang))
    quick_points = [x for x in overview if x][:5]
    for point in quick_points:
        bullet = _limit_sentences(point, max_sentences=2)
        if bullet:
            lines.append(f"- {bullet}")
    lines.append("")

    _append_patient_relevance_section(
        lines=lines,
        has_ph=has_ph,
        mpap=mpap,
        hemo_cat=hemo_cat,
        pvr=pvr,
        pawp=pawp,
        bnp_kind=str(bnp_kind),
        bnp_val=bnp_val,
        ci=ci,
        bio_qual=bio_qual,
        esc4=esc4,
        der=der,
        leading_action=leading_action,
        lang=lang,
    )

    lines.append(_tr("## Details und Erklärungen", lang))
    lines.append(_patient_variant_or_fallback(
        "PX_DETAILS_INTRO",
        blocks,
        ctx,
        rng,
        lang=lang,
        de="Die folgenden Abschnitte erklären die Befunde ausführlicher.",
        en="The following sections explain the findings in more detail.",
        zh="以下各部分将更详细地解释检查结果。",
    ))
    lines.append("")

    _append_patient_diagnosis_block(
        lines=lines,
        ui=ui,
        known_dx=known_dx,
        known_subtype=known_subtype,
        first_dx=first_dx,
        primary_dx=primary_dx,
        cause_patient=cause_patient,
        bundle=bundle,
        bundle_patient_blocks=bundle_patient_blocks,
        blocks=blocks,
        ctx=ctx,
        rng=rng,
        lang=lang,
    )

    db_ie = _report_db_text(case, audience="patient", section="rhk_ie")
    if db_ie:
        lines.append(_tr("### Ergänzende Einordnung", lang))
        lines.append(db_ie)
        lines.append("")


def _append_patient_measurement_sections(
    *,
    lines: List[str],
    ui: Dict[str, Any],
    der: Dict[str, Any],
    blocks: Dict[str, Any],
    rng: random.Random,
    ctx: Dict[str, Any],
    has_ph: bool,
    mpap: Optional[float],
    pawp: Optional[float],
    pvr: Optional[float],
    ci: Optional[float],
    rap: Optional[float],
    hemo_cat: str,
    bnp_kind: str,
    bnp_val: Optional[float],
    bio_qual: Optional[str],
    hf_txt: Optional[str],
    leading_action: str,
    esc4: Any,
    esc4_n: Any,
    esc4_missing: List[Any],
    risk_txt: Optional[str],
    age_years: Optional[float],
    sex_txt: str,
    who_fc_txt: str,
    bmi_val: Optional[float],
    trend_info: Dict[str, Any],
    arch_text: Callable[[str], str],
    lang: str = "de",
) -> None:
    lines.append(_tr("## Was wurde bei Ihnen gemessen – und warum ist das wichtig?", lang))

    if has_ph:
        # Local ctx snapshot extended with numeric placeholders used by the new
        # PX_MEASURE_* blocks. We keep this separate from the caller's ctx so we
        # don't accidentally leak them into other unrelated templates.
        measure_ctx = dict(ctx)
        if mpap is not None:
            measure_ctx["mpap_str"] = _fmt(mpap, 0)
        if pawp is not None:
            measure_ctx["pawp_str"] = _fmt(pawp, 0)
        if pvr is not None:
            measure_ctx["pvr_str"] = _fmt(pvr, 1)
        if ci is not None:
            measure_ctx["ci_str"] = _fmt(ci, 2)
        if rap is not None:
            measure_ctx["rap_str"] = _fmt(rap, 0)

        if mpap is not None:
            lines.append(_patient_variant_or_fallback(
                _patient_mpap_block_key(mpap), blocks, measure_ctx, rng, lang=lang,
                de=(
                    f"Bei Ihnen wurde ein erhöhter Druck im Lungenkreislauf gemessen (mPAP {_fmt(mpap,0)} mmHg, Lungenhochdruck ab >20 mmHg). "
                    "Das bedeutet: Das rechte Herz muss Blut gegen einen höheren Widerstand in Richtung Lunge pumpen."
                ),
                en=f"An elevated pressure in the pulmonary circulation was measured in your case (mPAP {_fmt(mpap,0)} mmHg; pulmonary hypertension starts at >20 mmHg). This means: the right side of the heart has to pump blood against increased resistance toward the lungs.",
                zh=f"您的肺循环压力升高（mPAP {_fmt(mpap,0)} mmHg,肺动脉高压标准为 >20 mmHg）。这意味着:右心必须克服更大的阻力将血液泵向肺部。",
            ))
        else:
            lines.append(_patient_variant_or_fallback(
                "PX_MEASURE_PH_NO_MPAP", blocks, measure_ctx, rng, lang=lang,
                de="Bei Ihnen zeigen die Messungen einen Lungenhochdruck. Das bedeutet: Das rechte Herz muss Blut gegen einen höheren Widerstand in Richtung Lunge pumpen.",
                en="The measurements show pulmonary hypertension. This means: the right side of the heart has to pump blood against increased resistance toward the lungs.",
                zh="测量结果显示肺动脉高压。这意味着:右心必须克服更大的阻力将血液泵向肺部。",
            ))

        if hemo_cat == "precap" and (pawp is not None) and (pvr is not None):
            # Bridge: after the opening mPAP statement, introduce the pattern
            # (PAWP + PVR) as a related / additive finding so the paragraph
            # does not jump to a fresh "Der Druck..." sentence out of nowhere.
            _append_patient_bridge(lines, "add", blocks, rng)
            lines.append(_patient_variant_or_fallback(
                "PX_MEASURE_PRECAP_PATTERN", blocks, measure_ctx, rng, lang=lang,
                de=(
                    f"Der Druck vor der linken Herzhälfte ist dabei nicht erhöht (PAWP {_fmt(pawp,0)} mmHg). "
                    f"Gleichzeitig ist der Widerstand in den Lungengefäßen deutlich erhöht (PVR {_fmt(pvr,1)} WU, erhöht ab >2 WU). "
                    "Das Muster spricht eher für eine Ursache im Lungenkreislauf selbst oder im Zusammenhang mit einer Lungenerkrankung."
                ),
                en=(
                    f"The pressure before the left side of the heart is not elevated (PAWP {_fmt(pawp,0)} mmHg). "
                    f"At the same time, the resistance in the pulmonary vessels is clearly elevated (PVR {_fmt(pvr,1)} WU; elevated above >2 WU). "
                    "This pattern suggests that the cause is more likely in the pulmonary circulation itself or related to a lung condition."
                ),
                zh=(
                    f"左心前的压力未升高（PAWP {_fmt(pawp,0)} mmHg）。"
                    f"同时,肺血管阻力明显升高（PVR {_fmt(pvr,1)} WU,升高阈值 >2 WU）。"
                    "这种模式更倾向于原因在肺循环本身或与肺部疾病相关。"
                ),
            ))
            # Severity-graded PVR follow-up for moderate/severe resistance.
            _pvr_sev_key = _patient_pvr_severity_key(pvr)
            if _pvr_sev_key in {"PX_MEASURE_PVR_MOD", "PX_MEASURE_PVR_SEV"}:
                _pvr_line = _render_patient_text(_pvr_sev_key, blocks, measure_ctx, rng)
                if _pvr_line:
                    # Bridge: the severity follow-up is a consequence of the
                    # pattern sentence above — glue them with a causal link.
                    _append_patient_bridge(lines, "consequence", blocks, rng)
                    lines.append(_pvr_line)
        elif hemo_cat in {"ipcph", "cpcph"} and pawp is not None:
            # Bridge: mPAP → PAWP is a contrast (pre- vs post-capillary side),
            # not a pure "and also" — use "contrast" here.
            _append_patient_bridge(lines, "contrast", blocks, rng)
            lines.append(_patient_variant_or_fallback(
                _patient_pawp_block_key(pawp), blocks, measure_ctx, rng, lang=lang,
                de=(
                    f"Der Druck vor der linken Herzhälfte ist erhöht (PAWP {_fmt(pawp,0)} mmHg). "
                    "Das kann einen Rückstau in die Lunge begünstigen und wird bei der Einordnung mit berücksichtigt."
                ),
                en=(
                    f"The pressure before the left side of the heart is elevated (PAWP {_fmt(pawp,0)} mmHg). "
                    "This can contribute to fluid backing up into the lungs and is taken into account during classification."
                ),
                zh=(
                    f"左心前的压力升高（PAWP {_fmt(pawp,0)} mmHg）。"
                    "这可能导致液体回流至肺部,在分类评估时会予以考虑。"
                ),
            ))
            # For cpcph the lung vessels also contribute — if PVR is moderately or
            # severely elevated we add a severity-graded line so the patient sees
            # that both sides are being addressed.
            if hemo_cat == "cpcph" and pvr is not None:
                _pvr_sev_key = _patient_pvr_severity_key(pvr)
                if _pvr_sev_key in {"PX_MEASURE_PVR_MOD", "PX_MEASURE_PVR_SEV"}:
                    _pvr_line = _render_patient_text(_pvr_sev_key, blocks, measure_ctx, rng)
                    if _pvr_line:
                        # Bridge: the added PVR line is an additive finding
                        # alongside the elevated PAWP in cpcph.
                        _append_patient_bridge(lines, "add", blocks, rng)
                        lines.append(_pvr_line)
        elif hemo_cat:
            if hemo_cat == "precap":
                lines.append(_patient_variant_or_fallback(
                    "PX_MEASURE_PRECAP_ONLY_CATEGORY", blocks, measure_ctx, rng, lang=lang,
                    de="Das Messmuster passt eher zu einer Form, bei der die Lungengefäße oder die Lunge selbst im Vordergrund stehen.",
                    en="The measurement pattern is more consistent with a form where the pulmonary vessels or the lungs themselves are primarily involved.",
                    zh="测量模式更符合以肺血管或肺本身为主要问题的类型。",
                ))
            elif hemo_cat in ("high_flow_or_borderline", "ph_unclassified"):
                t = _render_patient_text("PX_HIGH_FLOW" if "high_flow" in hemo_cat else "PX_UNCLASSIFIED", blocks, ctx, rng)
                if t:
                    lines.append(t)
            else:
                lines.append(_patient_variant_or_fallback(
                    "PX_MEASURE_POSTCAP_ONLY_CATEGORY", blocks, measure_ctx, rng, lang=lang,
                    de="Das Messmuster passt eher zu einer Form, bei der die linke Herzseite mitbeteiligt sein kann.",
                    en="The measurement pattern is more consistent with a form where the left side of the heart may also be involved.",
                    zh="测量模式更符合左心可能也参与其中的类型。",
                ))

        if ci is not None:
            # Bridge: topic shift from pressure/resistance to pump output.
            _append_patient_bridge(lines, "pump_focus", blocks, rng)
            _ci_sev_key = _patient_ci_low_severity_key(ci)
            if _ci_sev_key is not None:
                lines.append(_patient_variant_or_fallback(
                    _ci_sev_key, blocks, measure_ctx, rng, lang=lang,
                    de=(
                        f"Die Pumpleistung des Herzens ist dabei eher reduziert (CI {_fmt(ci,2)} l/min/m²). "
                        "Das kann erklären, warum Belastung schneller schwerfällt oder Schwindel auftreten kann."
                    ),
                    en=f"Cardiac output is rather reduced (CI {_fmt(ci,2)} l/min/m²). This may explain why exertion becomes difficult more quickly or dizziness may occur.",
                    zh=f"心脏泵血功能偏低（CI {_fmt(ci,2)} l/min/m²）。这可能解释了为什么运动时更容易感到吃力或出现头晕。",
                ))
            else:
                lines.append(_patient_variant_or_fallback(
                    "PX_MEASURE_CI_OK", blocks, measure_ctx, rng, lang=lang,
                    de=f"Die Pumpleistung ist im Rahmen der Messung nicht klar vermindert (CI {_fmt(ci,2)} l/min/m²).",
                    en=f"Cardiac output is not clearly reduced in this measurement (CI {_fmt(ci,2)} l/min/m²).",
                    zh=f"在本次检测中,心脏泵血功能未明显降低（CI {_fmt(ci,2)} l/min/m²）。",
                ))

        if rap is not None:
            _rap_sev_key = _patient_rap_severity_key(rap)
            if _rap_sev_key is not None:
                # Bridge: topic shift to the right-heart / venous side.
                _append_patient_bridge(lines, "right_heart", blocks, rng)
                lines.append(_patient_variant_or_fallback(
                    _rap_sev_key, blocks, measure_ctx, rng, lang=lang,
                    de=(
                        f"Der Druck im rechten Vorhof (RAP) liegt bei {_fmt(rap,0)} mmHg und ist erhöht. "
                        "Das kann ein Hinweis auf eine stärkere Belastung der rechten Herzhälfte sein."
                    ),
                    en=f"The right atrial pressure (RAP) is {_fmt(rap,0)} mmHg and is elevated. This may indicate increased strain on the right side of the heart.",
                    zh=f"右心房压力（RAP）为{_fmt(rap,0)} mmHg,偏高。这可能提示右心负荷增加。",
                ))

        if bnp_val is not None and bio_qual:
            # Bridge: topic shift from pressures / pump to laboratory marker.
            _append_patient_bridge(lines, "biomarker", blocks, rng)
            if bio_qual == "niedrig":
                _txt = {
                    "en": f"Your blood marker {bnp_kind} is low ({_fmt(bnp_val,0)} pg/ml). This argues against significant current cardiac overload — but the overall picture with symptoms and measurements always matters.",
                    "zh": f"您的血液标志物 {bnp_kind} 偏低（{_fmt(bnp_val,0)} pg/ml）。这不太支持目前存在明显心脏负荷过重——但始终需要结合症状和测量值综合判断。",
                }.get(lang, (
                    f"Der Blutwert {bnp_kind} ist bei Ihnen niedrig ({_fmt(bnp_val,0)} pg/ml). "
                    "Das spricht eher gegen eine aktuell ausgeprägte Herzüberlastung – wichtig ist aber immer die Gesamtschau mit Beschwerden und Messwerten."
                ))
                lines.append(_txt)
            elif bio_qual == "erhöht":
                _txt = {
                    "en": f"Your blood marker {bnp_kind} is elevated ({_fmt(bnp_val,0)} pg/ml). This is consistent with the heart currently having to work harder.",
                    "zh": f"您的血液标志物 {bnp_kind} 升高（{_fmt(bnp_val,0)} pg/ml）。这与心脏目前需要更努力工作的表现一致。",
                }.get(lang, (
                    f"Der Blutwert {bnp_kind} ist bei Ihnen erhöht ({_fmt(bnp_val,0)} pg/ml). "
                    "Das passt dazu, dass das Herz aktuell stärker arbeiten muss."
                ))
                lines.append(_txt)
            elif bio_qual == "deutlich erhöht":
                _txt = {
                    "en": f"Your blood marker {bnp_kind} is significantly elevated ({_fmt(bnp_val,0)} pg/ml). This is a warning sign that the heart is under greater strain and will be closely monitored.",
                    "zh": f"您的血液标志物 {bnp_kind} 明显升高（{_fmt(bnp_val,0)} pg/ml）。这是心脏负荷较重的警示信号，将在后续密切观察。",
                }.get(lang, (
                    f"Der Blutwert {bnp_kind} ist bei Ihnen deutlich erhöht ({_fmt(bnp_val,0)} pg/ml). "
                    "Das ist ein Warnsignal dafür, dass das Herz stärker belastet ist und wird im Verlauf eng beobachtet."
                ))
                lines.append(_txt)
    else:
        _txt = {
            "en": "At rest, the measurements do not show pulmonary hypertension. If symptoms occur mainly during exertion, this can still be investigated, because some changes only become visible under stress.",
            "zh": "静息状态下，测量值未显示肺动脉高压。如果症状主要在活动时出现，仍可进一步检查，因为某些变化只在负荷时才会显现。",
        }.get(lang, (
            "In Ruhe zeigen die Messwerte keinen Lungenhochdruck. Wenn Beschwerden vor allem unter Belastung auftreten, kann das trotzdem abgeklärt werden, "
            "weil manche Veränderungen erst unter Belastung sichtbar werden."
        ))
        lines.append(_txt)

    t_arch = arch_text("measured")
    if t_arch:
        lines.append(t_arch)
    lines.append("")

    if der.get("vol_challenge_done"):
        lines.append(_tr("## Zusatztest: Volumenchallenge (Flüssigkeitsbelastung)", lang))
        t = _render_patient_text("PX_VOLUME_CHALLENGE", blocks, ctx, rng)
        if t:
            lines.append(t)

        pawp_pre = _safe_float(der.get("vol_challenge_pawp_pre"))
        pawp_post = _safe_float(der.get("vol_challenge_pawp_post"))
        d_pawp = _safe_float(der.get("vol_challenge_delta_pawp"))
        endp_ge18 = bool(der.get("vol_challenge_pawp_ge_18"))

        bits: List[str] = []
        if pawp_pre is not None and pawp_post is not None:
            _ba_lbl = {"en": "PAWP before/after", "zh": "PAWP 前/后"}.get(lang, "PAWP vor/nach")
            bits.append(f"{_ba_lbl}: {fmt_float(pawp_pre,0)} → {fmt_float(pawp_post,0)} mmHg")
        if d_pawp is not None:
            _chg_lbl = {"en": "Change", "zh": "变化"}.get(lang, "Änderung")
            bits.append(f"{_chg_lbl}: {fmt_float(d_pawp,0)} mmHg")
        if bits:
            _orient_prefix = {"en": "Orientation: ", "zh": "参考数据："}.get(lang, "Orientierung: ")
            lines.append(_orient_prefix + " | ".join(bits) + ".")
        _interp_prefix = {"en": "Interpretation", "zh": "判读"}.get(lang, "Einordnung")
        if endp_ge18:
            _interp_body = {"en": "The pressure on the left side of the heart rises significantly. This can contribute to fluid backing up into the lungs.", "zh": "左心侧压力明显升高。这可能导致液体回流至肺部。"}.get(lang, "Der Druck auf der linken Herzseite steigt dabei deutlich an. Das kann zu einem Rückstau in die Lunge beitragen.")
        else:
            _interp_body = {"en": "The pressure on the left side of the heart remains rather low. This argues against a significant pressure increase from fluid alone.", "zh": "左心侧压力保持较低。这不太支持仅由液体因素引起的明显压力升高。"}.get(lang, "Der Druck auf der linken Herzseite bleibt dabei eher niedrig. Das spricht eher gegen eine ausgeprägte Druckerhöhung durch Flüssigkeit allein.")
        lines.append(f"{_interp_prefix}: {_interp_body}")
        lines.append("")

    if der.get("vaso_test_done"):
        lines.append(_tr("## Zusatztest: Vasoreaktivität", lang))
        t = _render_patient_text("PX_VASOREACTIVITY", blocks, ctx, rng)
        if t:
            lines.append(t)

        agent = str(ui.get("vaso_agent") or "—")
        resp_desc = str(ui.get("vaso_response_desc") or "").strip()
        responder = der.get("vaso_responder")
        if agent and agent != "—":
            _txt = {"en": f"Test medication: {agent}.", "zh": f"测试药物：{agent}。"}.get(lang, f"Testmedikament: {agent}.")
            lines.append(_txt)
        if resp_desc:
            # Avoid double periods when the source string already ends in "."
            resp_body = resp_desc.rstrip(". ")
            _txt = {
                "en": f"Observation: {resp_body}.",
                "zh": f"观察结果：{resp_body}。",
            }.get(lang, f"Beobachtung: {resp_body}.")
            lines.append(_txt)
        if responder is True:
            lines.append({"en": "Interpretation: There was a significant relaxation of the pulmonary vessels during the test. This may be relevant for further treatment planning.", "zh": "判读：测试中肺血管出现了明显的舒张反应，这对后续治疗方案的制定可能具有重要意义。"}.get(lang, "Einordnung: Es gab eine deutliche Entspannung der Lungengefäße im Test. Das kann für die weitere Therapieplanung relevant sein."))
        elif responder is False and resp_desc:
            lines.append({"en": "Interpretation: The test did not show a pronounced relaxation response according to the standard criteria.", "zh": "判读：根据经典标准，测试中未显示明显的舒张反应。"}.get(lang, "Einordnung: Es zeigte sich im Test keine ausgeprägte Entspannung nach den klassischen Kriterien."))
        lines.append("")

    lines.append(_tr("## Was bedeutet das für Sie?", lang))
    eti = der.get(K_PH_ETIOLOGY) if isinstance(der, dict) else None
    eti_patient_line = str(eti.get("patient_cause_line") or "").strip() if isinstance(eti, dict) else ""
    cand_n = len(eti.get(K_CANDIDATES) or []) if isinstance(eti, dict) else 0
    ambiguous = bool(cand_n > 1)

    if has_ph:
        if hemo_cat == "precap":
            lines.append(_patient_variant_or_fallback(
                "PX_OVERALL_PRECAP",
                blocks,
                ctx,
                rng,
                lang=lang,
                de="In der Zusammenschau spricht vieles dafür, dass der erhöhte Widerstand vor allem in den Lungengefäßen selbst entsteht. Entscheidend ist nun, warum das so ist.",
                en="Overall, the findings strongly suggest that the increased resistance primarily originates in the pulmonary vessels themselves. The key question now is why.",
                zh="综合来看，多项指标表明阻力升高主要源于肺血管本身。现在关键的问题是找出原因。",
            ))
        elif hemo_cat in {"ipcph", "cpcph"}:
            lines.append(_patient_variant_or_fallback(
                "PX_OVERALL_POSTCAP",
                blocks,
                ctx,
                rng,
                lang=lang,
                de="In der Zusammenschau gibt es Hinweise auf eine Mitbeteiligung der linken Herzseite. Entscheidend ist nun, wie groß dieser Anteil ist und ob zusätzlich der Lungenkreislauf selbst betroffen ist.",
                en="Overall, there are indications that the left side of the heart is also involved. The key question now is how large this contribution is and whether the pulmonary circulation itself is also affected.",
                zh="综合来看，有迹象表明左心也参与其中。现在关键的问题是左心的贡献有多大，以及肺循环本身是否也受到影响。",
            ))
        else:
            lines.append(_patient_variant_or_fallback(
                "PX_OVERALL_AMBIGUOUS",
                blocks,
                ctx,
                rng,
                lang=lang,
                de="In der Zusammenschau ist die Einordnung möglich, aber nicht alle Teilaspekte sind eindeutig. Wir stützen uns deshalb auf mehrere Bausteine (Messwerte, Bildgebung, Belastbarkeit).",
                en="Overall, classification is possible, but not all aspects are clear-cut. We therefore rely on multiple building blocks (measurements, imaging, exercise capacity).",
                zh="综合来看，可以进行分类，但并非所有方面都十分明确。因此我们综合多个方面（测量值、影像学、运动耐量）来判断。",
            ))
        lines.append("")
    else:
        lines.append(_patient_variant_or_fallback(
            "PX_OVERALL_NO_PH",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Die Messwerte in Ruhe sind unauffällig. Wenn Beschwerden vor allem unter Belastung auftreten, kann das trotzdem weiter eingeordnet werden – manche Veränderungen zeigen sich erst dann.",
            en="The resting measurements are unremarkable. If symptoms occur mainly during exertion, this can still be further evaluated — some changes only become apparent under stress.",
            zh="静息状态下的测量值正常。如果症状主要在活动时出现，仍可进一步评估——某些变化只在负荷时才会显现。",
        ))
        lines.append("")

    symp = _patient_symptom_profile(ui)
    if symp.get("syncope"):
        t = _render_patient_text("PX_SYMPTOM_PROFILE_SYNCOPE", blocks, ctx, rng)
        if t:
            lines.append(t)
            lines.append("")
    else:
        sev = symp.get(K_SEVERITY)
        symp_block_id: Optional[str] = {
            "low": "PX_SYMPTOM_PROFILE_LOW",
            "moderate": "PX_SYMPTOM_PROFILE_MODERATE",
            "high": "PX_SYMPTOM_PROFILE_HIGH",
        }.get(sev or "")
        if symp_block_id:
            t = _render_patient_text(symp_block_id, blocks, ctx, rng)
            if t:
                lines.append(t)
                lines.append("")

    functional_context = _patient_functional_context_lines(ui, lang=lang)
    if functional_context:
        lines.append(_tr("## Ihre Angaben zur Belastbarkeit im Alltag", lang))
        for item in functional_context[:6]:
            lines.append(f"- {item}")
        _func_help = {"en": "These details help to better assess changes over time and to set individual treatment goals.", "zh": "这些信息有助于更好地评估随时间的变化并制定个性化的治疗目标。"}.get(lang, "Diese Angaben helfen, Veränderungen im Verlauf besser einzuordnen und Therapieziele individuell festzulegen.")
        lines.append(_func_help)
        lines.append("")

    cpet_patient_lines = _patient_cpet_lines(ui, lang=lang)
    if cpet_patient_lines:
        lines.append(_tr("## Spiroergometrie (Belastungstest mit Atemgas-Messung)", lang))
        lines.extend(cpet_patient_lines)
        lines.append("")

    disc = _patient_discordance_flags(symp=symp, mpap=mpap, bio_qual=bio_qual, ui=ui)

    t_arch2 = arch_text("meaning")
    if t_arch2:
        lines.append(t_arch2)
        lines.append("")

    if ambiguous:
        lines.append(_patient_variant_or_fallback(
            "PX_ETIOLOGY_UNCLEAR",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Welche Ursache im Vordergrund steht, lässt sich anhand der vorliegenden Angaben noch nicht sicher festlegen.",
            en="Which cause is predominant cannot yet be determined with certainty based on the available information.",
            zh="根据现有资料，尚无法确定哪种原因占主导地位。",
        ))
        if leading_action:
            _txt = {"en": f"As the next step, we will specifically investigate {leading_action}. This will help clarify which treatment is best for you.", "zh": f"因此，下一步我们将有针对性地检查{leading_action}。这将有助于明确最适合您的治疗方案。"}.get(lang, f"Als nächster Schritt klären wir deshalb gezielt {leading_action}. Damit wird klarer, welche Behandlung bei Ihnen am besten passt.")
            lines.append(_txt)
        else:
            lines.append(_patient_variant_or_fallback(
                "PX_ETIOLOGY_FURTHER_TESTS",
                blocks,
                ctx,
                rng,
                lang=lang,
                de="Deshalb ergänzen wir weitere Untersuchungen. Ziel ist, die Hauptursache zu klären und die Behandlung gezielt auszurichten.",
                en="Therefore, we are adding further tests. The goal is to identify the main cause and tailor treatment accordingly.",
                zh="因此我们将安排进一步检查，目的是明确主要原因并有针对性地制定治疗方案。",
            ))
        lines.append("")

    if eti_patient_line:
        cleaned = eti_patient_line.replace("Hinweise auf:", "")
        cleaned = re.sub(r"\bHinweise auf\b", "", cleaned).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        if cleaned:
            _txt = {"en": f"Possible causes that we are investigating in your case: {cleaned}", "zh": f"我们正在为您检查的可能原因：{cleaned}"}.get(lang, f"Mögliche Ursachen, die wir in Ihrem Fall prüfen: {cleaned}")
            lines.append(_txt)
            lines.append("")

    if bool(ui.get(K_CHD_POS)) or bool(ui.get("step_up_present")):
        lines.append(_patient_variant_or_fallback(
            "PX_SHUNT_HINT",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Die Messungen geben Hinweise auf eine zusätzliche Verbindung zwischen Herzhöhlen. Das kann den Blutfluss beeinflussen und wird deshalb gezielt abgeklärt.",
            en="The measurements suggest an additional connection between heart chambers. This can affect blood flow and will therefore be specifically investigated.",
            zh="测量结果提示心腔之间可能存在额外的通道连接，这可能影响血流，因此将进行针对性检查。",
        ))
        lines.append("")

    if hf_txt:
        lines.append(hf_txt)
        lines.append("")

    missing_core: List[str] = []
    if mpap is None:
        missing_core.append({"en": "mean pulmonary artery pressure", "zh": "平均肺动脉压"}.get(lang, "mittlerer Druck in den Lungengefäßen"))
    if pawp is None:
        missing_core.append({"en": "pressure before the left heart", "zh": "左心前压力"}.get(lang, "Druck vor der linken Herzhälfte"))
    if pvr is None:
        missing_core.append({"en": "pulmonary vascular resistance", "zh": "肺血管阻力"}.get(lang, "Widerstand in den Lungengefäßen"))
    if ci is None:
        missing_core.append({"en": "cardiac output relative to body size", "zh": "相对于体表面积的心输出量"}.get(lang, "Pumpleistung bezogen auf die Körpergröße"))
    if missing_core:
        lines.append(_tr("## Nicht gemessene oder nicht verwertbare Kernwerte", lang))
        _missing_expl = {"en": "Some values could not be obtained or reliably evaluated during this examination. This does not mean they are normal — it means they are unavailable for classification.", "zh": "本次检查中部分数值无法获取或无法可靠评估。这并不意味着它们正常，而是说它们无法用于分类评估。"}.get(lang, "Einige Werte konnten in dieser Untersuchung nicht erhoben oder nicht sicher ausgewertet werden. Das bedeutet nicht, dass sie normal sind, sondern dass sie für die Einordnung fehlen.")
        lines.append(_missing_expl)
        lines.append("- " + "; ".join(missing_core) + ".")
        lines.append("")

    lines.append(_tr("## Wichtige Werte zur Orientierung", lang))
    hemo_items: List[str] = []
    _lbl_mpap = {"en": "Mean pulmonary artery pressure (mPAP)", "zh": "平均肺动脉压 (mPAP)"}.get(lang, "Mittlerer Druck in den Lungengefäßen (mPAP)")
    _lbl_pawp = {"en": "Pressure before the left heart (PAWP)", "zh": "左心前压力 (PAWP)"}.get(lang, "Druck vor der linken Herzhälfte (PAWP)")
    _lbl_pvr = {"en": "Pulmonary vascular resistance (PVR)", "zh": "肺血管阻力 (PVR)"}.get(lang, "Widerstand in den Lungengefäßen (PVR)")
    _lbl_ci = {"en": "Cardiac output relative to body size (CI)", "zh": "相对于体表面积的心输出量 (CI)"}.get(lang, "Pumpleistung bezogen auf die Körpergröße (CI)")
    _lbl_rap = {"en": "Right atrial pressure (RAP)", "zh": "右心房压力 (RAP)"}.get(lang, "Druck im rechten Vorhof (RAP)")
    _note_ph = {"en": "pulmonary hypertension above >20 mmHg", "zh": "肺动脉高压阈值 >20 mmHg"}.get(lang, "Lungenhochdruck ab >20 mmHg")
    _note_pawp = {"en": "often elevated above >15 mmHg", "zh": "常在 >15 mmHg 时升高"}.get(lang, "häufig erhöht ab >15 mmHg")
    _note_pvr = {"en": "elevated above >2 WU", "zh": "升高阈值 >2 WU"}.get(lang, "erhöht ab >2 WU")
    _note_rap = {"en": "often elevated above >8 mmHg", "zh": "常在 >8 mmHg 时升高"}.get(lang, "häufig erhöht ab >8 mmHg")
    _lbl_bio = {"en": "blood marker for cardiac stress", "zh": "心脏负荷血液标志物"}.get(lang, "Blutwert bei Herzbelastung")
    if mpap is not None:
        hemo_items.append(
            f"- **{_lbl_mpap}**: {_fmt(mpap,0)} mmHg ({_patient_hemo_qual('mPAP', mpap, lang=lang)}; {_note_ph})"
        )
    if pawp is not None:
        hemo_items.append(
            f"- **{_lbl_pawp}**: {_fmt(pawp,0)} mmHg ({_patient_hemo_qual('PAWP', pawp, lang=lang)}; {_note_pawp})"
        )
    if pvr is not None:
        hemo_items.append(
            f"- **{_lbl_pvr}**: {_fmt(pvr,1)} WU ({_patient_hemo_qual('PVR', pvr, lang=lang)}; {_note_pvr})"
        )
    if ci is not None:
        hemo_items.append(f"- **{_lbl_ci}**: {_fmt(ci,2)} l/min/m² ({_patient_hemo_qual('CI', ci, lang=lang)})")
    if rap is not None:
        hemo_items.append(
            f"- **{_lbl_rap}**: {_fmt(rap,0)} mmHg ({_patient_hemo_qual('RAP', rap, lang=lang)}; {_note_rap})"
        )
    if bnp_val is not None:
        q = _patient_bio_qual(str(bnp_kind), bnp_val, lang=lang)
        q_txt = f"{q}" if q else ""
        if q_txt:
            q_txt = f" ({q_txt})"
        hemo_items.append(f"- **{bnp_kind}** ({_lbl_bio}): {_fmt(bnp_val,0)} pg/ml{q_txt}")

    if hemo_items:
        lines.extend(hemo_items)
    else:
        lines.append({"en": "No core values available.", "zh": "无核心数值可用。"}.get(lang, "Keine Kernwerte verfügbar."))
    lines.append("")

    lines.append(_patient_variant_or_fallback(
        "PX_CORE_VALUES_NOTE",
        blocks,
        ctx,
        rng,
        lang=lang,
        de="Wichtig: Entscheidend ist die Kombination dieser Werte und der Verlauf. Eine einzelne Zahl erklärt Beschwerden selten vollständig.",
        en="Important: What matters is the combination of these values and how they change over time. A single number rarely explains symptoms fully.",
        zh="重要提示：关键在于这些数值的组合以及随时间的变化趋势。单一数值很少能完全解释症状。",
    ))
    lines.append("")

    lines.append(_tr("## Persönliche Risikoeinschätzung", lang))
    if esc4:
        risk_head = {"en": f"Your current ESC/ERS risk classification is: {esc4}.", "zh": f"您目前的ESC/ERS风险分级为：{esc4}。"}.get(lang, f"Ihre aktuelle ESC/ERS-Risikoeinstufung lautet: {esc4}.")
        if esc4_n is not None:
            try:
                risk_head = {"en": f"Your current ESC/ERS risk classification is: {esc4} (based on {int(esc4_n)} evaluable criteria).", "zh": f"您目前的ESC/ERS风险分级为：{esc4}（基于{int(esc4_n)}项可评估指标）。"}.get(lang, f"Ihre aktuelle ESC/ERS-Risikoeinstufung lautet: {esc4} (aus {int(esc4_n)} verwertbaren Merkmalen).")
            except (TypeError, ValueError) as exc:
                log_exception("RHK_REP_ESC4_COUNT", "ESC/ERS count formatting fallback used.", exc)
                risk_head = {"en": f"Your current ESC/ERS risk classification is: {esc4}.", "zh": f"您目前的ESC/ERS风险分级为：{esc4}。"}.get(lang, f"Ihre aktuelle ESC/ERS-Risikoeinstufung lautet: {esc4}.")
        lines.append(risk_head)
    else:
        lines.append(_patient_variant_or_fallback(
            "PX_ESC_RISK_UNAVAILABLE",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Eine standardisierte ESC/ERS-Risikoeinstufung konnte aus den aktuellen Angaben nicht sicher berechnet werden.",
            en="A standardized ESC/ERS risk stratification could not be reliably calculated from the available data.",
            zh="根据现有资料，无法可靠地计算标准化的ESC/ERS风险分层。",
        ))

    if risk_txt:
        lines.append(risk_txt)

    risk_context_bits: List[str] = []
    if age_years is not None:
        _lbl_age = {"en": "Age", "zh": "年龄"}.get(lang, "Alter")
        _lbl_yrs = {"en": "years", "zh": "岁"}.get(lang, "Jahre")
        risk_context_bits.append(f"{_lbl_age}: {int(round(age_years))} {_lbl_yrs}")
    if sex_txt:
        _lbl_sex = {"en": "Sex", "zh": "性别"}.get(lang, "Geschlecht")
        risk_context_bits.append(f"{_lbl_sex}: {sex_txt}")
    if who_fc_txt:
        _lbl_who = {"en": "WHO functional class", "zh": "WHO功能分级"}.get(lang, "WHO-Funktionsklasse")
        risk_context_bits.append(f"{_lbl_who}: {who_fc_txt}")
    if bmi_val is not None:
        risk_context_bits.append(f"BMI: {_fmt(bmi_val,1)} kg/m²")
    if risk_context_bits:
        _ctx_prefix = {"en": "Contextual factors considered: ", "zh": "已考虑的背景因素："}.get(lang, "Berücksichtigte Kontextfaktoren: ")
        lines.append(_ctx_prefix + "; ".join(risk_context_bits) + ".")

    miss = [str(x).strip() for x in (esc4_missing or []) if str(x).strip()]
    if miss:
        _miss_prefix = {"en": "For an even more precise risk assessment, the following are currently missing: ", "zh": "为了更精确地评估风险，目前尚缺以下信息："}.get(lang, "Für eine noch genauere Risikoeinschätzung fehlen aktuell: ")
        lines.append(_miss_prefix + ", ".join(miss[:8]) + ".")
    lines.append("")

    disc_blocks: List[str] = []
    if disc.get("high_mpap_low_bnp"):
        disc_blocks.append("PX_DISCORDANCE_HIGH_MPAP_LOW_BNP")
    if disc.get("low_pressure_high_symptoms"):
        disc_blocks.append("PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS")
    if disc.get("echo_ok_cath_high"):
        disc_blocks.append("PX_DISCORDANCE_ECHO_OK_CATH_HIGH")

    if disc_blocks:
        lines.append(_tr("## Wenn Werte und Beschwerden nicht gut zusammenpassen", lang))
        _disc_expl = {"en": "This is not uncommon with heart and lung conditions. What matters then is that we explain specifically which part of the findings is most relevant for your daily life.", "zh": "这在心肺疾病中并不少见。重要的是我们有针对性地解释哪些检查结果对您的日常生活最为关键。"}.get(lang, "Das kommt bei Herz und Lungenerkrankungen häufiger vor. Wichtig ist dann, dass wir gezielt erklären, welcher Teil des Befundes für Sie im Alltag entscheidend ist.")
        lines.append(_disc_expl)
        for bid in disc_blocks:
            t = _render_patient_text(bid, blocks, ctx, rng)
            if t:
                lines.append(t)
        lines.append("")

    if trend_info.get("has_prev"):
        lines.append(_tr("## Verlauf im Vergleich", lang))
        tx_txt = str(trend_info.get("tx_txt") or "").strip()
        if ui.get("prev_is_initial"):
            lines.append({"en": "This examination also serves as a **follow-up after a baseline measurement**.", "zh": "本次检查（也）作为**基线测量后的随访复查**。"}.get(lang, "Diese Untersuchung dient (auch) als **Verlaufskontrolle nach einer Ausgangsmessung**."))
        if tx_txt:
            _txt = {"en": f"Since the previous examination, the following therapy was reported: **{tx_txt}**.", "zh": f"自上次检查以来，报告的治疗方案为：**{tx_txt}**。"}.get(lang, f"Seit der Voruntersuchung wurde als Therapie angegeben: **{tx_txt}**.")
            lines.append(_txt)
        lines.append(trend_info.get("sentence_patient") or "")
        detail_patient = str(trend_info.get("detail_patient") or "").strip()
        if detail_patient:
            lines.append(detail_patient)
        recp = str(trend_info.get("rec_patient") or "").strip()
        subtype_pat = str(trend_info.get("subtype_patient") or "").strip()
        if subtype_pat:
            lines.append("")
            lines.append(subtype_pat)
        if recp:
            lines.append("")
            _practical_lbl = {"en": "What does this mean in practice?", "zh": "这在实际中意味着什么？"}.get(lang, "Was bedeutet das praktisch?")
            lines.append(f"**{_practical_lbl}** {recp}")
        lines.append("")


def _append_patient_followup_sections(
    *,
    lines: List[str],
    ui: Dict[str, Any],
    der: Dict[str, Any],
    blocks: Dict[str, Any],
    rng: random.Random,
    ctx: Dict[str, Any],
    module_summary: Dict[str, str],
    glossary: Dict[str, str],
    all_mods: List[str],
    policy: Dict[str, Any],
    has_ph: bool,
    followup_timing_desc: str,
    invasive_followup_desc: str,
    leading_action: str,
    congestion: bool,
    congestion_assessable: bool,
    pawp: Optional[float],
    warn_lines: List[str],
    first_nonempty: Callable[[Dict[str, Any], List[str]], str],
    lang: str = "de",
) -> None:
    lines.append(_tr("## Wie geht es weiter?", lang))
    lines.append(_tr("### Nachsorge und Kontrolltermine", lang))
    if followup_timing_desc:
        _followup_line = {"en": f"Recommended clinical follow-up: in {followup_timing_desc}.", "zh": f"建议的临床随访时间：{followup_timing_desc}内。"}.get(lang, f"Empfohlene klinische Verlaufskontrolle: in {followup_timing_desc}.")
        lines.append(f"- {_followup_line}")
    else:
        _followup_default = _patient_variant_or_fallback(
            "PX_FOLLOWUP_TIMING_DEFAULT",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Der genaue Zeitpunkt der nächsten klinischen Kontrolle wird im Behandlungsgespräch festgelegt.",
            en="The exact timing of the next clinical follow-up will be determined during the treatment discussion.",
            zh="下次临床复查的具体时间将在治疗讨论中确定。",
        )
        lines.append(f"- {_followup_default}")

    if has_ph and invasive_followup_desc:
        _inv_line = {"en": f"If therapy decisions or unclear findings require it: repeat right heart catheterization in {invasive_followup_desc}.", "zh": f"如果治疗决策或不明确的病程需要：在{invasive_followup_desc}内再次进行右心导管检查。"}.get(lang, f"Wenn Therapieentscheidungen oder unklare Verläufe es erfordern: erneute Rechtsherzkatheter-Kontrolle in {invasive_followup_desc}.")
        lines.append(f"- {_inv_line}")
    elif has_ph:
        _inv_default = _patient_variant_or_fallback(
            "PX_INVASIVE_FOLLOWUP_DEFAULT",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Eine erneute invasive Kontrolle wird bei klinischer Verschlechterung oder bei Therapiefragen geprüft.",
            en="A repeat invasive assessment will be considered if there is clinical deterioration or if treatment questions arise.",
            zh="如果临床状况恶化或出现治疗相关问题，将考虑再次进行有创检查。",
        )
        lines.append(f"- {_inv_default}")
    _observe = _patient_variant_or_fallback(
        "PX_OBSERVE_WARNING_SIGNS",
        blocks,
        ctx,
        rng,
        lang=lang,
        de="Bitte beobachten Sie bis zum nächsten Termin Luftnot, Belastbarkeit, Schwindel/Ohnmacht und mögliche Wassereinlagerungen.",
        en="Please monitor shortness of breath, exercise capacity, dizziness/fainting, and possible fluid retention until your next appointment.",
        zh="在下次就诊前，请留意呼吸困难、运动耐量、头晕/晕厥以及可能的水肿情况。",
    )
    lines.append(f"- {_observe}")
    lines.append("")

    levels_map: Dict[str, int] = (policy.get("levels") or {}) if isinstance(policy, dict) else {}
    eti = der.get(K_PH_ETIOLOGY) if isinstance(der, dict) else None
    eti_groups: List[int] = []
    if isinstance(eti, dict) and isinstance(eti.get(K_CANDIDATES), list):
        for c in (eti.get(K_CANDIDATES) or [])[:5]:
            try:
                eti_groups.append(int(c.get("group")))
            except (TypeError, ValueError) as exc:
                log_exception("RHK_REP_ETIOLOGY_GROUP_PARSE", "Etiology group id parsing failed.", exc)
                continue

    risk_cat_local = str(der.get(K_RISK_CATEGORY) or "").lower()
    lifestyle_allowed = not _patient_is_high_risk(risk_cat_local)

    if _patient_is_high_risk(risk_cat_local):
        _reassure = _patient_variant_or_fallback(
            "PX_REASSURE_HIGH_RISK",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Diese Befunde können belastend sein. Wir besprechen die nächsten Schritte mit Ihnen ruhig, transparent und ohne unnötige Dramatisierung.",
            en="These findings may be concerning. We will discuss the next steps with you calmly, transparently, and without unnecessary alarm.",
            zh="这些检查结果可能令人担忧。我们将与您平静、透明地讨论后续步骤，不做不必要的渲染。",
        )
        lines.append(_reassure)
        lines.append("")

    if all_mods:
        by_level: Dict[int, List[str]] = {1: [], 2: [], 3: []}
        for mid in all_mods:
            by_level[_patient_module_level(levels_map, mid)].append(mid)

        level_titles = {
            1: {"en": "Level I – priority recommendations", "zh": "Level I – 优先建议"}.get(lang, "Level I – prioritäre Empfehlungen"),
            2: {"en": "Level II – useful additions", "zh": "Level II – 有益的补充"}.get(lang, "Level II – sinnvolle Ergänzungen"),
            3: {"en": "Level III – optional (depending on context)", "zh": "Level III – 可选（视情况而定）"}.get(lang, "Level III – optional (je nach Kontext)"),
        }

        _steps_intro = _patient_variant_or_fallback(
            "PX_NEXT_STEPS_INTRO",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Die folgenden Schritte sind, je nach Gesamtbild, geplant oder sinnvoll. Falls verfügbar, steht darunter kurz, warum das in Ihrer Situation relevant sein kann.",
            en="The following steps are planned or recommended depending on the overall picture. Where available, a brief explanation is given below as to why this may be relevant in your situation.",
            zh="根据整体情况，以下步骤已计划或建议执行。如有相关信息，下方会简要说明为何该步骤可能与您的情况相关。",
        )
        lines.append(_steps_intro)
        lines.append("")

        for lvl in (1, 2, 3):
            mids = by_level.get(lvl) or []
            if not mids:
                continue
            lines.append(f"### {level_titles.get(lvl, f'Level {lvl}')}")
            for mid in mids:
                txt = str(module_summary.get(mid) or "").strip()
                if not txt:
                    try:
                        from rhk_textdb import ALL_BLOCKS as _ALL

                        blk = _ALL.get(mid)
                        if blk is not None:
                            txt = str(blk.title)
                    except (ImportError, ModuleNotFoundError, AttributeError, TypeError) as exc:
                        log_exception(
                            "RHK_REP_TEXTDB_TITLE_FALLBACK",
                            "Fallback module title lookup failed.",
                            exc,
                            module_id=mid,
                        )
                        txt = txt or mid
                reason = _patient_module_reason(
                    mid,
                    der=der,
                    ui=ui,
                    eti_groups=eti_groups,
                    pawp=pawp,
                    risk_cat_local=risk_cat_local,
                    congestion=congestion,
                    lang=lang,
                )
                if reason:
                    _why_lbl = {"en": "Why for you", "zh": "与您相关的原因"}.get(lang, "Warum bei Ihnen")
                    lines.append(f"- {txt}  \n  {_why_lbl}: {reason}.")
                else:
                    lines.append(f"- {txt}")
            lines.append("")
    else:
        t = _render_patient_text("PX_NEXT_STEPS", blocks, ctx, rng)
        if t:
            lines.append(t)
            lines.append("")

    lines.append(_tr("## Therapie und Medikamente", lang))
    if leading_action:
        _txt = {"en": f"The next therapeutic focus in your case is: {leading_action}.", "zh": f"您下一步的治疗重点是：{leading_action}。"}.get(lang, f"Der nächste therapeutische Schwerpunkt in Ihrem Fall ist: {leading_action}.")
        lines.append(_txt)

    eps = _get_ph_tx_episodes(ui, der)
    if eps:
        hist_eps = [e for e in eps if str(e.get(K_STATUS) or "").strip().lower() in ("früher", "abgesetzt", "pausiert")]
        cur_eps = [e for e in eps if str(e.get(K_STATUS) or "").strip().lower() == "aktuell"]
        planned_eps = [e for e in eps if str(e.get(K_STATUS) or "").strip().lower() == "geplant"]

        if cur_eps:
            lines.append(_tr("### Aktuell dokumentierte Therapie", lang))
            for e in cur_eps:
                b = _patient_episode_patient_bullet(e, lang=lang)
                if b:
                    lines.append(b)

        if planned_eps:
            lines.append(_tr("### Geplante/erwogene Therapie", lang))
            for e in planned_eps:
                b = _patient_episode_patient_bullet(e, lang=lang)
                if b:
                    lines.append(b)

        if hist_eps:
            lines.append(_tr("### Frühere oder pausierte Therapie", lang))
            for e in hist_eps:
                b = _patient_episode_patient_bullet(e, lang=lang)
                if b:
                    lines.append(b)
    else:
        lines.append(_patient_variant_or_fallback(
            "PX_NO_PH_MEDS_RECORDED",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Für diese Untersuchung sind keine strukturierten PH-Medikamente im Datensatz hinterlegt.",
            en="No structured PH medications are recorded in the dataset for this examination.",
            zh="本次检查的数据中未记录结构化的肺动脉高压药物信息。",
        ))

    # Sotatercept patient education block — show when sotatercept is among current/planned meds
    _all_drugs = " ".join(str(e.get("drug") or "") for e in eps).lower() if eps else ""
    if "sotatercept" in _all_drugs:
        t = _render_patient_text("PX_SOTATERCEPT_INFO", blocks, ctx, rng)
        if t:
            lines.append(t)

    _dose_note = _patient_variant_or_fallback(
        "PX_DOSE_NOTE",
        blocks,
        ctx,
        rng,
        lang=lang,
        de="Wenn Dosierungen in den Daten fehlen, werden sie im persönlichen Gespräch ergänzt. Bitte Medikamente nicht selbstständig ändern.",
        en="If dosing information is missing from the data, it will be clarified during your personal consultation. Please do not change medications on your own.",
        zh="如果数据中缺少剂量信息，将在面对面沟通中补充。请勿自行更改药物。",
    )
    lines.append(_dose_note)
    lines.append({"en": "Official drug information: [FDA](https://www.fda.gov) and [EMA](https://www.ema.europa.eu).", "zh": "官方药物信息：[BfArM](https://www.bfarm.de) 和 [BASG](https://www.basg.gv.at)。"}.get(lang, "Offizielle Informationen zu Arzneimitteln: [BfArM](https://www.bfarm.de) und [BASG](https://www.basg.gv.at)."))
    lines.append("")

    lines.append(_tr("## Alltag und Sicherheit", lang))
    syn = _patient_to_bool(ui.get("syncope"), {"ja", "yes", "true", "1", "gelegentlich", "manchmal"})
    diz = _patient_to_bool(ui.get("dizziness"), {"ja", "yes", "true", "1"})

    if syn:
        lines.append(_patient_variant_or_fallback(
            "PX_SYNCOPE_WARNING",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Da bei Ihnen Ohnmacht oder Beinahe-Ohnmacht angegeben wurde, ist das ein besonders wichtiges Warnsignal. Bitte melden Sie sich bei erneuten Episoden zeitnah.",
            en="Since fainting or near-fainting has been reported in your case, this is a particularly important warning sign. Please contact your care team promptly if episodes recur.",
            zh="由于您曾报告晕厥或接近晕厥的情况，这是一个特别重要的警示信号。如再次发生，请及时联系您的医疗团队。",
        ))
    elif diz:
        lines.append(_patient_variant_or_fallback(
            "PX_DIZZINESS_WARNING",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Da bei Ihnen Schwindel angegeben wurde, ist es wichtig, Belastung so zu dosieren, dass keine Beinahe-Ohnmacht auftritt. Bei deutlicher Zunahme bitte frühzeitig Rücksprache halten.",
            en="Since dizziness has been reported in your case, it is important to pace physical activity so that near-fainting does not occur. If symptoms increase noticeably, please consult your care team early.",
            zh="由于您曾报告头晕，重要的是控制活动量以避免接近晕厥。如果症状明显加重，请尽早联系您的医疗团队。",
        ))

    if congestion:
        lines.append(_patient_variant_or_fallback(
            "PX_CONGESTION_PRESENT",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Es gibt Hinweise auf Rückstau. Neue Schwellungen oder eine rasche Gewichtszunahme über wenige Tage sollten zeitnah besprochen werden.",
            en="There are signs of fluid congestion. New swelling or rapid weight gain over a few days should be discussed with your care team promptly.",
            zh="有液体淤积的迹象。如出现新的水肿或数日内体重快速增加，应及时与医疗团队沟通。",
        ))
    elif congestion_assessable:
        # Only emit the "no congestion currently" reassurance if RAP/IVC data
        # actually backs that statement. Otherwise the patient text would
        # falsely promise an absence we have not measured.
        lines.append(_patient_variant_or_fallback(
            "PX_CONGESTION_WATCH",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Wenn neue Schwellungen, rasche Gewichtszunahme oder deutlich zunehmende Luftnot auftreten, sollte das frühzeitig abgeklärt werden.",
            en="If new swelling, rapid weight gain, or noticeably increasing shortness of breath occur, this should be evaluated early.",
            zh="如出现新的水肿、体重快速增加或呼吸困难明显加重，应尽早就医检查。",
        ))
    # If neither RAP nor IVC information is available, we deliberately omit
    # the congestion paragraph entirely rather than asserting either side.

    if lifestyle_allowed:
        lines.append("")
        lines.append(_tr("### Evidenzbasierte Alltagshinweise", lang))
        _exercise1 = _patient_variant_or_fallback(
            "PX_EXERCISE_GUIDANCE",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Studien bei Patient*innen mit Lungengefäßerkrankungen zeigen, dass regelmäßige, moderate Bewegung die Belastbarkeit und Lebensqualität verbessern kann. Entscheidend ist nicht Tempo, sondern eine gut verträgliche Regelmäßigkeit.",
            en="Studies in patients with pulmonary vascular disease show that regular, moderate exercise can improve exercise capacity and quality of life. What matters is not speed, but consistent, well-tolerated regularity.",
            zh="针对肺血管疾病患者的研究表明，规律、适度的运动可以改善运动耐量和生活质量。重要的不是速度，而是持续、耐受良好的规律运动。",
        )
        lines.append(_exercise1)
        _exercise2 = {"en": "As a practical guide, a regular, well-tolerated walking or exercise program can be helpful (e.g., short sessions that you can manage without significant shortness of breath, dizziness, or chest pressure). If symptoms increase during exertion, a lower dose is often better tolerated than infrequent intense effort.", "zh": "作为日常参考，规律、耐受良好的步行或运动计划可能有所帮助（例如：能在不出现明显气短、头晕或胸闷的情况下完成的短时间运动）。如果运动时症状加重，较低强度往往比偶尔的高强度运动更容易耐受。"}.get(lang, "Als alltagsnahe Orientierung kann ein regelmäßiges, gut verträgliches Geh- oder Bewegungsprogramm hilfreich sein (z. B. kurze Einheiten, die Sie ohne deutliche Luftnot, Schwindel oder Brustdruck schaffen). Wenn Beschwerden unter Belastung zunehmen, ist eine geringere Dosis oft besser verträglich als ein seltener hoher Aufwand.")
        lines.append(_exercise2)
        if congestion:
            _fluid = {"en": "If there are signs of fluid congestion, individually adjusted fluid and salt intake can help. Specific targets will be determined during your consultation, as they depend on kidney function, medications, and your clinical course.", "zh": "如果有液体淤积的迹象，个性化调整饮水量和盐摄入量可能有所帮助。具体目标值将在就诊时确定，因为它们取决于肾功能、药物和临床病程。"}.get(lang, "Bei Hinweisen auf Rückstau kann eine individuell abgestimmte Trinkmenge und Salzaufnahme zur Entlastung beitragen. Konkrete Zielwerte werden im Gespräch festgelegt, weil sie von Nierenfunktion, Medikamenten und dem klinischen Verlauf abhängen.")
            lines.append(_fluid)
    else:
        lines.append("")
        lines.append(_tr("### Alltag bei erhöhtem Risiko", lang))
        lines.append(_patient_variant_or_fallback(
            "PX_LIFESTYLE_HIGH_RISK",
            blocks,
            ctx,
            rng,
            lang=lang,
            de="Bei höherem Risiko sollten körperliche Belastung, Trinkmenge und Tagesstruktur eng mit dem Behandlungsteam abgestimmt werden.",
            en="At higher risk, physical activity, fluid intake, and daily routine should be closely coordinated with your care team.",
            zh="风险较高时，体力活动、饮水量和日常作息应与您的医疗团队密切协调。",
        ))
        _basics = {"en": "Smoking cessation, balanced nutrition, vaccination status, and consistent medication adherence remain key pillars, but are individually adapted to your current condition.", "zh": "戒烟、均衡饮食、疫苗接种状态和坚持服药仍然是关键基础，但会根据您目前的状况个性化调整。"}.get(lang, "Rauchstopp, ausgewogene Ernährung, Impfstatus und konsequente Medikamenteneinnahme bleiben zentrale Bausteine, werden aber individuell auf Ihre aktuelle Stabilität angepasst.")
        lines.append(_basics)

    if warn_lines:
        lines.append("")
        _warn_lbl = {"en": "**Important notice:**", "zh": "**重要提示：**"}.get(lang, "**Wichtiger Hinweis:**")
        lines.append(_warn_lbl)
        for w in warn_lines:
            lines.append(f"- {w}")
    lines.append("")

    lines.append(_tr("## Ansprechpartner und Kontakt", lang))
    gp_contact = first_nonempty(ui, ["hausarzt", "hausarzt_name", "gp_name", "primary_care"])
    cardio_contact = first_nonempty(ui, ["kardiologe", "kardiologe_name", "cardio_contact", "ph_center_contact"])
    phone_contact = first_nonempty(ui, ["contact_phone", "phone", "telefon", "tel"])
    mail_contact = first_nonempty(ui, ["contact_mail", "email", "mail"])
    portal_contact = first_nonempty(ui, ["patient_portal", "portal_link", "portal"])

    if gp_contact:
        _lbl_gp = {"en": "Primary care physician", "zh": "家庭医生"}.get(lang, "Hausärztliche Ansprechperson")
        lines.append(f"- {_lbl_gp}: {gp_contact}")
    if cardio_contact:
        _lbl_cardio = {"en": "Cardiology/PH center", "zh": "心脏科/PH中心"}.get(lang, "Kardiologie/PH-Zentrum")
        lines.append(f"- {_lbl_cardio}: {cardio_contact}")
    if phone_contact:
        _lbl_phone = {"en": "Phone", "zh": "电话"}.get(lang, "Telefon")
        lines.append(f"- {_lbl_phone}: {phone_contact}")
    if mail_contact:
        _lbl_mail = {"en": "Email", "zh": "电子邮件"}.get(lang, "E-Mail")
        lines.append(f"- {_lbl_mail}: {mail_contact}")
    if portal_contact:
        _lbl_portal = {"en": "Patient portal", "zh": "患者门户"}.get(lang, "Patientenportal")
        lines.append(f"- {_lbl_portal}: {portal_contact}")

    if not (gp_contact or cardio_contact or phone_contact or mail_contact or portal_contact):
        _no_gp = {"en": "Primary care physician: schedule a follow-up discussion soon.", "zh": "家庭医生：尽快预约随访讨论。"}.get(lang, "Hausärztin/Hausarzt: zeitnahe Befundbesprechung vereinbaren.")
        _no_cardio = {"en": "Cardiology/PH team: contact on the same day if new warning signs appear.", "zh": "心脏科/PH团队：如出现新的警示信号，请当天联系。"}.get(lang, "Kardiologie/PH-Team: bei neuen Warnzeichen noch am selben Tag Rücksprache.")
        _emergency = {"en": "In case of acute severe shortness of breath, chest pain, or fainting, call emergency services (911) immediately.", "zh": "如出现急性严重呼吸困难、胸痛或晕厥，请立即拨打急救电话（120）。"}.get(lang, "Bei akuter schwerer Luftnot, Brustschmerz oder Ohnmacht sofort den Notruf 112 wählen.")
        lines.append(f"- {_no_gp}")
        lines.append(f"- {_no_cardio}")
        lines.append(f"- {_emergency}")
    lines.append("")

    lines.append(_tr("## Fragen für das Arztgespräch", lang))
    for q in _patient_conversation_questions(ui=ui, has_ph=has_ph, followup_timing_desc=followup_timing_desc, lang=lang):
        lines.append(f"- {q}")
    lines.append("")

    lines.append(_tr("## Wann sollten Sie sich sofort melden?", lang))
    t = _render_patient_text("PX_SAFETY_NET", blocks, ctx, rng)
    if t:
        lines.append(t)
    else:
        if lang == "en":
            lines.append("- severe or suddenly increasing shortness of breath at rest")
            lines.append("- chest pain or chest pressure")
            lines.append("- fainting or near-fainting")
            lines.append("- coughing up blood")
            lines.append("- rapid weight gain or severely increasing swelling")
        elif lang == "zh":
            lines.append("- 静息时严重或突然加重的呼吸困难")
            lines.append("- 胸痛或胸闷")
            lines.append("- 晕厥或接近晕厥")
            lines.append("- 咯血")
            lines.append("- 体重快速增加或严重加重的水肿")
        else:
            lines.append("- starke oder plötzlich zunehmende Luftnot in Ruhe")
            lines.append("- Brustschmerz/Brustdruck")
            lines.append("- Ohnmacht oder beinahe Ohnmacht")
            lines.append("- blutiger Auswurf/Husten von Blut")
            lines.append("- rasche Gewichtszunahme oder stark zunehmende Schwellungen")
    lines.append("")

    t = _render_patient_text("PX_DISCLAIMER", blocks, ctx, rng)
    if t:
        lines.append(t)


def _build_patient_short_report(case: CaseLike, *, lang: str = "de") -> str:
    """Compact patient report mode focused on key messages."""
    ui: CaseSection = case.get(K_UI, {}) or {}
    der: CaseSection = case.get(K_DERIVED, {}) or {}
    dec: CaseSection = case.get(K_DECISION, {}) or {}
    sc: CaseSection = case.get(K_SCORES, {}) or {}
    env: CaseSection = case.get(K_ENV, {}) or {}
    _blocks_short, _, _, glossary_db = _load_patient_textdb(lang=lang)
    glossary = _merge_patient_glossary(glossary_db)
    _ctx_short: Dict[str, Any] = {"name": _patient_name(ui)}
    _rng_short = random.Random(_stable_patient_seed(case))

    hemo_values = _patient_rest_hemo_values(der)
    mpap = hemo_values.get("mpap")
    pawp = hemo_values.get("pawp")
    pvr = hemo_values.get("pvr")
    ci = hemo_values.get("ci")
    has_ph = bool(mpap is not None and mpap > 20)
    hemo_cat = str(der.get("hemo_category") or "").strip().lower()

    bnp_kind = (ui.get("bnp_kind") or "BNP/NT-proBNP")
    bnp_val = _safe_float(ui.get("bnp_value"))
    esc4 = sc.get("esc_ers_4s")
    leading_action = _patient_norm(dec.get("leading_action") or "")
    reason_rhk = _patient_clean_choice(ui.get("ph_reason_rhk"))
    story = _patient_clean_choice(ui.get(K_STORY))
    followup_timing_desc = _patient_clean_choice(env.get("followup_timing_desc") or der.get("followup_timing_desc"))
    invasive_followup_desc = _patient_clean_choice(env.get("invasive_followup_desc") or der.get("invasive_followup_desc"))
    risk_cat_local = str(der.get(K_RISK_CATEGORY) or "").lower()
    risk_txt = _patient_risk_txt(der.get(K_RISK_CATEGORY), lang=lang)
    warn_lines = _patient_warn_lines(ui, lang=lang)

    lines: List[str] = []
    lines.append(_tr("# Kurzfassung zum Rechtsherzkatheter", lang))
    meta: List[str] = []
    pname = _patient_name(ui)
    if pname:
        meta.append(f"**Name:** {pname}")
    meta.append(f"**Datum:** {_dt.date.today().strftime('%d.%m.%Y')}")
    meta.append(f"**Version:** {APP_VERSION}")
    lines.append(" · ".join(meta))
    lines.append("")

    lines.append(_tr("## Anlass", lang))
    if reason_rhk and story:
        _txt = {"en": f"Reason per documentation: {reason_rhk}. Symptoms: {story}", "zh": f"根据文档记录的检查原因：{reason_rhk}。症状：{story}"}.get(lang, f"Anlass laut Dokumentation: {reason_rhk}. Beschwerden: {story}")
        lines.append(_txt)
    elif reason_rhk:
        _txt = {"en": f"Reason per documentation: {reason_rhk}.", "zh": f"根据文档记录的检查原因：{reason_rhk}。"}.get(lang, f"Anlass laut Dokumentation: {reason_rhk}.")
        lines.append(_txt)
    elif story:
        _txt = {"en": f"Documented symptoms: {story}", "zh": f"记录的症状：{story}"}.get(lang, f"Dokumentierte Beschwerden: {story}")
        lines.append(_txt)
    else:
        lines.append({"en": "No structured reason for the examination is currently recorded.", "zh": "目前未记录结构化的检查原因。"}.get(lang, "Ein strukturierter Anlass ist aktuell nicht hinterlegt."))
    lines.append("")

    comorb_line = _build_relevante_vorerkrankungen_line(ui)
    if comorb_line and comorb_line != "-":
        _comorb_prefix = {
            "en": "Relevant pre-existing conditions per documentation",
            "zh": "根据文档记录的相关既往病史",
        }.get(lang, "Relevante Vorerkrankungen laut Dokumentation")
        lines.append(f"{_comorb_prefix}: {comorb_line}")
        lines.append("")

    functional_context = _patient_functional_context_lines(ui, lang=lang)
    if functional_context:
        lines.append(_tr("## Persönliche Belastbarkeit im Alltag", lang))
        for item in functional_context[:4]:
            lines.append(f"- {item}")
        lines.append("")

    lines.append(_tr("## Kernbotschaft", lang))
    lines.append(_patient_overview_core_sentence(has_ph, mpap, lang=lang))
    lines.append(
        _patient_overview_clarity_sentence(
            has_ph=has_ph,
            hemo_cat=hemo_cat,
            mpap=mpap,
            pvr=pvr,
            pawp=pawp,
            lang=lang,
            blocks=_blocks_short,
            ctx=_ctx_short,
            rng=_rng_short,
        )
    )
    pattern_sentence = _patient_overview_pattern_sentence(has_ph, hemo_cat, pvr, pawp, lang=lang)
    if pattern_sentence:
        lines.append(pattern_sentence)
    bnp_sentence = _patient_overview_bnp_sentence(str(bnp_kind), bnp_val, ci, lang=lang)
    if bnp_sentence:
        lines.append(bnp_sentence)
    if esc4:
        _esc4_txt = {
            "en": f"The current ESC/ERS risk classification is {esc4}.",
            "zh": f"目前的ESC/ERS风险分级为{esc4}。",
        }.get(lang, f"Die ESC/ERS-Risikoeinstufung liegt aktuell bei {esc4}.")
        lines.append(_esc4_txt)
    if risk_txt:
        lines.append(risk_txt)
    if _patient_is_high_risk(risk_cat_local):
        _reassure = _patient_variant_or_fallback(
            "PX_REASSURE_HIGH_RISK",
            _blocks_short,
            _ctx_short,
            _rng_short,
            lang=lang,
            de="Diese Befunde können belastend sein. Wir gehen die nächsten Schritte mit Ihnen Schritt für Schritt und klar verständlich durch.",
            en="These findings may be concerning. We will guide you through the next steps clearly and step by step.",
            zh="这些检查结果可能令人担忧。我们将逐步清晰地引导您完成后续步骤。",
        )
        lines.append(_reassure)
    lines.append("")

    lines.append(_tr("## Nächste Schritte", lang))
    next_step = _patient_overview_next_step_sentence(der, leading_action, lang=lang)
    if next_step:
        lines.append(next_step)
    if followup_timing_desc:
        _followup_txt = {
            "en": f"Recommended clinical follow-up: in {followup_timing_desc}.",
            "zh": f"建议的临床随访时间：{followup_timing_desc}内。",
        }.get(lang, f"Empfohlene klinische Verlaufskontrolle: in {followup_timing_desc}.")
        lines.append(_followup_txt)
    else:
        _followup_default = {
            "en": "The timing of the next follow-up will be determined during the treatment discussion.",
            "zh": "下次随访的时间将在治疗讨论中确定。",
        }.get(lang, "Den Zeitpunkt der nächsten Kontrolle legen wir im Behandlungsgespräch fest.")
        lines.append(_followup_default)
    if has_ph and invasive_followup_desc:
        _inv_followup = {
            "en": f"If necessary: repeat right heart catheterization in {invasive_followup_desc}.",
            "zh": f"如有必要：在{invasive_followup_desc}内再次进行右心导管检查。",
        }.get(lang, f"Falls erforderlich: erneute Rechtsherzkatheter-Kontrolle in {invasive_followup_desc}.")
        lines.append(_inv_followup)
    lines.append("")

    lines.append(_tr("## Warnzeichen", lang))
    if warn_lines:
        for warn in warn_lines[:5]:
            lines.append(f"- {warn}")
    else:
        _warn_defaults = {
            "en": [
                "- significant or suddenly increasing shortness of breath",
                "- chest pain or chest pressure",
                "- fainting or near-fainting",
                "- rapid weight gain or new severe swelling",
            ],
            "zh": [
                "- 明显或突然加重的呼吸困难",
                "- 胸痛或胸闷",
                "- 晕厥或接近晕厥",
                "- 体重快速增加或出现新的严重水肿",
            ],
        }.get(lang, [
            "- deutliche oder plötzlich zunehmende Luftnot",
            "- Brustschmerz oder Brustdruck",
            "- Ohnmacht oder Beinahe-Ohnmacht",
            "- rasche Gewichtszunahme oder neue starke Schwellungen",
        ])
        for w in _warn_defaults:
            lines.append(w)
    lines.append("")
    _disclaimer = {
        "en": "Note: This summary supplements the medical report and does not replace a personal consultation with your doctor.",
        "zh": "提示：本摘要是对医学报告的补充，不能替代与医生的面对面沟通。",
    }.get(lang, "Hinweis: Diese Kurzfassung ergänzt den medizinischen Fachbericht und ersetzt nicht das persönliche Arztgespräch.")
    lines.append(_disclaimer)

    lines = _rewrite_patient_lines_for_lay_mode(lines, glossary, lang=lang)
    lines = _enforce_patient_layered_constraints(lines)
    # Short report is a 1-page take-home; 8 terms keeps the glossary scannable.
    _append_patient_glossary_section(lines, glossary, max_terms=8, lang=lang)
    out = "\n".join([ln.rstrip() for ln in lines]).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def build_patient_report(case: CaseLike, *, mode: Optional[str] = None, lang: str = "de") -> str:
    """Public entrypoint kept stable for UI/export callers."""
    return _build_patient_report_impl(case, mode=mode, lang=lang)


def _build_patient_report_impl(case: CaseLike, *, mode: Optional[str] = None, lang: str = "de") -> str:
    """Thin orchestration wrapper kept stable for callers."""
    return _build_patient_report_content(case, mode=mode, lang=lang)


def _build_patient_report_content(case: CaseLike, *, mode: Optional[str] = None, lang: str = "de") -> str:
    """Erstellt einen patientenfreundlichen Bericht (drucktauglich, mit echtem Mehrwert).

    Leitlinien für den Patientenbericht:
    - **Klarer Nutzen**: Was bedeutet der Befund konkret? Was passiert als Nächstes? Was kann ich selbst tun?
    - **Wenig Floskeln**: lieber kurze, konkrete Sätze.
    - **Keine verwirrenden Score-Labels** (z. B. "HFpEF-likely" wird übersetzt).
    - **Zahlen nur als Orientierung**: wenige Kernwerte + verständliche Einordnung.
    - **Dynamik**: Wenn ein Vor-RHK vorliegt → Verlauf (besser/stabil/schlechter) + Konsequenz.

    Hinweis: Dieser Text ersetzt kein ärztliches Gespräch.
    """

    report_mode = _resolve_patient_report_mode(case, mode)

    fp = _case_fingerprint(case)
    cache_kind = f"patient_report::{report_mode}::{lang}"
    cached = _cache_get(cache_kind, fp)
    if cached is not None:
        return cached

    if report_mode == PATIENT_REPORT_MODE_SHORT:
        out_short = _build_patient_short_report(case, lang=lang)
        _cache_set(cache_kind, fp, out_short)
        return out_short

    ui: CaseSection = case.get(K_UI, {}) or {}
    der: CaseSection = case.get(K_DERIVED, {}) or {}
    dec: CaseSection = case.get(K_DECISION, {}) or {}
    hf: CaseSection = case.get(K_HFPEF, {}) or {}
    sc: CaseSection = case.get(K_SCORES, {}) or {}
    env: CaseSection = case.get(K_ENV, {}) or {}

    blocks, bundles, module_summary, glossary_db = _load_patient_textdb(lang=lang)
    glossary = _merge_patient_glossary(glossary_db)
    rng = random.Random(_stable_patient_seed(case))

    # ------------------------------------------------------------------
    # Kernwerte (Ruhe)
    # ------------------------------------------------------------------
    hemo_values = _patient_rest_hemo_values(der)
    mpap = hemo_values.get("mpap")
    pawp = hemo_values.get("pawp")
    pvr = hemo_values.get("pvr")
    ci = hemo_values.get("ci")
    rap = hemo_values.get("rap")

    has_ph = bool(mpap is not None and mpap > 20)
    congestion = bool(der.get("congestion_likely"))
    congestion_assessable = bool(der.get("congestion_assessable"))
    hemo_cat = str(der.get("hemo_category") or "").strip().lower()

    # Grobe Einordnung (aus Regelwerk/Entscheidung)
    bundle = _patient_norm(dec.get(K_BUNDLE) or "")
    primary_dx = _patient_norm(dec.get("primary_dx") or "")
    leading_cause = _patient_norm(dec.get("leading_cause") or "")
    leading_action = _patient_norm(dec.get("leading_action") or "")

    # Patientenbericht-Archetypen (H1...H6) – Fokusverschiebung ohne Diagnostik
    archetype_id = str(der.get("p_archetype_id") or "H0").strip().upper()
    if not archetype_id:
        archetype_id = "H0"

    # ------------------------------------------------------------------
    # Vertikale Verfeinerung (Sub-Layer): Symptomprofil und Diskrepanzen
    # ------------------------------------------------------------------
    cause_patient = _patientize_cause_text(leading_cause or primary_dx)

    # Verlaufstrend (optional)
    trend_info = _compare_rhk_trend(ui, der)

    # Module: ausschließlich bewusst gewählte P-Module (Single Source of Truth)
    selected_mods = _normalize_module_ids(ui.get(K_MODULES) or [])

    policy = der.get("p_module_policy") or {}
    eff_policy = pmods_apply_overrides(policy, pmods_get_force_optional(ui))
    disabled_mods: Dict[str, str] = eff_policy.get("disabled") or {}
    allowed_order: List[str] = eff_policy.get("allowed") or list(_ALL_P_MODULE_IDS)

    all_mods = [m for m in selected_mods if m not in disabled_mods]

    order_index = {mid: i for i, mid in enumerate(allowed_order)}
    all_mods = sorted(all_mods, key=lambda m: order_index.get(m, 10_000))

    warn_lines = _patient_warn_lines(ui, lang=lang)
    hf_txt = _patient_hf_text(der, hf, lang=lang)

    # Risiko (vereinfachte Sprache)
    risk_txt = _patient_risk_txt(der.get(K_RISK_CATEGORY), lang=lang)

    # ESC/ERS Follow-up Risiko (4-Strata)
    esc4 = sc.get("esc_ers_4s")
    esc4_n = sc.get("esc_ers_4s_n")
    esc4_missing = sc.get("esc_ers_4s_missing") or []

    # BNP/NT-proBNP (patientenfreundliche Einordnung; keine harten Diagnosen)
    bnp_kind = (ui.get("bnp_kind") or "BNP/NT-proBNP")
    bnp_val = _safe_float(ui.get("bnp_value"))

    bio_qual = _patient_bio_qual(str(bnp_kind), bnp_val)

    # Kontextfelder für patientenzentrierte Struktur
    story = _patient_clean_choice(ui.get(K_STORY))
    reason_rhk = _patient_clean_choice(ui.get("ph_reason_rhk"))
    known_dx = _patient_clean_choice(ui.get("ph_known_dx"))
    known_subtype = _patient_clean_choice(ui.get("ph_known_subtype"))
    first_dx = _patient_clean_choice(ui.get("ph_first_dx"))
    sex_txt = _patient_clean_choice(ui.get("sex"))
    who_fc_txt = _patient_clean_choice(ui.get("who_fc"))
    followup_timing_desc = _patient_clean_choice(env.get("followup_timing_desc") or der.get("followup_timing_desc"))
    invasive_followup_desc = _patient_clean_choice(env.get("invasive_followup_desc") or der.get("invasive_followup_desc"))
    age_years = _safe_float(ui.get("age"))
    bmi_val = _safe_float(der.get("bmi"))


    # ------------------------------------------------------------------
    # Bericht zusammensetzen
    # ------------------------------------------------------------------
    lines: List[str] = []
    pname = _patient_name(ui)
    salutation = _patient_salutation(ui, rng, lang=lang)

    # Kontext für patientenfreundliche Textbausteine
    _age_bucket = "young" if (age_years and age_years < 40) else "elderly" if (age_years and age_years > 70) else "adult"
    _who_fc_raw = str(ui.get("who_fc") or "").strip()
    ctx = {
        "name": pname,
        "salutation": salutation,
        # v27.5: erweiterte Platzhalter für individuellere Textbausteine
        "age_context": (
            "Als jüngerer Patient" if _age_bucket == "young"
            else "In Ihrem Alter" if _age_bucket == "elderly"
            else ""
        ),
        "fc_context": (
            "Ihre aktuelle Belastbarkeit ist kaum eingeschränkt" if _who_fc_raw in ("I", "1")
            else "Ihre Belastbarkeit ist bei stärkerer Aktivität eingeschränkt" if _who_fc_raw in ("II", "2")
            else "Ihre Belastbarkeit ist bereits bei leichter Aktivität eingeschränkt" if _who_fc_raw in ("III", "3")
            else "Ihre Belastbarkeit ist auch in Ruhe eingeschränkt" if _who_fc_raw in ("IV", "4")
            else ""
        ),
        "trend_context": (
            "Im Vergleich zu Ihrer letzten Untersuchung" if bool(ui.get("prior_mpap") or ui.get("prior_pawp"))
            else "Dies ist Ihre erste Untersuchung dieser Art"
        ),
        "comorbidity_context": ", ".join(filter(None, [
            "Diabetes" if ui.get("diabetes") else None,
            "Lungenerkrankung" if (ui.get("copd") or ui.get("ct_emphysema")) else None,
            "Nierenerkrankung" if (der.get("renal_impairment") or (_safe_float(ui.get("krea")) and _safe_float(ui.get("krea")) > 1.5)) else None,
        ])) or "",
    }

    def _bundle_patient_blocks(bundle_id: str) -> List[str]:
        return _patient_bundle_patient_blocks(bundle_id, bundles, blocks)

    def _arch_text(kind: str) -> str:
        return _patient_arch_text(kind=kind, archetype_id=archetype_id, blocks=blocks, ctx=ctx, rng=rng)

    _append_patient_intro_sections(
        lines=lines,
        case=case,
        ui=ui,
        der=der,
        blocks=blocks,
        rng=rng,
        ctx=ctx,
        bundle=bundle,
        bundle_patient_blocks=_bundle_patient_blocks,
        reason_rhk=reason_rhk,
        story=story,
        has_ph=has_ph,
        mpap=mpap,
        hemo_cat=hemo_cat,
        pvr=pvr,
        pawp=pawp,
        ci=ci,
        bnp_kind=str(bnp_kind),
        bnp_val=bnp_val,
        bio_qual=bio_qual,
        esc4=esc4,
        leading_action=leading_action,
        known_dx=known_dx,
        known_subtype=known_subtype,
        first_dx=first_dx,
        primary_dx=primary_dx,
        cause_patient=cause_patient,
        lang=lang,
    )

    _append_patient_measurement_sections(
        lines=lines,
        ui=ui,
        der=der,
        blocks=blocks,
        rng=rng,
        ctx=ctx,
        has_ph=has_ph,
        mpap=mpap,
        pawp=pawp,
        pvr=pvr,
        ci=ci,
        rap=rap,
        hemo_cat=hemo_cat,
        bnp_kind=str(bnp_kind),
        bnp_val=bnp_val,
        bio_qual=bio_qual,
        hf_txt=hf_txt,
        leading_action=leading_action,
        esc4=esc4,
        esc4_n=esc4_n,
        esc4_missing=list(esc4_missing),
        risk_txt=risk_txt,
        age_years=age_years,
        sex_txt=sex_txt,
        who_fc_txt=who_fc_txt,
        bmi_val=bmi_val,
        trend_info=trend_info,
        arch_text=_arch_text,
        lang=lang,
    )

    _append_patient_followup_sections(
        lines=lines,
        ui=ui,
        der=der,
        blocks=blocks,
        rng=rng,
        ctx=ctx,
        module_summary=module_summary,
        glossary=glossary,
        all_mods=list(all_mods),
        policy=policy,
        has_ph=has_ph,
        followup_timing_desc=followup_timing_desc,
        invasive_followup_desc=invasive_followup_desc,
        leading_action=leading_action,
        congestion=congestion,
        congestion_assessable=congestion_assessable,
        pawp=pawp,
        warn_lines=list(warn_lines),
        first_nonempty=_patient_first_nonempty,
        lang=lang,
    )

    # Clean spacing
    lines = _rewrite_patient_lines_for_lay_mode(lines, glossary, lang=lang)
    lines = _enforce_patient_layered_constraints(lines)
    # 15 is a patient-friendly cap: dense enough to cover PH + comorbidity
    # language, short enough to scan in one breath. Was 40 (rarely hit in
    # practice — realistic max is ~10 — but the headroom allowed cruft.)
    _append_patient_glossary_section(lines, glossary, max_terms=15, lang=lang)
    out = "\n".join([ln.rstrip() for ln in lines]).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    _res = out
    _cache_set(cache_kind, fp, _res)
    return _res

