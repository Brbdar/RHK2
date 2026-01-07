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
