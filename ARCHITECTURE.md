# RHK Befundassistent — Architecture Notes

This file documents the **module groups** in the codebase and a **proposed
package layout** for a future flat→subpackage migration. The migration is
not yet executed; doing it well requires updating every import site,
re-running the full test suite, and validating that the OFFLINE/Launcher
spec files still resolve modules. That belongs in a dedicated PR, not a
mixed-in cleanup.

Until the migration happens, this file functions as a **navigation map** —
when you wonder "where do I add X?", look at the group below.

## Current state

74 `rhk_*.py` files live flat in the project root. There are existing
sub-folders for orthogonal concerns:

```
RHK-BEfunder/
├── archive/                  # legacy snapshots (read-only)
├── assets/                   # static UI assets
├── cpet_wizard/              # CPET teaching materials (markdown)
├── data/                     # shared data files
├── exports/                  # report output dir (gitignored)
├── Launcher/                 # JupyterLab launcher
├── OFFLINE/                  # offline build kits
├── run_logs/                 # runtime logs (gitignored)
├── standalone/               # standalone build configs
├── tests/                    # pytest suite
├── tools/                    # dev tools (lint, audit, version, scripts)
└── rhk_*.py                  # ← 74 files at the root, flat
```

## Module groups (proposed `core/`, `clinical/`, ...)

Until the actual move happens, treat the groups below as the mental model
for where things belong. New files should be named to fit one of these
groups so the eventual migration is mechanical.

### 1. `core/` — Domain-neutral primitives

Foundation modules with no clinical knowledge baked in:

| File | Role |
|------|------|
| `rhk_base.py` | Shared dataclasses, `SafeDict`, rule loading, render block |
| `rhk_case.py` | Case builder; central computation pipeline |
| `rhk_case_schema.py` | Typed dict / dataclass shapes for cases |
| `rhk_case_migrations.py` | Backwards-compat case shape upgrades |
| `rhk_config.py` | Runtime config |
| `rhk_logging.py` | Structured logging, redaction, correlation IDs |
| `rhk_runtime_policy.py` | Feature flags / runtime toggles |
| `rhk_thresholds.py` | **Single source of truth for clinical cutoffs** |
| `rhk_validation.py` | Input parsing/sanitization, `safe_float`, `parse_boolish` |

### 2. `clinical/` — Clinical decision logic

| File | Role |
|------|------|
| `rhk_echo_guidelines.py` | ESC/ERS echo probability scoring |
| `rhk_followup.py` | Follow-up timing logic |
| `rhk_hemo_deep_interpretation.py` | Deep hemodynamic phenotyping |
| `rhk_interpretation.py` | Headline interpretation paragraph |
| `rhk_medcalc.py` | BSA/BMI/derived indices |
| `rhk_ph_tx.py` | PH therapy logic |
| `rhk_pmodules.py` | P-module triggering |
| `rhk_rule_engine.py` | YAML expression evaluator |
| `rhk_study_checks.py` | Study eligibility / inclusion checks |

### 3. `reports/` — Report generation

| File | Role |
|------|------|
| `rhk_doctor_report_service.py` | Service entry for doctor report |
| `rhk_echo_report_doctor.py` | Echo-only doctor report |
| `rhk_echo_report_patient.py` | Echo-only patient report |
| `rhk_hemo_deep_interpretation.py` | (also clinical/, dual-classified) |
| `rhk_report_db.py` | Report-side derived data lookup |
| `rhk_report_markdown.py` | Markdown rendering helpers |
| `rhk_reports.py` | **Main report builder — 9 000 LoC, planned split** |

