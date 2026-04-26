RHK Befundassistent - Windows Offline Kit
=========================================

Dieses Verzeichnis ist fuer einen isolierten Windows-Rechner gedacht.

Start:
1. Den kompletten Ordner auf den Windows-PC kopieren.
2. `Start_RHK.bat` per Doppelklick starten.
3. Falls gewuenscht: `Create_Desktop_Shortcut.bat` ausfuehren.

Wichtig:
- Den Ordner nicht teilweise kopieren. `python\`, `assets\`, `data\` und die `rhk_*.py` Dateien muessen zusammenbleiben.
- Die App startet lokal auf `127.0.0.1` und benoetigt kein Internet.
- Exporte liegen in `exports\`.
- Laufzeitdateien und Logs liegen in `runtime\` und `run_logs\`.

Fehlersuche:
- Wenn der Start scheitert, zuerst `run_logs\run.log` oeffnen.
- Falls Windows fehlende Laufzeit-DLLs meldet, das gesamte Kit erneut kopieren; die benoetigten Python-Dateien sind bereits enthalten.
