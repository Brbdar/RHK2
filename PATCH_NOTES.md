# Patch 27.2.9 (2026-01-08)

Änderungen

1) Cards Mode – graue Balken wirklich entfernt
- Innerhalb von .rhk-card werden nun auch Gradio-Container (Row, Block, Markdown/Prose Wrapper) konsequent auf transparent gesetzt.
- Zusätzlich: .gr-row selbst wird innerhalb von Cards neutralisiert (kein Background-Fill, keine Padding-Balken).

2) Tabs – Reiter-Buttons werden nicht mehr durch eine Linie „geschnitten“
- Entfernt: mögliche Border/Shadow am [role=tablist] Container.
- Divider unterhalb der Tab-Pills weiter nach unten verschoben (mit zusätzlichem Abstand).

---

# Patch 27.2.8 (2026-01-08)

Änderungen

1) Cards Mode – graue Zwischenbalken vollständig entfernt
- Die Tab-Seite selbst ist jetzt „transparent“ (keine große Box). Die Gliederung erfolgt ausschließlich über die inneren .rhk-card Sektionen.
- Row- und Block-Hintergründe innerhalb der Tab-Seiten werden auf transparent gesetzt, sodass keine grauen Trennbalken mehr erscheinen.

2) Tabs – Reiterlinie schneidet nicht mehr durch die Buttons
- Mehr Abstand unter den Pill-Tabs und Divider-Line weiter nach unten versetzt.
- Z-Index-Fix: Buttons liegen immer vor der Divider-Line.

---

# Patch 27.2.7 (2026-01-08)

Änderungen

1) Arztbericht – manuell ausgewählte P-Module werden nicht mehr „verschluckt“
- Wenn ein P-Modul explizit ausgewählt wurde, erscheint es im Procedere auch dann, wenn alle Bullet-Points als „bereits erfolgt“ herausgefiltert wurden.
- In diesem Fall wird eine kurze, professionelle Zeile ausgegeben: „Derzeit keine zusätzliche Maßnahme ableitbar.“

2) Cards Mode – graue Balken innerhalb von Cards entfernt
- Die globalen Tab-Überschriften-Styles (h3/h4) wirken jetzt nur noch auf direkte Tab-Section-Header, nicht innerhalb von .rhk-card.
- Ergebnis: Card-Header wirken sauber und „card-like“, ohne graue Zwischenbalken.

---

# Patch 27.2.4 (2026-01-08)

Änderungen

1) Tabs – „angeschnittene“ Reiterlinie behoben
- Die optische Trennlinie unter den Pill-Tabs liegt jetzt bewusst unterhalb der Tabs und schneidet die Reiter nicht mehr an.

2) Cards Mode – echte Card-Sektionen in den Input-Reitern
- Klinik & Labor: aufgeteilt in vier Cards (Allgemeines/Anamnese/Vorerkrankungen, Funktion/Symptome, Labor, Medikation & Zusatzangaben).
- Bildgebung & Echo/CMR: getrennte Cards für Thorax-Bildgebung und MRT/CMR.
- Lungenfunktion: getrennte Cards für Lungenfunktion und CPET.

---

# Patch 27.2.3 (2026-01-08)

Änderungen

1) Klinik & Labor – bessere Orientierung
- Neue Abschnittsüberschrift „Allgemeines, Anamnese, Vorerkrankungen“ am Anfang des Tabs.
- Abschnitt „Symptome / Funktion“ umbenannt zu „Funktion / Symptome“ für konsistentere Navigation.

2) Cards Mode – professionellere Section Header
- Abschnittsüberschriften innerhalb der Tab-Cards sind jetzt klarer und „card header“-ähnlich gestylt (bessere Scanbarkeit, weniger Verlorenheitsgefühl).

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


## v27.2.6 (2026-01-08)
- FIX: P-Module titles restored in UI and selection works again (TextBlock structure preserved).
- IMPROVE: P-Module texts shortened and styled as concise Arztbrief-Procedere.
