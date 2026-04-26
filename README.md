# RHK Befundassistent – v1.1

## Aktueller Stand (v1.1)

- Modulare Architektur: UI, Case-Building, Reports und Rule-Engine sind in getrennten Modulen organisiert.
- Hosted-Mode unterstützt Gradio-Mount in FastAPI/uvicorn (für `0.0.0.0` Deployments ohne Share-Link-Zwang).
- Qualitäts-Gates: zentrale Tool-Konfiguration in `pyproject.toml`, plus CI-Workflow und pre-commit Hooks.

## Neu in v27.0.4

- Regressionfix Belastungshämodynamik: mPAP/CO Slope und PAWP/CO Slope werden wieder automatisch berechnet und erscheinen im Arztbefund.
- Patientenbericht ergänzt um patientengerechte Einordnung der Belastung (falls durchgeführt).

## Neu in v27.0.3

- Echo Import: Button "Echo Werte entfernen" (Undo). Entfernt die Import-Payloads und setzt nur die automatisch uebernommenen Felder zurueck (wenn unveraendert).
- DOCX Import (RHK): Undo-Buttons in der DOCX-Import-Uebersicht (aktueller RHK Import / Vor-RHK Import).
- DOCX Import (RHK): Import ueberschreibt keine manuellen Eingaben mehr. Nur leere Felder oder zuvor importierte, unveraenderte Felder werden aktualisiert.

## Neu in v27.0.2

- Echo Patientenbefund komplett neu gegliedert und deutlich erweitert: Kernaussage, Übersicht, erklärende Abschnitte, Verlauf, nächste Schritte, Safety Net und Messwerte Appendix.
- Echo Guideline Engine: min_abs und max_abs Cutoffs werden korrekt ausgewertet (wichtig für Strain Ampel und Trendlogik).

## Neu in v26.1.31

- Spiroergometrie / CPET unterhalb des Lungenfunktionsreiters integriert (inkl. Live-Risiko und Speicherung im Case).
- CPET Parameter in ESC/ERS Comprehensive Risk (wenn vorhanden) berücksichtigt.
- CPET Ausgabe in der Inputs-Zusammenfassung (Berichte) ergänzt.

## Neu in v26.1.30
- Pre-Cath Sticky Header: Kreatinin (Krea) mit Farbcodierung (primär eGFR, Fallback Kreatinin)
- Hämodynamik Sticky Header: Krea Chip entfernt (bleibt rein hämodynamisch)

## Neu in v26.1.28
- Erweiterung P Module: P26 Trinkmengenrestriktion, P27 kardiovaskuläre Risikofaktoren, P28 Gewichtsreduktion, P29 LTOT konsequent, P30 CT Befunde Konferenz mit Rückmeldung an PH Ambulanz
- P Modul Policy: automatische Priorisierung von P26 bei Stauung, P28 bei erhöhter BMI, P29 bei LTOT, P30 bei CT durchgeführt aber Kurzbefund ausstehend



## Neu in v26.1.27
- Fix: eGFR wird automatisch berechnet und im UI gesetzt (auch nach DOCX Import und Load)
- UX: Sticky Header Pre-Cath und Hämodynamik sehen identisch aus (gemeinsame CSS Basis)

## Neu in v26.1.26
- Neues UI Feld **Relevante Vorerkrankungen** direkt unter **Story / Kurz-Anamnese** (Klinik & Labor)
- Wird im Case gespeichert und in der Input Übersicht (Befund) mit ausgegeben

## Neu in v25.8.9
- Plausibilitätschecks mit Warnsystem (blockiert Befund nicht)
- Regelwerk-Explainability im Debug (ausgelöste Regeln + Fehler)
- YAML Snapshot Tests für Beispiel-Fälle (Regression-Schutz)
- UI-Rendering stabil: kein Viewport-Zwang standardmäßig (optional per ENV)

Eine **Gradio-Web-App** zur strukturierten Auswertung von Rechtsherzkatheter-Daten (RHK) inkl.:

- Hämodynamik-Berechnungen (z. B. Flüsse, Widerstände, Indizes)
- Risiko-/Einordnungslogik (z. B. ESC/ERS-Heuristik, REVEAL Lite 2 – soweit befüllt)
- **Deklaratives Regelwerk (YAML)** für Klassifikation/Bundles/Empfehlungen
- **Arztbericht** (Textbausteine) und **Patientenbericht** (verständliche Sprache, variantenreich)

