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