> `rhk_reports.py` is targeted for splitting into `reports/doctor.py`,
> `reports/patient.py`, `reports/measure_text.py`, `reports/filters.py`,
> and `reports/follow_up.py`.
>
> **Progress (2026-04):**
>   - `rhk_report_filters.py` extracted (markdown helpers, narrative
>     sanitisers, congestion-aware filtering — ~260 LoC).
>   - `rhk_report_cache.py` extracted (LRU cache + fingerprint —
>     ~110 LoC, isolates the privacy-sensitive in-memory cache policy).
>   - `rhk_reports.py` shrank from 9 003 → 8 700 LoC.
>
> Remaining extraction targets in priority order:
>   1. `rhk_report_summary.py` — the `_summary_*` family (~800 LoC).
>   2. `rhk_report_doctor.py` — the `_doctor_tpl_*` family (~1 600 LoC).
>   3. `rhk_report_patient.py` — the `_patient_*` family (~2 400 LoC).
>
> Each extraction must be a single dedicated PR, run the full test suite,
> and import back the moved symbols so external callers don't break.

### 4. `textdb/` — Text databases (template content)

| File | Role |
|------|------|
| `rhk_textdb.py` | Doctor-facing block templates (B…/K…/BZ…) |
| `rhk_textdb_patient.py` | Patient-facing blocks (DE) |
| `rhk_textdb_patient_en.py` | Patient blocks (EN) |
| `rhk_textdb_patient_zh.py` | Patient blocks (ZH) |
| `rhk_textdb_echo_patient.py` | Echo-specific patient blocks |

### 5. `ui/` — Gradio surface

| File | Role |
|------|------|
| `rhk_app_web_master.py` | Main entry point (boots Gradio) |
| `rhk_launch.py` | Launcher wrapper (port handling) |
| `rhk_standalone_entry.py` | Frozen-bundle entry |
| `rhk_ui*.py` | Tabs, bindings, helpers (~20 files) |

### 6. `services/` — Cross-cutting services

| File | Role |
|------|------|
| `rhk_case_service.py` | Case build orchestration |
| `rhk_export_service.py` | Export pipeline |
| `rhk_export_paths.py` | Output-path policy |
| `rhk_generate_service.py` | Generate (build) orchestration |
| `rhk_persistence_service.py` | Save/load persistence |
| `rhk_release_manifest.py` | Release artifact metadata |

### 7. `import_/` — Inbound data adapters

| File | Role |
|------|------|
| `rhk_echo_pdf_import.py` | Echo PDF parsing |
| `rhk_import_docx.py` | DOCX RHK parsing |
| `rhk_import_merge.py` | Merge imported with existing case |
| `rhk_import_service.py` | Import orchestration |
| `rhk_pdf_prerhk.py` | Pre-RHK PDF parsing |

### 8. `cpet/` — CPET / spiro

| File | Role |
|------|------|
| `spiro_logic.py` | CPET calculations |
| `spiro_predicted.py` | Predicted-value formulas |
| `spiro_teaching.py` | Patient-facing teaching text |

### 9. `i18n/` — Translations

| File | Role |
|------|------|
| `rhk_i18n.py` | EN/ZH translation tables; helper functions |

### 10. `viz/` — Visualisation

| File | Role |
|------|------|
| `rhk_viz.py` | Chart helpers |

## Migration plan (when ready)

A single-PR migration with this checklist:

1. Create the subpackage skeleton with empty `__init__.py` files.
2. `git mv` files into their target package.
3. Run a global find-and-replace for `from rhk_X import` → `from core.X import`
   etc. Keep old import paths working with a thin `rhk_X.py` shim that
   `from core.X import *` for one release cycle.
4. Update `pyproject.toml`, `ruff.toml`, `mypy.ini`, `pytest.ini` import
   roots.
5. Update `OFFLINE/`, `standalone/RHK_Befundassistent.spec`, and
   `Launcher/Launcher.py` to reference the new module paths.
6. Run `pytest` and the full UI smoke flow.
7. Remove the shims in the next cycle.

**Why not done now**: the change touches every single file in the codebase
and is high-risk under OneDrive-managed paths (sync conflicts during the
move). Schedule it as a dedicated session with no other concurrent work.