## Was ist neu in v25.0?

### UX/Robustheit
- **Keine "More/..."-Overflows mehr:** Tabs und P-Module-Listen werden per CSS/JS **immer vollständig** angezeigt.
- **Procedere/Module landen deterministisch im Bericht:** Änderungen an P-Modulen oder Procedere-Freitext aktualisieren den Bericht sofort (ohne erneutes komplettes Re-Compute).

### Struktur
- **Patienten-Textbausteine:** `rhk_textdb_patient.py` (DE) ist die einzige Quelle für deutsche Patientenberichte; `rhk_textdb_patient_en.py` und `rhk_textdb_patient_zh.py` spiegeln die gleiche Block-ID-Struktur für EN/ZH.
- _Hinweis_: Der frühere Kompatibilitäts-Shim `rhk_textdb_patient_v7.py` wurde in v27.4.25 entfernt (einzige Quelle: `rhk_textdb_patient.py`).

> Hinweis: v25.0 ist primär ein UX-/Robustheits-Release; die klinische Logik entspricht inhaltlich weitgehend v24.16.

## Desktop-only (optional)

Diese App ist bewusst für **Desktop/Laptop** optimiert (viele Eingaben, breite Tabs).  
Optional kann auf **kleinen Bildschirmen** ein Overlay angezeigt werden, das die Nutzung blockiert.

**Konfiguration:**
- `RHK_DESKTOP_ONLY=1` aktiviert die Blockade (Standard: aus)
- `RHK_DESKTOP_MIN_WIDTH=1100` setzt die Mindestbreite (in px)
- `RHK_FORCE_DESKTOP_VIEWPORT=1` injiziert optional eine „Desktop-Viewport“-Breite (Default: aus)
- `RHK_DESKTOP_VIEWPORT_WIDTH=1200` setzt die Viewport-Breite (in px)
- `RHK_ENABLE_RUNTIME_GUARD=0` deaktiviert optional den `sitecustomize` Import-Hook (Default: aktiv)

---

## Installation

Getestete Python-Versionen: **3.11** und **3.13**.

```bash
pip install -r requirements.txt
```

`requirements.txt` enthält auch die Hosted-Mode Runtime-Abhängigkeiten (`fastapi`, `uvicorn`) für den ASGI-Mount in `rhk_app_web_master.py`.

## Start

```bash
python rhk_app_web_master.py
```

Danach läuft ein lokaler Webserver (Standard: `http://127.0.0.1:7860`).

Alternativ mit Direkt-Command (Wrapper-Skript):

```bash
./start_rhk.sh
```

## Gate Scope

Vor Release sollten alle Gates grün sein:

```bash
ruff check .
mypy
pytest -q --maxfail=1
```

Lokale Hook-Installation:

