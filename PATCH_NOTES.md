## v1.1

- **Versionsschema neu** — Rückgesetzt auf semantische Versionierung `vMAJOR.MINOR[.PATCH]` ab v1.1.
  Auto-Increment bei jedem Update via `tools/bump_version.py --note "..."`.
- **P-Module-System überarbeitet.**
  - TextBlock-Metadata neu: `level_default`, `clinical_group`, `required_context` für saubere Trennung zwischen Inhalt, Priorität und Pflicht-Kontextvariablen.
  - P03–P06 (PDE5i/ERA/Riociguat/Eskalation) von Stub-Platzhaltern auf vollständige Baseline-Prosa mit Monitoring, Kontraindikationen und Querverweisen erweitert.
  - Duplikat-Paare disambiguiert: P02 (aktive Dekongestion) vs P40 (Euvolämie-Maintenance), P13 (Diagnostik) vs P42 (Substitution), P29 (LTOT-Indikation) vs P48 (LTOT-Reevaluation), P11/P49/P51 mit expliziten Scope-Hinweisen.
  - P32-Meta-Regel (`R_CONTEXT_ADD_P32`): ersetzt 7 duplizierte `add_modules: [P32]` Einträge aus Einzelregeln.
  - Laienbefund: alle P-Module (P01–P52) in DE/EN/ZH mit patientengerechter Übersetzung verfügbar.
- **Arztbericht strukturell überarbeitet** — Zusammenfassung/Epikrise-Block am Berichtsanfang, saubere H2/H3-Hierarchie, Procedere-Refactor mit drei getrennten Sub-Sections.
- **Tello-Lab-Design-Adaption** — Blau-Palette, Inter-Typografie, Pill-Tabs mit Gradient-Underline, Glass-Cards, radiale Hintergrund-Glows.

## v27.4.23 (pre-rebase)

- Fix: Übergabe von Browser-Text an Gradio über stabile elem_id Root-IDs der versteckten Textfelder (Echo PDF/OCR, aktuell/vor).
- Ursache: aria-label basierte Selektion war offline/auf Render/Gradio-Versionen nicht stabil.

## v27.4.22
- Fix: Echo Screenshot/PDF Text konnte in einigen Gradio-Versionen nicht in Hidden-Textboxes geschrieben werden (aria-label mismatch). Jetzt robust via elem_id (Root-ID) + Fallback.

## v27.4.21

- Bugfix Echo Import: `extract_echo_from_text()` war durch falsche Key-Referenzen defekt (OCR/PDF-Text-Pfade konnten Werte nicht übernehmen). Jetzt identisch zum PDF-Pfad: stabil, kein Crash, korrektes Mapping auf UI-Keys.

## v27.4.20

- Echo Import: "Screenshot aus Zwischenablage" (Ctrl+V/Snipping Tool) ohne Upload. OCR läuft vollständig im Browser; Server erhält weiterhin nur extrahierten Text.
- UI: Import bleibt kompakt, nur ein zusätzlicher Button im bestehenden Import-Header.

## v27.4.17

- Echo Import: Screenshot Import jetzt auch online nutzbar (Browser OCR via tesseract.js, PHI bleibt im Browser). Ergebnisse fließen wie beim PDF Import in Vor und Aktuell Echo und überschreiben keine manuellen Felder.
- Stabilität: sitecustomize Import Hook deaktiviert Gradio Analytics Summary (verhindert pandas/pyarrow Imports und NumPy ABI Crashes auf Anaconda).

## v27.4.11

- Bugfix UI: Spiroergometrie/CPET Bereich visuell stabilisiert (kein Pulsieren/Transparenz bei Live-Updates).
- CSS: neue Klasse `rhk-cpet-card` erzwingt volle Opazität und deaktiviert Transition/Animation innerhalb des CPET Cards.

## v27.4.9

- Spiro-Logic: Feldtooltips (Hover/Info) in allen CPET Wizard Modulen inkl. 9-Felder Grafik.
- Spiro-Logic: Befundausgabe in drei Ebenen: Kurzheadline (Briefkopf), klinische Zusammenfassung, technische Details (Appendix).
- Spiro-Logic: Übernahmebutton übernimmt Kurzheadline + klinische Zusammenfassung (nur wenn Zieltext leer).
- Spiro-Logic: Missing-Guard: physiologisch unmögliche 0-Werte werden als "nicht erhoben" behandelt.

