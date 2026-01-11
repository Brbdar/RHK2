"""Compatibility shim (legacy import path).

Historically the project used a version-suffixed patient text database module.
From v25.0 onward, `rhk_textdb_patient.py` is the single source of truth.

Do not modify clinical content here. Edit `rhk_textdb_patient.py` instead.
"""

from rhk_textdb_patient import *  # noqa: F401,F403


_add(
    "PX_VOLUME_CHALLENGE",
    "Volumenchallenge",
    [
        "Manchmal geben wir während der Untersuchung gezielt eine definierte Menge Flüssigkeit über die Vene. Damit prüfen wir, ob der Druck auf der linken Herzseite dabei auffällig ansteigt. Das kann helfen, eine Mitbeteiligung der linken Herzhälfte besser einzuordnen.",
        "Bei der Volumenchallenge wird kontrolliert Flüssigkeit gegeben. Wir schauen dann, ob sich der Füllungsdruck im linken Herzen deutlich erhöht. Das ist ein Hinweis darauf, dass es unter mehr Blutvolumen leichter zu einem Rückstau in die Lunge kommt."
    ],
)

_add(
    "PX_VASOREACTIVITY",
    "Vasoreaktivität",
    [
        "Bei der Vasoreaktivität wird ein kurzwirksames Testmedikament eingesetzt. Damit prüfen wir, ob sich die Lungengefäße im Test deutlich entspannen. Das kann in ausgewählten Fällen Einfluss auf die Therapieplanung haben.",
        "Bei diesem Zusatztest schauen wir, ob die Lungengefäße auf ein kurzfristig gegebenes Medikament spürbar reagieren. Eine deutliche Reaktion kann therapeutisch bedeutsam sein."
    ],
)
