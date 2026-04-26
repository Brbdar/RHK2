#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Textbausteine für den Echo Patientenbericht.

Ziel
- Echokardiographische Messwerte in verständlicher, patientengerechter Sprache einordnen.
- Zahlen werden als Orientierung erklärt, ohne Überinterpretation.

Konvention
- ECHO_PATIENT_BLOCKS: dict[str, dict] mit "templates"
- Platzhalter via format_map: z.B. {lvef_fmt}, {tapse_fmt}, {pasp_fmt}

Wichtig
- Keine kursiven Formatierungen.
- Möglichst ohne Bindestriche in den Texten.
- Einheitliche Anrede (Standard: Sie).
"""


ECHO_PATIENT_BLOCKS = {
    # ------------------------------------------------------------------
    # Intro / Kontext
    # ------------------------------------------------------------------
    "intro": {
        "templates": [
            "{salutation}\n\nHier finden Sie eine verständliche Einordnung der Werte aus dem Herzultraschall. Das hilft beim Mitlesen und Einordnen. Die endgültige Bewertung ergibt sich immer aus Beschwerden, Laborwerten und weiteren Untersuchungen.",
            "{salutation}\n\nIm Herzultraschall lassen sich viele Dinge gut abschätzen. Manche Werte sind jedoch nur Näherungen. Unten finden Sie die wichtigsten Messwerte und was sie in der Regel bedeuten.",
        ]
    },

    # Kurze Einleitung je Abschnitt (optional)
    "rv_section_intro": {
        "templates": [
            "Die rechte Herzkammer pumpt Blut in die Lunge. Für die Beurteilung nutzen wir mehrere Messwerte, die wir hier kurz einordnen.",
        ]
    },
    "pasp_section_intro": {
        "templates": [
            "Der Druck im Lungenkreislauf wird im Ultraschall aus mehreren Zeichen abgeschätzt. Eine genaue Messung ist nur mit einem Rechtsherzkatheter möglich.",
        ]
    },
    "stau_section_intro": {
        "templates": [
            "Wir schauen auf Hinweise, ob das rechte Herz stärker belastet ist. Dazu zählen zum Beispiel die Größe des rechten Vorhofs und Zeichen einer möglichen Stauung.",
        ]
    },
    "ee_section_intro": {
        "templates": [
            "E/e ist ein Hinweiswert aus dem Ultraschall. Er kann helfen, den Füllungsdruck im linken Herzen einzuschätzen. Ein einzelner Wert reicht dafür nicht aus.",
        ]
    },

    # ------------------------------------------------------------------
    # Linke Herzkammer (LVEF)
    # ------------------------------------------------------------------
    "lv_normal": {
        "templates": [
            "Die Pumpfunktion der linken Herzkammer liegt im üblichen Bereich. Die LVEF beträgt {lvef_fmt} Prozent.",
        ]
    },
    "lv_mild": {
        "templates": [
            "Die Pumpfunktion der linken Herzkammer ist leicht vermindert. Die LVEF beträgt {lvef_fmt} Prozent. Das bedeutet, dass pro Herzschlag etwas weniger Blut ausgeworfen wird als üblich.",
        ]
    },
    "lv_moderate": {
        "templates": [
            "Die Pumpfunktion der linken Herzkammer ist mittelgradig vermindert. Die LVEF beträgt {lvef_fmt} Prozent. Das kann zu schnellerer Ermüdung oder Luftnot bei Belastung beitragen.",
        ]
    },
    "lv_severe": {
        "templates": [
            "Die Pumpfunktion der linken Herzkammer ist deutlich vermindert. Die LVEF beträgt {lvef_fmt} Prozent. Wir besprechen das immer im Gesamtbild und achten dabei besonders auf Beschwerden und den Verlauf.",
        ]
    },

    # ------------------------------------------------------------------
    # Rechte Herzkammer (TAPSE, S', RV EF)
    # ------------------------------------------------------------------
    "rv_tapse_normal": {
        "templates": [
            "TAPSE liegt bei {tapse_fmt} mm. Das spricht für eine gute Längsbewegung der rechten Herzkammer.",
        ]
    },
    "rv_tapse_mild": {
        "templates": [
            "TAPSE liegt bei {tapse_fmt} mm. Das kann auf eine leichte Einschränkung der rechten Herzkammerfunktion hinweisen.",
        ]
    },
    "rv_tapse_moderate": {
        "templates": [
            "TAPSE liegt bei {tapse_fmt} mm. Das kann auf eine deutliche Einschränkung der rechten Herzkammerfunktion hinweisen.",
        ]
    },
    "rv_tapse_severe": {
        "templates": [
            "TAPSE liegt bei {tapse_fmt} mm. Das passt zu einer schwergradigen Einschränkung der rechten Herzkammerfunktion.",
        ]
    },

    "rv_sprime_normal": {
        "templates": [
            "S' liegt bei {sprime_fmt} cm/s. Das spricht für eine gute Bewegung der rechten Herzkammer an dieser Messstelle.",
        ]
    },
    "rv_sprime_border": {
        "templates": [
            "S' liegt bei {sprime_fmt} cm/s. Das liegt im Grenzbereich. Wir bewerten diesen Wert immer zusammen mit den anderen Messwerten der rechten Herzkammer.",
        ]
    },
    "rv_sprime_reduced": {
        "templates": [
            "S' liegt bei {sprime_fmt} cm/s. Das kann auf eine Einschränkung der rechten Herzkammerfunktion hinweisen.",
        ]
    },
    "rv_sprime_severe": {
        "templates": [
            "S' liegt bei {sprime_fmt} cm/s. Das passt zu einer ausgeprägten Einschränkung der rechten Herzkammerfunktion.",
        ]
    },

    "rv_ef_normal": {
        "templates": [
            "Die Ejektionsfraktion der rechten Herzkammer beträgt {rv_ef_fmt} Prozent und liegt im üblichen Bereich.",
        ]
    },
    "rv_ef_mild": {
        "templates": [
            "Die Ejektionsfraktion der rechten Herzkammer beträgt {rv_ef_fmt} Prozent. Das kann zu einer leichten Einschränkung passen.",
        ]
    },
    "rv_ef_moderate": {
        "templates": [
            "Die Ejektionsfraktion der rechten Herzkammer beträgt {rv_ef_fmt} Prozent. Das kann zu einer mittelgradigen Einschränkung passen.",
        ]
    },
    "rv_ef_severe": {
        "templates": [
            "Die Ejektionsfraktion der rechten Herzkammer beträgt {rv_ef_fmt} Prozent. Das spricht für eine deutliche Einschränkung. Wir ordnen das immer gemeinsam mit Beschwerden, Belastbarkeit und Verlauf ein.",
        ]
    },

    # ------------------------------------------------------------------
    # Druckabschätzung in den Lungengefäßen
    # ------------------------------------------------------------------
    "pasp_normal": {
        "templates": [
            "Der im Ultraschall geschätzte systolische Druck in der Lungenschlagader (sPAP) liegt bei {pasp_fmt} mmHg und ist im üblichen Bereich. Wichtig: Das ist eine Abschätzung und kein direkt gemessener Katheterwert.",
        ]
    },
    "pasp_mild": {
        "templates": [
            "Der im Ultraschall geschätzte systolische Druck in der Lungenschlagader (sPAP) liegt bei {pasp_fmt} mmHg. Das ist leicht erhöht. Für die Einordnung ist der Gesamtbefund entscheidend.",
        ]
    },
    "pasp_moderate": {
        "templates": [
            "Der im Ultraschall geschätzte systolische Druck in der Lungenschlagader (sPAP) liegt bei {pasp_fmt} mmHg. Das ist ein Hinweis auf eine deutliche Druckerhöhung. Im Ultraschall bleibt das eine Abschätzung.",
        ]
    },
    "pasp_severe": {
        "templates": [
            "Der im Ultraschall geschätzte systolische Druck in der Lungenschlagader (sPAP) liegt bei {pasp_fmt} mmHg. Das ist ein Hinweis auf eine starke Druckerhöhung. Wir prüfen dann immer sorgfältig mögliche Ursachen und die nächsten Schritte.",
        ]
    },

    "echo_prob_niedrig": {
        "templates": [
            "Nach den Ultraschallzeichen ist die Wahrscheinlichkeit für eine pulmonale Hypertonie eher niedrig.",
        ]
    },
    "echo_prob_intermediär": {
        "templates": [
            "Nach den Ultraschallzeichen ist die Wahrscheinlichkeit für eine pulmonale Hypertonie im mittleren Bereich.",
        ]
    },
    "echo_prob_hoch": {
        "templates": [
            "Nach den Ultraschallzeichen ist die Wahrscheinlichkeit für eine pulmonale Hypertonie eher hoch.",
        ]
    },


    # Linker Vorhof
    "la_size_normal": {
        "templates": [
            "Der linke Vorhof ist nicht vergrößert. Das spricht eher gegen eine länger bestehende Druckbelastung des linken Herzens.",
        ]
    },
    "la_size_enlarged": {
        "templates": [
            "Der linke Vorhof ist vergrößert. Das kann zu länger bestehenden erhöhten Drücken im linken Herzen passen.",
        ]
    },

    # RV Strain (FWLS)
    "rv_strain_normal": {
        "templates": [
            "Die Dehnungs Messung der rechten Herzkammer (Strain) ist unauffällig. Das unterstützt den Eindruck einer guten Pumpfunktion.",
        ]
    },
    "rv_strain_border": {
        "templates": [
            "Die Dehnungs Messung der rechten Herzkammer (Strain) ist grenzwertig. Das kann ein frühes Zeichen einer Belastung sein.",
        ]
    },
    "rv_strain_reduced": {
        "templates": [
            "Die Dehnungs Messung der rechten Herzkammer (Strain) ist vermindert. Das passt zu einer eingeschränkten Pumpfunktion.",
        ]
    },
    "rv_strain_severe": {
        "templates": [
            "Die Dehnungs Messung der rechten Herzkammer (Strain) ist deutlich vermindert. Das spricht für eine ausgeprägte Einschränkung der Pumpfunktion.",
        ]
    },

    # TAPSE zu sPAP
    "tapse_spap_good": {
        "templates": [
            "Das Verhältnis aus TAPSE und dem geschätzten Druck in den Lungengefäßen wirkt günstig. Das spricht für eine gute Kopplung von rechter Herzkammer und Lungenkreislauf.",
        ]
    },
    "tapse_spap_border": {
        "templates": [
            "Das Verhältnis aus TAPSE und dem geschätzten Druck in den Lungengefäßen ist grenzwertig. Das kann zu einer beginnenden Belastung des rechten Herzens passen.",
        ]
    },
    "tapse_spap_low": {
        "templates": [
            "Das Verhältnis aus TAPSE und dem geschätzten Druck in den Lungengefäßen ist ungünstig. Das kann zu einer deutlicheren Belastung des rechten Herzens passen.",
        ]
    },

    # Perikard
    "pericardial_no": {
        "templates": [
            "Es wurde kein Hinweis auf einen Perikarderguss gefunden.",
        ]
    },
    "pericardial_yes": {
        "templates": [
            "Es wurde ein Perikarderguss beschrieben. Das bedeutet, dass sich Flüssigkeit im Herzbeutel befindet. Bitte besprechen Sie mit uns die klinische Einordnung.",
        ]
    },

    # ------------------------------------------------------------------
    # Vorhöfe und Stauungszeichen
    # ------------------------------------------------------------------
    "ra_normal": {
        "templates": [
            "Die Fläche des rechten Vorhofs beträgt {ra_esa_fmt} cm² und wirkt nicht vergrößert.",
        ]
    },
    "ra_enlarged": {
        "templates": [
            "Die Fläche des rechten Vorhofs beträgt {ra_esa_fmt} cm² und ist vergrößert. Das kann zu einer länger bestehenden Belastung des rechten Herzens passen.",
        ]
    },

    "ivc_normal": {
        "templates": [
            "Die untere Hohlvene wirkt unauffällig. Das passt eher zu normalen Drücken im rechten Herzen.",
        ]
    },
    "ivc_high_rap": {
        "templates": [
            "Die untere Hohlvene ist eher weit und kollabiert wenig. Das kann zu erhöhten Drücken im rechten Herzen passen. Wir bewerten das zusammen mit Beschwerden, zum Beispiel geschwollenen Beinen oder einer schnellen Gewichtszunahme.",
        ]
    },
    "ivc_unclear": {
        "templates": [
            "Die Angaben zur unteren Hohlvene sind nicht eindeutig. Wir nutzen dafür immer mehrere Hinweise im Ultraschall und im klinischen Befund.",
        ]
    },

    # ------------------------------------------------------------------
    # Füllungsdruck Hinweise (E/e)
    # ------------------------------------------------------------------
    "ee_normal": {
        "templates": [
            "E/e liegt bei {ee_fmt}. Das spricht eher nicht für deutlich erhöhte Füllungsdrücke im linken Herzen.",
        ]
    },
    "ee_intermediate": {
        "templates": [
            "E/e liegt bei {ee_fmt}. Das ist ein Zwischenbereich, also nicht klar normal, aber auch nicht klar deutlich erhöht. Zur Einordnung helfen weitere Ultraschallzeichen und Ihre Beschwerden.",
        ]
    },
    "ee_high": {
        "templates": [
            "E/e liegt bei {ee_fmt}. Das kann zu erhöhten Füllungsdrücken im linken Herzen passen. Wir ordnen das immer zusammen mit anderen Zeichen ein.",
        ]
    },

    # ------------------------------------------------------------------
    # Outro
    # ------------------------------------------------------------------
    "outro": {
        "templates": [
            "### Wie geht es weiter\n\nWir betrachten Ultraschallwerte immer im Zusammenhang mit Belastbarkeit, Laborwerten und, wenn nötig, der Messung im Rechtsherzkatheter. Wenn Sie einzelne Begriffe nicht verstehen, sprechen Sie uns bitte an. Wir erklären das gerne Schritt für Schritt.",
        ]
    },
}


ECHO_PATIENT_GLOSSARY = {
    "LVEF": "Anteil des Blutes, den die linke Herzkammer pro Herzschlag auswirft. Das gibt einen groben Eindruck von der Pumpkraft.",
    "TAPSE": "Maß für die Längsbewegung der rechten Herzkammer. Es ist ein Hinweis auf die Pumpfunktion.",
    "S'": "Geschwindigkeit der Bewegung am Trikuspidalklappenring. Ebenfalls ein Hinweis auf die Funktion der rechten Herzkammer.",
    "sPAP": "Im Ultraschall geschätzter Druck in der Lungenschlagader während der Auswurfphase. Das ist eine Abschätzung, kein direkt gemessener Wert.",
    "TRV": "Geschwindigkeit eines Rückflusssignals an der Trikuspidalklappe. Daraus lässt sich der Druck im Ultraschall abschätzen.",
    "E/e": "Verhältnis zweier Ultraschallmessungen, das Hinweise geben kann, ob der Druck im linken Herzen erhöht ist.",
    "LAVI": "Volumen des linken Vorhofs bezogen auf die Körperoberfläche. Ein Langzeit Marker für Druckbelastung im linken Herzen.",
    "RVFAC": "Flächenänderung der rechten Herzkammer während des Herzschlags. Ein Hinweis auf die Pumpfunktion des rechten Herzens.",
    "Strain": "Dehnungs Messung des Herzmuskels. Beim rechten Herzen ist vor allem FWLS relevant. Mehr negativ ist meist besser.",
    "PAAT": "Pulmonal Arterien Akzeleration Time. Ein kurzer Wert kann ein Hinweis auf höheren Druck im Lungenkreislauf sein.",
    "VCI": "Vena cava inferior. Die Größe und der Kollaps können Hinweise auf Stauung geben.",
}
