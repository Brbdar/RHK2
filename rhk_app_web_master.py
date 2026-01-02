#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – v25.8.9 (split)

Diese Datei ist nur noch der stabile Entry-Point.
Die eigentliche Implementierung liegt jetzt in:
- rhk_base.py
- rhk_case.py
- rhk_reports.py
- rhk_ui.py
- rhk_launch.py

Zum Starten:
    python rhk_app_web_master.py
"""

from rhk_launch import main

if __name__ == "__main__":
    main()