```bash
pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Versionierung

- Single Source of Truth: `APP_VERSION` in `rhk_base.py`
- Format: `vMAJOR.MINOR.PATCH` (z. B. `v1.1`)
- Versions-Update per Tool:

```bash
python tools/bump_version.py --note "Kurzbeschreibung"
```

## Repository Hygiene

Caches/Artefakte lokal aufräumen:

```bash
./tools/cleanup_artifacts.sh
```

Nur Vorschau (ohne Löschen):

```bash
./tools/cleanup_artifacts.sh --dry-run
```

Cleanup plus Release-Preflight:

```bash
./tools/cleanup_artifacts.sh --audit-release
```

## Quality Gates

- `ruff` prueft jetzt zusaetzlich Import-Hygiene (`I`) neben den bisherigen Runtime-Risk-Regeln.
- `mypy` prueft `check_untyped_defs` schrittweise fuer die neuen Service-/Helper-Module statt sofort repo-weit.
- `pytest` laeuft mit `pytest-cov`; die Coverage-Grenze liegt aktuell bei 75% auf dem definierten Quality-Core-Scope in `pyproject.toml`.

Lokal ausfuehren:

```bash
python -m ruff check .
python -m mypy
python -m pytest
```

## Release Hygiene

- Release-Whitelist und Root-Blocker sind zentral in `release_manifest.json` definiert.
- Der Release-Preflight bricht Builds ab, wenn nicht freigegebene Root-Artefakte gefunden werden.
- `Launcher/Launcher.py` und `standalone/RHK_Befundassistent.spec` verwenden dieselbe Manifest-Quelle.

Manueller Release-Audit:

```bash
python tools/release_audit.py
```

Strukturierte Ausgabe:

```bash
python tools/release_audit.py --json
```

## Datenschutz und Betrieb

- Deploy-Profile laufen jetzt zentral über `RHK_DEPLOY_PROFILE=offline|clinic|cloud`.
- `offline`: localhost-only, keine CDN-/Browser-Import-Features per Default, Exporte bevorzugt in `./exports`.
- `clinic`: localhost-only, Privacy-defaults aktiv, Export-/Temp-/Log-Dateien bevorzugt unter dem Runtime-Temp-Root statt im Projektbaum.
- `cloud`: Browser-PDF/OCR und gehostete Browser-Tools aktiv, Server-Upload standardmäßig aus (`RHK_ALLOW_SERVER_UPLOAD=0`), kein localhost-only Binding.
- Laufzeit-Retention ist per Profil definiert und bei Bedarf via `RHK_LOG_RETENTION_DAYS`, `RHK_EXPORT_RETENTION_DAYS` und `RHK_TEMP_RETENTION_DAYS` überschreibbar.
- Runtime-Verzeichnisse lassen sich bei Bedarf explizit setzen: `RHK_RUNTIME_ROOT_DIR`, `RHK_LOG_DIR`, `RHK_CASE_DIR`, `RHK_EXPORT_DIR`.
- Strukturierte Fehlerlogs redigieren Dateipfade, Dateinamen und ganze Case-/Import-Payloads zentral, damit keine PHI in Standard-Logs landet.

## Snapshot Tests (Regelwerk Regression)

Die Datei `tests/rules_snapshot.py` erzeugt/vergleicht Snapshots der Regelwerk-Outputs für definierte Beispiel-Fälle.

### Vergleich gegen bestehende Snapshots

```bash
python tests/rules_snapshot.py
```

### Snapshots aktualisieren (bewusst, nach Regeländerungen)

```bash
python tests/rules_snapshot.py --update
```

---

## Projektstruktur (modular)

Die Codebasis ist in fachliche Module aufgeteilt (kein einzelner Monolith):

| Datei | Zweck |
|---|---|
| `rhk_app_web_master.py` | Entry-Point und Launch-Strategie (lokal + Hosted/FastAPI/uvicorn) |
| `rhk_ui.py` | Gradio-UI Layout + Bindings |
| `rhk_ui_helpers.py` | UI-Hilfsfunktionen (Signaturen, Workflow-HTML, Lazy Imports) |
| `rhk_case.py` | Case-Building (Normalisierung, Ableitungen, Env) |
| `rhk_case_schema.py` | Typed Case-Schema (`TypedDict`) |
| `rhk_rule_engine.py` | Deklarative Rule-Engine (`Rule`, `Decision`, Safe-Eval, Rulebook-Laden) |
| `rhk_reports.py` | Report-Building (Arzt/Patient/Intern + Export-APIs) |
| `rhk_report_markdown.py` | Markdown/Word/DOCX-Konvertierung |
| `rhk_rules.yaml` | Regelwerk |
| `rhk_textdb*.py` | Textbaustein-Datenbanken |

Legacy-Duplikate sind archiviert unter `archive/legacy/` und nicht Teil der aktiven Laufzeit.

---

## Architektur in 60 Sekunden (Datenfluss)

1. **UI-Eingaben** → `ui` (Rohdaten)
2. **Ableitungen** → `derived` (Berechnungen, Plausibilität, Flags)
3. **Umgebung/Features** → `env` (bool/str-Features für Regelwerk)
4. **Regelengine (YAML)** → `decision` (Bundle `Kxx`, Empfehlungen, Hinweise)
5. **Reports**
   - Arztbericht: `rhk_textdb.py` + `decision`
   - Patientenbericht: `rhk_textdb_patient.py` + `decision` + Kontext

**Wichtig:** `rhk_rules.yaml` arbeitet nur mit **Keys**, die im Code in `env` gesetzt werden.  
Wenn du neue Regeln willst, musst du sicherstellen, dass der passende `env`-Key existiert.

---

## „Nur eine Datei ändern“ – genau so ist es gedacht

### 1) Du willst nur andere Empfehlungen / neue Klassifikation?
➡️ **Nur** `rhk_rules.yaml` anpassen.

Typische Aufgaben:
- neue Bundle-Regeln (Kxx)
- neue Trigger/Schwellen
- neue Textausgaben im Bereich Empfehlungen/Hinweise

### 2) Du willst nur die Arztbericht-Texte ändern?
➡️ **Nur** `rhk_textdb.py` anpassen.

Regel:
- Block-IDs möglichst **nicht umbenennen**, sonst greifen Zuordnungen nicht mehr.

### 3) Du willst nur den Patientenbericht weicher/variantenreicher machen?
➡️ **Nur** `rhk_textdb_patient.py` anpassen.

Regeln für Patienten-Texte:
- **keine Messzahlen** (keine mmHg, keine Liter/Min, keine Scores als Zahl)
- möglichst **keine Abkürzungen**
- lieber **Wahrscheinlichkeit/Einordnung** statt „definitiv“
- Variationen als mehrere `templates` pro Block

---

## Patientenbericht: wie die Variabilität funktioniert

- Die Bausteine sind in `PATIENT_BLOCKS` definiert.
- Die Zuordnung „Bundle → Bausteinliste“ steht in `PATIENT_BUNDLES`.
- Beim Erstellen wird pro Block **eine Template-Variante** gewählt.
- Die Wahl ist **deterministisch pro Fall** (Seed aus Kernmerkmalen), damit bei kleinen UI-Änderungen nicht alles komplett anders klingt.

Wenn du mehr Variation willst:
- mehr Varianten in `templates` ergänzen
- pro Bundle weitere passende Block-IDs hinzufügen
- optional: neue Block-IDs definieren (und im Bundle referenzieren)

---

## Regelwerk (YAML): Arbeitsweise & Leitplanken

Das Regelwerk ist absichtlich **deklarativ**. Es soll:
- schnell anpassbar sein
- für LLMs/Editoren gut wartbar sein
- ohne Codeänderung neue Bundles/Empfehlungen erlauben

**Leitplanke:** YAML sollte *keine* komplexe Logik „simulieren“.  
Komplexe Berechnungen gehören in den Code (→ `derived`/`env`), die Entscheidung dann ins YAML.

---

## Wartung durch zukünftige LLMs (bitte strikt befolgen)

Wenn du dieses Repo als LLM weiterentwickelst:

1. **Ändere nur die minimal notwendige Datei.**  
   - Texte? → `rhk_textdb*.py`  
   - Regeln? → `rhk_rules.yaml`  
   - UI/Berechnung? → `rhk_app_web_master.py`

2. **Keine Breaking Changes ohne Migrationslayer.**  
   - Keine Umbenennung von `PATIENT_BLOCK`-IDs oder Bundle-IDs (`Kxx`), außer du ergänzt Abwärtskompatibilität.

3. **Stabilität vor „Schönheit“.**  
   - Lieber kleine, nachvollziehbare Patches als Komplett-Rewrites.

4. **Regression-Checks vor Ausgabe:**
   - `python -m py_compile rhk_app_web_master.py`
   - App startet lokal (mindestens bis UI erscheint)
   - YAML lädt ohne Fehler
   - Patientenbericht enthält keine Zahlen/Abkürzungs-Orgie

5. **Dokumentiere jede Änderung am Ende dieser README unter „Changelog“.**

---

## Offene Punkte / Backlog (priorisiert)

### P0 – sinnvoll als Nächstes
- **Validierung & Plausibilitätswarnungen verbessern** (z. B. inkonsistente Flüsse, unrealistische Bereiche)
- **Automatische Testfälle** (kleine JSON-Fälle + erwartete Bundle-Ausgabe)
- **Erweiterte „Wenn unklar“-Strategie**: Wenn Daten fehlen → gezielte Nachfragen/ToDo-Liste im Arztbericht

### P1 – Qualitätsverbesserungen
- **PDF-Export** (Arztbericht + Patientenbericht als PDF)
- **Mehrsprachigkeit** (Patientenbericht optional EN)
- **Feingranulare Schweregrade** in Textbausteinen (mild/moderat/schwer)

### P2 – Komfort/Produkt
- **Preset-Profile** (z. B. „Kontrollmessung“, „CTEPH-Verdacht“, „HFpEF-Verdacht“)
- **Anonymisierung** beim Export (Patientendaten entfernen)
- **Audit-Log**: Welche Regeln haben zum Bundle geführt (Explainability)

---

## Changelog

- **Unreleased**
  - Neuer Arbeitsmodus `Einfach`/`Experte`: Standard-Workflow fokussiert auf Import -> Pflichtfelder -> Review -> Export.
  - Legacy-/Admin-Werkzeuge standardmäßig ausgeblendet (JSON/Verlauf/Beispiele/Debug/Legacy-PH-Therapie) und nur noch im Expertenmodus sichtbar.
  - Monolith-Schnitt weitergeführt: neue Service-Layer für `case`, `generate`, `save/load`, `import`, `export` sowie versionierte Persistenz-Migrationen am Rand.
  - Release-Hygiene gehärtet: manifestgetriebene Allowlist fuer Bundle-Dateien, Root-Blocker-Audit und Builder-Preflight vor Packaging.
  - Quality Gates vertieft: `pytest-cov` mit 75%-Gate auf dem Quality-Core-Scope, `ruff` inklusive Import-Hygiene und `mypy` `check_untyped_defs` fuer ausgewaehlte Service-/Helper-Module.

- **v26.1.29 (2026-01-07)**
  - Hämodynamik Sticky Header zeigt jetzt Kreatinin (Krea) mit Farbcodierung (eGFR-basiert, Fallback Kreatinin)

- **v23.2**
  - Desktop-only Enforcement (Overlay + Mobile-Viewport-Tag)
  - README stark erweitert: „nur eine Datei ändern“, LLM-Wartungsregeln, Backlog

- **v23.6**
  - „ESC/ERS umfassend“ entfernt (nicht mehr angezeigt)
  - Light-Theme-Härtung (auch bei System-Darkmode): Eingabefelder konsequent hell
  - Labor/Lungenfunktion in der Befundübersicht als Fließtext; BNP/NT-proBNP separat dargestellt
  - Adaptionstyp-Logik angepasst: ΔsPAP < 30 mmHg → Hinweis auf heterometrischen Adaptionstyp
  - Zusatzmodule erweitert: P14–P25


## v27.0.5 (2026-01-07)
- Copy-Export: Reihenfolge/Format an Screenshot-Stil angepasst (Klinik/Labor/Bildgebung/Lufu/CPET → Beurteilung → Empfehlung/Procedere).
- Clipboard Copy: robust gegen Gradio-Rerenders (Handler wird neu installiert via MutationObserver).


## v27.0.6 (2026-01-07)
- FIX: Copy-Buttons wieder funktionsfähig: JS Copy-Observer/Handler Fehler (duplizierte/rekursive installCopyObserver Definition) behoben.


## v27.0.7 (2026-01-07)
- Neuer Download Button: Arztbericht kann zusätzlich als fertig formatiertes DOCX heruntergeladen werden (Copy Layout, in-app Bericht unverändert).
- Copy/Download Button Row kompakter gestaltet.


## v27.0.8 (2026-01-07)
- DOCX Export erweitert: Im selben Dokument werden nun unterhalb des Arztberichts zusätzlich der Patientenbericht Rechtsherzkatheter und der Patientenbericht Echokardiographie angehängt (jeweils mit Seitenumbruch).
- DOCX Layout Engine erweitert: Überschriften (##/###) und explizite Seitenumbrüche ([[PAGEBREAK]]) werden unterstützt.


## v27.2 (2026-01-07)

- UX: Hauptreiter jetzt sticky und als segmented control deutlich sichtbarer.
- Tab Unterzeile (Kontext) + Statuspunkte pro Tab (zeigt befüllte Tabs).
- Dashboard: Verlaufskarte für RHK Ruhe (Vorbefund vs aktuell, Trendpfeile).

## v27.2.2 (2026-01-08)

- Klinik & Labor: Allergien-Workflow ergänzt (Checkbox → Mehrfachauswahl; „sonstiges“ → Freitext).
- Pre-Cath Sticky Header: Allergien-Chip immer sichtbar (bei fehlenden Angaben: „Allergien: –“), Anzeige neben Nierenfunktion.
- Fix: Antikoagulation „pausiert“ wird beim Laden/Speichern nicht mehr zurückgesetzt.

## v27.1 (2026-01-07)
- UI Redesign: Modernes, helles Card-based Dashboard Layout (Cards statt unstrukturierter Blöcke), bessere visuelle Gruppierung zur schnelleren Orientierung.
- Accordions und Eingabebereiche sind optisch vereinheitlicht (Card Look, konsistente Radien, reduzierte visuelle Unruhe).