## v27.4.4

- Bugfix: LSB Chip wird nun im Pre-Cath Sticky Header korrekt angezeigt (nur wenn aktiv) und steht direkt neben Krea.
- Tooltip: klinische Warnung zu LSB (Risiko katheterinduziertes RSB → kompletter AV-Block) plus optionale Begründung.

## v27.4.3

- Sticky Header: LSB Chip bekommt jetzt einen Tooltip mit klinischer Sicherheitswarnung (Risiko kompletten AV-Blocks bei katheterinduziertem RSB) und optionaler Begründung aus dem Feld "LSB: Begründung".
- UI: Neues Feld "LSB: Begründung" (nur sichtbar wenn LSB aktiv) und wird in Pre-Cath Header + Arztbericht übernommen.

# Patch 27.3.9 (2026-01-08)

Änderungen

1) Echo Expertenbericht (Arztbericht) neu strukturiert und deutlich erweitert: Executive Summary, Nachlast/PH-Surrogate, RV-Funktion und RV-PA-Kopplung, Remodeling, Stauungszeichen, Linksherz-Kontext, leitlinienorientierte Einordnung, Verlauf (meaningful change).
2) Fix: korrigiert fehlerhafte Ellipsen/Trunkierungen in der bisherigen Extended-Report-Implementierung (Stabilität).

# Patch 27.3.6 (2026-01-08)

Änderungen

1) Cards Mode – Sektionen als "Header Card" (nicht sticky)
- Klinik & Labor: Allgemeines/Anamnese/Vorerkrankungen, Funktion/Symptome, Labor, Medikation als eigenständige Cards mit klarer Kopfzeile.
- Bildgebung & Echo/CMR: Thorax-Bildgebung, Echokardiographie, MRT/CMR als eigenständige Cards.
- Lungenfunktion: Lungenfunktion und Spiroergometrie/CPET als eigenständige Cards.

2) Fortschritt je Sektion (minimalistisch)
- In jeder Sektion wird oben rechts ein kompakter Ausfüllgrad angezeigt (x/y + dezenter Progress-Bar).
- Optional-Sektionen (z.B. CMR/CPET/Lufu ohne "durchgeführt") zeigen "optional" statt 0/0.

3) Tabs – Button wird nicht mehr von der Linie "geschnitten"
- Divider unterhalb der Tab-Pills (Pseudo-Element), zusätzlicher Abstand nach unten.

---

# Patch 27.3.5 (2026-01-08)

Änderungen

1) Arztbericht – neue automatische Interpretation unter „Beurteilung“
- Unterhalb der Beurteilung wird nun ein eigenständiger Absatz „Interpretation“ erzeugt.
- Narrative, guideline-aligned Einordnung der Ruhehämodynamik (keine PH vs. präkapillär vs. isoliert postkapillär vs. kombiniert post/präkapillär vs. unklassifizierte Konstellation).
- Integration von Provokationstests: Belastung (mPAP/CO Slope, PAWP/CO Slope) und Volumenchallenge (PAWP Endpunkt ≥18 mmHg) inkl. Hinweis auf limitierte Datenlage bei PAH.
- Zusätzlich werden zentrale pathologische Signale aus der numerischen Zusammenfassung (z.B. RAP, CI, PAC/PP) kurz verbalisiert.

2) Procedere – neue P Module
- P31 „Risikofaktoren Management“ ergänzt.
- P32 „Ausschluss einer pulmonalen Hypertonie“ ergänzt.

---

# Patch 27.2.2 (2026-01-08)

Änderungen

1) Allergien (Klinik & Labor)
- Neues Allergien-Workflow direkt unter „Relevante Vorerkrankungen“: Checkbox „Allergien“ aktiviert Mehrfachauswahl (Pflaster, Heparin, Lidocain, sonstiges).
- Bei Auswahl „sonstiges“ erscheint ein zusätzliches Freitextfeld „Allergien – Sonstiges“.

2) Pre-Cath Sticky Header
- Neuer Allergien-Chip ist **immer sichtbar** (bei fehlenden Angaben: „Allergien: –“) und wird neben der Nierenfunktion angezeigt.

