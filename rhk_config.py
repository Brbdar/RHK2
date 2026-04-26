"""Central configuration for the RHK Befundassistent.

Single source of truth for thresholds, severity rankings, color codes,
validation tokens, and other constants used across multiple modules.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Severity Rankings
# ---------------------------------------------------------------------------
#: Numeric rank per severity code for comparison (higher = worse).
SEV_RANK: dict[str, int] = {"": 0, "g": 1, "y": 2, "r": 3}

#: Background CSS per severity code (traffic-light colouring).
SEV_BG: dict[str, str] = {
    "g": "background:rgba(34,197,94,.14);",
    "y": "background:rgba(234,179,8,.16);",
    "r": "background:rgba(239,68,68,.14);",
    "":  "",
}

#: Left-border CSS per severity code.
SEV_BORDER: dict[str, str] = {
    "g": "border-left:6px solid rgba(34,197,94,.45);",
    "y": "border-left:6px solid rgba(234,179,8,.55);",
    "r": "border-left:6px solid rgba(239,68,68,.45);",
    "":  "border-left:6px solid rgba(0,0,0,.04);",
}

# ---------------------------------------------------------------------------
# Warning Levels
# ---------------------------------------------------------------------------
#: Numeric ordering for triage / warning levels.
WARNING_LEVEL_ORDER: dict[str, int] = {"hint": 1, "important": 2, "critical": 3}

#: Human-readable German labels for warning levels.
WARNING_LEVEL_LABEL: dict[str, str] = {"hint": "Hinweis", "important": "Wichtig", "critical": "Kritisch"}

# ---------------------------------------------------------------------------
# Validation Tokens
# ---------------------------------------------------------------------------
#: String tokens accepted as boolean *true* from UI / imports.
TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "t", "yes", "y", "ja", "j", "on"})

#: String tokens accepted as boolean *false* from UI / imports.
FALSE_TOKENS: frozenset[str] = frozenset({"0", "false", "f", "no", "n", "nein", "off", ""})

#: String tokens treated as *missing* for numeric fields.
MISSING_TOKENS: frozenset[str] = frozenset({"–", "-", "na", "n/a", "nan", "none", "null"})

# ---------------------------------------------------------------------------
# Field Labels (summary UI)
# ---------------------------------------------------------------------------
#: Short German labels for hemodynamic / saturation field keys.
FIELD_LABELS: dict[str, str] = {
    "spap_rest": "sPAP",
    "dpap_rest": "dPAP",
    "mpap_rest": "mPAP",
    "pawp_rest": "PAWP",
    "pawp_pre": "PAWP pre",
    "pawp_post": "PAWP post",
    "co_rest": "CO",
    "ci_rest": "CI",
    "pvr_rest": "PVR",
    "sat_svc": "SVC-Sättigung",
    "sat_ra": "RA-Sättigung",
    "sat_rv": "RV-Sättigung",
    "sat_pa": "PA-Sättigung",
    "sat_ao": "Ao-Sättigung",
    "on_nitrates": "Nitrate/NO-Donor",
    "pde5_hardship": "PDE-5 Härtefall",
    "pde5_hardship_desc": "Härtefall-Begründung",
}

# ---------------------------------------------------------------------------
# Exercise Patterns
# ---------------------------------------------------------------------------
#: Human-readable German descriptions for exercise-response pattern codes.
EXERCISE_PATTERN_LABELS: dict[str, str] = {
    # legacy
    "normal_pattern": "Regelhafte Druck und Flussreaktion unter Belastung",
    "precap_pattern": "Auffällige pulmonalvaskuläre Reaktion unter Belastung (Heuristik)",
    "postcap_pattern": "Auffällige Druck und Flussreaktion mit linksatrialer Komponente (Heuristik)",
    "left_pressure_pattern": "Auffällige linksatriale Druckreaktion unter Belastung (Heuristik)",
    # new (two-point QC-gated)
    "exercise_2pt_normal": "unauffällige Druck und Flussantwort (Slopes im Normbereich)",
    "exercise_2pt_pv_dominant": "pulmonalvaskulär dominierte Druckantwort (ΔmPAP/ΔCO und ΔTPG/ΔCO erhöht bei unauffälliger ΔPAWP/ΔCO)",
    "exercise_2pt_la_dominant": "linksatrial dominierte Druckantwort (ΔPAWP/ΔCO erhöht bei niedrigem ΔTPG/ΔCO)",
    "exercise_2pt_mixed": "kombinierte Druckantwort (ΔPAWP/ΔCO und ΔTPG/ΔCO erhöht)",
    "exercise_2pt_unclear": "nicht eindeutig oder QC limitiert",
}
