"""Single source of truth for clinical hemodynamic thresholds.

Every constant in this module is anchored to a guideline or peer-reviewed
publication. When a number is changed, the citation **must** be updated
together with it. New thresholds without a citation are not allowed.

This module is intentionally dependency-free so it can be imported anywhere
(rule engine, case builder, deep interpretation, tests).

Primary references
------------------
[ESC/ERS 2022]
    Humbert M, Kovacs G, Hoeper MM, et al. 2022 ESC/ERS Guidelines for the
    diagnosis and treatment of pulmonary hypertension.
    Eur Heart J 2022; 43(38):3618–3731. doi:10.1093/eurheartj/ehac237.

[WSPH 2018]
    Simonneau G, Montani D, Celermajer DS, et al. Haemodynamic definitions
    and updated clinical classification of pulmonary hypertension.
    Eur Respir J 2019; 53(1):1801913. doi:10.1183/13993003.01913-2018.

[REVEAL 2.0]
    Benza RL, Gomberg-Maitland M, Elliott CG, et al. Predicting Survival in
    Patients With Pulmonary Arterial Hypertension: The REVEAL Risk Score
    Calculator 2.0. Chest 2019; 156(2):323–337.

[H2FPEF]
    Reddy YNV, Carter RE, Obokata M, et al. A Simple, Evidence-Based Approach
    to Help Guide Diagnosis of Heart Failure With Preserved Ejection Fraction.
    Circulation 2018; 138(9):861–870.

[Vanderpool 2015]
    Vanderpool RR, Pinsky MR, Naeije R, et al. RV-pulmonary arterial coupling
    predicts outcome in patients referred for pulmonary hypertension.
    Heart 2015; 101(1):37–43.
"""
from __future__ import annotations

from typing import Final

# =============================================================================
# 1. PH definition (ESC/ERS 2022 § 4.3 / WSPH 2018)
# =============================================================================

#: mPAP cutoff for pulmonary hypertension at rest, mmHg.
#: Lowered from > 25 mmHg in the 2022 ESC/ERS guideline. [ESC/ERS 2022 § 4.3]
PH_MPAP_REST: Final[float] = 20.0

#: PVR cutoff separating pre-/post-capillary pure forms, Wood Units.
#: Lowered from > 3 WU. [ESC/ERS 2022 § 4.3 / WSPH 2018 update]
PH_PVR_PRECAPILLARY: Final[float] = 2.0

#: PAWP cutoff for post-capillary involvement, mmHg.
#: [ESC/ERS 2022 § 4.3, WSPH 2018 hemodynamic definitions]
PH_PAWP_POSTCAPILLARY: Final[float] = 15.0

# =============================================================================
# 2. ESC/ERS 2022 Risk Strata (Table 16 in the guideline)
# =============================================================================
# 4-strata risk: low / intermediate-low / intermediate-high / high.
# Numbers below describe the cut-points between adjacent strata; "high-risk
# threshold" is the worst-tier cutoff.

#: RAP, mmHg. Low/intermediate boundary at 8, intermediate/high at 14.
RAP_INTERMEDIATE: Final[float] = 8.0
RAP_HIGH_RISK: Final[float] = 14.0

#: CI, L/min/m². Intermediate-low/-high boundary 2.5; high-risk threshold 2.0.
CI_INTERMEDIATE_HIGH: Final[float] = 2.5
CI_HIGH_RISK: Final[float] = 2.0

#: SVI, mL/m². Intermediate-high/high-risk threshold 31.
SVI_HIGH_RISK: Final[float] = 31.0

#: TAPSE/sPAP coupling ratio, mm/mmHg. [ESC/ERS 2022 Table 16]
TAPSE_SPAP_LOW_RISK: Final[float] = 0.32
TAPSE_SPAP_HIGH_RISK: Final[float] = 0.19

# =============================================================================
# 3. Narrative cutoffs (used by clinical-text generation)
# =============================================================================
# These thresholds are slightly more permissive than the strict guideline
# strata because they drive narrative description ("RAP elevated as a sign
# of right-sided filling pressure increase") rather than risk classification.

#: RAP, mmHg. At/above this we describe central venous congestion in prose.
#: Halfway between the intermediate-low (8) and high-risk (14) boundaries —
#: matches the ESC/ERS intermediate-risk midpoint.
RAP_CONGEST_NARRATIVE: Final[float] = 10.0

#: RAP, mmHg. RV failure / massive congestion narrative.
#: Set to ESC/ERS 2022 high-risk RAP cutoff + 1 (>14 mmHg) → ≥ 15.
RAP_SEVERE_NARRATIVE: Final[float] = 15.0

#: PAWP, mmHg. Threshold above which the local IVC/heuristic flags
#: "congestion likely". Same as PH definition cutoff (PH_PAWP_POSTCAPILLARY)
#: but exposed separately for clarity in volume-status logic.
PAWP_CONGEST_NARRATIVE: Final[float] = 15.0

# =============================================================================
# 4. Mechanistic markers
# =============================================================================