3) Bugfix Antikoagulation
- „Antikoagulation pausiert“ wird nicht mehr beim Laden/Speichern still zurückgesetzt (Status „ja“ erhält den gespeicherten Checkbox-Wert).

---

# Patch 27.2 (2026-01-07)

Änderungen

1) Anwenderfreundlichkeit – Orientierung
- Hauptreiter als sticky segmented control (hell, klar, deutlich sichtbar) inklusive dynamischer Unterzeile je Tab.
- Kleine Statuspunkte pro Tab: gefüllt, sobald in dem Tab mindestens ein Feld belegt ist.

2) Verlauf – RHK (Dashboard)
- Neue Verlaufskarte im Dashboard: Vergleich Vorbefund vs aktuell für die wichtigsten Ruheparameter (mPAP, PAWP, PVR, CI, RAP) inkl. Trendpfeilen.
- Anzeige nur wenn ein Vor RHK mit Datum und mindestens einem Vorwert hinterlegt ist.

---

# Patch 27.0.8 (2026-01-07)

Änderungen

1) DOCX Download (Arztbericht)
- Der DOCX Export enthält nun zusätzlich den Patientenbericht Rechtsherzkatheter sowie den Patientenbericht Echokardiographie (jeweils mit Seitenumbruch).
- Überschriftenstruktur (Arztbericht, Patientenberichte) für eine Word kompatible, professionellere Gliederung.

2) DOCX Layout Engine
- Unterstützt nun Überschriften (##/###) sowie explizite Seitenumbrüche ([[PAGEBREAK]]).

---

# Patch 27.0.4 (2026-01-07)

Änderungen

1) Belastungshämodynamik (RHK)
- Regression behoben: mPAP/CO Slope und PAWP/CO Slope werden wieder robust berechnet (auch bei kleinen Rundungsdifferenzen) und im Arztbefund sowie in der strukturierten RHK Sektion angezeigt.
- Korrektur der dynamischen Befundzeilen: ΔsPAP und peak CI greifen wieder auf die richtigen Derived Keys zu.

2) Patientenbericht (RHK)
- Bei durchgeführter Belastung wird die Belastungseinordnung jetzt auch patientengerecht im Kurzfazit erläutert (inklusive Slopes und Belastungsmuster, sofern vorhanden).

---

# Patch 27.0.2 (2026-01-07)

Änderungen

1) Echo Patientenbericht
- Komplett neu gegliedert: Kernaussage, Übersicht, erklärende Abschnitte, Verlauf, nächste Schritte, Safety Net.
- Zahlenblock nur noch als Appendix "Messwerte (für Unterlagen)" (platzsparend, aber vollständig).
- Einordnung mit drei Dimensionen (rechte Pumpfunktion, Druckzeichen im Lungenkreislauf, Stauungszeichen) als klare Übersicht.

2) Echo Guideline Engine
- Cutoffs mit min_abs und max_abs werden korrekt ausgewertet (wichtig für Strain Ampel und Trendlogik).

---

# Patch 26.1.31 (2026-01-07)

Änderungen

1) Spiroergometrie / CPET
- Neuer CPET Abschnitt unterhalb des Lungenfunktionsreiters.
- Live-Zusammenfassung mit ESC/ERS CPET 3-Strata (Peak VO2 + VE/VCO2 slope) und 4-Strata CPET Score (Peak VO2 + VE/VCO2 slope + Peak O2-Puls % Soll).
- CPET Felder werden vollständig im Case gespeichert.

2) Risikostratifizierung
- CPET Parameter werden in der ESC/ERS Comprehensive Risk Berechnung berücksichtigt, sofern vorhanden.

3) Bericht
- Inputs-Zusammenfassung ergänzt um Abschnitt Spiroergometrie / CPET.

---

# Patch 26.1.30 (2026-01-07)

Änderungen

1) Pre-Cath Sticky Header
- Kreatinin (Krea) wird im Pre-Cath Safety Sticky Header angezeigt (nicht im Hämodynamik Sticky Header)
- Farbcodierung primär anhand eGFR (>= 60 grün, 30 bis 59 orange, < 30 rot), Fallback anhand Kreatinin
- Tooltip zeigt eGFR, sofern berechenbar

