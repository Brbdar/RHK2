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