#: DPG (diastolic pressure gradient), mmHg. Historic CpcPH supportive marker.
#: ESC/ERS 2022 explicitly removed DPG as a definitional criterion for CpcPH;
#: the current CpcPH definition uses ONLY mPAP > 20 + PAWP > 15 + PVR > 2 WU
#: (Table 5). DPG ≥ 7 mmHg is therefore retained here only as a *narrative*
#: remodelling hint when reading individual cases — never as a classifier.
#: When in doubt, follow ESC/ERS 2022 Table 5 (PVR-only criterion).
#: [WSPH 2018; ESC/ERS 2022 § 3.1, Table 5]
DPG_HIGH: Final[float] = 7.0

#: PAC (pulmonary arterial compliance), mL/mmHg. Below this value indicates
#: reduced compliance / increased pulsatile RV afterload. [ESC/ERS 2022,
#: discussed in § hemodynamic phenotyping]
PAC_LOW: Final[float] = 2.0

#: RC-time (= PVR · PAC), seconds. Below 0.4 s → compliance loss dominates
#: resistance — classic uncoupling marker.
#: [Vanderpool 2015; Tedford RJ et al. Circ Heart Fail 2018; 11(7):e004576]
RC_TIME_LOW: Final[float] = 0.4

#: Group 3 PH severity boundary, Wood Units. PVR > 5 WU → severe Group 3 PH;
#: PVR ≤ 5 WU → non-severe. Replaces the prior mPAP/CI definition from the
#: 2015 guideline. [ESC/ERS 2022 § 8.3 / Figure 12]
PVR_GROUP3_SEVERE: Final[float] = 5.0

#: ASD/VSD/PDA shunt-closure decision thresholds, Wood Units.
#: ESC/ERS 2022 Recommendation Table 6 / WSPH 2018:
#: PVR < 3 → closure recommended; 3–5 → closure should be considered;
#: > 5 → closure may be considered only if PVR drops < 5 with PAH therapy.
SHUNT_PVR_CLOSE_OK: Final[float] = 3.0
SHUNT_PVR_CLOSE_BORDERLINE: Final[float] = 5.0

# =============================================================================
# 4b. Exercise PH (ESC/ERS 2022 § 5.1.12.3, re-introduced)
# =============================================================================

#: mPAP/CO slope between rest and exercise, mmHg/(L/min). Above this →
#: exercise PH per ESC/ERS 2022 Table 5 / Section 5.1.12.3.
EXERCISE_MPAP_CO_SLOPE: Final[float] = 3.0

#: PAWP/CO slope between rest and exercise, mmHg/(L/min). Above this →
#: cardiac exercise limitation / HFpEF-suspect, especially with resting
#: PAWP 12-15 mmHg. [ESC/ERS 2022 § 5.1.12.3]
EXERCISE_PAWP_CO_SLOPE: Final[float] = 2.0

#: Fluid challenge: PAWP rise to ≥ this value (mmHg) is suggestive of HFpEF
#: after rapid 500 mL bolus over 5-10 min. [ESC/ERS 2022 § 5.1.12.4]
FLUID_CHALLENGE_PAWP_HFPEF: Final[float] = 18.0

# =============================================================================
# 4c. Vasoreactivity testing responder criterion
# =============================================================================
# [ESC/ERS 2022 Recommendation Table 8; idem for paediatric Section 14]

#: Required mPAP drop from baseline to be considered a responder (mmHg).
VASO_RESPONDER_MPAP_DROP: Final[float] = 10.0

#: Required absolute mPAP after vasodilator challenge (mmHg).
VASO_RESPONDER_MPAP_ABS: Final[float] = 40.0

# =============================================================================
# 5. Echo / RV strain markers
# =============================================================================

#: S'/RAAI ratio. Internal warning cutoff for RA strain interpretation.
#: NOT in any major guideline; based on internal validation cohort at
#: PH Zentrum Gießen. Treat as house convention, not as definitional.
SPRIME_RAAI_CUTOFF: Final[float] = 0.81

# =============================================================================
# 6. Safety / QC buffers
# =============================================================================

#: PAWP must not exceed dPAP by more than this margin (mmHg). Above →
#: physically implausible "overwedging" artifact. House QC convention; no
#: formal guideline cutoff exists.
OVERWEDGE_BUFFER: Final[float] = 2.0

# =============================================================================
# 7. Tracking / repeat-RHK noise gates (house convention)
# =============================================================================
# These are NOT guideline values. They are derived from the test-retest
# variability of repeated RHKs in the PH Zentrum Gießen cohort and are used
# only to suppress "responder"-grade narratives for changes that fall inside
# measurement noise. Edit only with backing from a re-analysis of that data.

NOISE_REL_PVR: Final[float] = 0.15   # 15 % relative change to call it real
NOISE_ABS_PVR: Final[float] = 0.5    # WU
NOISE_REL_MPAP: Final[float] = 0.10
NOISE_ABS_MPAP: Final[float] = 3.0   # mmHg
NOISE_REL_PAWP: Final[float] = 0.20
NOISE_ABS_PAWP: Final[float] = 3.0   # mmHg
NOISE_REL_CI: Final[float] = 0.15
NOISE_ABS_CI: Final[float] = 0.3     # L/min/m²