2) Hämodynamik Sticky Header
- Entfernt: Krea Chip (auf Wunsch, damit der Hämodynamik Header rein hämodynamisch bleibt)

---

# Patch 26.1.29 (2026-01-07)

Änderungen

1. RHK Sticky Header
- Kreatinin (Krea) wird im Hämodynamik Sticky Header angezeigt
- Farbcodierung primär anhand eGFR (>= 60 grün, 30 bis 59 orange, < 30 rot), Fallback anhand Kreatinin

---

# Patch 26.1.28 (2026-01-07)

Änderungen

1. Erweiterung P Module
- Neu: P26 Trinkmengenrestriktion und konsequentes Volumenmanagement
- Neu: P27 Minimierung kardiovaskulärer Risikofaktoren
- Neu: P28 Gewichtsreduktion und metabolische Optimierung
- Neu: P29 LTOT konsequent anwenden und Verlauf kontrollieren
- Neu: P30 CT Befunde interdisziplinär vorstellen und Rückmeldung an PH Ambulanz

2. P Modul Priorisierung
- P26 wird bei Stauungszeichen oder erhöhtem RAP automatisch als Level I priorisiert
- P28 wird bei erhöhter BMI priorisiert (Level I ab BMI ≥ 30, sonst Level II ab BMI ≥ 27)
- P29 wird bei dokumentierter LTOT automatisch als Level I priorisiert
- P30 wird bei CT durchgeführt und Kurzbefund ausstehend automatisch als Level I priorisiert

---

# Patch 26.1.27 (2026-01-07)

Änderungen

1. eGFR Automatik
- eGFR wird automatisch berechnet, sobald Kreatinin, Alter und Geschlecht verfügbar sind
- Nach DOCX Import und Load wird eGFR zuverlässig gesetzt (zusätzlicher Sync Schritt)

2. Sticky Header Konsistenz
- Pre-Cath Sticky Header und Hämodynamik Sticky Header sind visuell identisch (gemeinsame CSS Basis)
- Pre-Cath Placeholder nutzt denselben Renderer wie die Ampel

---

# Patch 26.1.26 (2026-01-07)

Änderungen

1. Klinik UI
- Neues Freitextfeld "Relevante Vorerkrankungen" direkt unter "Story / Kurz-Anamnese" (Tab Klinik & Labor)

2. Befund Input Übersicht
- Klinik Abschnitt gibt "Relevante Vorerkrankungen" aus (wenn befüllt)

---

# Patch 26.1.22

Änderungen

1. requirements.txt
- Ergänzt: Pillow und pytesseract (für Screenshot OCR Import)
- Ergänzt: pypdf und PyPDF2 (für PDF Textlayer Import)

2. Echo UI
- Speichert Vor Echo Werte zusätzlich als unsichtbares JSON Feld (echo_prev_json)
  Dadurch kann der Bericht später die Dynamik (Verlauf) beschreiben.
- Vor Echo und aktuelles Echo bleiben weiterhin unabhängig voneinander importierbar.

3. Echo Berichte
- Echo Expertenbericht (extended) ist jetzt Fließtext ohne Listen.
- Echo Patientenbericht ist erweitert (mehr Werte, Stauungszeichen, Strain, TAPSE zu sPAP, Notch, Perikard).
- Wenn Vor Echo Werte vorhanden sind, wird ein Verlauf Abschnitt erzeugt.

Hinweis OCR
- pytesseract benötigt eine lokale Tesseract Installation.
  Windows: tesseract.exe installieren und ggf. in PATH aufnehmen oder den Pfad in der App setzen.



## v27.0.5 (2026-01-07)
- FIX: Arztbericht kopieren funktioniert auch nach erneutem Render/State-Update zuverlässig (robuster JS-Handler).
- IMPROVE: Copy/Word-Export Struktur und Reihenfolge wie gewünscht (inkl. CPET Abschnitt).


## v27.0.6 (2026-01-07)
- FIX: Copy-Buttons wieder funktionsfähig: JS Copy-Observer/Handler Fehler (rekursive/duplizierte installCopyObserver Definition) behoben.


## v27.0.7 (2026-01-07)
- FEATURE: Arztbericht zusätzlich als DOCX herunterladen (fertig formatiert; Copy Layout; in-app Bericht unverändert).
- UI: Copy/Download Button Row kompakter (kleinere Buttons).


