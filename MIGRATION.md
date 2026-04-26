# Split/Migration (v25.1)

Du hattest vorher nur `rhk_app_web_master.py` (sehr groß).
Jetzt ist die App funktional identisch, aber in Module aufgeteilt.

## Neue Dateien

- `rhk_base.py` – Utilities, Kalkulationen, Risk/Heuristiken, Rule-Engine, Text-Rendering, P-Module-Policy
- `rhk_case.py` – `build_case()` + Ableitungen/Render-Context/Dashboard-HTML
- `rhk_reports.py` – Arztbericht/Patientenbericht/Interner Bericht + JSON Export/Import
- `rhk_ui.py` – Gradio UI (CSS/JS, Callbacks, `build_demo()`)
- `rhk_app_web_master.py` – dünner Entry-Point (startet die Gradio-App direkt)

## Backward Compatibility

- Die alte Monolith-Datei liegt als `rhk_app_web_master_flat.py` bei.
- `rhk_textdb_patient_v7.py` wurde in v27.4.25 entfernt. Imports wurden auf `rhk_textdb_patient` umgeschrieben; die EN-/ZH-Varianten leben unter `rhk_textdb_patient_en.py` und `rhk_textdb_patient_zh.py`.

## Typischer Workflow beim Debugging

1. **UI/Tab/Buttons**: `rhk_ui.py`
2. **„Case-State stimmt nicht“ / Module landen im falschen Bericht**: `rhk_case.py`
3. **Text/Absätze im Bericht**: `rhk_reports.py` oder `rhk_textdb*.py`
4. **Regeln/Bundles**: `rhk_rules.yaml`