## v27.0.8 (2026-01-07)
- FEATURE: DOCX Download enthält zusätzlich angehängt: Patientenbericht RHK und Patientenbericht Echo (jeweils mit Seitenumbruch).


## v27.1 (2026-01-07)
- UI Redesign: Modernes, helles Card-based Dashboard Layout für bessere Orientierung (Cards/Accordions im einheitlichen Card Look, reduzierte visuelle Unruhe).

## v27.2.1 (2026-01-08)
- Clinic/Labor, Imaging, Lufu/CPET sections are now card-grouped for better scanability.
- DOCX export uses DownloadButton; removed large empty file widget.


## v27.3.3 (2026-01-08)
- FEATURE: Volumenchallenge Endpunkt leitlinienbasiert ergänzt: absolute PAWP-Antwort (PAWP post ≥18 mmHg) als Hinweis auf okkulte LV-Diastolikstörung/HFpEF (mit Hinweis auf begrenzte Validierung).
- IMPROVE: Arztbericht – „Hämodynamische Zusatzinterpretation“ ergänzt: relevante Auffälligkeiten aus PP/PAC/TPG/DPG/CI/RAP sowie Belastungs-Slopes werden kurz als Text verbalisiert, damit Zahlen nicht „stehen bleiben“.
- FEATURE: DOCX Export zusätzlich als „lokales Speichern“ (Ordner frei wählbar) – Workaround für Klinik-Policies/Protected-View bei Browser-Downloads.


## v27.4.1
- Release-Hygiene: Entfernt __pycache__ und Untitled.ipynb
- Tests: Snapshot-Regression für Regelwerk (tests/rules_snapshot.py)
- Sicherheit: Kontraindikations-Guard Nitrate/NO-Donor + PDE-5-Hemmer

## v27.4.2 (2026-01-09)
- Risiko: Test Guard gegen tote Inputs (tests/test_risk_input_coverage.py). Riskorelevante Eingaben müssen mindestens einen Score beeinflussen.
- Therapie: Kontraindikation PDE 5 Hemmer plus Riociguat ergänzt.
- Therapie: Sotatercept Gruppenguard (nur PAH Gruppe 1) plus PDE 5 außerhalb Gruppe 1 nur mit Härtefall Dokumentation.
- EKG: Hinweis wenn EKG nicht dokumentiert plus Tag bei dokumentierten Rechtsherzbelastungszeichen.
- Pre Cath Safety: LSB Checkbox plus Warn Chip im Sticky Header nur wenn aktiv.
- Medikation: Nitrate NO Donor als Sicherheitsabfrage plus PDE 5 Härtefall Begründung im Tab Medikation.
- Reports: Arztbericht erweitert um EKG Angaben LSB Nitrate und Therapie Verlauf Felder.

## v27.4.6 (2026-01-09)
- CPET: Neuer Spiro-Logic Wizard als deterministisches Expertensystem mit Modul 1 bis 4, Live Plausibilitätschecks, edukativen Erklärungen und automatisch generiertem Befundtext.
- CPET: Wizard fragt zusätzliche Parameter ab (HF Prozent Soll, RR Peak, PETCO2 Ruhe und Peak, Atemreserve, O2 Puls Slope).
- Reports: Optionaler Abschnitt "Spiro-Logic Interpretation" im Arztbericht (Checkbox).
- Stabilität: Übernahme des Spiro-Logic Textes in den CPET Kommentar nur wenn das Feld leer ist.

## v27.4.7 (2026-01-09)
- CPET: Neues Modul "9 Felder Grafik" im Spiro-Logic Wizard mit kurvenbasierten Pattern Entscheidungen (VT1, RCP, EOV, Flow Volume Loop, VO2 Work Muster, Ventilatorische Äquivalente).
- CPET: Live Edukation und Nachfragen für die 9 Felder Interpretation.
- Reports: 9 Felder Grafik Befunde werden in den Spiro-Logic Befundtext übernommen (wenn dokumentiert).

## v27.4.9 (2026-01-09)
- CPET: Spiro-Logic erweitert um leitliniennahe Pflichtbausteine für eine vollständige ärztliche CPET Befundung.
- Neu: Modul 0 Testqualität/Validität (Abbruchgrund, Borg, Maximalitätskriterien, Safety Stop).
- Neu: Modul 5 Mechanik (V'E Peak, MVV, V'E/MVV, berechnete Atemreserve) als objektiver Nachweis einer ventilatorischen Limitation.
- Neu: Modul 6 Gasaustausch (SpO2 Ruhe/Peak/Nadir, ΔSpO2, O2 Gabe) inkl. Desaturation Red Flags.
- Neu: Modul 7 Sicherheit (RR Ruhe/Peak, hypertensive Antwort, Hypotonie, Arrhythmie, ST/T, Symptome) – dokumentiert sicherheitslimitierte Tests.
- Neu: Modul 8 Limitationstyp/Next Steps mit deterministischer Klassifikation, leitliniennahen Empfehlungen und optionalem ärztlichen Override inkl. Begründung.
- Reports: Spiro-Logic Befundtext strukturiert erweitert (Qualität, Kernergebnisse, Mechanik, SpO2/O2, Sicherheit, 9 Felder, Limitation/Next Steps).

## v27.4.9

- Spiro-Logic: Tooltips (Hover/Info) an allen CPET Wizard Feldern inkl. 9-Felder Grafik.
- Spiro-Logic: Befundtext in drei Ebenen (Kurzheadline, klinische Zusammenfassung, technische Details).
- Spiro-Logic: Übernahmebutton übernimmt Kurzheadline + klinische Zusammenfassung (nur wenn Zieltext leer).
- Spiro-Logic: 0-Werte werden als fehlend behandelt (Missing-Guard), um irreführende Texte zu verhindern.

## v27.4.10 (2026-01-09)
- Fix: Gradio Start-Crash behoben, wenn UI-Helfer `add()` mit `info=` aufgerufen wird (Tooltips). `add()` akzeptiert jetzt `info` und setzt es sicher auf dem Component.

## v27.4.12
- Arztbericht: neues Muster-Layout (wie befundmuster.docx) mit fester Gliederung, deutlich weniger Redundanz.
- Spiroergometrie/CPET im Arztbericht: nur Kurzheadline + klinische Zusammenfassung (arztadressiert), keine technischen Doppellungen.
- DOCX Export: Download-Workflow stabilisiert (Button erzeugt DOCX, Datei wird als Download-Link ausgegeben); Export nutzt Muster-Layout.
- DOCX Generator: Markdown-Bullet-Listen unterstützen jetzt verschachtelte Ebenen (List Bullet 2/3).

## v27.4.13
- Fix: Belastungshämodynamik/Provokation/Volumenchallenge werden nur übernommen, wenn das jeweilige Modul als durchgeführt markiert ist (Checkbox). Bei vorhandenen Belastungswerten ohne aktiviertes Modul wird ein Hinweis ausgegeben.
- Fix: Stufenoxymetrie wird nur bewertet, wenn mindestens 4 von 6 Sättigungswerten vorliegen.
- Fix: Empfehlungstexte mit Transplantationsbezug werden bei Alter ≥70 Jahre unterdrückt.
- Fix: Residualvolumen-Hinweis korrigiert (Units-Mismatch): Bewertung nur bei deutlich erhöhtem RV (% Soll) und passender Konstellation.
- Fix: Arztbericht enthält im Abschnitt „Beurteilung“ wieder eine kompakte numerische Ruhehämodynamik-Zusammenfassung.

## v27.4.16 (2026-01-09)

- Echo Screenshot Import: OCR ohne Tesseract. Lokal (Windows) wird jetzt zuerst Windows Built in OCR (WinRT via PowerShell) verwendet. Tesseract bleibt optionaler Fallback.

## v27.4.15 (2026-01-09)
- Fix: NumPy 2.x ABI-Crash durch Gradio Analytics/Queueing endgültig verhindert (Analytics-Guard läuft bereits beim Import; Queueing wird zusätzlich in `launch()` deaktiviert, wenn unterstützt).
- Fix: Belastungshämodynamik Peak RAP NameError behoben (`rap_peak` wird korrekt als `rap_pk` gelesen).

- v27.4.19: Echo Import UI merged (single control), unified JS handler, still client-side only.

