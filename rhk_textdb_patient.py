#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patienten-Textbausteine (DE) – variantenreich, patientenfreundlich, drucktauglich.

Ziel:
- Der Patientenbericht soll den fachlichen Arztbericht **verständlich ergänzen**.
- Fachbegriffe werden möglichst vermieden oder **kurz erklärt**.
- Einige zentrale Messwerte können optional als Orientierung genannt werden (mit Einordnung „normal/erhöht“),
  ohne den Bericht zu einem Zahlenfriedhof zu machen.

Konzept:
- PATIENT_BLOCKS: Bausteine mit mehreren Formulierungs-Varianten
- PATIENT_BUNDLES: Zuordnung von Regelwerk-Bundles (Kxx) → typischer Bausteinsatz
- PATIENT_MODULE_SUMMARY: patientenfreundliche Kurzbeschreibung der P-Module (P01–P25)
- PATIENT_GLOSSARY: kurze Begriffserklärungen (für den Ausdruck)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Union


@dataclass(frozen=True)
class PatientBlock:
    id: str
    title: str
    templates: List[str] = field(default_factory=list)


PATIENT_BLOCKS: Dict[str, PatientBlock] = {}


def _as_list(x: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(x, str):
        return [x.strip()]
    return [str(t).strip() for t in x if str(t).strip()]


def _add(block_id: str, title: str, templates: Union[str, Sequence[str]]):
    incoming = _as_list(templates)
    existing = PATIENT_BLOCKS.get(block_id)
    if existing is None:
        PATIENT_BLOCKS[block_id] = PatientBlock(
            id=block_id,
            title=title,
            templates=incoming,
        )
        return

    # Falls ein Block mehrfach definiert wird, Varianten zusammenführen statt überschreiben.
    merged: List[str] = []
    seen: set[str] = set()
    for raw in list(existing.templates) + incoming:
        txt = str(raw or "").strip()
        if not txt:
            continue
        key = " ".join(txt.split()).casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(txt)

    PATIENT_BLOCKS[block_id] = PatientBlock(
        id=block_id,
        title=title or existing.title,
        templates=merged,
    )


# ---------------------------------------------------------------------------
# Grundbausteine
# ---------------------------------------------------------------------------

_add(
    "PX_INTRO",
    "Einleitung",
    [
        "{salutation}\n\nWir haben bei Ihnen eine Herzkatheter-Untersuchung durchgeführt. Dabei werden Druckwerte und Blutfluss im Bereich von Herz und Lunge gemessen.",
        "{salutation}\n\nHier finden Sie eine verständliche Zusammenfassung einer Herzkatheter-Untersuchung. Dabei messen wir, wie das Blut durch Herz und Lunge fließt und ob es Hinweise auf eine Druckerhöhung gibt.",
        "{salutation}\n\nWir möchten Ihnen die Ergebnisse einer Herzkatheter-Untersuchung in einfacher Sprache erklären. Die Messung hilft uns, Ursachen von Luftnot und eingeschränkter Belastbarkeit besser einzuordnen.",
        "{salutation}\n\nIm Folgenden fassen wir die Ergebnisse Ihrer Herzkatheter-Untersuchung zusammen. Unser Ziel ist es, Ihnen die Befunde so zu erklären, dass Sie gut informiert in die nächsten Gespräche gehen können.",
        "{salutation}\n\nBei der Herzkatheter-Untersuchung haben wir gemessen, wie Ihr Blut durch Herz und Lunge fließt. Mit diesem Bericht möchten wir Ihnen helfen, die Ergebnisse besser einzuordnen.",
        "{salutation}\n\nDiese Zusammenfassung erklärt Ihnen die Ergebnisse Ihrer Herzkatheter-Untersuchung in verständlicher Sprache. Dabei geht es vor allem um Druckwerte und Durchblutung in den Lungengefäßen.",
    ],
)

_add(
    "PX_NO_PH",
    "Kein Lungenhochdruck in Ruhe",
    [
        "In Ruhe zeigen die Messwerte **keinen Hinweis** auf eine Druckerhöhung in den Blutgefäßen der Lunge.",
        "Die Druckwerte in den Blutgefäßen der Lunge sind **in Ruhe nicht erhöht**. Das ist ein beruhigender Befund.",
        "Es liegt **kein Lungenhochdruck in Ruhe** vor. Das bedeutet, dass die Druckwerte in den Lungengefäßen im Normalbereich liegen.",
        "Die Messung in Ruhe zeigt **keine erhöhten Druckwerte** in den Lungengefäßen. Das ist zunächst eine gute Nachricht.",
        "Die Druckverhältnisse in den Lungengefäßen sind **in Ruhe unauffällig**. Die rechte Herzhälfte arbeitet unter normalen Bedingungen.",
        "Ihre Kreislaufwerte in Ruhe fallen heute **in den Normalbereich**. Für die weitere Beratung zählt nun vor allem, wie Ihr Körper auf Belastung reagiert und ob Beschwerden einer anderen Ursache zugeordnet werden müssen.",
    ],
)


# ---------------------------------------------------------------------------
# Patientenbericht-Archetypen (H1...H6)
#
# Hinweis:
# - Diese Bausteine sind *fokusverschiebend* (Schwerpunkt), nicht diagnostisch.
# - Sie werden nur verwendet, wenn `derived.p_archetype_id` gesetzt ist.
# - Fallback bleibt immer der bestehende Standardtext.
# ---------------------------------------------------------------------------

_add(
    "PX_ARCH_H1_FOCUS_MEASURED",
    "Archetyp H1: kein PH in Ruhe, aber Risiko/Vorerkrankung – Fokus Messung",
    [
        "Auch wenn die Werte in Ruhe unauffällig sind, bedeutet das nicht automatisch Entwarnung. Bei bestimmten Vorerkrankungen kann es wichtig sein, den Verlauf und die Belastungssituation im Blick zu behalten.",
        "Ein Normalbefund in Ruhe ist in Ihrer Konstellation ein gutes Zeichen, ersetzt aber nicht die Verlaufskontrolle. Manche Veränderungen zeigen sich zuerst unter Belastung oder im zeitlichen Verlauf.",
        "Die gemessenen Werte in Ruhe liegen im Normalbereich. Das ist erfreulich. Trotzdem empfehlen wir bei Ihrer Vorgeschichte regelmäßige Kontrollen, damit wir Veränderungen früh erkennen.",
        "In Ruhe sind die Druckwerte unauffällig. Bei Vorerkrankungen, die ein erhöhtes Risiko mit sich bringen, schauen wir aber besonders genau auf den Verlauf und auf Belastungssituationen.",
        "Die Ruhemessung zeigt keine Auffälligkeiten. Bei bestimmten Grunderkrankungen können sich Veränderungen jedoch schleichend entwickeln. Deshalb planen wir gezielte Verlaufskontrollen.",
        "Heute bekommen wir ein detailliertes Bild Ihrer Kreislaufsituation in Ruhe – und dieses Bild ist unauffällig. "
        "Bei Ihrer Vorgeschichte hilft uns dieser Befund vor allem, die Entwicklung über die Zeit sicher einordnen zu können.",
    ],
)

_add(
    "PX_ARCH_H1_FOCUS_MEANING",
    "Archetyp H1: kein PH in Ruhe, aber Risiko/Vorerkrankung – Fokus Bedeutung",
    [
        "Das Ziel ist jetzt vor allem, Veränderungen früh zu erkennen. Wichtig sind dabei Beschwerden, Belastbarkeit und Kontrolluntersuchungen, nicht nur ein einzelner Messzeitpunkt.",
        "In solchen Situationen ist oft die Kombination aus Symptomen, Verlauf und ergänzenden Untersuchungen entscheidend. So können wir rechtzeitig handeln, falls sich etwas verändert.",
        "Auch wenn heute alles unauffällig ist, behalten wir Ihre Situation aufmerksam im Blick. Frühzeitiges Erkennen ermöglicht frühzeitiges Handeln.",
        "Ein normaler Befund heute ist ein guter Ausgangspunkt. Wir planen Kontrollen, damit wir auch in Zukunft sicher sein können, dass sich nichts verändert.",
        "Entscheidend ist nicht nur der heutige Wert, sondern der Verlauf über die Zeit. Gemeinsam achten wir darauf, ob Beschwerden oder Belastbarkeit sich verändern.",
        "Bei Ihrer Ausgangssituation bedeutet ein unauffälliger Befund heute: Wir haben Zeit und können gezielt vorbeugend arbeiten. "
        "Das nutzen wir – mit klaren Intervallen und mit dem Blick auf Beschwerden im Alltag.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEASURED",
    "Archetyp H2: Grenzwerte/frühe PH – Fokus Messung",
    [
        "Einige Werte liegen in einem Grenzbereich. Das kann ein sehr frühes Stadium sein oder eine vorübergehende Schwankung. Deshalb ist Dynamik oft wichtiger als eine Momentaufnahme.",
        "Die Messwerte bewegen sich nahe an den Grenzbereichen. Das allein ist noch keine Aussage darüber, wie stabil die Situation bleibt. Entscheidend ist der Verlauf zusammen mit Ihren Beschwerden.",
        "Manche Werte liegen knapp über oder an der Grenze zum Auffälligen. In solchen Fällen ist es besonders wichtig, den Verlauf zu beobachten und eine Kontrollmessung einzuplanen.",
        "Die Druckwerte bewegen sich in einem Bereich, der nicht eindeutig normal, aber auch nicht klar erhöht ist. Eine einzelne Messung reicht hier oft nicht für eine sichere Einordnung.",
        "Die Ergebnisse zeigen Grenzwerte. Das muss noch nichts Bedrohliches bedeuten, erfordert aber eine sorgfältige Verlaufsbeobachtung, um die Entwicklung richtig einzuschätzen.",
        "Ein Befund im Grenzbereich ist ein Hinweis, kein Urteil. "
        "Erst die Kombination aus Verlauf, Beschwerden und Zusatzuntersuchungen zeigt, ob wir es mit einer beginnenden Veränderung zu tun haben oder mit einer individuellen Schwankung.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEANING",
    "Archetyp H2: Grenzwerte/frühe PH – Fokus Bedeutung",
    [
        "In einem Frühstadium geht es häufig darum, Ursachen sauber einzuordnen und den Verlauf zu beobachten. Eine Behandlung wird immer gegen Nutzen und Risiken abgewogen.",
        "Bei grenzwertigen Befunden ist es besonders wichtig, Trends zu erkennen: Werden Werte oder Beschwerden schlechter, bleibt alles stabil oder verbessert es sich? Daraus leiten wir die nächsten Schritte ab.",
        "Grenzwerte bedeuten, dass wir besonders aufmerksam bleiben. In vielen Fällen reicht zunächst eine gute Beobachtung, bevor therapeutische Schritte eingeleitet werden.",
        "Die Bedeutung von Grenzwerten lässt sich erst im Verlauf richtig einschätzen. Deshalb steht jetzt die sorgfältige Verlaufskontrolle im Vordergrund.",
        "In einer solchen Konstellation klären wir zunächst, ob sich die Werte in einer Richtung bewegen oder stabil bleiben. Das ist die Grundlage für alle weiteren Entscheidungen.",
        "Grenzbefunde sind eine Einladung zum genauen Hinschauen, aber kein Grund zur Sorge. "
        "Viele Menschen bleiben langfristig in diesem Bereich – und wir erkennen frühzeitig, falls sich das ändert.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEASURED",
    "Archetyp H3: etablierte präkapilläre PH – Fokus Messung",
    [
        "Die Werte sprechen dafür, dass die Lungengefäße einen erhöhten Widerstand bieten. Das rechte Herz muss dadurch gegen eine höhere Nachlast arbeiten.",
        "Im Vordergrund steht eine erhöhte Belastung des rechten Herzens durch den Widerstand in den Lungengefäßen. Das erklärt, warum Belastung und Leistungsfähigkeit so wichtig sind.",
        "Die Messwerte zeigen, dass die Blutgefäße in der Lunge verengt oder versteift sind. Das rechte Herz muss entsprechend mehr leisten, um das Blut hindurchzupumpen.",
        "Der erhöhte Widerstand in den Lungengefäßen belastet das rechte Herz deutlich messbar. Die Untersuchung hilft uns, den Schweregrad genau einzuschätzen.",
        "Die Messung bestätigt eine klare Druckerhöhung in den Lungengefäßen. Daraus ergibt sich, wie stark die rechte Herzhälfte aktuell beansprucht wird.",
        "Diese Messung hat den klaren Zweck, die Situation genau zu vermessen – und genau das ist uns gelungen. "
        "Auf dieser Basis können wir jetzt einen individuell passenden Therapieplan erarbeiten.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEANING",
    "Archetyp H3: etablierte präkapilläre PH – Fokus Bedeutung",
    [
        "Der Schwerpunkt liegt nun weniger auf der Frage *ob* Lungenhochdruck vorliegt, sondern darauf, wie gut das rechte Herz damit zurechtkommt und welche Therapieziele wir gemeinsam verfolgen.",
        "Wichtig ist, die Belastung des rechten Herzens zu senken und die Belastbarkeit zu stabilisieren oder zu verbessern. Kontrollen helfen, Therapieeffekte früh zu erkennen.",
        "Es geht jetzt vor allem darum, die richtige Behandlung zu finden und zu überprüfen, wie gut sie wirkt. Ihre Belastbarkeit im Alltag ist dabei ein wichtiger Gradmesser.",
        "Gemeinsam legen wir Therapieziele fest und überprüfen regelmäßig, ob die Behandlung Ihnen im Alltag spürbar hilft. Das rechte Herz bestmöglich zu entlasten, steht dabei im Mittelpunkt.",
        "In dieser Situation gibt es gezielte Behandlungsmöglichkeiten. Welche davon für Sie am besten geeignet sind, hängt von der genauen Ursache und Ihrem Befinden ab.",
        "Die moderne Behandlung dieser Form des Lungenhochdrucks hat sich in den letzten Jahren deutlich weiterentwickelt: "
        "Es gibt heute mehrere Medikamenten-Klassen, die wir kombinieren und gezielt an Ihre Situation anpassen können.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEASURED",
    "Archetyp H4: postkapilläre/kombinierte PH – Fokus Messung",
    [
        "Es gibt Hinweise, dass der Druckanstieg (auch) durch einen Rückstau von der linken Herzseite mitbedingt ist. Das verändert, welche Behandlungsansätze im Vordergrund stehen.",
        "Das Muster spricht dafür, dass die linke Herzhälfte eine wichtige Rolle spielt. Dann ist die Einordnung der linken Herzfunktion und der Flüssigkeitsbalance besonders relevant.",
        "Die Messwerte deuten darauf hin, dass der erhöhte Druck in der Lunge zumindest teilweise durch die linke Herzseite verursacht wird. Das ist ein häufiges Muster, das wir gezielt behandeln können.",
        "Wir sehen in den Messungen, dass sich Druck von der linken Herzseite auf die Lungengefäße überträgt. Das ist ein wichtiger Hinweis für die Auswahl der richtigen Therapie.",
        "Die Katheter-Messung zeigt, dass die linke Herzseite eine wesentliche Rolle bei der Druckerhöhung spielt. Das beeinflusst, welche Behandlungsstrategie am sinnvollsten ist.",
        "Diese Unterscheidung zwischen „Lungengefäß-Problem“ und „Rückstau vom linken Herzen“ ist klinisch wichtig, "
        "weil sich die richtige Behandlung grundlegend unterscheidet. Die Katheter-Werte haben uns genau diese Klarheit gebracht.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEANING",
    "Archetyp H4: postkapilläre/kombinierte PH – Fokus Bedeutung",
    [
        "In solchen Konstellationen ist oft die Behandlung des linken Herzens und der Begleiterkrankungen entscheidend. Eine spezifische PH-Therapie ist nicht automatisch der erste Schritt.",
        "Der wichtigste Hebel ist häufig, den Rückstau zu reduzieren und die linke Herzfunktion bestmöglich zu unterstützen. Welche Medikamente sinnvoll sind, wird individuell entschieden.",
        "Wenn die linke Herzseite beteiligt ist, steht die Optimierung der Herzbehandlung und des Flüssigkeitshaushalts im Vordergrund. Das kann Beschwerden oft deutlich lindern.",
        "Die Behandlung richtet sich hier vor allem auf die linke Herzseite und die Begleiterkrankungen. Oft hilft eine gute Einstellung der bestehenden Medikamente bereits spürbar.",
        "Bei diesem Muster ist die enge Zusammenarbeit zwischen verschiedenen Fachbereichen besonders wichtig. So können wir alle Ursachen berücksichtigen und die Therapie gut abstimmen.",
        "Die gute Nachricht: Für viele Ursachen auf der linken Herzseite gibt es wirksame, etablierte Behandlungen. "
        "Wenn wir diese konsequent optimieren, entlasten wir gleichzeitig die Lungengefäße – oft mit spürbarer Wirkung im Alltag.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEASURED",
    "Archetyp H5: thromboembolische Konstellation/CTEPH – Fokus Messung",
    [
        "Es gibt Hinweise, dass (auch) ältere Blutgerinnsel in den Lungengefäßen eine Rolle spielen könnten. Dann geht es besonders um die Mechanik des Blutflusses durch die Lunge.",
        "Bei diesem Muster ist wichtig zu prüfen, ob Engstellen durch ältere Gerinnsel bestehen. Das kann man mit gezielter Bildgebung oft sehr gut beurteilen.",
        "Die Messwerte passen zu einem Muster, bei dem ältere Blutgerinnsel in den Lungengefäßen den Blutfluss behindern könnten. Eine gezielte Bildgebung kann das weiter klären.",
        "Die Druckverteilung in den Messungen spricht dafür, dass mechanische Hindernisse in den Lungengefäßen eine Rolle spielen könnten. Das lässt sich mit speziellen Untersuchungen gut überprüfen.",
        "Wir sehen Hinweise, die an eine Durchblutungsstörung der Lunge denken lassen. Ob ältere Gerinnsel die Ursache sind, können wir mit einer ergänzenden Bildgebung gezielt abklären.",
        "Bei diesem Muster ist die gezielte Bildgebung oft der entscheidende Schritt, weil sie zeigt, wie die Durchblutung der Lunge tatsächlich verläuft. "
        "Die Katheter-Werte liefern dafür die quantitative Grundlage.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEANING",
    "Archetyp H5: thromboembolische Konstellation/CTEPH – Fokus Bedeutung",
    [
        "Wenn sich der Verdacht bestätigt, gibt es neben Medikamenten auch spezielle Behandlungsoptionen, die die Durchblutung der Lunge direkt verbessern können. Welche davon passt, hängt von der genauen Verteilung ab.",
        "In diesem Zusammenhang sind bestimmte Untersuchungen wie die Ventilations/Perfusions-Szintigraphie besonders hilfreich. Sie zeigen, wie gleichmäßig die Lunge durchblutet wird.",
        "Falls ältere Gerinnsel die Ursache sind, gibt es heute gut erprobte Behandlungsmöglichkeiten. Dazu gehören Medikamente, aber auch spezielle Eingriffe, die die Durchblutung wiederherstellen können.",
        "Eine genaue Abklärung ist hier besonders wichtig, weil bei dieser Form des Lungenhochdrucks gezielte Therapien zur Verfügung stehen, die sehr wirksam sein können.",
        "Bei bestätigtem Verdacht wird im spezialisierten Team besprochen, welche Behandlung am besten geeignet ist. Die Möglichkeiten reichen von Medikamenten bis hin zu speziellen Eingriffen.",
        "Diese Form des Lungenhochdrucks gehört zu den wenigen, bei denen unter günstigen Voraussetzungen eine Heilung möglich ist. "
        "Deshalb lohnt sich die sorgfältige Abklärung besonders – sie kann Therapietüren öffnen, die bei anderen Formen nicht zur Verfügung stehen.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEASURED",
    "Archetyp H6: rechtes Herz im Vordergrund bei moderatem Druck – Fokus Messung",
    [
        "Obwohl die Druckwerte nicht extrem hoch sind, zeigen Marker des rechten Herzens eine relevante Belastung. Das kann erklären, warum Beschwerden dennoch deutlich sein können.",
        "Manchmal spiegelt der Druck allein nicht die gesamte Situation wider. Hinweise auf eine Belastung des rechten Herzens oder Rückstau können dann besonders aussagekräftig sein.",
        "Die Druckwerte sind nur mäßig erhöht, aber das rechte Herz zeigt dennoch Zeichen einer deutlichen Beanspruchung. Das nehmen wir ernst und beobachten es gezielt.",
        "Auch bei moderaten Druckwerten kann das rechte Herz spürbar belastet sein. Die Messung zeigt, dass wir hier genauer hinschauen sollten.",
        "Der Druck allein erzählt nicht die ganze Geschichte. Die Zeichen der Rechtsherzbelastung ergänzen das Bild und helfen uns, die Situation realistisch einzuschätzen.",
        "In dieser Konstellation schauen wir weniger auf einzelne Grenzwerte und mehr auf das Zusammenspiel von Druck, Fluss und Herzfunktion. "
        "So entsteht ein realitätsnahes Bild Ihrer Belastbarkeit.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEANING",
    "Archetyp H6: rechtes Herz im Vordergrund bei moderatem Druck – Fokus Bedeutung",
    [
        "Dann ist besonders wichtig, Funktion, Belastbarkeit und Verlauf zu betrachten. Therapieentscheidungen orientieren sich oft daran, wie gut das rechte Herz die Situation kompensieren kann.",
        "In solchen Fällen achten wir besonders auf Verlauf, Belastbarkeit und Zeichen von Rückstau. Das hilft, die Behandlung an das anzupassen, was für Sie im Alltag relevant ist.",
        "Bei dieser Konstellation schauen wir besonders auf die Leistungsfähigkeit des rechten Herzens. Die Therapie richtet sich danach, wie gut das Herz die Belastung bewältigt.",
        "Der Zustand des rechten Herzens bestimmt hier maßgeblich, wie es Ihnen im Alltag geht. Deshalb stehen Verlaufskontrollen und gezielte Therapie im Vordergrund.",
        "Wir orientieren uns bei der Behandlungsplanung vor allem daran, wie das rechte Herz arbeitet und wie belastbar Sie sich fühlen. Das gibt uns die besten Hinweise für die nächsten Schritte.",
        "Gerade wenn der Druck moderat, die Herzfunktion aber relevant beansprucht ist, kann frühzeitiges Handeln Reserven bewahren. "
        "Das gelingt umso besser, je früher wir gemeinsam eine maßgeschneiderte Strategie festlegen.",
    ],
)


# ---------------------------------------------------------------------------
# Vertikale Verfeinerung: Symptomgewichtung, Diskrepanz-Erklärungen, Verlaufstypen
# ---------------------------------------------------------------------------

_add(
    "PX_SYMPTOMS_LOW",
    "Symptome: eher mild",
    [
        "Ihre Beschwerden wirken eher mild. Das ist ein gutes Zeichen. Trotzdem achten wir auf den Verlauf, weil sich Lungengefäß-Erkrankungen auch schleichend verändern können.",
        "Die aktuelle Belastbarkeit wirkt eher gut. Für die Einordnung ist dann besonders wichtig, ob sich etwas im Verlauf verändert und wie Sie Belastung im Alltag vertragen.",
        "Dass Ihre Beschwerden aktuell gering sind, ist erfreulich. Wir nutzen diese Ausgangslage, um einen guten Vergleichspunkt für zukünftige Kontrollen zu haben.",
        "Milde Symptome bedeuten, dass Sie im Alltag wenig eingeschränkt sind. Dennoch behalten wir die Situation im Blick, weil Veränderungen sich manchmal langsam entwickeln.",
        "Ihre Beschwerden sind gering ausgeprägt, was für den Moment beruhigend ist. Bitte achten Sie darauf, ob sich an Ihrer Belastbarkeit etwas verändert, und berichten Sie das bei der nächsten Kontrolle.",
        "Dass Sie im Alltag wenig gebremst sind, lässt uns vor allem in Ruhe und mit klaren Kontrollintervallen arbeiten. "
        "Unser Ziel ist, Ihnen diese gute Ausgangslage möglichst lange zu erhalten.",
    ],
)

_add(
    "PX_SYMPTOMS_MODERATE",
    "Symptome: moderat",
    [
        "Ihre Beschwerden wirken spürbar, aber nicht maximal ausgeprägt. Für die Therapieplanung ist wichtig, ob Sie im Alltag stabil bleiben oder ob die Belastbarkeit weiter abnimmt.",
        "Die Symptome passen zu einer moderaten Einschränkung. Wir nutzen Messwerte und Verlauf gemeinsam, um zu entscheiden, ob und wann Anpassungen nötig sind.",
        "Ihre Beschwerden sind im mittleren Bereich. Das heißt, Sie merken die Einschränkung im Alltag, können aber viele Dinge noch gut bewältigen. Wichtig ist, ob sich das stabil hält.",
        "Bei mittelschweren Beschwerden schauen wir genau, welche Aktivitäten Ihnen schwerfallen. Das hilft uns, die Therapie gezielt an Ihre Bedürfnisse anzupassen.",
        "Ihre Beschwerden sind spürbar vorhanden, aber nicht in der stärksten Ausprägung. Das gibt uns die Möglichkeit, mit gezielten Maßnahmen eine Verbesserung anzustreben.",
        "Eine moderate Einschränkung ist häufig genau der Moment, in dem eine gezielte Therapieoptimierung viel bewirken kann. "
        "Wir schauen, welche Stellschraube – Medikation, Begleiterkrankung, Alltagsroutine – den meisten Gewinn bringt.",
    ],
)

_add(
    "PX_SYMPTOMS_HIGH",
    "Symptome: deutlich",
    [
        "Ihre Beschwerden wirken deutlich. In solchen Situationen hat die klinische Situation oft das gleiche Gewicht wie einzelne Messwerte. Wir planen Kontrollen und Therapie so, dass Sie im Alltag sicher bleiben.",
        "Bei deutlich eingeschränkter Belastbarkeit ist besonders wichtig, Warnzeichen ernst zu nehmen und Veränderungen früh zu besprechen. Dann kann man rechtzeitig gegensteuern.",
        "Ihre Beschwerden schränken den Alltag spürbar ein. Das nehmen wir sehr ernst und richten die Therapie darauf aus, Ihnen so viel Lebensqualität wie möglich zurückzugeben.",
        "Wenn alltägliche Aktivitäten schwerfallen, hat das höchste Priorität bei der Behandlungsplanung. Wir arbeiten daran, die Situation so schnell wie möglich zu stabilisieren.",
        "Deutliche Beschwerden bedeuten, dass wir nicht nur die Messwerte betrachten, sondern vor allem Ihre Lebensqualität in den Mittelpunkt stellen. Wir besprechen, was Ihnen am meisten helfen kann.",
        "Wenn Sie sich im Alltag deutlich eingeschränkt fühlen, ist jede kleine Verbesserung wertvoll. "
        "Wir setzen dort an, wo Sie den größten Unterschied spüren – zum Beispiel beim Treppensteigen, beim Einkaufen oder im Schlaf.",
    ],
)

_add(
    "PX_SYMPTOMS_SYNCOPE",
    "Symptome: Synkope",
    [
        "Ohnmacht oder Beinahe-Ohnmacht ist bei Lungengefäß-Erkrankungen ein wichtiges Warnsignal. Das bedeutet nicht automatisch Gefahr im Moment, sollte aber konsequent und zeitnah abgeklärt werden.",
        "Wenn es zu Ohnmacht oder Beinahe-Ohnmacht kommt, kann das darauf hinweisen, dass Kreislauf und rechtes Herz unter Belastung an Grenzen kommen. Bitte sprechen Sie neue Episoden immer zeitnah an.",
        "Schwindelanfälle oder kurzzeitige Bewusstlosigkeit sind ein ernstzunehmendes Signal. Wir klären das gezielt ab, um Ihre Sicherheit im Alltag zu gewährleisten.",
        "Ohnmachtsanfälle können bei Lungenhochdruck auftreten, wenn das Herz vorübergehend nicht genug Blut in den Kreislauf pumpen kann. Das erfordert eine zeitnahe Abklärung und gegebenenfalls Therapieanpassung.",
        "Falls Sie Schwindelanfälle, Schwarzwerden vor den Augen oder Bewusstlosigkeit erleben, melden Sie das bitte immer sofort. Diese Symptome haben für uns bei der Behandlungsplanung ein hohes Gewicht.",
        "Bei Ohnmachten ist es hilfreich, die Umstände zu notieren: Was haben Sie gerade gemacht? Wie lange hat es gedauert? Gab es Vorzeichen? "
        "Diese Details geben uns wertvolle Hinweise für die richtige Einordnung und die sinnvollste Therapieanpassung.",
    ],
)

_add(
    "PX_DISCORDANCE_HIGH_MPAP_LOW_BNP",
    "Diskrepanz: hoher Druck, aber niedriger BNP",
    [
        "Manchmal sind die Druckwerte deutlich erhöht, während der Blutwert BNP oder NT-proBNP eher niedrig bleibt. Das kann passieren, wenn das rechte Herz die Situation noch gut kompensiert oder wenn der Blutwert durch andere Faktoren beeinflusst wird. Entscheidend ist dann die Gesamtschau aus Beschwerden, Belastbarkeit und Verlauf.",
        "Ein niedriger BNP oder NT-proBNP Wert schließt eine relevante Druckerhöhung nicht aus. Umgekehrt bedeutet ein hoher Druck nicht immer, dass das Herz bereits überlastet ist. Deshalb betrachten wir Messwerte, Symptome und Verlauf gemeinsam.",
    ],
)

_add(
    "PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS",
    "Diskrepanz: eher niedriger Druck, aber deutliche Beschwerden",
    [
        "Es kann vorkommen, dass Druckwerte in Ruhe nur leicht erhöht oder unauffällig sind, Beschwerden aber deutlich sind. Häufig spielen dann Belastungssituationen, Begleiterkrankungen der Lunge oder des linken Herzens, Blutarmut oder der Trainingszustand eine Rolle. Deshalb ist die Abklärung oft breiter als nur die Druckwerte.",
        "Wenn Symptome stärker sind als es eine einzelne Zahl erwarten lässt, schauen wir besonders auf Belastungstests, Lungenfunktion, Bildgebung und den Verlauf. So lässt sich meist erklären, welcher Faktor im Alltag den größten Anteil hat.",
    ],
)

_add(
    "PX_DISCORDANCE_ECHO_GOOD_CATH_HIGH",
    "Diskrepanz: Echo wirkt unauffällig, Katheter zeigt höhere Werte",
    [
        "Ultraschall (Echo) und Herzkatheter messen unterschiedliche Dinge. Das Echo schätzt Druckwerte indirekt und kann unauffällig wirken, auch wenn der Katheter eine Druckerhöhung zeigt. Der Katheter ist für die Druckmessung der zuverlässigere Test.",
        "Wenn Echo und Katheter nicht perfekt zusammenpassen, ist das nicht ungewöhnlich. Dann nutzen wir den Katheter als Referenz und schauen ergänzend, wie das rechte Herz im Echo arbeitet und wie sich die Belastbarkeit entwickelt.",
        "Das Echo ist ein gutes Werkzeug, um die Herzfunktion zu beurteilen, aber für die genaue Druckmessung ist der Herzkatheter verlässlicher. Die scheinbar widersprüchlichen Ergebnisse ergänzen sich in der Gesamtbeurteilung.",
        "Dass das Echo ruhig wirkt, bedeutet nicht, dass es falsch war – es zeigt, dass die Herzfunktion erhalten ist. Der Katheter fügt Informationen über die Durchblutung der Lunge hinzu, die im Ultraschall nur schwer direkt zu erfassen sind.",
        "Leichte bis mittlere Druckerhöhungen werden vom Echo oft nicht sicher erkannt, weil die Schallfenster begrenzt sind und die Schätzung von der Jet-Qualität abhängt. Der Katheter schließt diese Lücke mit einer direkten Messung.",
        "Für den weiteren Weg bedeutet das: Wir orientieren uns an den Katheterwerten und nutzen das Echo vor allem, um Veränderungen der Herzfunktion im Verlauf zu beobachten. So ergänzen sich beide Untersuchungen sinnvoll.",
    ],
)

_add(
    "PX_TREND_SUBTYPE_PRESSURE_BETTER_PVR_WORSE",
    "Verlaufstyp: Druck besser, Widerstand schlechter",
    [
        "Ein Teil der Werte ist besser, ein anderer ungünstiger. Wenn der Druck etwas fällt, der Widerstand aber steigt, kann das zum Beispiel an Messstreuung, dem Flüssigkeitshaushalt oder einer veränderten Durchblutung der Lunge liegen. Wichtig ist dann, welche Veränderung am besten zu Ihren Beschwerden passt.",
        "Wenn Druck und Widerstand unterschiedliche Richtungen zeigen, schauen wir besonders auf Pumpleistung, Rückstau und Belastbarkeit. Daraus ergibt sich, welcher Teil klinisch entscheidend ist.",
        "Gegenläufige Veränderungen von Druck und Widerstand sind nicht ungewöhnlich. Für die Behandlung orientieren wir uns an dem Wert, der am besten zu Ihren Beschwerden und zum Gesamtbild passt.",
        "Entscheidend ist nicht eine einzelne Zahl, sondern der Eindruck im Alltag: Wenn Sie sich gleich gut oder besser belastbar fühlen und keine Warnzeichen auftreten, ist das in dieser Konstellation ein wichtiges, beruhigendes Signal.",
        "Druck und Widerstand hängen nicht starr zusammen – sie werden vom Fluss, vom Füllungszustand und vom Lungengefäßbett beeinflusst. Ein Auseinanderdriften ist deshalb oft erklärbar und nicht automatisch ein Rückschlag.",
        "Für die weitere Planung hilft uns eine Kontrollmessung unter gleichen Bedingungen, zusammen mit Ihrer Rückmeldung zur Belastbarkeit. Erst in der Zusammenschau zeigt sich, ob der Trend echt ist oder Messstreuung widerspiegelt.",
    ],
)

_add(
    "PX_TREND_SUBTYPE_EFFECT_UNCLEAR",
    "Verlaufstyp: Therapieeffekt unklar",
    [
        "Wenn sich einzelne Werte nur wenig verändern oder unterschiedliche Richtungen zeigen, kann der Therapieeffekt noch unklar sein. Dann hilft oft eine Verlaufskontrolle mit denselben Messmethoden und ein Blick auf Belastbarkeit und Symptome.",
        "Nicht jede Veränderung ist sofort eindeutig. Entscheidend ist, ob Sie sich im Alltag stabiler fühlen und ob Warnzeichen auftreten. Das besprechen wir gezielt im Verlauf.",
        "Ein unklarer Therapieeffekt bedeutet nicht, dass die Behandlung versagt hat. Manchmal braucht es einfach mehr Zeit oder eine Kontrollmessung unter gleichen Bedingungen, um den Effekt richtig beurteilen zu können.",
        "Gerade frühe Kontrollen zeigen oft noch keinen klaren Ausschlag – Medikamente brauchen Wochen, manchmal Monate, um ihre volle Wirkung zu entfalten. Geduld und kontinuierliche Einnahme sind jetzt am wichtigsten.",
        "Wir legen großen Wert auf Ihre eigene Wahrnehmung: Gehen Sie Treppen leichter hoch? Schlafen Sie ruhiger? Halten Sie längere Wege durch? Solche Alltagshinweise sind manchmal aussagekräftiger als eine einzelne Zahl.",
        "Eine unklare Zwischenbilanz ist ein Grund für genaues Beobachten, kein Grund zur Sorge. Wir planen eine Kontrolle unter gleichen Bedingungen und entscheiden dann gemeinsam, ob die Therapie angepasst werden sollte.",
    ],
)

_add(
    "PX_INCOMPLETE",
    "Einordnung derzeit nicht eindeutig",
    [
        "Die Messwerte sind noch **nicht vollständig** oder liegen in einem Bereich, der sich nicht eindeutig einordnen lässt. Das ist nicht ungewöhnlich – dann braucht es meist zusätzliche Informationen.",
        "Aktuell lässt sich aus den Messwerten **keine eindeutige Einordnung** ableiten. In solchen Situationen sind Ihre Beschwerden und ergänzende Untersuchungen besonders wichtig.",
        "Einige Werte fehlen noch oder liegen in einem Grenzbereich. Das kommt vor und bedeutet nicht, dass etwas übersehen wurde. Wir ergänzen die fehlenden Informationen, um eine sichere Einordnung zu ermöglichen.",
        "Für eine vollständige Beurteilung brauchen wir noch ergänzende Informationen. Sobald diese vorliegen, können wir die Situation klarer einordnen und die nächsten Schritte planen.",
        "Ein Befund, der sich noch nicht klar einordnen lässt, ist in diesem Bereich häufig – der Körper passt nicht immer sauber in Lehrbuch-Kategorien. Mit gezielter Zusatzdiagnostik lässt sich meist die nötige Klarheit gewinnen.",
        "Bitte verstehen Sie, dass manchmal mehr als ein Termin nötig ist, um ein vollständiges Bild zu bekommen. Die bisherigen Messungen sind wertvolle Bausteine; wir brauchen nur noch einige Puzzleteile, um das Gesamtbild zuverlässig zusammenzusetzen.",
    ],
)

_add(
    "PX_WHAT_IS_PH",
    "Was bedeutet Lungenhochdruck?",
    [
        "Wenn der Blutdruck in den Gefäßen der Lunge erhöht ist, muss die rechte Herzhälfte **mehr arbeiten**. Das kann Luftnot, Müdigkeit oder Wassereinlagerungen erklären.",
        "Eine Druckerhöhung in den Blutgefäßen der Lunge kann **verschiedene Ursachen** haben. Entscheidend ist, *wo* der Druckanstieg entsteht – zum Beispiel eher in den Lungengefäßen selbst, durch die linke Herzseite oder durch ältere Blutgerinnsel.",
        "Lungenhochdruck ist **kein einzelnes Krankheitsbild**. Die Ursache kann sehr unterschiedlich sein. Darum ist die genaue Einordnung wichtig, damit wir die passende Behandlung auswählen.",
        "Wichtig für die Einordnung: Nicht jede Druckerhöhung bedeutet dasselbe. Erst das Zusammenspiel aus Messwerten, Beschwerden und Begleiterkrankungen zeigt, welche Ursache am wahrscheinlichsten ist.",
        "Bei Lungenhochdruck sind die Blutgefäße in der Lunge verengt oder versteift. Das rechte Herz muss stärker pumpen, um das Blut durch die Lunge zu befördern. Deshalb können Beschwerden wie Luftnot und Erschöpfung auftreten.",
        "Es gibt verschiedene Formen von Lungenhochdruck. Manche entstehen durch die Lungengefäße selbst, andere durch Erkrankungen des linken Herzens oder der Lunge. Die genaue Unterscheidung ist wichtig, weil sich die Behandlung danach richtet.",
        "Vereinfacht gesagt: Das Blut muss bei jedem Herzschlag durch die Lunge fließen. Wenn die Gefäße dort enger oder steifer werden, steigt der Druck und das rechte Herz wird stärker belastet. Ziel der Behandlung ist, diese Belastung zu verringern.",
        "Lungenhochdruck bedeutet, dass die rechte Herzhälfte gegen einen erhöhten Widerstand arbeiten muss. Das kann sich durch Luftnot, schnelle Erschöpfung oder Wassereinlagerungen bemerkbar machen. Die Ursache zu klären ist der erste Schritt zur richtigen Therapie.",
    ],
)


_add(
    "PX_HEMO_EXPLAIN",
    title="Kurz erklärt: was die wichtigsten Zahlen bedeuten",
    templates=[
        "Die wichtigsten Messwerte lassen sich so verstehen: "
        "**mPAP** beschreibt den durchschnittlichen Druck in den Lungengefäßen. "
        "**PAWP** ist ein Hinweis darauf, ob sich Blut vor der linken Herzhälfte „staut“. "
        "**PVR** beschreibt den Widerstand in den Lungengefäßen (erhöht z.B. bei verengten/steifen Gefäßen). "
        "**CI** beschreibt die Pumpleistung bezogen auf die Körpergröße. "
        "**RAP** ist ein Hinweis auf Rückstau im Körperkreislauf. "
        "Entscheidend ist immer die Kombination dieser Werte – nicht eine Zahl allein.",
        "Kurz zur Orientierung: mPAP = Druck in der Lunge, PAWP = Rückstau vor dem linken Herzen, "
        "PVR = Widerstand in den Lungengefäßen, CI = Pumpleistung, RAP = Rückstau im Körper. "
        "Aus dem Muster dieser Werte lässt sich ableiten, welche Ursachen wahrscheinlicher sind und welche nächsten Schritte sinnvoll sind.",
        "Bei der Herzkatheter-Untersuchung werden mehrere Werte gemessen. "
        "Der **Lungendruck** zeigt, wie stark die rechte Herzhälfte arbeiten muss. "
        "Der **Füllungsdruck** links hilft zu erkennen, ob die linke Herzseite beteiligt ist. "
        "Der **Gefäßwiderstand** zeigt, wie eng oder steif die Lungengefäße sind. "
        "Die **Pumpleistung** zeigt, ob das Herz genug Blut in den Kreislauf bringt. "
        "Zusammen ergeben diese Werte ein Gesamtbild.",
        "Sie werden in Ihrem Befund einige Abkürzungen finden. "
        "**mPAP** steht für den durchschnittlichen Druck in der Lunge. "
        "**PAWP** zeigt, ob Blut vor dem linken Herzen zurückgestaut wird. "
        "**PVR** misst den Widerstand in den Lungengefäßen. "
        "**CI** gibt an, wie gut das Herz pumpt. "
        "Keine einzelne Zahl erzählt die ganze Geschichte – erst das Zusammenspiel ist aussagekräftig.",
        "Manche Werte beschreiben den Druck, andere die Leistung oder den Widerstand. "
        "Entscheidend ist das Muster: Ein erhöhter Druck bei gleichzeitig hohem Widerstand spricht für eine Veränderung in den Lungengefäßen selbst. "
        "Ein erhöhter Rückstau vor dem linken Herzen weist eher auf eine Beteiligung der linken Herzseite hin. "
        "So lässt sich aus der Zahlenkonstellation ableiten, welche Ursache am wahrscheinlichsten ist.",
        "Als Orientierung: Der Lungendruck (mPAP) beschreibt die Belastung für das rechte Herz. "
        "Der Füllungsdruck (PAWP) zeigt, ob die linke Herzseite mitbeteiligt ist. "
        "Der Widerstand (PVR) gibt Hinweise auf Veränderungen in den Lungengefäßen. "
        "Die Pumpleistung (CI) sagt aus, wie gut das Herz den Körper versorgt. "
        "Diese Größen ergänzen sich – erst gemeinsam erlauben sie eine verlässliche Einordnung.",
    ],
)



_add(
    "PX_VOLUME_CHALLENGE",
    "Volumenchallenge",
    [
        "Manchmal geben wir während der Untersuchung gezielt eine definierte Menge Flüssigkeit über die Vene. Damit prüfen wir, ob der Druck auf der linken Herzseite dabei auffällig ansteigt. Das kann helfen, eine Mitbeteiligung der linken Herzhälfte besser einzuordnen.",
        "Bei der Volumenchallenge wird kontrolliert Flüssigkeit gegeben. Wir schauen dann, ob sich der Füllungsdruck im linken Herzen deutlich erhöht. Das ist ein Hinweis darauf, dass es unter mehr Blutvolumen leichter zu einem Rückstau in die Lunge kommt.",
        "Durch die gezielte Gabe von Flüssigkeit können wir testen, wie das linke Herz auf eine erhöhte Füllung reagiert. Steigt der Druck dabei deutlich an, spricht das für eine versteckte Beteiligung der linken Herzseite.",
        "Die Volumenchallenge ist ein wichtiger Zusatztest. Manchmal zeigt sich erst unter mehr Flüssigkeit, dass die linke Herzseite nicht so gut arbeitet wie erwartet. Das kann die Therapiewahl entscheidend beeinflussen.",
        "Der Volumentest simuliert eine alltagsnahe Situation mit höherer Anforderung – zum Beispiel nach einer größeren Mahlzeit oder unter Belastung –, in der das Herz mehr Blut bewältigen muss. So werden Schwächen sichtbar, die in Ruhe verborgen bleiben.",
        "Sie werden während des Tests vielleicht bemerken, dass Sie sich etwas voller fühlen oder nach der Untersuchung einen kurzen Harndrang haben. Das ist eine normale, harmlose Reaktion auf die zusätzliche Flüssigkeit.",
    ],
)

_add(
    "PX_VASOREACTIVITY",
    "Vasoreaktivität",
    [
        "Bei der Vasoreaktivität wird ein kurzwirksames Testmedikament eingesetzt. Damit prüfen wir, ob sich die Lungengefäße im Test deutlich entspannen. Das kann in ausgewählten Fällen Einfluss auf die Therapieplanung haben.",
        "Bei diesem Zusatztest schauen wir, ob die Lungengefäße auf ein kurzfristig gegebenes Medikament spürbar reagieren. Eine deutliche Reaktion kann therapeutisch bedeutsam sein.",
        "Die Vasoreaktivitätstestung zeigt uns, ob die Lungengefäße noch die Fähigkeit haben, sich zu entspannen. Bei einer deutlich positiven Reaktion können bestimmte Medikamente besonders gut wirken.",
        "Mit einem kurzwirksamen Medikament testen wir, wie flexibel die Lungengefäße noch reagieren. Das Ergebnis kann den Therapieplan maßgeblich beeinflussen, weil manche Medikamente nur bei guter Reaktion sinnvoll sind.",
        "Das Testmedikament wirkt nur wenige Minuten und wird rasch wieder abgebaut. Sie können während des Tests kurz ein leichtes Gefühl wie Kopfwärme oder leichten Kopfdruck verspüren – das geht von selbst zurück.",
        "Auch ein Test ohne ausgeprägte Reaktion ist aussagekräftig – er hilft uns, die Therapieauswahl einzugrenzen und Medikamente auszuschließen, die in Ihrem Fall weniger wirksam wären.",
    ],
)

_add(
    "PX_INTERPRETATION",
    "Wie ordnen wir das ein?",
    [
        "Die Messwerte sind ein wichtiger Baustein. Für die Gesamtbeurteilung schauen wir zusätzlich auf Bildgebung, Ultraschall des Herzens, Lungenfunktion und Ihre Beschwerden.",
        "Wichtig ist die Zusammenschau: Messwerte, Beschwerden und weitere Untersuchungen gehören zusammen. Erst daraus leiten wir das sinnvollste Vorgehen ab.",
        "Zusätzlich zu den Zahlen berücksichtigen wir, wie belastbar Sie im Alltag sind und wie sich die Befunde im Verlauf entwickeln. So entsteht eine Einordnung, die besser zu Ihrer persönlichen Situation passt.",
        "Eine einzelne Messung ist immer nur ein Puzzleteil. Zusammen mit Ihren Beschwerden, dem Herzultraschall und der Vorgeschichte ergibt sich ein vollständiges Bild, auf dem wir die Therapie aufbauen.",
        "Für die Einordnung betrachten wir nicht nur die Kathetermessung allein. Laborwerte, Bildgebung, Lungenfunktion und vor allem Ihre persönliche Belastbarkeit fließen in die Bewertung ein.",
        "Wir stellen die Messergebnisse in den Zusammenhang mit allem, was wir über Ihre Gesundheit wissen. Nur so können wir eine Einordnung treffen, die wirklich zu Ihrer Situation passt.",
    ],
)


# ---------------------------------------------------------------------------
# Hämodynamische Einordnung (Ruhe)
# ---------------------------------------------------------------------------

_add(
    "PX_PRECAP_MILD",
    "Präkapilläre Druckerhöhung – eher leicht",
    [
        "Die Messwerte sprechen für eine **leichtere Druckerhöhung** in den Blutgefäßen der Lunge. Das deutet darauf hin, dass die Ursache eher in den Lungengefäßen oder in der Lunge selbst liegen kann.",
        "Es gibt Hinweise auf eine **leichtere Druckerhöhung** in den Blutgefäßen der Lunge. Häufig entsteht so etwas eher durch Veränderungen in den Lungengefäßen oder durch eine Lungenerkrankung.",
        "Der Druck in den Lungengefäßen ist **leicht erhöht**. Die Ursache liegt dabei eher in den Lungengefäßen selbst als in der linken Herzseite. Wir klären die genaue Ursache weiter ab.",
        "Die Messung zeigt eine **milde Druckerhöhung** in den Lungengefäßen. Das ist ein Befund, den wir beobachten und weiter abklären, aber der nicht zwingend sofort eine Therapie erfordert.",
        "Es besteht eine **leichtgradige Druckerhöhung** in den Blutgefäßen der Lunge. Die linke Herzseite scheint nicht die Hauptursache zu sein. Zur genauen Zuordnung sind weitere Untersuchungen hilfreich.",
        "Gute Nachricht: Eine leichtere Druckerhöhung erkannt wir oft in einer Phase, in der wir gut vorbeugend handeln können. "
        "Gemeinsam schauen wir, welche Maßnahmen jetzt den meisten Nutzen bringen – und was sich sinnvoll beobachten lässt.",
    ],
)

_add(
    "PX_PRECAP_MOD",
    "Präkapilläre Druckerhöhung – mittel",
    [
        "Die Messwerte sprechen für eine **Druckerhöhung**, die eher in den Blutgefäßen der Lunge oder in der Lunge selbst entsteht.",
        "Die Untersuchung zeigt Hinweise auf einen Lungenhochdruck, bei dem die Ursache eher **vor** der linken Herzseite liegt – also eher in der Lunge bzw. den Lungengefäßen.",
        "Es liegt eine **mittelschwere Druckerhöhung** in den Lungengefäßen vor. Die Ursache scheint in den Lungengefäßen selbst oder in der Lunge zu liegen.",
        "Die Messung bestätigt einen **Lungenhochdruck mittlerer Ausprägung**. Die linke Herzseite scheint nicht die Hauptursache zu sein. Eine gezielte Ursachenabklärung und Therapieplanung sind jetzt wichtig.",
        "Der Druck in den Lungengefäßen ist **deutlich über dem Normalbereich**. Dieses Muster spricht dafür, dass die Veränderung in den Lungengefäßen selbst liegt. Eine strukturierte Abklärung hilft, die beste Behandlung zu finden.",
        "Eine mittelgradige Druckerhöhung ist für uns eine klare Handlungsaufforderung, aber kein Grund zur Panik. "
        "Wir haben heute gute medikamentöse Möglichkeiten, die Belastung zu senken und die Belastbarkeit im Alltag zu bewahren.",
    ],
)

_add(
    "PX_PRECAP_SEV",
    "Präkapilläre Druckerhöhung – deutlich",
    [
        "Die Messwerte sprechen für eine **deutliche Druckerhöhung** in den Blutgefäßen der Lunge. Das sollte zeitnah in einem spezialisierten Team weiter eingeordnet werden.",
        "Es liegt eine **ausgeprägte Druckerhöhung** in den Blutgefäßen der Lunge nahe. Dafür ist eine strukturierte Ursachenabklärung und Therapieplanung wichtig.",
        "Die Druckwerte in den Lungengefäßen sind **deutlich erhöht**. Das bedeutet, dass das rechte Herz erheblich mehr arbeiten muss. Eine zeitnahe Therapieeinleitung und spezialisierte Betreuung sind sinnvoll.",
        "Es besteht eine **ausgeprägte Druckerhöhung** in den Lungengefäßen. Die Ursache liegt nicht in der linken Herzseite, sondern in den Lungengefäßen selbst. In einem spezialisierten Zentrum stehen gezielte Behandlungsmöglichkeiten zur Verfügung.",
        "Die Messung zeigt eine **schwere Druckerhöhung** in den Blutgefäßen der Lunge. Das erfordert eine rasche und gezielte Abklärung der Ursache sowie den Beginn einer passenden Behandlung.",
        "Auch wenn die Werte deutlich erhöht sind: Bei dieser Form der Druckerhöhung stehen heute mehrere Medikamenten-Klassen zur Verfügung, die oft in Kombination verordnet werden. "
        "Das Ziel ist, Ihre Lebensqualität und Belastbarkeit möglichst rasch und dauerhaft zu verbessern.",
    ],
)

_add(
    "PX_POSTCAP",
    "Druckerhöhung durch die linke Herzseite",
    [
        "Die Messwerte sprechen dafür, dass der Druckanstieg vor allem durch die **linke Herzseite** mitbedingt ist. Das kann zu einer Rückstau-Situation Richtung Lunge führen.",
        "Die Messwerte passen eher zu einer Situation, bei der die **linke Herzseite** eine wichtige Rolle spielt. Dadurch kann sich Druck in Richtung Lungengefäße übertragen.",
        "Die Untersuchung zeigt, dass die Druckerhöhung in der Lunge vor allem durch einen **Rückstau von der linken Herzseite** entsteht. Die Behandlung richtet sich daher in erster Linie auf das linke Herz.",
        "Der erhöhte Druck in den Lungengefäßen wird hauptsächlich durch die **linke Herzseite** verursacht. Das ist ein häufiges Muster, für das es bewährte Behandlungsansätze gibt.",
        "Die Messung zeigt ein typisches Muster: Die linke Herzseite kann das Blut nicht ideal weiterleiten, und der Druck staut sich zurück in die Lungengefäße. Die Therapie setzt daher vor allem an der linken Herzseite an.",
        "Eine postkapilläre Druckerhöhung hat den Vorteil, dass wir meist auf etablierte, gut erprobte Behandlungen für die linke Herzseite zurückgreifen können. "
        "Wenn die Grunderkrankung gut eingestellt ist, bessert sich in der Regel auch der Druck in den Lungengefäßen.",
    ],
)

_add(
    "PX_CPCPH",
    "Gemischte Druckerhöhung",
    [
        "Die Messwerte sprechen für eine **Mischkonstellation**: Es gibt Anzeichen für einen Druckanstieg durch die linke Herzseite und zusätzlich Hinweise auf eine zusätzliche Verengung in den Lungengefäßen.",
        "Die Befunde passen zu einer **kombinierten Situation**: Druckübertragung von der linken Herzseite und zugleich eine zusätzliche Belastung der Lungengefäße.",
        "Es handelt sich um eine **gemischte Druckerhöhung**: Die linke Herzseite und die Lungengefäße tragen beide zur Druckerhöhung bei. Die Behandlung muss deshalb beide Seiten berücksichtigen.",
        "Die Messung zeigt ein **kombiniertes Muster**: Zum einen überträgt die linke Herzseite Druck auf die Lunge, zum anderen reagieren die Lungengefäße selbst mit einer zusätzlichen Verengung. Das erfordert eine differenzierte Therapie.",
        "Die Druckerhöhung hat **zwei Komponenten**: eine Belastung durch die linke Herzseite und eine eigenständige Veränderung der Lungengefäße. Beide müssen bei der Behandlung berücksichtigt werden.",
        "Bei einer Mischkonstellation arbeiten wir oft schrittweise: zuerst die linke Herzseite optimieren, dann prüfen, wieviel der Lungengefäß-Komponente dadurch zurückgeht. "
        "So finden wir das richtige Maß und vermeiden unnötige Medikamente.",
    ],
)

# ---------------------------------------------------------------------------
# Hämodynamik unter Belastung
# ---------------------------------------------------------------------------

_add(
    "PX_EX_LEFT",
    "Auffällige Druckantwort unter Belastung – eher linke Herzseite",
    [
        "In Ruhe waren die Werte nicht eindeutig auffällig. **Unter körperlicher Belastung** zeigt sich aber ein Druckanstieg, der eher zu einer Belastung der linken Herzseite passt.",
        "Die Messung unter Belastung deutet darauf hin, dass die linke Herzseite bei körperlicher Aktivität stärker unter Druck gerät. Das kann eine Erklärung für Luftnot bei Belastung sein.",
        "Erst unter körperlicher Anstrengung wird sichtbar, dass die linke Herzseite den erhöhten Blutfluss nicht optimal bewältigt. Das erklärt, warum Beschwerden vor allem bei Aktivität auftreten.",
        "Die Belastungsmessung zeigt, dass sich bei Anstrengung Blut vor der linken Herzseite staut. In Ruhe ist das noch nicht auffällig. Dieses Muster ist häufig und lässt sich gezielt behandeln.",
        "Unter Belastung muss das Herz in kürzerer Zeit mehr Blut bewegen. Dabei wird erkennbar, dass die Anpassungsfähigkeit der linken Herzseite eingeschränkt ist – eine wertvolle Information für eine gezielte Therapie.",
        "Die gute Nachricht: Weil wir dieses Muster erkannt haben, können wir gezielt darauf reagieren. Viele Ursachen einer belastungsabhängigen Einschränkung der linken Herzseite sprechen gut auf Medikamente, Training und Lebensstilmaßnahmen an.",
    ],
)

_add(
    "PX_EX_PVASC",
    "Auffällige Druckantwort unter Belastung – eher Lungengefäße",
    [
        "In Ruhe waren die Werte nicht eindeutig auffällig. **Unter körperlicher Belastung** zeigt sich aber ein Muster, das eher zu einer Belastung der Lungengefäße passt.",
        "Bei Belastung steigt der Druck in den Lungengefäßen stärker an als erwartet. Das kann helfen, eine beginnende Erkrankung der Lungengefäße früh zu erkennen.",
        "Unter körperlicher Anstrengung reagieren die Lungengefäße mit einem übermäßigen Druckanstieg. Das kann ein frühes Zeichen dafür sein, dass die Lungengefäße weniger elastisch sind als normal.",
        "Die Ruhewerte allein hätten diesen Befund nicht gezeigt. Erst die Belastung macht sichtbar, dass die Lungengefäße unter Druck geraten. Deshalb war die Belastungsmessung hier besonders wichtig.",
        "Ein auffälliger Druckanstieg der Lungengefäße unter Belastung kann erklären, warum Sie bei Aktivität deutlich kurzatmiger werden, als die Ruhewerte vermuten lassen. Es ist ein feines, aber klinisch bedeutsames Signal.",
        "In vielen Fällen ist dieses Muster ein frühes Warnsignal, das uns ermöglicht, vorsorglich zu handeln – durch engmaschigere Kontrollen, Empfehlungen zum Lebensstil und gegebenenfalls ausgewählte Medikamente.",
    ],
)

_add(
    "PX_UNCLASSIFIED",
    "Nicht eindeutig zuzuordnende Konstellation",
    [
        "Die Messwerte liegen in einem Bereich, der sich nicht eindeutig einer bestimmten Form von Lungenhochdruck zuordnen lässt. "
        "Das bedeutet nicht, dass alles unklar bleibt — es bedeutet, dass wir sorgfältig die Gesamtsituation betrachten und gegebenenfalls weitere Informationen einholen.",
        "Die Druckwerte sind zwar erhöht, aber das Muster passt nicht klar in eine einzelne Kategorie. "
        "Solche Konstellationen sehen wir häufiger und sie erfordern eine besonders gründliche Gesamtschau aus Vorgeschichte, Bildgebung und Laborwerten.",
        "Die Ergebnisse zeigen eine Druckerhöhung, deren genaue Ursache aus den Kathetermesswerten allein noch nicht sicher eingeordnet werden kann. "
        "Das ist kein Grund zur Sorge, sondern ein normaler Schritt auf dem Weg zur richtigen Einordnung.",
        "In Ihrem Fall zeigt die Messung ein Bild, das zwischen verschiedenen Mustern liegt. "
        "Das kommt vor und erfordert eine schrittweise Abklärung, um die richtige Ursache und den besten Weg zu finden.",
        "Nicht jede Druckerhöhung lässt sich sofort einer eindeutigen Kategorie zuordnen – gerade Grenzbefunde sind ein häufiger Anlass, genauer hinzusehen. "
        "Die Einordnung gelingt dann am besten aus der Kombination von Messwerten, Bildgebung, Labor und Ihren Beschwerden.",
        "Wenn die Messwerte sich nicht eindeutig zuordnen lassen, ist das oft ein Hinweis darauf, dass mehrere Faktoren zusammenwirken. "
        "Wir nähern uns Schritt für Schritt und können in aller Regel im Verlauf eine klare Aussage treffen, auf der die Therapie aufbauen kann.",
    ],
)

_add(
    "PX_HIGH_FLOW",
    "Druckerhöhung bei hohem Blutfluss",
    [
        "Die Druckerhöhung scheint in Ihrem Fall mit einem **ungewöhnlich hohen Blutfluss** zusammenzuhängen. "
        "Das bedeutet, dass die Lungengefäße selbst möglicherweise nicht verengt sind, sondern durch die Menge an Blut, die durchfließt, überlastet werden.",
        "Wenn das Herz besonders viel Blut pumpt, kann der Druck in den Lungengefäßen allein dadurch ansteigen. "
        "In solchen Fällen suchen wir nach der Ursache des erhöhten Blutflusses — das können zum Beispiel eine Blutarmut, eine Schilddrüsenüberfunktion oder andere Zustände sein.",
        "Die Messung zeigt einen hohen Blutfluss durch die Lungengefäße. Das erklärt wahrscheinlich einen Teil der Druckerhöhung. "
        "Die Behandlung richtet sich in erster Linie nach der Ursache des erhöhten Blutflusses.",
        "Der Druck in den Lungengefäßen ist erhöht, aber der Widerstand ist nicht wesentlich gesteigert. "
        "Das spricht dafür, dass vor allem die Menge des durchfließenden Blutes für die Druckwerte verantwortlich ist. Wir klären die Ursache dafür ab.",
        "Eine hochflussbedingte Druckerhöhung ist eine wichtige Unterscheidung, weil sich die Behandlung grundlegend von anderen Formen unterscheidet. "
        "Wir klären, welcher zugrunde liegende Auslöser – zum Beispiel Schilddrüse, Blutarmut oder ein Shunt – den hohen Fluss verursacht.",
        "Wenn vor allem der hohe Blutfluss für die Druckwerte verantwortlich ist, ist das eine gute Nachricht: "
        "Meistens lässt sich die Grundursache gut behandeln, und damit normalisiert sich auch die Druckkonstellation in den Lungengefäßen.",
    ],
)

_add(
    "PX_SOTATERCEPT_INFO",
    "Neuer Therapieansatz: Sotatercept",
    [
        "In Ihrer Therapieplanung wird ein neueres Medikament namens **Sotatercept** erwähnt. "
        "Dieses Medikament wirkt über einen besonderen Signalweg (BMPR2/Activin-Pfad) und kann bei bestimmten Formen der pulmonal-arteriellen Hypertonie den Druck in den Lungengefäßen senken und die Belastbarkeit verbessern.",
        "Sotatercept ist ein neuartiger Therapieansatz, der an einer anderen Stelle angreift als die bisherigen Medikamente. "
        "Es wird als Ergänzung zur bestehenden Behandlung eingesetzt und in spezialisierten PH-Zentren verordnet.",
        "In Ihrem Fall wird Sotatercept als Therapieoption besprochen. Dieses Medikament richtet sich gezielt gegen Veränderungen in der Gefäßwand der Lungengefäße. "
        "Es wird als Spritze unter die Haut verabreicht und engmaschig überwacht.",
        "Das Medikament Sotatercept ist ein neuer Baustein in der Behandlung. "
        "Es kann zusätzlich zu bestehenden Medikamenten helfen, die Lungengefäße zu entlasten. Ob es in Ihrer Situation passend ist, wird im PH-Zentrum individuell geprüft.",
        "Mit Sotatercept steht seit Kurzem eine Therapieoption zur Verfügung, die direkt an den krankhaften Umbauprozessen der Lungengefäße ansetzt. "
        "Studien zeigen: Viele Patientinnen und Patienten werden belastbarer, und die Druckwerte bessern sich deutlich.",
        "Für die Entscheidung, ob Sotatercept für Sie sinnvoll ist, braucht es eine genaue Einordnung Ihrer Erkrankung und bereits laufender Therapien. "
        "Das wird im spezialisierten PH-Zentrum sorgfältig geprüft und ausführlich mit Ihnen besprochen.",
    ],
)

# ---------------------------------------------------------------------------
# Zusatzbefunde / Ursache-Hinweise (vorsichtig formuliert)
# ---------------------------------------------------------------------------


_add(
    "PX_GROUP1_HINT",
    title="Mögliche seltenere Ursache: Erkrankung der Lungengefäße selbst",
    templates=[
        "In manchen Situationen kann (auch) eine Erkrankung der kleinen Lungengefäße selbst eine Rolle spielen. "
        "Das kann z.B. im Zusammenhang mit bestimmten Autoimmun-/Rheuma-Erkrankungen, seltenen genetischen Veränderungen "
        "oder bestimmten Infektionen auftreten. "
        "Um das sicher einzuordnen, sind oft spezielle Laborwerte, eine genaue Bildgebung und die Beurteilung im spezialisierten PH-Zentrum sinnvoll.",
        "Wenn neben anderen Ursachen auch eine sogenannte „pulmonal-arterielle“ Form in Frage kommt, "
        "wird häufig eine gezielte Zusatzdiagnostik empfohlen (z.B. Autoimmun- und Virus-Tests, ggf. genetische Abklärung). "
        "Das dient vor allem dazu, die bestmögliche, individuell passende Therapie zu finden.",
        "Eine Erkrankung der kleinen Lungengefäße selbst ist selten, aber gut behandelbar, wenn sie frühzeitig erkannt wird. "
        "Deshalb empfehlen wir in Ihrer Situation eine gezielte Abklärung in einem spezialisierten Zentrum.",
        "Bei Hinweisen auf eine eigenständige Erkrankung der Lungengefäße gibt es heute gezielte Medikamente, "
        "die den Druck senken und die Belastbarkeit verbessern können. Voraussetzung ist eine sorgfältige Einordnung der Ursache.",
        "Diese Form der Lungenhochdruck-Erkrankung ist selten, aber sehr gut erforscht. "
        "Wenn sich der Verdacht bestätigt, stehen wirksame Medikamente zur Verfügung, die gezielt an den betroffenen Gefäßen ansetzen.",
        "Eine sorgfältige Ursachensuche ist bei dieser Form besonders wichtig, weil sich die Behandlung deutlich von anderen Formen unterscheidet. "
        "Deshalb gehört die Einordnung in die Hände eines erfahrenen PH-Zentrums.",
    ],
)

_add(
    "PX_GROUP2_HINT",
    "Hinweis auf linke Herzseite",
    [
        "Ein Teil der Befunde passt dazu, dass die **linke Herzseite** mitbeteiligt sein könnte. Das wird kardiologisch weiter eingeordnet.",
        "Es gibt Hinweise, dass eine Belastung der linken Herzseite eine Rolle spielen könnte. Oft ist dann eine kardiologische Therapieoptimierung sinnvoll.",
        "Die Befunde sprechen dafür, dass die linke Herzseite bei der Druckerhöhung eine Rolle spielt. Eine gezielte kardiologische Behandlung kann hier den größten Unterschied machen.",
        "Wenn die linke Herzseite mitbeteiligt ist, richtet sich die Therapie vor allem darauf, das linke Herz zu unterstützen und den Flüssigkeitshaushalt zu optimieren.",
        "Eine Beteiligung der linken Herzseite ist häufig gut zu behandeln: "
        "Blutdruck, Herzrhythmus und Flüssigkeitshaushalt können gezielt angepasst werden – und das entlastet auch die Lungengefäße.",
        "Weil die rechte und linke Herzseite eng zusammenspielen, kann eine Schwäche auf der linken Seite zu Druckanstieg in der Lunge führen. "
        "Die gute Nachricht: Für diesen Mechanismus gibt es klare, gut erprobte Therapiewege.",
    ],
)

_add(
    "PX_GROUP3_HINT",
    "Hinweis auf Lunge / Sauerstoff",
    [
        "Es gibt Hinweise, dass eine **Lungenerkrankung** oder eine niedrige Sauerstoffversorgung mitbeteiligt sein könnte. Dann sind Lungenfunktion und Bildgebung besonders wichtig.",
        "Ein Teil der Befunde kann zu einer Beteiligung der Lunge passen. In solchen Fällen hilft eine pneumologische Mitbeurteilung, um die Behandlung zu optimieren.",
        "Wenn eine Lungenerkrankung oder ein niedriger Sauerstoffgehalt im Blut zur Druckerhöhung beiträgt, ist die Behandlung der Grunderkrankung oft der wichtigste Hebel.",
        "Die Sauerstoffversorgung und die Lungenfunktion spielen in Ihrer Situation möglicherweise eine wichtige Rolle. Wir prüfen das gezielt, um die bestmögliche Behandlung zu finden.",
        "Wenn Lunge und Sauerstoff eine Rolle spielen, kann eine gute Behandlung der Grunderkrankung – etwa der Bronchien, einer Lungenvernarbung oder einer nächtlichen Unterbeatmung – den Druck in den Lungengefäßen spürbar entlasten.",
        "Manchmal ist nicht die Lunge im Ruhezustand das Problem, sondern ein Sauerstoffabfall unter Belastung oder im Schlaf. "
        "Genau das lässt sich mit einfachen Messungen gut überprüfen und gezielt behandeln.",
    ],
)

_add(
    "PX_GROUP4_HINT",
    "Hinweis auf ältere Blutgerinnsel",
    [
        "Es gibt Hinweise, die zu **älteren oder chronischen Blutgerinnseln** in den Lungengefäßen passen könnten. Das sollte gezielt weiter abgeklärt werden.",
        "Ein Teil der Befunde lässt an eine chronische Durchblutungsstörung der Lunge denken, zum Beispiel durch ältere Blutgerinnsel. Dann ist eine spezialisierte Abklärung wichtig.",
        "Falls ältere Blutgerinnsel in den Lungengefäßen die Ursache sind, gibt es heute sehr wirksame Behandlungsmöglichkeiten. Eine genaue Bildgebung hilft, das sicher einzuordnen.",
        "Die Befunde passen zu einem Muster, bei dem **chronische Gerinnsel** in den Lungengefäßen eine Rolle spielen könnten. Das ist wichtig zu erkennen, weil es gezielte Therapien dafür gibt.",
        "Diese Form ist einer der wenigen Typen der Lungenhochdruck-Erkrankung, bei denen unter bestimmten Voraussetzungen eine Heilung möglich ist – zum Beispiel durch einen spezialisierten Eingriff. "
        "Deshalb ist die saubere Abklärung besonders lohnend.",
        "Chronische Gerinnsel werden oft erst spät erkannt, weil die Beschwerden schleichend beginnen. "
        "Die gute Nachricht: In spezialisierten Zentren gibt es wirksame Operationen, Katheter-Verfahren und Medikamente, die die Situation deutlich verbessern können.",
    ],
)

_add(
    "PX_SHUNT_HINT",
    "Hinweis auf zusätzliche Verbindung zwischen Herzhöhlen",
    [
        "Die Sauerstoffmessungen im Herzen sprechen dafür, dass es möglicherweise eine **zusätzliche Verbindung zwischen Herzhöhlen** gibt. Das ist oft gut weiter abklärbar, zum Beispiel mit einem spezialisierten Ultraschall.",
        "Die Messungen im Herzen geben Hinweise auf eine mögliche zusätzliche Verbindung zwischen Herzhöhlen. Das kann den Blutfluss beeinflussen und sollte gezielt abgeklärt werden.",
        "Wenn eine ungewöhnliche Verbindung zwischen Herzhöhlen besteht, fließt Blut auf einem Umweg. Das kann die Druckverhältnisse beeinflussen und ist mit speziellen Untersuchungen gut abklärbar.",
        "Die Sauerstoffmessungen deuten auf eine mögliche Kurzschlussverbindung im Herzen hin. Das ist ein wichtiger Befund, weil er die Therapiestrategie verändern kann. Eine gezielte Bildgebung schafft Klarheit.",
        "Eine solche Verbindung zwischen den Herzhöhlen ist manchmal angeboren und bleibt lange unbemerkt. "
        "Ob und wie sie behandelt werden sollte, hängt von Größe, Fluss-Richtung und Ihren Beschwerden ab – das klären wir gezielt ab.",
        "Wenn sich der Verdacht bestätigt, ist das keine schlechte Nachricht: "
        "Viele dieser Verbindungen sind heute mit Katheter-Verfahren ohne größere Operation gut behandelbar. Voraussetzung ist die sorgfältige Einordnung, die wir jetzt anstoßen.",
    ],
)

_add(
    "PX_ANEMIA",
    "Blutarmut",
    [
        "Im Blutbild gibt es Hinweise auf eine **Blutarmut**. Das kann die Belastbarkeit beeinflussen und sollte gezielt abgeklärt und behandelt werden.",
        "Es bestehen Hinweise auf eine Blutarmut. Eine Behandlung kann helfen, die Leistungsfähigkeit zu verbessern.",
        "Blutarmut kann Luftnot und Müdigkeit verstärken, auch unabhängig von der Druckerhöhung in der Lunge. Eine gezielte Behandlung, zum Beispiel mit Eisen, kann Ihre Belastbarkeit spürbar verbessern.",
        "Wenn zu wenig rote Blutkörperchen vorhanden sind, wird weniger Sauerstoff transportiert. Das kann Beschwerden wie Luftnot und Erschöpfung verschlimmern. Wir klären die Ursache ab und behandeln gezielt.",
        "Eine Blutarmut zu behandeln lohnt sich gerade bei Lungenhochdruck besonders: "
        "Das Herz muss weniger kompensieren und Sie bekommen wieder mehr Reserven für den Alltag.",
        "Die Ursache der Blutarmut ist oft ebenso wichtig wie die Behandlung selbst. "
        "Zu den häufigen Auslösern gehören Eisenmangel, chronische Entzündungen oder bestimmte Medikamente – jede Ursache braucht einen etwas anderen Weg.",
    ],
)

_add(
    "PX_CONGESTION",
    "Wassereinlagerung / Rückstau",
    [
        "Es gibt Hinweise auf **Wassereinlagerung oder Rückstau**. Dann ist es wichtig, den Flüssigkeitshaushalt gut einzustellen und die Nierenwerte im Blick zu behalten.",
        "Ein Teil der Befunde passt zu Wassereinlagerung. Oft hilft eine Anpassung der Entwässerung und eine regelmäßige Kontrolle der Werte.",
        "Wassereinlagerungen können sich als geschwollene Beine, Gewichtszunahme oder zunehmende Luftnot bemerkbar machen. Mit einer gezielten Anpassung der Entwässerungsmedikamente lässt sich das oft gut in den Griff bekommen.",
        "Wenn der Körper Wasser einlagert, belastet das Herz und Kreislauf zusätzlich. Tägliches Wiegen und eine klare Trinkmenge helfen, die Situation stabil zu halten.",
        "Hilfreich ist, morgens nüchtern zur gleichen Zeit zu wiegen und Veränderungen von mehr als 1–2 kg innerhalb weniger Tage frühzeitig in der Sprechstunde zu melden. "
        "So können wir gegensteuern, bevor sich Beschwerden aufbauen.",
        "Eine gute Balance beim Wasserhaushalt ist ein Grundpfeiler der Behandlung. "
        "Weder zu viel noch zu wenig Flüssigkeit ist günstig – gemeinsam finden wir das Maß, das für Ihr Herz und Ihre Nieren stimmt.",
    ],
)

_add(
    "PX_SAFETY_NET",
    "Sicherheitshinweis",
    [
        "Wenn neue oder starke Beschwerden auftreten (zum Beispiel Ohnmacht, stark zunehmende Luftnot oder Brustschmerz), suchen Sie bitte zeitnah ärztliche Hilfe.",
        "Bitte holen Sie rasch ärztliche Hilfe, wenn es zu plötzlich starker Luftnot, Ohnmacht, Brustschmerz oder blutigem Auswurf kommt.",
        "Bitte suchen Sie umgehend ärztliche Hilfe auf, wenn Sie plötzlich stark luftnötig werden, Brustschmerzen bekommen, ohnmächtig werden oder Blut husten. Im Zweifel lieber einmal zu viel als zu wenig.",
        "Sollten sich Ihre Beschwerden plötzlich und deutlich verschlechtern, zögern Sie nicht, den Notruf zu wählen oder eine Notaufnahme aufzusuchen. Besonders Ohnmacht, starke Luftnot und Brustschmerzen erfordern schnelles Handeln.",
        "Wir möchten, dass Sie sich sicher fühlen. Falls Sie zwischen den Terminen plötzlich starke Luftnot, Schwindel, Ohnmacht oder Brustschmerzen verspüren, suchen Sie bitte sofort ärztliche Hilfe.",
        "Merken Sie sich als einfache Regel: Neue oder deutlich stärkere Beschwerden sind immer ein Grund, sich zu melden – lieber einmal zu früh als einmal zu spät. Unsere Ambulanz und der Notruf (112) sind für genau solche Situationen da.",
    ],
)

_add(
    "PX_NEXT_STEPS",
    "Wie geht es weiter?",
    [
        "Wir besprechen die Ergebnisse mit Ihnen und planen die nächsten Schritte. Das kann zusätzliche Untersuchungen, eine Anpassung der Medikamente und Verlaufskontrollen beinhalten.",
        "Als nächstes planen wir gemeinsam mit Ihnen die weiteren Schritte. Je nach Ursache können weitere Tests, eine Therapieanpassung und Verlaufskontrollen sinnvoll sein.",
        "Die Ergebnisse werden nun im Team eingeordnet. Daraus leiten wir ab, welche weiteren Untersuchungen oder Therapieschritte in Ihrem Fall am meisten helfen.",
        "Im nächsten Schritt verbinden wir Ihre Beschwerden, die Messwerte und die bisherigen Vorbefunde zu einem klaren Plan. Dadurch wird nachvollziehbar, welche Maßnahme zuerst wichtig ist und was zunächst beobachtet werden kann.",
        "Auf Basis dieser Ergebnisse erarbeiten wir gemeinsam mit Ihnen einen individuellen Plan. Dazu gehören gegebenenfalls weitere Untersuchungen, eine Anpassung der Therapie und regelmäßige Kontrollen.",
        "Sie werden nicht allein gelassen: Wir besprechen die Befunde ausführlich mit Ihnen und legen gemeinsam fest, welche Schritte als nächstes sinnvoll sind.",
    ],
)

_add(
    "PX_DISCLAIMER",
    "Hinweis",
    [
        "Dieser Text ist eine verständliche Zusammenfassung und ersetzt kein ärztliches Gespräch. Bitte klären Sie offene Fragen im nächsten Termin.",
        "Hinweis: Diese Zusammenfassung dient der Orientierung. Die individuelle Einordnung und Behandlung erfolgt im persönlichen Gespräch.",
        "Diese Zusammenfassung soll Ihnen helfen, die Befunde besser zu verstehen. Sie ersetzt nicht das persönliche Gespräch mit Ihrem Arzt oder Ihrer Ärztin, in dem alle Fragen ausführlich besprochen werden.",
        "Bitte beachten Sie: Dieser Text ist eine vereinfachte Zusammenfassung. Die genaue Einordnung und alle Behandlungsentscheidungen werden im ärztlichen Gespr��ch mit Ihnen gemeinsam getroffen.",
        "Diese Seiten sind für Sie als Unterstützung gedacht – zum Nachlesen in Ruhe und als Gesprächsgrundlage. "
        "Alle wichtigen Entscheidungen treffen wir gemeinsam im Gespräch, passend zu Ihrer persönlichen Situation.",
        "Wenn beim Lesen Fragen auftauchen, notieren Sie sie gerne und bringen sie zum nächsten Termin mit. "
        "Medizinische Zusammenhänge sind oft komplex, und wir nehmen uns die Zeit, Ihnen die Ergebnisse verständlich zu erklären.",
    ],
)


# ---------------------------------------------------------------------------
# Altersadaptierter Kontext
# ---------------------------------------------------------------------------

_add(
    "PX_AGE_YOUNG",
    "Alterskontext: jüngere Patienten",
    [
        "Als jüngerer Mensch stellen sich bei einer solchen Diagnose oft besondere Fragen – zum Beispiel zu Beruf, Sport, Familienplanung oder Zukunftsplanung. Wir berücksichtigen diese Aspekte bei der Beratung.",
        "Gerade in jüngeren Jahren kann eine solche Diagnose besonders belastend wirken. Wir möchten Ihnen versichern, dass es gute Behandlungsmöglichkeiten gibt und wir Sie langfristig begleiten.",
        "Für jüngere Menschen ist es besonders wichtig, die Erkrankung frühzeitig gut einzustellen. So können wir dazu beitragen, dass Ihr Alltag, Ihre Arbeitsfähigkeit und Ihre Lebensplanung möglichst wenig beeinträchtigt werden.",
        "In Ihrem Alter haben wir die Chance, frühzeitig und gezielt zu handeln. Das kann langfristig einen großen Unterschied machen. Themen wie Beruf, Reisen und Familienplanung besprechen wir gerne gemeinsam.",
        "Wir wissen, dass eine solche Diagnose in jüngeren Lebensjahren viele Fragen aufwirft. Unser Ziel ist es, dass Sie so normal wie möglich leben können – mit der richtigen Unterstützung.",
        "Bei jungen Patientinnen und Patienten denken wir immer mit, was in den nächsten Jahren wichtig wird: Sport, Reisen, Karriere, Kinderwunsch. "
        "All das besprechen wir offen – und suchen die Therapie, die sich am besten in Ihr Leben einfügt.",
    ],
)

_add(
    "PX_AGE_ELDERLY",
    "Alterskontext: ältere Patienten",
    [
        "Im höheren Lebensalter stehen oft Lebensqualität und Alltagssicherheit im Vordergrund. Wir stimmen die Behandlung darauf ab, was Ihnen im täglichen Leben am meisten hilft.",
        "Mit zunehmendem Alter können mehrere Erkrankungen zusammenwirken. Wir achten besonders darauf, die Therapie so einfach und verträglich wie möglich zu gestalten.",
        "In Ihrem Alter legen wir besonderen Wert darauf, dass die Behandlung gut verträglich ist und Ihren Alltag so wenig wie möglich belastet. Lebensqualität hat hier höchste Priorität.",
        "Wir berücksichtigen, dass im höheren Alter andere Erkrankungen und Medikamente eine Rolle spielen. Unser Ziel ist eine Behandlung, die gut in Ihren Alltag passt und Ihre Selbstständigkeit unterstützt.",
        "Gerade bei älteren Menschen ist es wichtig, den Nutzen jeder Maßnahme gegen mögliche Belastungen abzuwägen. Wir besprechen offen mit Ihnen, welche Schritte wirklich hilfreich sind.",
        "Lebensqualität bedeutet für jeden Menschen etwas anderes. Wir hören Ihnen zu, was Ihnen im Alltag wichtig ist – und richten die Behandlung genau darauf aus.",
    ],
)

# ---------------------------------------------------------------------------
# Komorbiditäts-Kontext
# ---------------------------------------------------------------------------

_add(
    "PX_COMORBID_DIABETES",
    "Komorbiditätskontext: Diabetes",
    [
        "Diabetes kann das Herz und die Blutgefäße auf verschiedene Weisen belasten. Eine gute Blutzuckereinstellung ist daher auch für die Lungengefäße wichtig.",
        "Bei Diabetes achten wir besonders darauf, wie sich der Stoffwechsel auf Herz und Gefäße auswirkt. Eine enge Zusammenarbeit mit der Diabetesbehandlung ist hier sinnvoll.",
        "Diabetes und Lungenhochdruck können sich gegenseitig beeinflussen. Deshalb ist es wichtig, beide Erkrankungen gemeinsam im Blick zu behalten und aufeinander abzustimmen.",
        "Eine gute Diabeteseinstellung kann helfen, die Gefäße zu schützen und die Herzbelastung zu verringern. Wir stimmen die Behandlung beider Erkrankungen aufeinander ab.",
        "Langzeitzucker, Blutdruck und Cholesterin zusammen gut im Bereich zu halten, ist einer der wirksamsten Hebel, die Lungengefäße zu schützen. "
        "Dabei sind kleine, beständige Verbesserungen oft wichtiger als kurzfristige Umstellungen.",
        "Bei Diabetes achten wir auch auf Unterzucker und Wassereinlagerungen, denn einige Diabetes-Medikamente beeinflussen den Flüssigkeitshaushalt. "
        "So können wir die Therapie so wählen, dass sie Herz und Nieren möglichst gut unterstützt.",
    ],
)

_add(
    "PX_COMORBID_COPD",
    "Komorbiditätskontext: COPD/Lungenerkrankung",
    [
        "Eine bestehende Lungenerkrankung kann die Druckwerte in den Lungengefäßen beeinflussen. Deshalb betrachten wir Lungenfunktion und Lungendruck immer gemeinsam.",
        "Bei einer begleitenden Lungenerkrankung ist es manchmal schwieriger, die genaue Ursache der Druckerhöhung festzustellen. Eine sorgfältige Abklärung hilft, die richtige Behandlung zu wählen.",
        "Lungenerkrankungen und Lungenhochdruck können sich überlagern. Wir arbeiten eng mit der Pneumologie zusammen, um beide Aspekte bestmöglich zu behandeln.",
        "Wenn eine Lungenerkrankung vorliegt, kann auch die Sauerstoffversorgung eine Rolle spielen. Wir prüfen gezielt, ob eine Optimierung der Lungenbehandlung den Druck in den Lungengefäßen positiv beeinflussen kann.",
        "Die Kombination aus Lungenerkrankung und Druckerhöhung in den Lungengefäßen erfordert eine besonders sorgfältige Abstimmung der Behandlung. Nicht jede Therapie, die bei einer Form des Lungenhochdrucks hilft, ist bei begleitender Lungenerkrankung geeignet.",
        "Eine gute Einstellung der Lungenerkrankung – etwa durch konsequente Inhalation, Pneumokokken-Impfung und wenn nötig Sauerstoff – ist bei Lungenhochdruck oft der wichtigste Hebel überhaupt. "
        "Wir besprechen ganz konkret, wo Sie den größten Nutzen erwarten können.",
    ],
)

_add(
    "PX_COMORBID_RENAL",
    "Komorbiditätskontext: Nierenerkrankung",
    [
        "Eine eingeschränkte Nierenfunktion kann den Flüssigkeitshaushalt und damit auch die Druckverhältnisse im Kreislauf beeinflussen. Wir berücksichtigen das bei der Therapieplanung.",
        "Bei Nierenerkrankungen achten wir besonders auf den Flüssigkeitshaushalt und die Medikamentenverträglichkeit. Einige Medikamente müssen an die Nierenfunktion angepasst werden.",
        "Nieren und Kreislauf hängen eng zusammen. Wenn die Nieren eingeschränkt arbeiten, kann das die Druckwerte in den Lungengefäßen beeinflussen. Deshalb beziehen wir die Nierenwerte in die Gesamtbeurteilung ein.",
        "Bei begleitender Nierenerkrankung ist die Steuerung des Flüssigkeitshaushalts besonders wichtig. Eine gute Abstimmung kann sowohl die Nieren als auch das Herz entlasten.",
        "Manche Kontrastmittel und Medikamente können die Nieren zusätzlich belasten. "
        "Deshalb planen wir Untersuchungen und Therapie so, dass Ihre Nieren möglichst geschont werden.",
        "Regelmäßige Kontrollen der Nierenwerte – zusammen mit Gewicht und Trinkmenge – helfen uns, Veränderungen früh zu erkennen und rechtzeitig gegenzusteuern, bevor Beschwerden entstehen.",
    ],
)

_add(
    "PX_COMORBID_OBESITY",
    "Komorbiditätskontext: Übergewicht",
    [
        "Übergewicht kann die Belastung für Herz und Lunge erhöhen und manche Messwerte beeinflussen. Eine Gewichtsreduktion kann sich positiv auf die Beschwerden auswirken.",
        "Bei deutlichem Übergewicht können Atemmechanik, Blutvolumen und Herzarbeit verändert sein. Wir berücksichtigen das bei der Einordnung der Messwerte.",
        "Übergewicht ist ein Faktor, der Luftnot und Kreislaufbelastung verstärken kann. Eine strukturierte Gewichtsabnahme gehört daher oft zum Behandlungskonzept dazu.",
        "Bei bestehendem Übergewicht schauen wir besonders darauf, wie viel von den Beschwerden durch das Gewicht selbst erklärt werden kann und was auf die Druckerhöhung zurückgeht. Das hilft, die Behandlung gezielt auszurichten.",
        "Übergewicht und Lungenhochdruck können sich gegenseitig verstärken. Eine Gewichtsreduktion kann ein wichtiger Baustein sein, um die Belastbarkeit zu verbessern und die Druckwerte positiv zu beeinflussen.",
        "Bei bestehendem Übergewicht gibt es oft mehrere Wege parallel: Bewegungsprogramme, Ernährungsberatung und in manchen Fällen auch neue medikamentöse Therapien. "
        "Wir suchen gemeinsam den Weg, der für Sie realistisch und nachhaltig ist.",
    ],
)

# ---------------------------------------------------------------------------
# WHO-Funktionsklasse – alltagsnahe Beschreibung
# ---------------------------------------------------------------------------

_add(
    "PX_FC_I",
    "Funktionsklasse I: keine Einschränkung",
    [
        "Im Alltag sind Sie derzeit nicht spürbar eingeschränkt. Sie können normale körperliche Aktivitäten ohne Luftnot oder Erschöpfung bewältigen. Das ist ein gutes Zeichen.",
        "Ihre Belastbarkeit ist aktuell gut erhalten. Gewöhnliche Alltagstätigkeiten verursachen keine besonderen Beschwerden. Wir behalten die Situation trotzdem im Blick.",
        "Sie berichten, dass Sie im Alltag keine wesentlichen Einschränkungen bemerken. Das spricht dafür, dass Herz und Kreislauf die Situation derzeit gut bewältigen.",
        "Aktuell können Sie Treppen steigen, spazieren gehen und Ihren Alltag normal gestalten, ohne besondere Luftnot. Das ist eine gute Ausgangslage.",
        "Dass Sie sich bei alltäglichen Anstrengungen wohl fühlen, ist ein wichtiger Teil unserer Verlaufsbeurteilung. "
        "Wir nutzen diese Ausgangslage, um frühzeitig zu erkennen, falls sich etwas verändert.",
        "Eine gute Belastbarkeit im Alltag ist ein wertvolles Signal – sie spricht dafür, dass Herz und Lungenkreislauf aktuell gut zusammenarbeiten. "
        "Das heißt nicht, dass wir die Kontrollen vernachlässigen: Gerade dann lohnt es sich, am Ball zu bleiben.",
    ],
)

_add(
    "PX_FC_II",
    "Funktionsklasse II: leichte Einschränkung",
    [
        "In Ruhe haben Sie keine Beschwerden. Bei stärkerer Belastung, zum Beispiel beim Treppensteigen oder schnellen Gehen, kann es aber zu Luftnot oder Erschöpfung kommen.",
        "Im normalen Alltag kommen Sie gut zurecht. Bei größerer Anstrengung, wie beim Bergaufgehen oder beim Tragen schwerer Einkäufe, bemerken Sie jedoch eine Einschränkung.",
        "Leichte Alltagstätigkeiten gehen gut. Anstrengendere Aktivitäten wie Sport oder längere Spaziergänge in hügeligem Gelände können aber Beschwerden auslösen.",
        "Sie merken die Einschränkung vor allem bei stärkerer Belastung. In Ruhe und bei leichter Bewegung geht es Ihnen gut. Das ist eine milde Einschränkung, die wir im Verlauf beobachten.",
        "Im Alltag fühlen Sie sich weitgehend normal. Erst bei deutlicher körperlicher Anstrengung treten Beschwerden wie Luftnot oder schnelle Erschöpfung auf.",
        "Viele unserer Patientinnen und Patienten in diesem Stadium berichten, dass sie den Alltag gut bewältigen, aber Tempo und Dauer anstrengender Tätigkeiten bewusst dosieren müssen. Das ist ein normaler und vernünftiger Umgang mit einer milden Einschränkung.",
    ],
)

_add(
    "PX_FC_III",
    "Funktionsklasse III: deutliche Einschränkung",
    [
        "Schon bei alltäglichen Aktivitäten, wie dem Anziehen, kurzen Wegen in der Wohnung oder leichtem Treppensteigen, können Luftnot oder Erschöpfung auftreten. In Ruhe geht es Ihnen besser.",
        "Ihre Belastbarkeit ist deutlich eingeschränkt. Viele Alltagstätigkeiten fallen schwerer als gewohnt. Wir arbeiten daran, Ihre Situation durch die Behandlung zu verbessern.",
        "Sie bemerken Beschwerden bereits bei geringer Belastung. Das zeigt, dass Herz und Kreislauf stärker beansprucht sind. Die Therapie zielt darauf ab, Ihnen wieder mehr Belastbarkeit zu ermöglichen.",
        "Alltägliche Aufgaben wie Einkaufen, Kochen oder ein kurzer Spaziergang können bereits anstrengend sein. Das nehmen wir sehr ernst und richten die Behandlung gezielt darauf aus.",
        "Die Einschränkung im Alltag ist deutlich spürbar. Wir setzen alles daran, Ihnen durch die richtige Behandlung mehr Lebensqualität und Sicherheit im Alltag zurückzugeben.",
        "In dieser Phase lohnt es sich besonders, den Alltag bewusst zu strukturieren – ausreichend Pausen, kurze Wege, Hilfen beim Tragen. Das ist keine Schwäche, sondern eine kluge Strategie, bis die Therapie ihre Wirkung entfaltet.",
    ],
)

_add(
    "PX_FC_IV",
    "Funktionsklasse IV: schwere Einschränkung",
    [
        "Selbst in Ruhe können Beschwerden auftreten. Jede körperliche Aktivität verstärkt die Symptome. In dieser Situation ist eine engmaschige Betreuung besonders wichtig.",
        "Ihre Beschwerden sind auch in Ruhe vorhanden oder treten bei geringster Anstrengung auf. Das erfordert eine intensive Behandlung und enge Begleitung durch das Behandlungsteam.",
        "Die Einschränkung ist schwer ausgeprägt. Wir wissen, wie belastend das ist, und setzen alle verfügbaren Mittel ein, um Ihren Zustand zu stabilisieren und zu verbessern.",
        "In diesem Stadium ist die Zusammenarbeit zwischen Ihnen und dem spezialisierten Behandlungsteam besonders eng. Jede Verschlechterung wird zeitnah besprochen und behandelt.",
        "Auch wenn die Situation belastend ist: Es gibt auch in fortgeschrittenen Stadien Behandlungsmöglichkeiten, die Ihre Lebensqualität verbessern können. Wir besprechen gemeinsam, welche Schritte für Sie sinnvoll sind.",
        "Gerade jetzt ist unser Ziel, Symptome zu lindern und Ihnen so viel Lebensqualität wie möglich zu erhalten. Nicht jeder Schritt geht gegen die Erkrankung – viele gehen ganz bewusst für Sie als Mensch.",
    ],
)

# ---------------------------------------------------------------------------
# Emotionale Rahmung
# ---------------------------------------------------------------------------

_add(
    "PX_REASSURANCE",
    "Beruhigung",
    [
        "Wir wissen, dass solche Befunde erst einmal beunruhigend klingen können. Wichtig ist: Wir haben die Situation im Blick und planen die nächsten Schritte gemeinsam mit Ihnen.",
        "Das klingt vielleicht erst einmal besorgniserregend. Aber: Viele dieser Befunde lassen sich gut behandeln, und wir begleiten Sie auf diesem Weg.",
        "Es ist verständlich, wenn Sie sich nach einer solchen Untersuchung Sorgen machen. Wir nehmen uns die Zeit, alles in Ruhe mit Ihnen zu besprechen.",
        "Bitte lassen Sie sich von den medizinischen Begriffen nicht verunsichern. Wir erklären Ihnen gerne alles Schritt für Schritt und beantworten Ihre Fragen.",
        "Auch wenn die Ergebnisse zunächst beunruhigend wirken: Durch die Untersuchung wissen wir jetzt genau, woran wir sind, und können gezielt handeln. Das ist ein wichtiger Vorteil.",
        "Es ist normal, nach so einer Untersuchung viele Fragen oder auch Ängste zu haben. Nehmen Sie sich die Zeit, die Sie brauchen – wir beantworten gerne auch Fragen, die erst später auftauchen, beim nächsten Termin oder telefonisch.",
    ],
)

_add(
    "PX_ENCOURAGEMENT",
    "Ermutigung bei stabilem/positivem Verlauf",
    [
        "Die Ergebnisse geben Anlass zur Zuversicht. Ihre Situation ist stabil, und die bisherige Behandlung scheint gut zu wirken.",
        "Das sind ermutigende Befunde. Sie zeigen, dass wir auf dem richtigen Weg sind. Wir behalten die Situation weiterhin aufmerksam im Blick.",
        "Die aktuelle Entwicklung ist positiv. Das bestätigt, dass die eingeschlagene Richtung stimmt. Gemeinsam sorgen wir dafür, dass das so bleibt.",
        "Es freut uns, Ihnen mitteilen zu können, dass die Befunde insgesamt günstig aussehen. Wir nutzen die gute Ausgangslage, um die Betreuung optimal fortzusetzen.",
        "Die Ergebnisse zeigen eine erfreuliche Stabilität. Das gibt uns die Möglichkeit, die Behandlung in Ruhe fortzuführen und weitere Verbesserungen anzustreben.",
        "Stabile Werte über einen längeren Zeitraum sind bei dieser Erkrankung keine Selbstverständlichkeit, sondern ein echter Erfolg – Ihrer Mitarbeit und der gemeinsamen Therapieplanung sei Dank.",
    ],
)

_add(
    "PX_EMPATHY_BURDEN",
    "Anerkennung der Belastung",
    [
        "Wir wissen, dass eine solche Diagnose und die damit verbundenen Untersuchungen belastend sein können. Ihre Sorgen sind berechtigt, und wir nehmen sie ernst.",
        "Es ist uns bewusst, dass dieser Befund eine zusätzliche Last bedeuten kann. Bitte zögern Sie nicht, uns mitzuteilen, wenn Sie Unterstützung brauchen – auch über die rein medizinische Behandlung hinaus.",
        "Eine chronische Erkrankung betrifft nicht nur den Körper, sondern auch die Seele. Wenn Sie das Gefühl haben, dass die Belastung zu groß wird, sprechen Sie uns bitte an. Es gibt Unterstützungsangebote.",
        "Wir verstehen, dass die Diagnose und die regelmäßigen Untersuchungen anstrengend sind. Sie sind damit nicht allein – wir begleiten Sie und stehen Ihnen zur Seite.",
        "Solche Befunde können verunsichern. Wir möchten, dass Sie wissen: Sie werden nicht allein gelassen. Unser Ziel ist es, Sie medizinisch und menschlich bestmöglich zu begleiten.",
        "Die Kombination aus Diagnose, Terminen und Wartezeiten kann erschöpfen. Wenn Sie merken, dass Ihnen die Situation zu viel wird – sprechen Sie uns an. Psychokardiologische und psychosoziale Unterstützung gehört bei uns selbstverständlich zum Gesamtkonzept.",
    ],
)

# ---------------------------------------------------------------------------
# Trend / Verlauf / Follow-up
# ---------------------------------------------------------------------------

_add(
    "PX_TREND_IMPROVED",
    "Verlaufstrend: verbessert",
    [
        "Im Vergleich zur letzten Untersuchung haben sich die Werte **verbessert**. Das spricht dafür, dass die Behandlung wirkt und Ihre Situation sich positiv entwickelt.",
        "Die aktuellen Messwerte sind **günstiger** als beim letzten Mal. Das ist ein erfreuliches Ergebnis und bestätigt den eingeschlagenen Therapieweg.",
        "Es zeigt sich eine **positive Entwicklung** im Vergleich zum Vorbefund. Die Behandlung scheint gut anzuschlagen. Wir setzen den aktuellen Kurs fort.",
        "Die Werte haben sich im Verlauf **gebessert**. Das ist ein gutes Zeichen und motiviert, die Therapie konsequent weiterzuführen.",
        "Im Vergleich zur Voruntersuchung sehen wir eine **Verbesserung**. Gemeinsam achten wir darauf, dass dieser positive Trend anhält.",
        "Ein günstiger Verlauf ist bei Lungenhochdruck kein Zufall, sondern das Ergebnis konsequenter Therapie und guter Mitarbeit. Bitte verstehen Sie diese Entwicklung als Ermutigung, den eingeschlagenen Weg beizubehalten.",
    ],
)

_add(
    "PX_TREND_STABLE",
    "Verlaufstrend: stabil",
    [
        "Die Messwerte sind im Vergleich zur letzten Untersuchung **stabil geblieben**. Das bedeutet, dass sich die Situation nicht verschlechtert hat, was ein beruhigendes Zeichen ist.",
        "Im Verlauf zeigen die Werte keine wesentliche Veränderung. **Stabilität** ist in dieser Situation ein gutes Ergebnis und zeigt, dass die aktuelle Behandlung hält, was sie soll.",
        "Die Befunde sind **weitgehend unverändert** im Vergleich zum Vorbefund. Das spricht dafür, dass die aktuelle Therapie die Situation gut kontrolliert.",
        "Stabile Werte bedeuten, dass die Erkrankung unter der aktuellen Behandlung nicht fortschreitet. Wir führen die Therapie fort und kontrollieren regelmäßig.",
        "Die Werte sind im Wesentlichen **stabil geblieben**. Das zeigt, dass die aktuelle Behandlung greift und die Situation gut unter Kontrolle ist.",
        "Dass sich die Messwerte nicht verschlechtert haben, ist ein **ermutigendes Zeichen**. Stabilität ist bei dieser Erkrankung ein wichtiges Therapieziel, und das haben wir erreicht.",
    ],
)

_add(
    "PX_TREND_WORSENED",
    "Verlaufstrend: verschlechtert",
    [
        "Im Vergleich zur letzten Untersuchung haben sich einige Werte **ungünstig verändert**. Das heißt nicht automatisch, dass sich alles verschlechtert hat, aber wir nehmen das als Anlass, die Therapie zu überprüfen.",
        "Es zeigt sich eine **Verschlechterung** einzelner Messwerte im Vergleich zum Vorbefund. Wir besprechen mit Ihnen, welche Anpassungen jetzt sinnvoll sind.",
        "Manche Werte haben sich im Verlauf **verschoben**. Das erfordert eine sorgfältige Überprüfung der aktuellen Behandlung. Wir schauen gemeinsam, wo Anpassungen helfen können.",
        "Die Entwicklung der Messwerte zeigt, dass wir die Therapie **anpassen** sollten. Verschiedene Optionen stehen zur Verfügung, und wir besprechen die nächsten Schritte mit Ihnen.",
        "Eine Veränderung der Werte in ungünstiger Richtung bedeutet, dass wir aufmerksamer hinschauen und gegebenenfalls handeln müssen. Das besprechen wir offen und planen die nächsten Schritte zusammen.",
        "Ein ungünstigerer Verlauf ist nicht ungewöhnlich bei einer chronischen Lungengefäßerkrankung – und er bedeutet nicht, dass etwas falsch gelaufen wäre. Es ist ein Signal, gemeinsam neue Optionen zu besprechen und die Therapie weiterzuentwickeln.",
    ],
)

_add(
    "PX_FIRST_EXAM",
    "Erstuntersuchung – kein Vergleich",
    [
        "Dies ist Ihre erste Herzkatheter-Untersuchung in unserem Haus. Ein Vergleich mit Vorwerten ist daher noch nicht möglich. Die heutigen Messwerte dienen als wichtiger Ausgangspunkt für die weitere Betreuung.",
        "Da es sich um die erste Messung handelt, gibt es noch keine Vergleichswerte. Wir nutzen die heutigen Ergebnisse als Referenz, an der wir zukünftige Veränderungen messen können.",
        "Für eine Verlaufsbeurteilung brauchen wir mindestens zwei Messzeitpunkte. Die heutige Untersuchung liefert die Basis, auf der wir aufbauen.",
        "Dies ist die Ausgangsmessung. Erst bei einer Kontrolluntersuchung können wir beurteilen, ob sich die Werte verändert haben. Das ist ein normaler Teil der Diagnostik.",
        "Bei einer Erstdiagnostik sind die heutigen Zahlen besonders wertvoll – sie bilden die Grundlage, an der sich jede zukünftige Kontrolle misst. "
        "So können wir Veränderungen frühzeitig erkennen und die Therapie feinjustieren.",
        "Bei der ersten Untersuchung steht die genaue Einordnung im Vordergrund: Welcher Typ der Druckerhöhung liegt vor, welche Ursachen spielen mit, und wo können wir am wirksamsten ansetzen? "
        "Die Ergebnisse von heute schaffen die Grundlage für Ihre persönliche Behandlungsstrategie.",
    ],
)

# ---------------------------------------------------------------------------
# Übergangsphrasen (Transition Blocks)
# ---------------------------------------------------------------------------

_add(
    "PX_TRANSITION_TO_DETAILS",
    "Übergang: von Einleitung zu Details",
    [
        "Im Folgenden erklären wir Ihnen, was die einzelnen Messwerte bedeuten und wie wir sie einordnen.",
        "Nun möchten wir Ihnen die Ergebnisse im Einzelnen erklären.",
        "Schauen wir uns die Befunde genauer an:",
        "Was genau gemessen wurde und was das für Sie bedeutet, erklären wir im nächsten Abschnitt.",
        "Im Folgenden gehen wir die wichtigsten Ergebnisse Schritt für Schritt durch.",
        "Damit Sie die Zahlen und Begriffe besser einordnen können, erklären wir sie gleich in der Reihenfolge, die für Ihre Situation wichtig ist.",
    ],
)

_add(
    "PX_TRANSITION_TO_NEXT_STEPS",
    "Übergang: von Befunden zu nächsten Schritten",
    [
        "Was bedeutet das nun für die nächsten Schritte?",
        "Auf Grundlage dieser Ergebnisse ergeben sich folgende Empfehlungen:",
        "Aus den Befunden leiten wir nun gemeinsam mit Ihnen das weitere Vorgehen ab.",
        "Nun zur Frage, wie es weitergeht:",
        "Basierend auf diesen Ergebnissen empfehlen wir folgende Maßnahmen:",
        "Zum Schluss fassen wir zusammen, welche konkreten Schritte für Sie sinnvoll sind und in welcher Reihenfolge wir sie planen.",
    ],
)

_add(
    "PX_TRANSITION_TO_RISK",
    "Übergang: zu Risikobesprechung",
    [
        "Ein wichtiger Aspekt ist auch, wie wir das Risiko einschätzen und worauf Sie achten sollten.",
        "Neben den Messwerten ist es wichtig, gemeinsam über mögliche Risiken und Warnzeichen zu sprechen.",
        "Im Folgenden möchten wir noch auf Punkte eingehen, die für Ihre Sicherheit wichtig sind.",
        "Bevor wir zum Abschluss kommen, möchten wir noch auf wichtige Sicherheitsaspekte hinweisen.",
        "Verstehen Sie Risikoeinschätzung bitte nicht als Bewertung, sondern als Werkzeug: "
        "Sie hilft uns, die Behandlung passgenau zuzuschneiden und dort intensiver zu kontrollieren, wo es sinnvoll ist.",
        "Zu einer guten Betreuung gehört, Chancen und Risiken offen zu benennen. "
        "So können wir gemeinsam die Schritte auswählen, die Ihnen den größten Nutzen bei möglichst geringer Belastung bringen.",
    ],
)

# ---------------------------------------------------------------------------
# Bündel: Zuordnung an Rulebook-Bundles (Kxx)
# ---------------------------------------------------------------------------
# Rulebook-Bundles in rhk_rules.yaml: K00, K01, K05, K06, K07, K09, K10, K11, K14, K15, K16
PATIENT_BUNDLES: Dict[str, List[str]] = {
    # kein Lungenhochdruck in Ruhe
    # (Der ausführliche Ablauf/Plan steht im generierten Patientenbericht; hier nur die Kernaussage.)
    "K00": ["PX_NO_PH", "PX_REASSURANCE"],

    # unvollständig / nicht eindeutig
    "K01": ["PX_INCOMPLETE", "PX_REASSURANCE"],

    # Belastungsreaktion linkskardial
    "K02": ["PX_EX_LEFT", "PX_REASSURANCE"],

    # Belastungsreaktion pulmonalvaskulär
    "K03": ["PX_EX_PVASC", "PX_REASSURANCE"],

    # unklassifiziert / grenzwertig
    "K04": ["PX_UNCLASSIFIED", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # präkapillär (leicht / mittel / deutlich)
    "K05": ["PX_PRECAP_MILD", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K06": ["PX_PRECAP_MOD",  "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K07": ["PX_PRECAP_SEV",  "PX_WHAT_IS_PH", "PX_EMPATHY_BURDEN", "PX_TRANSITION_TO_NEXT_STEPS"],

    # postkapillär / kombiniert
    "K14": ["PX_POSTCAP", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K15": ["PX_CPCPH",  "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # Belastungsdruckantwort
    "K09": ["PX_EX_PVASC", "PX_REASSURANCE"],
    "K10": ["PX_EX_LEFT", "PX_REASSURANCE"],

    # präkapillär + Hinweis auf ältere Blutgerinnsel
    "K11": ["PX_PRECAP_MOD", "PX_GROUP4_HINT", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # Shunt-Verdacht
    "K16": ["PX_SHUNT_HINT", "PX_REASSURANCE"],
}


# ---------------------------------------------------------------------------
# Patientenerklärungen zu den P-Modulen (P01–P52)
# ---------------------------------------------------------------------------

# Hinweis: Diese Texte werden im Patientenbericht als "Warum dieser Schritt?" ausgegeben.
# Ziel ist nicht Vollständigkeit, sondern ein verständlicher Mehrwert (Warum / Was / Wofür).
# Struktur je Eintrag:
#   **Kurztitel in Laiensprache:** Ein bis zwei Sätze — erklärt, warum dieser
#   Schritt geplant ist und was Patient*innen konkret erwartet.
# Für alle P-Module (inkl. P31–P52) muss hier ein Eintrag existieren; fehlende
# Keys würden im Laienbefund auf den technischen Modul-Titel zurückfallen, was
# für Patient*innen unverständlich ist.

PATIENT_MODULE_SUMMARY: Dict[str, str] = {
    "P01": "**Basisabklärung vervollständigen:** Wir ergänzen Standard-Untersuchungen, um Ursache und Schweregrad besser einzuordnen und die passende Behandlung zu wählen.",
    "P02": "**Entwässerung jetzt verstärken:** Bei aktuellen Zeichen einer Wassereinlagerung (geschwollene Beine, Gewichtszunahme, Atemnot) passen wir Ihre Entwässerungs-Medikamente an, damit der Körper den Überschuss ausscheiden kann.",
    "P03": "**Medikament zur Entlastung der Lungengefäße (PDE5-Hemmer):** Ein Baustein der Grund-Therapie bei bestimmten Formen von Lungenhochdruck. Wir kontrollieren Blutdruck und Verträglichkeit; Wechselwirkungen mit anderen Medikamenten (z.B. Nitraten) beachten wir.",
    "P04": "**Medikament zur Entlastung der Lungengefäße (ERA):** Zweite wichtige Wirkstoffgruppe. Wir kontrollieren die Leberwerte regelmäßig und achten auf Nebenwirkungen wie Beinschwellungen. Während der Therapie ist eine Schwangerschaft nicht möglich.",
    "P05": "**Riociguat:** Spezielles Medikament, vor allem bei Lungenhochdruck durch chronische Gerinnsel (CTEPH) oder als Alternative. Wichtig: nicht gleichzeitig mit PDE5-Hemmern einnehmen — wir halten Pausen zwischen den Präparaten ein.",
    "P06": "**Intensivere Therapie (bis hin zu Infusionstherapie) prüfen:** Wenn die bisherige Behandlung nicht ausreicht oder das rechte Herz stark belastet ist, besprechen wir im PH-Zentrum stärkere Optionen — einschließlich kontinuierlicher Medikamentengabe über einen Katheter.",
    "P07": "**Studienteilnahme prüfen:** Manchmal gibt es Studien, die zusätzliche Therapie-Optionen oder engmaschige Betreuung ermöglichen.",
    "P08": "**Interdisziplinäre Besprechung (Lunge/Bildgebung):** Befunde werden gemeinsam (Radiologie/Pneumologie/PH-Team) bewertet, um die Ursache sicherer festzulegen.",
    "P09": "**Kardiologische Mitbeurteilung:** Prüfung von Herzklappen, Herzrhythmus und Durchblutung – besonders wichtig, wenn die linke Herzseite mitbeteiligt ist.",
    "P10": "**Blutverdünnung (Antikoagulation) klären/optimieren:** Bei Verdacht auf Gerinnsel-Problematik ist das ein zentraler Baustein.",
    "P11": "**Verlaufskontrolle zeitnah (bei Therapieänderung oder instabiler Lage):** Weil sich gerade etwas geändert hat oder die Situation noch nicht stabil ist, planen wir kurzfristige Kontrollen (z.B. Echo, Labor) — zusätzlich zum regulären Ambulanz-Termin.",
    "P12": "**Lungenfunktion & Diffusion:** Klärt, ob die Lunge (Atemwege/Gewebe) zur Luftnot oder Druckerhöhung beiträgt.",
    "P13": "**Blutarmut / Eisenmangel abklären (Diagnostik):** Wir bestimmen Blutbild, Ferritin und Transferrin-Sättigung. Blutarmut und Eisenmangel verstärken oft Luftnot und Müdigkeit — zuerst klären wir, ob tatsächlich ein Mangel vorliegt.",
    "P14": "**Rechte Herzhälfte genauer einschätzen:** Ultraschall-Kennzeichen helfen zu beurteilen, wie stark das rechte Herz belastet ist – das beeinflusst Kontrollen und Therapieintensität.",
    "P15": "**Belastungsdiagnostik:** Ein Belastungstest kann zeigen, warum Beschwerden vor allem bei Aktivität auftreten und ob Herz, Lunge oder Kreislauf limitieren.",
    "P16": "**Schlafmedizin (Schlafapnoe) prüfen:** Atemaussetzer in der Nacht können Herz und Lunge belasten – Behandlung kann Symptome und Blutdruck verbessern.",
    "P17": "**Autoimmun-/Rheuma-Abklärung:** Manche Bindegewebserkrankungen können PH verursachen – Bluttests/Abklärung helfen, das zu erkennen.",
    "P18": "**Infektiologisches Screening:** Bestimmte Infektionen (z.B. HIV, Hepatitis) können relevant sein – je nach Situation wird dies überprüft.",
    "P19": "**Leber/Portale Hypertonie abklären:** Bei Hinweisen auf Leber-/Pfortader-Probleme kann das für die Ursache wichtig sein.",
    "P20": "**Genetische Aspekte prüfen:** Bei Familienhinweisen oder sehr frühem Beginn kann eine genetische Beratung/Testung sinnvoll sein.",
    "P21": "**Schwangerschaft/Verhütung besprechen:** Bei PH kann eine Schwangerschaft riskant sein – eine gute Beratung schützt.",
    "P22": "**Reha/Training:** Angepasstes, betreutes Training kann die Alltagsbelastbarkeit verbessern (oft besser als „Schonung“).",
    "P23": "**Impfstatus/Infektprophylaxe:** Atemwegsinfekte können Beschwerden verschlechtern – Schutzmaßnahmen werden geprüft.",
    "P24": "**Sauerstoffversorgung messen:** In Ruhe, bei Belastung und ggf. nachts – damit Therapie (z.B. Sauerstoff) gezielt eingestellt werden kann.",
    "P25": "**Advanced Therapies / Transplant-Optionen früh prüfen:** Bei schwerer Erkrankung ist es hilfreich, frühzeitig Optionen in einem Zentrum zu besprechen.",
    "P26": "**Trinkmengenrestriktion & Volumenmanagement:** Wenn der Körper Wasser einlagert, helfen klare Trinkmengen, tägliches Wiegen und ein konsequenter Plan, um Luftnot und Schwellungen zu vermeiden.",
    "P27": "**Kardiovaskuläre Risikofaktoren reduzieren:** Blutdruck, Blutzucker und Blutfette werden optimiert, Nikotinkarenz unterstützt und Begleiterkrankungen behandelt, damit Herz und Gefäße langfristig entlastet werden.",
    "P28": "**Gewichtsreduktion:** Eine strukturierte Gewichtsreduktion kann Belastbarkeit, Atmung und den Kreislauf entlasten, besonders wenn Übergewicht die Symptome verstärkt.",
    "P29": "**Sauerstoff-Langzeittherapie (LTOT) neu einleiten:** Wenn dauerhaft zu wenig Sauerstoff im Blut ankommt, verordnen wir eine Langzeitsauerstoff-Therapie. Wir stellen das Gerät gemeinsam ein und erklären die Anwendung.",
    "P30": "**CT Befunde interdisziplinär besprechen:** Ausstehende oder unklare CT Befunde werden in einer gemeinsamen Konferenz (Radiologie und Pneumologie) eingeordnet, damit das weitere Vorgehen gezielt geplant werden kann.",
    "P31": "**Lebensstil-Bausteine:** Bewegung, Ernährung, Nichtrauchen und die Behandlung von Begleiterkrankungen entlasten Ihr Herz-Kreislauf-System langfristig — wir zeigen konkrete Schritte für den Alltag.",
    "P32": "**Fluss und Druck genauer zuordnen:** Bei Ihnen ist die Druckerhöhung möglicherweise vor allem eine Folge von vermehrtem Blutfluss (z.B. bei Blutarmut, Schilddrüsen-Überfunktion, Lebererkrankung oder Kurzschluss-Verbindungen). Wir prüfen diese Ursachen, weil die Therapie dann anders aussieht als bei klassischem Lungenhochdruck.",
    "P33": "**Herzklappen im Team besprechen:** Hinweise auf eine relevante Herzklappen-Situation — Kardiologie, Kardiochirurgie und PH-Team beraten gemeinsam, ob und wann ein Eingriff sinnvoll ist.",
    "P34": "**CTEPH-Fallkonferenz:** Bei Verdacht auf Lungenhochdruck durch chronische Gerinnsel bespricht ein spezialisiertes Team (PH, Chirurgie, Katheter, Radiologie), welche Therapie für Sie am besten passt: Operation, Katheter-Dehnung der Lungengefäße (BPA) oder Medikamente.",
    "P35": "**Abklärung einer Kurzschluss-Verbindung:** Der Sauerstoffsprung in den Messungen legt nahe, dass Blut eine abnorme Verbindung zwischen Herzhöhlen oder Gefäßen nimmt. Wir untersuchen das mit Ultraschall mit Kontrastmittel und gegebenenfalls Kardio-MRT oder CT.",
    "P36": "**Herzmuskel-Steifigkeit genauer untersuchen:** Ein auffälliges Druck-Muster im Katheter spricht für eine mögliche Steifigkeit der Herzkammer oder des Herzbeutels. Das Kardio-MRT hilft, das besser einzuordnen.",
    "P37": "**Spezielle Schnittbild-Untersuchung der Lunge:** Ein hochauflösendes CT (ggf. mit Dual-Energy-Technik) zeigt Gefäße und Gewebe der Lunge detailliert — wichtig, um Gerinnsel, Gefäßverengungen oder andere Veränderungen sicher zu sehen.",
    "P38": "**Ursachen von hohem Blutfluss ausschließen:** Bevor wir die Therapie erweitern, prüfen wir Blutarmut, Schilddrüsen-Überfunktion, Leber-Erkrankungen und Kurzschluss-Verbindungen — sie alle können den Druck im Lungenkreislauf erhöhen, erfordern aber eine andere Behandlung.",
    "P39": "**Aorta im Verlauf kontrollieren:** Die Hauptschlagader ist leicht erweitert. Mit regelmäßigen Bildgebungen verfolgen wir, ob sich daran etwas ändert — das gibt Sicherheit und ermöglicht rechtzeitige Entscheidungen.",
    "P40": "**Wassereinlagerungen stabil halten (ambulante Kontrolle):** Die aktuelle Wasserbilanz ist in Ordnung — wir erhalten das. Tägliches Wiegen, festes Trinkverhalten und quartalsweise Labor-Kontrollen helfen, früh gegenzusteuern, falls sich etwas ändert.",
    "P41": "**Leberwerte abklären:** Bevor wir leberwirksame Medikamente einsetzen, untersuchen wir die erhöhten Leberwerte (Ultraschall des Bauchs, ggf. gastroenterologische Mitbeurteilung), damit die Therapie sicher verordnet werden kann.",
    "P42": "**Eisenmangel behandeln (Eisen-Infusion):** Der Eisenmangel ist bestätigt. In der Regel geben wir Eisen über eine kurze Infusion — das wirkt schneller und zuverlässiger als Tabletten und verbessert oft die Belastbarkeit innerhalb weniger Wochen.",
    "P43": "**Spiroergometrie (Herz-Lungen-Belastungstest):** Ein Belastungstest mit Atemgas-Messung zeigt, ob Ihre Beschwerden eher durch Lunge, Herz oder Muskulatur entstehen — das hilft, die nächsten Schritte gezielt zu planen.",
    "P44": "**6-Minuten-Gehtest:** Ein einfacher Test zur Einschätzung Ihrer aktuellen Belastbarkeit: Sie gehen sechs Minuten lang auf einer flachen Strecke, und wir messen die zurückgelegte Entfernung. Gut für Verlaufs-Vergleiche.",
    "P45": "**Lungengewebe gemeinsam beurteilen:** Vorhandene oder externe CT-Bilder der Lunge werden in einer pneumologisch-radiologischen Konferenz besprochen, um die richtige Einordnung (z.B. Fibrose, Emphysem) zu sichern.",
    "P46": "**Schlafuntersuchung:** Übergewicht oder auffällige Tagesmüdigkeit sprechen für mögliche Atemaussetzer in der Nacht. Eine nächtliche Aufzeichnung klärt, ob eine Behandlung (z.B. CPAP-Maske) sinnvoll ist.",
    "P47": "**Autoimmun-Labor vervollständigen:** Wir ergänzen Bluttests (z.B. ANA, ENA, Sklerodermie-Marker), um eine Autoimmun-Ursache des Lungenhochdrucks sicher auszuschließen oder zu erkennen.",
    "P48": "**Sauerstoff-Therapie optimieren:** Sie haben bereits eine Sauerstoff-Therapie. Wir prüfen mit Blutgas-Analysen in Ruhe, bei Belastung und nachts, ob die aktuelle Einstellung optimal ist, und passen den Fluss bei Bedarf an.",
    "P49": "**Engmaschige PH-Ambulanz-Termine (alle 3 Monate):** Wegen des erhöhten Risikos sehen wir uns häufiger — alle drei Monate — zu Labor, Echo und Gespräch. So können wir bei Bedarf zeitnah reagieren.",
    "P50": "**Blutdruck konsequent einstellen:** Ein zu hoher systemischer Blutdruck belastet zusätzlich das Herz und die Lungengefäße. Wir optimieren die Blutdruck-Medikation, damit die Gesamtsituation besser wird.",
    "P51": "**Regelmäßige PH-Ambulanz-Termine (alle 6 Monate):** Die aktuelle Situation ist stabil genug für einen sechsmonatigen Routine-Rhythmus: Labor, Echo und Gespräch. Zwischen den Terminen erreichen Sie uns bei Fragen jederzeit.",
    "P52": "**Studien-Koordination:** Wenn Sie an einer Studie teilnehmen, stimmen wir die Termine und Untersuchungen mit der Studien-Ambulanz ab, damit alles reibungslos zusammenläuft.",
}


# ---------------------------------------------------------------------------
# Glossar – kurze Erklärungen zentraler Begriffe
# ---------------------------------------------------------------------------

PATIENT_GLOSSARY: Dict[str, str] = {
    "PH": "Pulmonale Hypertonie (Lungenhochdruck): Erhöhter Blutdruck in den Gefäßen der Lunge.",
    "PAH": "Pulmonal-arterielle Hypertonie: Untergruppe des Lungenhochdrucks mit primärer Beteiligung der Lungengefäße.",
    "CTEPH": "Chronisch thromboembolische pulmonale Hypertonie: Lungenhochdruck durch ältere Blutgerinnsel in den Lungengefäßen.",
    "Rechtsherzkatheter": "Untersuchung, bei der über einen dünnen Schlauch Drücke und Blutfluss in Herz und Lunge gemessen werden.",
    "mPAP": "Mittlerer Druck in der Lungenarterie (ein Kernwert für Lungenhochdruck).",
    "PAWP": "Messwert, der Hinweise darauf geben kann, ob die linke Herzseite an der Druckerhöhung beteiligt ist.",
    "PVR": "Widerstand der Lungengefäße – vereinfacht: wie stark die Gefäße „eng“ sind.",
    "WU": "Wood-Units: Maßeinheit für den Widerstand in den Lungengefäßen (PVR).",
    "CO": "Herzzeitvolumen: Blutmenge, die das Herz pro Minute pumpt.",
    "CI": "Herzindex – wie viel Blut das Herz pro Minute (bezogen auf Körpergröße) fördert.",
    "RAP": "Druck im rechten Vorhof – kann bei Wassereinlagerung/„Rückstau“ erhöht sein.",
    "sPAP": "Systolischer Druck in der Lungenarterie (oberer Druckwert).",
    "dPAP": "Diastolischer Druck in der Lungenarterie (unterer Druckwert).",
    "präkapillär": "Muster, bei dem der Druckanstieg vor allem in den Lungengefäßen selbst entsteht.",
    "postkapillär": "Muster, bei dem die linke Herzseite den Druckanstieg mitverursacht.",
    "IpcPH": "Isoliert postkapilläre pulmonale Hypertonie: Druckanstieg überwiegend durch die linke Herzseite.",
    "CpcPH": "Kombinierte post- und präkapilläre pulmonale Hypertonie: Druckübertragung von links plus Gefäßveränderung in der Lunge.",
    "HFpEF": "Herzschwäche trotz normaler Pumpkraft: Das Herz ist oft „steifer“ und füllt sich schlechter, vor allem bei Belastung.",
    "Dyspnoe": "Luftnot.",
    "Synkope": "Kurzzeitige Ohnmacht durch vorübergehend verminderte Hirndurchblutung.",
    "WHO-FC": "WHO-Funktionsklasse: Einteilung, wie stark Symptome die Alltagsbelastbarkeit einschränken.",
    "6MWD": "6-Minuten-Gehtest: Strecke, die in sechs Minuten gegangen werden kann; zeigt die aktuelle Belastbarkeit.",
    "V/Q": "Ventilations-/Perfusionsszintigrafie: Untersuchung der Lungen-Durchblutung (wichtig bei Verdacht auf ältere Blutgerinnsel).",
    "CT": "Computertomographie: Schnittbild-Untersuchung, z.B. von Lunge und Lungengefäßen.",
    "Antikoagulation": "Blutverdünnung (Gerinnungshemmung), um Blutgerinnsel zu verhindern oder zu behandeln.",
    "NT-proBNP": "Blutwert, der auf die Belastung des Herzens hinweisen kann.",
    "NT pro BNP": "Alternative Schreibweise von NT-proBNP; Blutwert als Hinweis auf Herzbelastung.",
    "DLCO": "Diffusionskapazität: zeigt, wie gut Sauerstoff über die Lunge ins Blut gelangt.",
    "Tiffeneau": "FEV1/FVC-Quotient aus der Lungenfunktion. Ein niedriger Wert kann für verengte Atemwege sprechen.",
    "ILD": "Interstitielle Lungenerkrankung (z.B. Lungenfibrose): Erkrankung des Lungengewebes.",
    "ERA": "Medikamentengruppe bei bestimmten Formen von PH/PAH (wir erklären im Gespräch, ob das für Sie passt).",
    "PDE5": "Medikamentengruppe, die Lungengefäße entspannen kann (z.B. Sildenafil/Tadalafil).",
    "Echokardiografie": "Ultraschall-Untersuchung des Herzens: zeigt Größe, Funktion und Klappen beider Herzhälften.",
    "Vasoreaktivität": "Testverfahren während des Herzkatheters, bei dem geprüft wird, ob die Lungengefäße auf ein Medikament reagieren.",
    "Volumenchallenge": "Gezielter Flüssigkeitstest während des Herzkatheters, um eine versteckte Beteiligung der linken Herzseite aufzudecken.",
    "Funktionsklasse": "Einteilung (I–IV), wie stark Beschwerden den Alltag einschränken (I = keine Einschränkung, IV = Beschwerden in Ruhe).",
    "Prostacyclin": "Körpereigener Botenstoff, der Lungengefäße erweitert. Wird in verschiedenen Formen als Medikament eingesetzt.",
    "BPA": "Ballon-Pulmonale-Angioplastie: Katheter-Eingriff, bei dem verengte Lungengefäße mit einem Ballon aufgedehnt werden (bei chronischen Gerinnseln).",
    "PEA": "Pulmonale Endarteriektomie: Operation, bei der chronische Gerinnsel aus den Lungengefäßen entfernt werden.",
    "Eisenmangel": "Häufiger Begleitzustand bei Lungenhochdruck, der Müdigkeit und Luftnot verstärken kann. Lässt sich gut behandeln.",
    "Diuretikum": "Entwässerungsmedikament: hilft, Wassereinlagerungen zu reduzieren und das Herz zu entlasten.",
    "Ödeme": "Wassereinlagerungen, vor allem in Beinen, Knöcheln oder Bauch. Können ein Zeichen für Rückstau im Kreislauf sein.",
    "Sättigung": "Sauerstoffsättigung: zeigt, wie gut das Blut mit Sauerstoff beladen ist. Wird oft am Finger gemessen.",
    "Shunt": "Abnormale Verbindung zwischen zwei Herzhöhlen oder Blutgefäßen, durch die Blut auf einem ungewöhnlichen Weg fließt.",
    "Compliance": "Dehnbarkeit der Lungengefäße: beschreibt, wie elastisch die Gefäße noch sind.",
    "Rechtsherzversagen": "Zustand, in dem das rechte Herz die erhöhte Belastung nicht mehr ausreichend bewältigen kann.",
    "Sotatercept": "Neueres Medikament für bestimmte Formen von PAH, das über den BMPR2/Activin-Signalweg wirkt und die Lungengefäße entlasten kann.",
    "Riociguat": "Medikament, das bei bestimmten Formen von PH (u.a. CTEPH) die Lungengefäße erweitern kann.",
    "BMPR2": "Ein Signalweg in den Zellen der Gefäßwand, der bei PAH gestört sein kann. Sotatercept greift hier an.",
}



# ---------------------------------------------------------------------------
# Vertikale Verfeinerung: Symptom-Gewichtung (Sub-Layer)
# ---------------------------------------------------------------------------

_add(
    "PX_SYMPTOM_PROFILE_LOW",
    "Symptomprofil: eher milde Beschwerden",
    [
        "Ihre Angaben sprechen eher f��r milde Einschränkungen im Alltag. Wichtig ist trotzdem, Veränderungen früh zu bemerken und nicht nur auf einzelne Messwerte zu schauen.",
        "Die Belastbarkeit wirkt insgesamt eher stabil. Entscheidend ist, ob sich Luftnot oder Leistungsfähigkeit im Verlauf verändern.",
        "Im Alltag scheinen Sie wenig eingeschränkt zu sein. Das ist ein positives Signal. Bitte beobachten Sie, ob sich daran etwas ändert.",
        "Milde Beschwerden bei vorhandenen Befunden können ein Zeichen dafür sein, dass der Körper die Situation noch gut ausgleicht. Regelmäßige Kontrollen helfen, das zu beobachten.",
        "Dass Ihre Beschwerden aktuell gering sind, nehmen wir als guten Ausgangspunkt für die weitere Betreuung. Veränderungen im Verlauf sind dennoch wichtig zu erkennen.",
        "Wenige Beschwerden trotz auffälliger Messwerte sind nicht ungewöhnlich – der Körper kompensiert oft lange, bevor sich etwas deutlich bemerkbar macht. Genau deshalb sind regelmäßige Kontrollen auch in gefühlt guten Phasen wichtig.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_MODERATE",
    "Symptomprofil: mittlere Einschränkungen",
    [
        "Ihre Beschwerden wirken im Alltag spürbar. Wir richten die nächsten Schritte deshalb nicht nur nach Zahlen aus, sondern auch nach dem, was Sie im täglichen Leben belastet.",
        "Bei mittleren Beschwerden ist oft die Kombination aus Messwerten, Belastbarkeit und Verlauf entscheidend. Genau darauf stützen wir die Planung der Kontrollen und Therapie.",
        "Ihre Beschwerden beeinflussen den Alltag merklich. Das ist ein wichtiges Signal, das wir bei der Therapieplanung berücksichtigen.",
        "Moderate Einschränkungen zeigen, dass der Körper die Belastung zwar noch bewältigt, aber bereits an seine Grenzen kommt. Hier können gezielte Maßnahmen oft eine spürbare Verbesserung bringen.",
        "Wenn Alltagsaktivitäten etwas schwerer fallen als gewohnt, ist das ein Grund, genauer hinzuschauen. Wir nutzen diese Information, um die Behandlung so anzupassen, dass Sie sich im Alltag wieder wohler fühlen.",
        "Eine mittlere Ausprägung der Beschwerden lässt oft noch deutlichen Spielraum nach oben – mit gezielter Therapie, Training und manchmal auch kleinen Anpassungen im Alltag lassen sich häufig spürbare Verbesserungen erreichen.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_HIGH",
    "Symptomprofil: deutliche Einschränkungen",
    [
        "Sie berichten über deutliche Einschränkungen. Dann ist besonders wichtig, dass wir nicht nur die Messwerte betrachten, sondern gezielt klären, was Ihre Beschwerden antreibt und wie wir die Situation rasch stabilisieren.",
        "Wenn Alltagstätigkeiten deutlich schwerfallen, hat das für die Therapieplanung ein hohes Gewicht. Wir besprechen deshalb engmaschig, welche Schritte am meisten helfen können.",
        "Deutliche Beschwerden im Alltag sind ein wichtiges Signal. Wir nehmen das sehr ernst und priorisieren die Maßnahmen, die Ihnen am schnellsten Erleichterung bringen können.",
        "Ihre Einschränkungen wirken erheblich. In dieser Situation arbeiten wir besonders eng mit Ihnen zusammen, um die Belastung schnellstmöglich zu reduzieren.",
        "Bei ausgeprägten Beschwerden steht Ihre Lebensqualität im Mittelpunkt der Behandlung. Wir prüfen alle Möglichkeiten, um Ihren Alltag so weit wie möglich zu erleichtern.",
        "Deutliche Beschwerden bedeuten oft, dass wir nicht Monate warten wollen, sondern zügiger eine wirksame Therapie aufbauen. Wir richten die Termine und Entscheidungen entsprechend eng getaktet aus.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_SYNCOPE",
    "Symptomprofil: Synkope als Warnsignal",
    [
        "Ohnmacht oder Beinahe-Ohnmacht ist bei Lungengefäßerkrankungen ein wichtiges Warnsignal. Bitte melden Sie solche Episoden immer zeitnah, auch wenn einzelne Werte auf den ersten Blick nicht dramatisch wirken.",
        "Synkopen sind ein ernstes Signal, weil kurzfristig weniger Blut im Kreislauf ankommen kann. Das beeinflusst, wie wir Risiko und Therapie einschätzen.",
        "Bewusstlosigkeit oder kurzes Schwarzwerden vor den Augen nehmen wir bei Lungengefäßerkrankungen besonders ernst. Bitte berichten Sie jede solche Episode umgehend.",
        "Ohnmachtsanfälle zeigen, dass der Kreislauf vorübergehend nicht ausreichend versorgt wird. Das hat für uns ein hohes Gewicht bei der Einschätzung der Dringlichkeit.",
        "Falls Ohnmacht oder Beinahe-Ohnmacht aufgetreten ist, ordnen wir die Befunde mit besonderer Sorgfalt ein. Solche Episoden beeinflussen, wie engmaschig wir kontrollieren und wie rasch wir handeln.",
        "Auch eine einzelne Synkope – selbst wenn alles wieder gut ausgeht – ist für uns ein roter Faden. Sie verändert Risikoeinschätzung, Therapiewahl und gegebenenfalls die Dringlichkeit weiterer Abklärungen.",
    ],
)

# ---------------------------------------------------------------------------
# Vertikale Verfeinerung: Diskrepanz-Erklärungen (Sub-Layer)
# ---------------------------------------------------------------------------

_add(
    "PX_DISCORDANCE_HIGH_MPAP_LOW_BNP",
    "Diskrepanz: hoher Druck, niedriger BNP",
    [
        "Manchmal ist der Druck im Lungenkreislauf deutlich erhöht, während der Blutwert BNP oder NT pro BNP niedrig bleibt. Das kann vorkommen, wenn das rechte Herz die Belastung noch gut kompensiert oder wenn der Blutwert durch andere Faktoren mit beeinflusst wird. Entscheidend ist dann die Gesamtschau mit Belastbarkeit und Echo.",
        "Ein niedriger BNP oder NT pro BNP Wert schließt eine Druckerhöhung nicht aus. Wir nutzen den Wert als Verlaufspunkt, aber nicht als alleinige Erklärung Ihrer Situation.",
        "Die scheinbare Diskrepanz zwischen hohem Druck und niedrigem BNP-Wert ist kein Widerspruch. Sie zeigt eher, dass das rechte Herz die Belastung derzeit noch gut bewältigt. Das ist ein positives Signal, das wir im Verlauf weiter beobachten.",
        "BNP ist ein wertvoller Marker, aber kein Allheilmittel. Körpergewicht, Alter, Nierenfunktion und Medikamente können den Wert beeinflussen – deshalb setzen wir ihn immer ins Verhältnis zum Gesamtbild.",
    ],
)

_add(
    "PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS",
    "Diskrepanz: eher niedriger Druck, aber starke Beschwerden",
    [
        "Starke Beschwerden können auch auftreten, wenn die Druckwerte nur moderat sind. Gründe können zum Beispiel eine eingeschränkte Pumpleistung, Rückstau, eine Lungenerkrankung, Blutarmut oder ein Zusammenspiel mehrerer Faktoren sein. Deshalb betrachten wir immer das Gesamtbild.",
        "Wenn Symptome und Druckwerte nicht zusammenpassen, ist das kein Widerspruch. Dann prüfen wir gezielt andere Ursachen, die die Belastbarkeit im Alltag beeinflussen.",
        "Ihre Beschwerden sind stärker als es die Druckwerte allein erklären würden. Das nehmen wir sehr ernst und suchen gezielt nach zusätzlichen Faktoren, die Ihre Belastbarkeit beeinflussen.",
        "Manchmal steigen Druckwerte erst unter Belastung deutlich an, auch wenn sie in Ruhe unauffällig scheinen. Deshalb kombinieren wir Ruhemessung, Belastungsuntersuchungen und Ihre Alltagserfahrung, um ein vollständiges Bild zu bekommen.",
    ],
)

_add(
    "PX_DISCORDANCE_ECHO_OK_CATH_HIGH",
    "Diskrepanz: Echo wirkt beruhigend, Katheter zeigt hohe Werte",
    [
        "Das Echo kann manchmal unauffällig wirken, obwohl der Herzkatheter erhöhte Druckwerte zeigt. Das liegt daran, dass Echo Werte indirekt schätzt und nicht immer jede Konstellation sicher abbilden kann. Für die Einordnung ist der Katheter dann besonders wichtig.",
        "Wenn Echo und Katheter unterschiedliche Signale geben, orientieren wir uns an den zuverlässigsten Messungen und schauen zusätzlich auf Verlauf und Beschwerden.",
        "Der Herzkatheter misst die Druckwerte direkt und gilt deshalb als genauer. Dass das Echo unauffällig wirkte, bedeutet nicht, dass der Befund weniger ernst zu nehmen ist. Beide Untersuchungen ergänzen sich.",
        "Wir wissen, dass so ein Unterschied zunächst irritierend wirken kann – vielleicht hatten Sie nach dem Echo das Gefühl, es sei alles in Ordnung. Der Katheter liefert nun eine genauere Einschätzung, und auf dieser Grundlage planen wir die nächsten Schritte.",
        "Weil der Herzkatheter die Drücke direkt in den Blutgefäßen der Lunge misst, zählt er bei der Diagnosestellung als Goldstandard. Das Echo bleibt wichtig für den Verlauf, ersetzt aber in kritischen Konstellationen nicht die direkte Messung.",
        "Gerade bei leichter bis mittlerer Druckerhöhung kann das Echo unauffällig erscheinen – das ist eine bekannte Grenze der Methode, kein Fehler. Genau deshalb haben wir den Katheter gemacht, um sicher einzuordnen, was im Ultraschall noch nicht sichtbar war.",
    ],
)


# ---------------------------------------------------------------------------
# Messwert-Bausteine (v27.4.24+): Varianten für bisher hart kodierte Sätze
# im Abschnitt "Was wurde bei Ihnen gemessen – und warum ist das wichtig?".
# Platzhalter:
#   {mpap_str}       — z. B. "26" (aus mPAP in mmHg, ganzzahlig)
#   {pawp_str}       — z. B. "12"
#   {pvr_str}        — z. B. "3.4" (eine Nachkommastelle)
#   {ci_str}         — z. B. "2.10"
#   {rap_str}        — z. B. "8"
# ---------------------------------------------------------------------------

_add(
    "PX_MEASURE_MPAP_ELEVATED",
    "Messung: erhöhter mPAP (mit Wert)",
    [
        "Bei Ihnen wurde ein erhöhter Druck im Lungenkreislauf gemessen (mPAP {mpap_str} mmHg, Lungenhochdruck ab >20 mmHg). Das bedeutet: Das rechte Herz muss Blut gegen einen höheren Widerstand in Richtung Lunge pumpen.",
        "Die Direktmessung im Herzkatheter ergab einen mittleren Lungendruck von {mpap_str} mmHg. Ab einem Wert über 20 mmHg sprechen wir von einer pulmonalen Hypertonie – Ihr Wert liegt darüber. Für das rechte Herz bedeutet das mehr Arbeit beim Bluttransport zur Lunge.",
        "Der mittlere Druck in den Lungenarterien liegt bei Ihnen bei {mpap_str} mmHg und damit oberhalb der Schwelle von 20 mmHg. Dadurch braucht Ihre rechte Herzkammer mehr Kraft, um das Blut in die Lunge zu befördern.",
        "Im Herzkatheter zeigte sich ein erhöhter mittlerer Lungendruck (mPAP {mpap_str} mmHg). Werte bis einschließlich 20 mmHg gelten als normal; alles darüber wird als pulmonale Hypertonie eingeordnet. Das rechte Herz wird dadurch stärker belastet.",
        "Die Messung bestätigt einen Lungenhochdruck: Ihr mittlerer Lungendruck beträgt {mpap_str} mmHg (Grenzwert 20 mmHg). Das rechte Herz muss mehr Druck aufbauen, um das Blut in die Lungengefäße zu befördern.",
        "Bei der Messung im Herzkatheter lag Ihr mittlerer Druck in der Lungenschlagader bei {mpap_str} mmHg. Das ist oberhalb des normalen Bereichs und zeigt, dass das rechte Herz vermehrt gegen einen Widerstand Richtung Lunge pumpen muss.",
    ],
)

_add(
    "PX_MEASURE_PH_NO_MPAP",
    "Messung: Lungenhochdruck ohne konkreten mPAP-Wert",
    [
        "Bei Ihnen zeigen die Messungen einen Lungenhochdruck. Das bedeutet: Das rechte Herz muss Blut gegen einen höheren Widerstand in Richtung Lunge pumpen.",
        "Die Messwerte sprechen für einen Lungenhochdruck. Ihr rechtes Herz arbeitet dadurch gegen einen erhöhten Widerstand, wenn es Blut Richtung Lunge transportiert.",
        "Die Untersuchung zeigt, dass der Druck im Lungenkreislauf erhöht ist. Das rechte Herz braucht deshalb mehr Kraft, um Blut in die Lungengefäße zu pumpen.",
        "Zusammengefasst ergibt sich das Bild eines Lungenhochdrucks. Für Sie ist wichtig zu wissen: Ihr rechtes Herz steht unter einer höheren Belastung als bei einem normalen Kreislauf.",
        "Nach den aktuellen Messungen liegt ein Lungenhochdruck vor. Das heißt praktisch: Die rechte Herzhälfte muss einen höheren Widerstand überwinden, um das Blut in die Lunge zu befördern.",
        "Unterm Strich zeigen die Werte einen erhöhten Druck im Lungenkreislauf. Dadurch hat das rechte Herz mehr zu tun als normal, weil es das Blut gegen diesen Widerstand pumpen muss.",
    ],
)

_add(
    "PX_MEASURE_PRECAP_PATTERN",
    "Messung: präkapilläres Muster (PAWP normal, PVR erhöht)",
    [
        "Der Druck vor der linken Herzhälfte ist dabei nicht erhöht (PAWP {pawp_str} mmHg). Gleichzeitig ist der Widerstand in den Lungengefäßen deutlich erhöht (PVR {pvr_str} WU, erhöht ab >2 WU). Das Muster spricht eher für eine Ursache im Lungenkreislauf selbst oder im Zusammenhang mit einer Lungenerkrankung.",
        "Auf der linken Seite des Herzens ist der Druck mit {pawp_str} mmHg im normalen Bereich. Gleichzeitig ist der Widerstand in den kleinen Lungengefäßen erhöht (PVR {pvr_str} WU). Diese Kombination deutet auf eine Form hin, bei der die Lungengefäße oder die Lunge selbst im Vordergrund stehen.",
        "Der PAWP (Druck vor der linken Herzkammer) liegt mit {pawp_str} mmHg im Normbereich. Der Gefäßwiderstand in der Lunge (PVR) ist mit {pvr_str} WU dagegen erhöht. Dieses Muster nennt man präkapillär – die linke Herzhälfte ist also nicht die Hauptursache.",
        "Messwertlich typisch für eine Erkrankung der Lungengefäße: Der PAWP ist normal ({pawp_str} mmHg), der PVR ist erhöht ({pvr_str} WU). Die Ursache liegt damit eher vor der linken Herzhälfte, also in den Lungenarterien selbst.",
        "Hier zeigt sich ein sogenanntes präkapilläres Muster: Der Druck direkt vor dem linken Herzen ist normal (PAWP {pawp_str} mmHg), aber der Widerstand in den Lungengefäßen ist erhöht (PVR {pvr_str} WU). Das passt zu einer Erkrankung der Lungengefäße oder der Lunge.",
        "Die Kombination aus normalem PAWP ({pawp_str} mmHg) und erhöhtem PVR ({pvr_str} WU) nennt man präkapillär. In einfachen Worten: Die linke Herzhälfte arbeitet sauber – der Engpass liegt in den Gefäßen der Lunge.",
    ],
)

_add(
    "PX_MEASURE_POSTCAP_PAWP_HIGH",
    "Messung: postkapilläres Muster (PAWP erhöht)",
    [
        "Der Druck vor der linken Herzhälfte ist erhöht (PAWP {pawp_str} mmHg). Das kann einen Rückstau in die Lunge begünstigen und wird bei der Einordnung mit berücksichtigt.",
        "Auf der linken Seite des Herzens ist der Druck mit {pawp_str} mmHg erhöht. Dieser Rückstau kann sich bis in die Lunge fortsetzen und fließt in die Einordnung ein.",
        "Der PAWP (Maß für den Druck vor der linken Herzkammer) liegt bei {pawp_str} mmHg und damit über dem normalen Bereich. Das bedeutet: Ein Teil des Lungendrucks erklärt sich aus dem Rückstau von der linken Herzhälfte.",
        "Ein erhöhter PAWP von {pawp_str} mmHg spricht dafür, dass die linke Herzhälfte am Lungenhochdruck beteiligt ist. Diesen Anteil berücksichtigen wir bei der Therapieplanung mit.",
        "Bei Ihnen zeigt sich ein postkapilläres Muster: Der PAWP liegt mit {pawp_str} mmHg oberhalb des Normbereichs. Das weist darauf hin, dass der Blutstau in die Lunge von der linken Herzseite mitverursacht wird.",
        "Die Messung zeigt einen Rückstau aus der linken Herzhälfte in Richtung Lunge (PAWP {pawp_str} mmHg). Das ist ein wichtiger Baustein, um die Ursache Ihres Lungenhochdrucks genauer einzuordnen.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW",
    "Messung: reduzierte Pumpleistung (CI niedrig oder grenzwertig)",
    [
        "Die Pumpleistung des Herzens ist dabei eher reduziert (CI {ci_str} l/min/m²). Das kann erklären, warum Belastung schneller schwerfällt oder Schwindel auftreten kann.",
        "Der Herzindex (CI), ein Maß für die Pumpleistung, liegt mit {ci_str} l/min/m² unter bzw. am Rand des normalen Bereichs. Das passt dazu, dass Sie bei Belastung eher schnell an Grenzen stoßen.",
        "Aus den Messungen ergibt sich eine eher niedrige Pumpleistung (CI {ci_str} l/min/m²). Für Sie kann das bedeuten, dass körperliche Belastung früher anstrengend wird oder auch Schwindel möglich ist.",
        "Die Pumpleistung pro Quadratmeter Körperoberfläche liegt bei {ci_str} l/min/m² und ist damit eher gering. Das erklärt oft Symptome wie rasche Erschöpfung oder Benommenheit bei Anstrengung.",
        "Ihr Herz pumpt unter Ruhebedingungen weniger Volumen, als wir uns wünschen würden (CI {ci_str} l/min/m²). Das kann einen Teil Ihrer Alltagsbeschwerden, insbesondere die Belastungsintoleranz, erklären.",
        "Der CI (Cardiac Index) ist mit {ci_str} l/min/m² reduziert. Er beschreibt, wie viel Blut Ihr Herz im Verhältnis zu Ihrer Körpergröße pro Minute auswirft – ein niedrigerer Wert bedeutet weniger Reserve bei Anstrengung.",
    ],
)

_add(
    "PX_MEASURE_CI_OK",
    "Messung: erhaltene Pumpleistung (CI normal)",
    [
        "Die Pumpleistung ist im Rahmen der Messung nicht klar vermindert (CI {ci_str} l/min/m²).",
        "Der Herzindex liegt bei {ci_str} l/min/m² und ist damit nicht eindeutig reduziert. Die Pumpleistung ist aus dieser Sicht erhalten.",
        "Die Pumpleistung des Herzens ist in der Messung unauffällig (CI {ci_str} l/min/m²). Das ist eine gute Ausgangslage für die weitere Therapie.",
        "Aus dem CI-Wert ({ci_str} l/min/m²) lässt sich keine klare Pumpschwäche ableiten. Die Pumpleistung des Herzens ist in dieser Momentaufnahme in Ordnung.",
        "Ihr CI (Cardiac Index) liegt mit {ci_str} l/min/m² im akzeptablen Bereich. Die Pumpleistung Ihres Herzens ist zum Messzeitpunkt nicht eingeschränkt.",
        "Die Messung der Pumpleistung ergibt einen CI von {ci_str} l/min/m². Damit sehen wir aktuell keine klare Pumpschwäche.",
    ],
)

_add(
    "PX_MEASURE_RAP_HIGH",
    "Messung: erhöhter rechter Vorhofdruck (RAP)",
    [
        "Der Druck im rechten Vorhof (RAP) liegt bei {rap_str} mmHg und ist erhöht. Das kann ein Hinweis auf eine stärkere Belastung der rechten Herzhälfte sein.",
        "Im rechten Vorhof haben wir einen Druck von {rap_str} mmHg gemessen – das ist erhöht. Es deutet darauf hin, dass die rechte Herzhälfte bereits gegen einen höheren Widerstand arbeitet.",
        "Der RAP (Druck im rechten Vorhof) liegt bei {rap_str} mmHg und damit über dem üblichen Bereich. Ein erhöhter RAP ist ein Zeichen, dass das rechte Herz unter Belastung steht.",
        "Ein erhöhter rechter Vorhofdruck von {rap_str} mmHg zeigt uns, dass sich vor der rechten Herzkammer Druck aufbaut. Das ist ein Warnsignal für die rechtsseitige Herzbelastung und fließt in die Risikoeinschätzung mit ein.",
        "Der Messwert im rechten Vorhof ist mit {rap_str} mmHg erhöht. Je höher dieser Wert, desto mehr arbeitet die rechte Herzhälfte gegen einen Gegendruck. Das berücksichtigen wir bei der Therapieplanung.",
        "Der RAP ({rap_str} mmHg) gehört zu den zentralen Risikomarkern. Er ist bei Ihnen erhöht, und das nehmen wir als Hinweis auf eine deutliche Belastung der rechten Herzhälfte ernst.",
    ],
)

_add(
    "PX_MEASURE_PRECAP_ONLY_CATEGORY",
    "Messung: präkapillär ohne Zahlenwerte (Kategorie)",
    [
        "Das Messmuster passt eher zu einer Form, bei der die Lungengefäße oder die Lunge selbst im Vordergrund stehen.",
        "Zusammengefasst passt das Muster am ehesten zu einer Erkrankung, die von den Lungengefäßen ausgeht.",
        "Die Werte deuten darauf hin, dass die Lungengefäße oder die Lunge selbst die Hauptursache sind – nicht die linke Herzhälfte.",
        "In der Gesamtschau zeigt sich ein Muster, das wir als präkapillär bezeichnen: Die eigentliche Ursache liegt im Lungenkreislauf, nicht im linken Herzen.",
        "Das Zusammenspiel der Messwerte spricht für eine Form, die vor allem die Lungengefäße betrifft. Die linke Herzseite scheint dabei eine eher untergeordnete Rolle zu spielen.",
        "Für die weitere Therapie ist wichtig: Die Messungen passen zu einer Form, die in den Lungengefäßen selbst beginnt – und damit zu einer gefäßgerichteten Behandlung.",
    ],
)

_add(
    "PX_MEASURE_POSTCAP_ONLY_CATEGORY",
    "Messung: Beteiligung der linken Herzseite (Kategorie)",
    [
        "Das Messmuster passt eher zu einer Form, bei der die linke Herzseite mitbeteiligt sein kann.",
        "Die Messwerte deuten darauf hin, dass die linke Herzhälfte am Lungenhochdruck mitbeteiligt ist.",
        "Zusammengefasst spricht das Muster dafür, dass auch die linke Herzseite an der Druckerhöhung mitwirkt.",
        "Im Gesamtbild passt Ihr Befund zu einer Form, bei der die linke Herzhälfte mit einer Rolle spielt. Das beeinflusst die Wahl der Therapie.",
        "Die Konstellation der Werte zeigt, dass die linke Herzseite wahrscheinlich mitbeteiligt ist. Wir berücksichtigen das bei der weiteren Behandlung.",
        "Das Muster spricht dafür, dass nicht nur die Lungengefäße, sondern auch die linke Herzhälfte am Lungenhochdruck mitbeteiligt sind.",
    ],
)


# ---------------------------------------------------------------------------
# Severity-Tiers für hämodynamische Kernmessgrößen
# ---------------------------------------------------------------------------
# Schwellen:
#   mPAP: normal ≤20 · leicht 21–30 · mittel 31–45 · schwer >45 mmHg
#   PAWP: normal ≤15 · leicht 16–20 · mittel 21–25 · schwer >25 mmHg
#   PVR:  normal ≤2  · leicht 2.1–3 · mittel 3.1–5 · schwer >5 WU
#   RAP:  normal ≤7  · leicht 8–12  · mittel 13–15 · schwer >15 mmHg
#   CI:   grenzwertig 2.2–2.5 · reduziert 1.8–<2.2 · deutlich <1.8 l/min/m²
# Ton: leicht = ruhig/beobachten · mittel = klar handlungsleitend · schwer = ernst, aber
# nicht alarmierend; Therapieoptionen stets benennen.

_add(
    "PX_MEASURE_MPAP_MILD",
    "Messung: mPAP leicht erhöht (21–30 mmHg)",
    [
        "Der mittlere Lungendruck liegt mit {mpap_str} mmHg leicht über dem Grenzwert von 20 mmHg. Ihr rechtes Herz arbeitet damit gegen einen etwas höheren Widerstand — diese Konstellation beobachten wir aufmerksam, erfordert aber nicht zwingend eine sofortige Therapie.",
        "Mit einem mPAP von {mpap_str} mmHg liegt bei Ihnen eine leichte Druckerhöhung in den Lungengefäßen vor (Schwelle >20 mmHg). Das ist ein Befund, bei dem die genaue Ursache im Vordergrund steht — die absolute Druckhöhe allein ist noch kein Grund zur Sorge.",
        "Die Messung ergab einen leicht erhöhten Lungendruck (mPAP {mpap_str} mmHg). In diesem Bereich ist das rechte Herz in der Regel noch gut kompensiert. Entscheidend sind jetzt die Ursache und das Gesamtbild mit Beschwerden und Belastbarkeit.",
        "Ihr mittlerer Druck in der Lungenarterie ist mit {mpap_str} mmHg grenzwertig bis leicht erhöht. Das rechte Herz kann diese Mehrarbeit im Alltag meist gut leisten. Wichtig bleibt, die Ursache einzuordnen und den Verlauf zu beobachten.",
        "Der Lungendruck ist mit {mpap_str} mmHg leicht über der Schwelle. Solche Werte finden wir häufig früh im Verlauf oder bei Begleiterkrankungen — eine strukturierte Abklärung hilft, die Ursache präzise einzugrenzen.",
        "Mit {mpap_str} mmHg liegt Ihr Lungendruck am unteren Ende des erhöhten Bereichs. Das bedeutet: Es gibt eine messbare Veränderung, aber in einer Größenordnung, die sich oft gut beeinflussen lässt, wenn wir die Ursache gezielt adressieren.",
    ],
)

_add(
    "PX_MEASURE_MPAP_MOD",
    "Messung: mPAP mittelgradig erhöht (31–45 mmHg)",
    [
        "Der mittlere Lungendruck beträgt {mpap_str} mmHg und ist damit klar erhöht (Normbereich ≤20 mmHg). Das rechte Herz muss spürbar mehr Arbeit leisten — ein Befund, der eine strukturierte Therapieplanung rechtfertigt.",
        "Mit einem mPAP von {mpap_str} mmHg liegt eine mittelgradige Lungendruckerhöhung vor. Das ist kein Notfall, aber ein klares Signal, die Ursache gezielt zu behandeln, damit das rechte Herz entlastet wird.",
        "Die Druckwerte in Ihrer Lungenarterie sind mit {mpap_str} mmHg deutlich erhöht. In diesem Bereich profitieren die meisten Patient:innen von einer gezielten Therapie — welche davon für Sie passt, klären wir im nächsten Schritt.",
        "Der Lungendruck liegt bei {mpap_str} mmHg und damit im mittleren Bereich der Druckerhöhung. Das rechte Herz bewältigt diese Belastung derzeit, aber eine konsequente Behandlung hilft, langfristige Folgen zu vermeiden.",
        "Mit {mpap_str} mmHg ist Ihr Lungendruck relevant erhöht. Moderne Therapien können in diesem Bereich oft messbar Druck und Belastbarkeit verbessern — wir schauen gemeinsam, welche Bausteine für Sie sinnvoll sind.",
        "Ein mPAP von {mpap_str} mmHg bedeutet, dass die Lungengefäße einen deutlichen Widerstand aufbauen. Für Sie bedeutet das: Belastung kann sich anstrengender anfühlen als früher — und genau da setzen wir mit der Therapie an.",
    ],
)

_add(
    "PX_MEASURE_MPAP_SEV",
    "Messung: mPAP deutlich erhöht (>45 mmHg)",
    [
        "Der mittlere Lungendruck ist mit {mpap_str} mmHg ausgeprägt erhöht. Das bedeutet, dass Ihr rechtes Herz unter erheblicher Belastung arbeitet und eine rasche, strukturierte Therapie wichtig ist — oft in einem spezialisierten Zentrum.",
        "Mit {mpap_str} mmHg zeigt sich eine schwergradige Druckerhöhung in der Lungenarterie. Das ist ernst zu nehmen, aber behandelbar: Heute stehen mehrere Medikamentenklassen zur Verfügung, die wir oft in Kombination einsetzen.",
        "Ihr Lungendruck beträgt {mpap_str} mmHg und liegt damit weit oberhalb des normalen Bereichs. Die gute Nachricht: Je klarer das Bild, desto gezielter können wir therapieren. Eine Mitbetreuung an einem PH-Zentrum empfehlen wir zeitnah.",
        "Die Messung ergab einen stark erhöhten mPAP von {mpap_str} mmHg. Das rechte Herz muss dauerhaft gegen einen sehr hohen Widerstand arbeiten. Wir planen die nächsten Schritte eng mit Ihnen — Ziel ist Druck senken, Belastbarkeit erhalten.",
        "Mit {mpap_str} mmHg liegt eine ausgeprägte Lungendruckerhöhung vor. Das erfordert eine konsequente, meist mehrgleisige Behandlung — und auch Ihr aktives Mittun bei Kontrollen und Medikamenten wird wichtiger.",
        "Der Lungendruck ist mit {mpap_str} mmHg deutlich im Warnbereich. Das klingt bedrohlich — ist aber kein endgültiger Befund: In spezialisierten Zentren lässt sich dieser Druck bei vielen Patient:innen durch moderne Therapien relevant senken.",
    ],
)

_add(
    "PX_MEASURE_PAWP_MILD",
    "Messung: PAWP leicht erhöht (16–20 mmHg)",
    [
        "Der Druck vor dem linken Herzen (PAWP {pawp_str} mmHg) ist leicht über dem Normbereich (≤15 mmHg). Das spricht für einen kleinen Rückstau-Anteil von der linken Herzseite — häufig gut mitbehandelbar.",
        "Ihr PAWP liegt mit {pawp_str} mmHg knapp oberhalb der Norm. Das deutet darauf hin, dass die linke Herzseite nicht ganz ideal entlastet wird. Diese Komponente fließt in die Therapieplanung ein, ist aber in der Regel gut beeinflussbar.",
        "Mit einem PAWP von {pawp_str} mmHg zeigt sich eine leichte Belastung der linken Herzseite. Oft reicht es, bestehende Herz- und Blutdruck-Therapien zu optimieren, um hier Verbesserungen zu erzielen.",
        "Der gemessene PAWP ({pawp_str} mmHg) liegt im leicht erhöhten Bereich. Das ist ein häufiger Befund — er zeigt, dass die linke Herzhälfte etwas mehr Arbeit leistet, ohne dass dies zwingend eine eigenständige Krankheit sein muss.",
        "Die Druckverhältnisse vor dem linken Herzen sind mit {pawp_str} mmHg leicht auffällig. Wir beobachten diese Komponente im Verlauf und entscheiden gemeinsam, ob zusätzliche Maßnahmen sinnvoll sind.",
        "Ein PAWP von {pawp_str} mmHg ist grenzwertig erhöht. Praktisch heißt das: Wir haben einen Hinweis auf die linke Herzseite, aber noch keinen ausgeprägten Stau. Ideale Ausgangslage, um frühzeitig gegenzusteuern.",
    ],
)

_add(
    "PX_MEASURE_PAWP_MOD",
    "Messung: PAWP mittelgradig erhöht (21–25 mmHg)",
    [
        "Der PAWP ist mit {pawp_str} mmHg klar erhöht. Das bedeutet einen spürbaren Rückstau von der linken Herzseite in Richtung Lunge — ein wichtiger Baustein, an dem wir in der Therapie gezielt ansetzen.",
        "Mit einem PAWP von {pawp_str} mmHg arbeitet die linke Herzhälfte unter deutlicher Mehrbelastung. Entwässerung und Herz-optimierende Medikamente können hier oft relevant helfen.",
        "Ihr Druck vor dem linken Herzen liegt bei {pawp_str} mmHg — mittelgradig erhöht. Für Sie kann das Luftnot bei Belastung oder Wassereinlagerungen erklären. Die Therapie setzt vor allem an der linken Herzseite an.",
        "Die Messung zeigt einen PAWP von {pawp_str} mmHg, deutlich über dem Normbereich. Das ist ein relevanter Befund, der jedoch auf bewährte Behandlungsansätze anspricht — wir passen Ihre Medikation darauf abgestimmt an.",
        "Mit {pawp_str} mmHg ist der PAWP mittelgradig erhöht. Das heißt praktisch: Die linke Herzhälfte gibt das Blut nicht optimal weiter, und dieser Rückstau überträgt sich in die Lungengefäße — behandelbar, aber ernst zu nehmen.",
        "Ein PAWP von {pawp_str} mmHg ist ein klarer Hinweis auf eine postkapilläre Komponente. Das beeinflusst die Therapie erheblich: Statt nur die Lungengefäße anzusteuern, optimieren wir bewusst auch das linke Herz.",
    ],
)

_add(
    "PX_MEASURE_PAWP_SEV",
    "Messung: PAWP deutlich erhöht (>25 mmHg)",
    [
        "Mit einem PAWP von {pawp_str} mmHg liegt ein ausgeprägter Rückstau von der linken Herzseite vor. Das erklärt häufig Luftnot und Wassereinlagerungen — und ist ein zentrales Ziel unserer Therapie.",
        "Der PAWP ist mit {pawp_str} mmHg deutlich erhöht. Die linke Herzhälfte bewältigt das Blutvolumen nicht ausreichend, und der Stau reicht bis in die Lunge. Wir werden die Entwässerung und Herz-Medikation deshalb konsequent einstellen.",
        "Ihr PAWP liegt mit {pawp_str} mmHg weit über dem Normbereich. Diese Größenordnung bedeutet: Die linke Herzseite ist die treibende Kraft. Eine enge kardiologische Begleitung mit Gewichtskontrolle und Medikamentenanpassung ist jetzt wichtig.",
        "Die Messung ergab einen stark erhöhten PAWP ({pawp_str} mmHg). Das ist ernst — aber gerade bei dieser Konstellation gibt es etablierte Strategien (Entwässerung, Blutdruck- und Herz-Therapie), die oft rasch Erleichterung bringen.",
        "Mit {pawp_str} mmHg zeigt sich eine schwergradige Druckbelastung vor dem linken Herzen. Die gute Nachricht: Postkapilläre Druckerhöhungen sprechen häufig gut auf bewährte Herz-Medikamente an, wenn sie konsequent eingesetzt werden.",
        "Ein PAWP von {pawp_str} mmHg bedeutet einen ausgeprägten Rückstau — das kann sich anfühlen wie „Wasser in der Lunge“. Wir setzen mit Medikamenten und Verhaltensmaßnahmen (z. B. Trinkmengen, tägliches Wiegen) entschlossen gegen.",
    ],
)

_add(
    "PX_MEASURE_PVR_MILD",
    "Messung: PVR leicht erhöht (2.1–3.0 WU)",
    [
        "Der Gefäßwiderstand in den Lungengefäßen (PVR {pvr_str} WU) ist leicht erhöht (Schwelle >2 WU). Das ist ein zarter Hinweis auf Veränderungen in den Lungenarterien — in diesem Bereich meist früh und gut beobachtbar.",
        "Ihr PVR liegt mit {pvr_str} WU knapp über der Norm. Das bedeutet: Die Lungengefäße zeigen eine beginnende Widerstandserhöhung. Die Ursache dahinter klären wir strukturiert — oft lässt sich in diesem frühen Stadium viel erreichen.",
        "Mit einem PVR von {pvr_str} WU zeigt sich eine milde Widerstandserhöhung in der Lungenstrombahn. Das ist kein Wert, der sofort behandelt werden muss, aber einer, der regelmäßige Kontrollen rechtfertigt.",
        "Die Gefäße in Ihrer Lunge arbeiten mit einem leicht erhöhten Widerstand (PVR {pvr_str} WU). Solche Werte finden wir häufig bei Begleiterkrankungen oder früh im Krankheitsverlauf — die genaue Einordnung bestimmt das weitere Vorgehen.",
        "Der PVR ist mit {pvr_str} WU nur gering erhöht. Damit haben wir einen messbaren, aber noch zurückhaltenden Befund — ideal, um vorbeugend zu handeln statt reagieren zu müssen.",
        "Mit {pvr_str} WU ist Ihr Lungengefäßwiderstand grenzwertig bis leicht erhöht. Das ist ein Frühzeichen, dem wir Aufmerksamkeit schenken, ohne sofort alle therapeutischen Hebel in Bewegung zu setzen.",
    ],
)

_add(
    "PX_MEASURE_PVR_MOD",
    "Messung: PVR mittelgradig erhöht (3.1–5.0 WU)",
    [
        "Der Widerstand in den Lungengefäßen ist mit {pvr_str} WU klar erhöht. Das spricht für eine relevante Veränderung in den kleinen Lungenarterien — hier kommen oft gefäßerweiternde Medikamente zum Einsatz.",
        "Mit einem PVR von {pvr_str} WU liegt eine mittelgradige Widerstandserhöhung vor. Die Lungengefäße sind spürbar „enger“ geworden. Das ist behandelbar: Mehrere etablierte Medikamente können hier nachweisbar helfen.",
        "Ihr PVR beträgt {pvr_str} WU und liegt damit im mittleren Bereich der Erhöhung. Das beeinflusst die Therapieentscheidung deutlich: In diesem Bereich ist eine gefäßgerichtete Behandlung oft indiziert.",
        "Die Messung ergab einen erhöhten Lungengefäßwiderstand ({pvr_str} WU). Das ist ein wichtiger Hinweis auf eine pulmonal-arterielle Komponente — also Veränderungen, die primär die Lungengefäße betreffen und gezielt behandelt werden können.",
        "Ein PVR von {pvr_str} WU zeigt, dass die Lungengefäße einen klar erhöhten Widerstand aufbauen. Für Sie bedeutet das mehr Arbeit für das rechte Herz — und für uns ein eindeutiges Therapiekriterium.",
        "Mit {pvr_str} WU ist Ihr Gefäßwiderstand spürbar erhöht. Das rechte Herz muss gegen diesen Widerstand pumpen. Moderne PH-Medikamente können hier oft in mehreren Stufen Druck und Widerstand senken.",
    ],
)

_add(
    "PX_MEASURE_PVR_SEV",
    "Messung: PVR deutlich erhöht (>5 WU)",
    [
        "Mit einem PVR von {pvr_str} WU liegt eine schwere Widerstandserhöhung in den Lungengefäßen vor. Das erfordert eine konsequente, oft kombinierte Therapie — in aller Regel an einem spezialisierten PH-Zentrum.",
        "Der Widerstand in Ihren Lungengefäßen ist mit {pvr_str} WU stark erhöht. Das bedeutet, dass das rechte Herz viel Kraft aufbringen muss — aber auch, dass wir einen klaren therapeutischen Ansatzpunkt haben.",
        "Ihr PVR von {pvr_str} WU zeigt eine ausgeprägte Enge der Lungengefäße. Das ist ernst, aber behandelbar: Mehrere Medikamentenklassen greifen genau hier an und können Druck und Widerstand nachweisbar senken.",
        "Die Messung ergab einen deutlich erhöhten PVR ({pvr_str} WU). Solche Werte erfordern meist eine Kombinationstherapie. Wir werden diese Entscheidung gemeinsam mit einem PH-Zentrum in Ruhe treffen.",
        "Mit {pvr_str} WU ist Ihr Lungengefäßwiderstand stark erhöht. Das rechte Herz arbeitet gegen eine erhebliche Barriere. Umso wichtiger ist eine zügige, mehrgleisige Therapie, um die Belastbarkeit zu erhalten.",
        "Ein PVR von {pvr_str} WU bedeutet schwere Gefäßveränderungen in der Lunge. Das klingt beunruhigend — ist aber gerade in dieser Ausprägung ein Bereich, in dem moderne PH-Therapien in den letzten Jahren die größten Fortschritte gemacht haben.",
    ],
)

_add(
    "PX_MEASURE_RAP_MILD",
    "Messung: RAP leicht erhöht (8–12 mmHg)",
    [
        "Der Druck im rechten Vorhof (RAP) ist mit {rap_str} mmHg leicht erhöht. Das ist ein früher Hinweis darauf, dass die rechte Herzhälfte etwas mehr arbeitet als normal — meist noch gut kompensiert.",
        "Mit einem RAP von {rap_str} mmHg sehen wir eine leichte Mehrbelastung der rechten Herzseite. Das ist ein Befund, den wir im Verlauf beobachten, der aber noch keinen unmittelbaren Handlungsdruck macht.",
        "Ihr RAP liegt mit {rap_str} mmHg knapp über dem Normbereich (≤7 mmHg). Solche Werte sind häufig gut behandelbar, insbesondere wenn wir die zugrundeliegende Drucksituation in den Lungengefäßen verbessern.",
        "Die rechte Herzseite zeigt mit einem RAP von {rap_str} mmHg eine leichte Druckerhöhung. Das ist ein frühes Warnzeichen, das wir im Blick behalten — aber noch kein Notfall.",
        "Ein RAP von {rap_str} mmHg bedeutet: Vor der rechten Herzkammer baut sich etwas Druck auf. Das ist ein feiner Marker, den wir im Zusammenspiel mit anderen Werten (CI, BNP) interpretieren.",
        "Der gemessene RAP ({rap_str} mmHg) liegt im leicht erhöhten Bereich. Häufig reagiert dieser Wert gut, wenn wir die Gesamtsituation (Lungendruck, Entwässerung) optimieren.",
    ],
)

_add(
    "PX_MEASURE_RAP_MOD",
    "Messung: RAP mittelgradig erhöht (13–15 mmHg)",
    [
        "Der Druck im rechten Vorhof ist mit {rap_str} mmHg klar erhöht. Das spricht für eine spürbare Belastung der rechten Herzhälfte und ist ein wichtiger Risikomarker, den wir in der Therapieplanung berücksichtigen.",
        "Mit einem RAP von {rap_str} mmHg arbeitet Ihre rechte Herzseite unter deutlicher Mehrbelastung. Entwässerung und gezielte Druckentlastung der Lungengefäße sind in diesem Bereich oft hilfreich.",
        "Ihr RAP von {rap_str} mmHg zeigt, dass das rechte Herz relevant belastet ist. Dieser Wert gehört zu den zentralen Markern im PH-Risiko-Score — wir werden ihn im Verlauf engmaschig mitverfolgen.",
        "Die Messung ergab einen mittelgradig erhöhten RAP ({rap_str} mmHg). Praktisch bedeutet das: Die rechte Herzkammer muss gegen einen erhöhten Widerstand arbeiten, und der Druck staut sich vor ihr auf.",
        "Mit {rap_str} mmHg ist der rechte Vorhofdruck klar über der Norm. Das ist ein Befund, der zusammen mit Belastbarkeit und BNP-Wert in die Risikoeinschätzung einfließt — und unsere Therapieintensität mitbestimmt.",
        "Ein RAP von {rap_str} mmHg ist ein ernstzunehmendes Signal der rechten Herzbelastung. Die gute Nachricht: Bei konsequenter Behandlung des Lungendrucks sinkt der RAP in vielen Fällen mit.",
    ],
)

_add(
    "PX_MEASURE_RAP_SEV",
    "Messung: RAP deutlich erhöht (>15 mmHg)",
    [
        "Mit einem RAP von {rap_str} mmHg liegt eine ausgeprägte Belastung der rechten Herzhälfte vor. Das ist ein ernster Befund, der eine zügige, intensivierte Therapie und enge Kontrollen rechtfertigt.",
        "Der rechte Vorhofdruck ist mit {rap_str} mmHg stark erhöht. Solche Werte gehören zu den wichtigsten Risikomarkern bei PH — wir werden die Therapie darauf abstimmen und eine Zentrumsanbindung eng einbeziehen.",
        "Ihr RAP liegt mit {rap_str} mmHg weit über dem Normbereich. Das rechte Herz ist erheblich unter Druck. Gerade deshalb setzen wir auf eine konsequente Entwässerung und gefäßgerichtete Therapie, oft in Kombination.",
        "Die Messung ergab einen schwergradig erhöhten RAP ({rap_str} mmHg). Das klingt bedrohlich — gleichzeitig ist dies ein Bereich, in dem eine strukturierte Behandlung häufig relevante Entlastung bringt, wenn sie konsequent umgesetzt wird.",
        "Mit {rap_str} mmHg zeigt sich ein deutlicher Rückstau vor der rechten Herzhälfte. Das geht oft mit Wassereinlagerungen und Atemnot einher — beides versuchen wir mit einer Kombination aus Medikamenten und Verhaltensmaßnahmen zu bessern.",
        "Ein RAP von {rap_str} mmHg ist ein klares Alarmsignal für die rechte Herzbelastung. Wir werden Ihre Therapie zeitnah optimieren, Ihre Belastbarkeit engmaschig kontrollieren und bei Bedarf ein spezialisiertes Zentrum einbinden.",
    ],
)

_add(
    "PX_MEASURE_CI_BORDERLINE",
    "Messung: CI grenzwertig (2.2–2.5 l/min/m²)",
    [
        "Der Herzindex (CI) liegt mit {ci_str} l/min/m² im grenzwertigen Bereich (Schwelle 2.5). Das heißt, die Pumpreserve ist knapp bemessen — bei starker Belastung kann das spürbar werden.",
        "Mit einem CI von {ci_str} l/min/m² zeigt Ihre Pumpleistung noch keine klare Schwäche, aber die Reserven sind begrenzt. Wir berücksichtigen das bei Empfehlungen zu Belastung und Training.",
        "Ihr CI liegt bei {ci_str} l/min/m² — grenzwertig. Das erklärt oft, warum intensive Belastung rasch an Grenzen stößt, auch wenn in Ruhe wenig auffällt.",
        "Die Pumpleistung ist mit einem CI von {ci_str} l/min/m² knapp im ausreichenden Bereich. Entscheidend ist der Verlauf: Bleibt der CI stabil oder verändert er sich? Das beobachten wir bei Kontrollen.",
        "Mit {ci_str} l/min/m² zeigt sich eine gerade noch ausreichende Pumpleistung. Das ist noch kein Grund zu engen Einschränkungen, aber ein Marker, den wir bei der Therapieintensität berücksichtigen.",
        "Der CI von {ci_str} l/min/m² ist grenzwertig. Für den Alltag reicht das meist aus — bei stärkerer Belastung oder Krankheit sind die Reserven jedoch begrenzt, das planen wir gemeinsam ein.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW_MOD",
    "Messung: CI reduziert (1.8–2.2 l/min/m²)",
    [
        "Der Herzindex ist mit {ci_str} l/min/m² reduziert. Das ist ein relevanter Befund: Die Pumpleistung ist eingeschränkt, und wir werden Therapie und Alltag daran ausrichten.",
        "Mit einem CI von {ci_str} l/min/m² liegt eine klare Pumpleistungsminderung vor. Das erklärt oft Erschöpfung und rasche Belastungsgrenzen — und ist ein Grund, die Herz- und PH-Therapie gezielt zu verstärken.",
        "Ihre Pumpleistung ist mit einem CI von {ci_str} l/min/m² reduziert. Wir werden Medikamente, Flüssigkeitsmanagement und ggf. Training so abstimmen, dass das Herz bestmöglich unterstützt wird.",
        "Die Messung zeigt einen verminderten CI ({ci_str} l/min/m²). Das bedeutet: Pro Herzschlag gelangt weniger Blut in den Kreislauf, als wir uns wünschen würden. Eine intensivierte Therapie ist in diesem Bereich oft sinnvoll.",
        "Mit {ci_str} l/min/m² ist der CI klar reduziert. Für den Alltag kann das heißen, dass schon moderate Belastung anstrengend wird. Wir planen mit Ihnen, wie wir Leistungsfähigkeit und Ruhephasen gut ausbalancieren.",
        "Ein CI von {ci_str} l/min/m² zeigt eine eingeschränkte Pumpfunktion. Das ist behandelbar — je nach Ursache mit gefäßgerichteten, entwässernden und herzunterstützenden Medikamenten.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW_SEV",
    "Messung: CI deutlich reduziert (<1.8 l/min/m²)",
    [
        "Mit einem CI von {ci_str} l/min/m² liegt eine deutlich eingeschränkte Pumpleistung vor. Das ist ein ernstes Zeichen — wir werden Therapie und Überwachung zügig intensivieren, meist in enger Abstimmung mit einem spezialisierten Zentrum.",
        "Der Herzindex ist mit {ci_str} l/min/m² stark reduziert. Das rechte Herz schafft es aktuell nicht, genügend Blut zu fördern. Diese Situation erfordert rasche therapeutische Anpassungen.",
        "Ihr CI liegt bei {ci_str} l/min/m² — deutlich unter dem Zielbereich. Das klingt bedrohlich, und wir nehmen es ernst: In spezialisierten Zentren stehen Therapien zur Verfügung, die gerade in dieser Situation helfen können.",
        "Die Messung ergab einen stark verminderten CI ({ci_str} l/min/m²). Solche Werte gehören zu den wichtigsten Marker für eine fortgeschrittene Herzbelastung — eine strukturierte, intensivierte Behandlung ist jetzt entscheidend.",
        "Mit {ci_str} l/min/m² ist die Pumpleistung deutlich eingeschränkt. Das erklärt oft ausgeprägte Müdigkeit, Luftnot und Schwindel. Wir werden alle verfügbaren Therapieoptionen — auch Kombinationen und zentrumsbasierte Optionen — prüfen.",
        "Ein CI von {ci_str} l/min/m² bedeutet: Das Herz arbeitet mit deutlich verminderter Leistung. Das ist ein Warnsignal, kein Endzustand — gerade bei PH haben sich die Therapiemöglichkeiten in den letzten Jahren erheblich erweitert.",
    ],
)


# ---------------------------------------------------------------------------
# Übergänge / Kontextübergänge (v27.4.25+)
# ---------------------------------------------------------------------------

_add(
    "PX_DETAILS_INTRO",
    "Überleitung zur Detailsektion",
    [
        "Die folgenden Abschnitte erklären die Befunde ausführlicher.",
        "Auf den nächsten Seiten gehen wir Punkt für Punkt auf die Befunde ein.",
        "Im Folgenden erklären wir die einzelnen Ergebnisse in Ruhe.",
        "Die nachfolgenden Abschnitte nehmen die wichtigsten Punkte noch einmal genauer auseinander.",
        "Wir haben die Details so aufbereitet, dass Sie jeden Abschnitt in Ruhe lesen und bei Bedarf noch einmal darauf zurückkommen können.",
        "Damit die Einordnung möglichst verständlich bleibt, folgt im nächsten Schritt eine ausführlichere Erklärung der einzelnen Befunde.",
    ],
)

_add(
    "PX_TRANSPARENCY_INTRO",
    "Einordnung: was dieser Patientenbericht ist",
    [
        "Dieser Patientenbericht ist eine laienfreundliche Ergänzung zum medizinischen Fachbericht. Er soll das Gespräch mit Ihrer Hausärztin/Ihrem Hausarzt und dem Kardiologie-Team erleichtern.",
        "Dieser Bericht ist als verständliche Zusammenfassung gedacht — zum Nachlesen in Ruhe und als Vorbereitung für das nächste Arztgespräch. Er ersetzt keinen medizinischen Termin.",
        "Diese Zusammenfassung fasst Ihre Befunde in Alltagssprache zusammen. Sie soll Ihnen helfen, die Zusammenhänge zu verstehen und eigene Fragen zu formulieren.",
        "Sie lesen gerade einen Patientenbericht — gemeint als Brücke zwischen dem ärztlichen Fachbericht und Ihrer eigenen Perspektive. Alles, was unklar bleibt, können wir gemeinsam besprechen.",
        "Dieser Text ergänzt den medizinischen Fachbericht und ist für Sie persönlich geschrieben. Nehmen Sie sich Zeit beim Lesen; die Details können wir jederzeit gemeinsam vertiefen.",
        "Diese Erklärung ist so geschrieben, dass Sie sie ohne medizinische Vorkenntnisse verstehen können. Sie ist eine Ergänzung, keine Ersatz für das persönliche Gespräch mit Ihrem Behandlungsteam.",
    ],
)

_add(
    "PX_TRANSPARENCY_DATA_NOTE",
    "Einordnung: Datenbasis und Grenzen",
    [
        "Wichtig: Die Einordnung basiert auf den hinterlegten Messwerten und Angaben. Nicht alle Informationen liegen immer als strukturierte Codes vor; deshalb bleibt das persönliche Arztgespräch entscheidend.",
        "Hinweis zur Datenbasis: Der Bericht stützt sich auf die im System hinterlegten Werte. Manche Aspekte Ihrer Geschichte lassen sich nur im Gespräch richtig einordnen — darum bleibt der direkte Austausch wichtig.",
        "Transparenz: Wir nutzen die dokumentierten Messwerte und Angaben. Einige Nuancen — etwa Belastungssituationen im Alltag — lassen sich nur im persönlichen Gespräch vollständig bewerten.",
        "Grenzen dieser Einordnung: Sie beruht auf strukturierten Daten und kann daher nicht jede Besonderheit Ihrer Geschichte erfassen. Das ausführliche Arztgespräch bleibt deshalb zentral.",
        "Eine wichtige Einschränkung: Nicht alle relevanten Informationen sind strukturiert erfasst. Bitte bringen Sie Beobachtungen aus Ihrem Alltag zum nächsten Termin mit — sie helfen uns, das Bild zu vervollständigen.",
        "Zum Verständnis: Dieser Bericht nutzt die im System erfassten Werte. Weil nicht alles in Codes passt, bleibt Ihr persönliches Erleben ein wichtiger Baustein der Einordnung.",
    ],
)

_add(
    "PX_REASON_MISSING",
    "Fallback, wenn kein strukturierter Untersuchungsanlass hinterlegt ist",
    [
        "Ein konkreter Untersuchungsanlass wurde im Datensatz nicht strukturiert hinterlegt.",
        "Der genaue Anlass für die Untersuchung ist in den Daten nicht gesondert dokumentiert.",
        "In der Akte ist kein eigens markierter Untersuchungsanlass vermerkt — das werden wir im Gespräch gerne gemeinsam ergänzen.",
        "Zum Anlass der Untersuchung ist im Datensatz nichts Näheres hinterlegt; das können wir bei Gelegenheit gemeinsam dokumentieren.",
        "Der Untersuchungsgrund wurde nicht strukturiert erfasst — falls Sie möchten, können wir ihn beim nächsten Termin gemeinsam nachtragen.",
        "Für den spezifischen Anlass liegt derzeit kein strukturierter Eintrag vor. Bei Rückfragen gehen wir das gerne mit Ihnen durch.",
    ],
)

_add(
    "PX_SUMMARY_MISSING",
    "Fallback, wenn Kurzfazit nicht möglich ist",
    [
        "Eine kompakte Einordnung ist derzeit nicht sicher möglich, weil zentrale Angaben fehlen.",
        "Für eine belastbare Zusammenfassung fehlen aktuell noch einige zentrale Messwerte.",
        "Wir können im Moment noch keine eindeutige Kurzfassung geben, weil wichtige Daten noch nicht vorliegen.",
        "Bevor wir eine sichere Gesamteinordnung abgeben, möchten wir die fehlenden Werte ergänzen.",
        "Für eine klare Zusammenfassung fehlen aktuell Angaben, die wir im nächsten Termin gerne ergänzen.",
        "Mit den vorliegenden Daten lässt sich noch keine saubere Kurzfassung erstellen — wir ergänzen das, sobald die offenen Werte vorliegen.",
    ],
)


# ---------------------------------------------------------------------------
# Follow-up-Sektion (v27.4.24+): Varianten mit persönlicher Tonalität
# ---------------------------------------------------------------------------

_add(
    "PX_REASSURE_HIGH_RISK",
    "Einordnung bei erhöhtem Risiko",
    [
        "Diese Befunde können belastend sein. Wir besprechen die nächsten Schritte mit Ihnen ruhig, transparent und ohne unnötige Dramatisierung.",
        "Es ist nachvollziehbar, wenn solche Ergebnisse Sorge auslösen. Wir gehen die nächsten Schritte Stück für Stück gemeinsam mit Ihnen durch, ohne Ihnen etwas zu beschönigen oder Angst zu machen.",
        "Diese Ergebnisse sind nicht leicht zu lesen. Bitte wissen Sie: Wir nehmen uns die Zeit, alles verständlich zu erklären und gemeinsam mit Ihnen einen klaren Plan zu entwickeln.",
        "Wir wissen, dass solche Befunde zunächst verunsichern können. Unser Ziel ist es, dass Sie genau verstehen, was wir sehen und was uns dazu möglich ist.",
        "Auch wenn die Ergebnisse ernst zu nehmen sind: Sie sind nicht allein. Wir planen die weiteren Schritte Schritt für Schritt mit Ihnen und lassen Raum für Ihre Fragen.",
        "Solche Befunde können viele Fragen aufwerfen. Bitte melden Sie sich jederzeit, wenn Ihnen etwas unklar ist — wir nehmen uns die Zeit, die Sie brauchen.",
    ],
)

_add(
    "PX_EXERCISE_GUIDANCE",
    "Alltagsnahe Bewegungsempfehlung",
    [
        "Studien bei Patient*innen mit Lungengefäßerkrankungen zeigen, dass regelmäßige, moderate Bewegung die Belastbarkeit und Lebensqualität verbessern kann. Entscheidend ist nicht Tempo, sondern eine gut verträgliche Regelmäßigkeit.",
        "Bewegung tut dem Herz-Kreislauf-System gut — auch bei Lungenhochdruck. Wichtig ist: in gut verträglichem Tempo, lieber kürzer und regelmäßig als lang und überfordert.",
        "Regelmäßige Aktivität hilft, die Belastbarkeit zu erhalten. Orientierung: Wenn Sie sich dabei unterhalten können, ohne nach Luft zu schnappen, ist das ein gutes Maß.",
        "Viele Patient*innen profitieren von kleinen, regelmäßigen Bewegungseinheiten im Alltag — z. B. täglich 15–20 Minuten spazieren gehen, wenn das ohne starke Luftnot möglich ist.",
        "Studien zeigen: Leichte bis moderate Bewegung, an Ihre persönliche Belastbarkeit angepasst, kann die Lebensqualität verbessern. Zu Beginn ist es oft sinnvoll, das Tempo niedrig zu halten und schrittweise zu steigern.",
        "Bewegung ist hilfreich, aber sie soll sich nicht wie Kampf anfühlen. Als Faustregel: Sie sollten sich danach erfrischt und nicht ausgepowert fühlen. Bei Luftnot, Schwindel oder Brustdruck lieber pausieren.",
    ],
)

_add(
    "PX_CONGESTION_PRESENT",
    "Hinweis auf Flüssigkeitsrückstau",
    [
        "Es gibt Hinweise auf Rückstau. Neue Schwellungen oder eine rasche Gewichtszunahme über wenige Tage sollten zeitnah besprochen werden.",
        "Aktuell sehen wir Hinweise darauf, dass sich Flüssigkeit in Ihrem Körper ansammelt. Bitte achten Sie besonders auf Beine, Knöchel und Bauch — und melden Sie sich, wenn die Schwellungen zunehmen.",
        "Die Befunde deuten auf einen Rückstau hin. Tägliches Wiegen am Morgen kann helfen, Veränderungen früh zu erkennen: 2 kg in wenigen Tagen ist ein Signal, das wir wissen möchten.",
        "Es zeigt sich ein Flüssigkeitsstau. Das ist behandelbar — wichtig ist, dass wir bei Veränderungen frühzeitig reagieren können. Bitte sprechen Sie uns bei zunehmenden Schwellungen oder rascher Gewichtszunahme an.",
        "Die Untersuchung zeigt Hinweise auf eine Stauungskomponente. Typische Warnzeichen sind zunehmende Beinschwellungen, ein dickerer Bauchumfang oder ein plötzlicher Gewichtsanstieg.",
        "Ein beginnender Rückstau ist erkennbar. Bitte beobachten Sie Schwellungen an Füßen und Beinen und das Gewicht — und melden Sie schnell, wenn sich beides deutlich verändert.",
    ],
)

_add(
    "PX_CONGESTION_WATCH",
    "Prophylaktischer Hinweis ohne aktuellen Rückstau",
    [
        "Wenn neue Schwellungen, rasche Gewichtszunahme oder deutlich zunehmende Luftnot auftreten, sollte das frühzeitig abgeklärt werden.",
        "Aktuell sehen wir keinen Rückstau — sehr gut. Sollten aber neue Schwellungen an Beinen oder Bauch auftreten oder Sie innerhalb weniger Tage deutlich zunehmen, melden Sie sich bitte.",
        "Ein Rückstau ist derzeit nicht erkennbar. Als Orientierung für später: Schwellungen, eine rasche Gewichtszunahme oder zunehmende Luftnot sind Warnzeichen, die wir wissen möchten.",
        "Bislang zeigen sich keine Zeichen einer Flüssigkeitsansammlung. Sollte sich das ändern — z. B. durch Schwellungen oder eine rasche Gewichtszunahme — ist das ein Grund, sich früh bei uns zu melden.",
        "Derzeit sehen wir keinen Rückstau. Bitte beobachten Sie dennoch Ihr Gewicht und mögliche Schwellungen: Veränderungen fallen Ihnen oft am frühesten selbst auf.",
        "Aktuell ist kein Rückstau zu sehen. Dennoch lohnt sich der Blick auf Gewicht und Schwellungen — frühe Veränderungen erkennen wir zusammen am besten.",
    ],
)


_add(
    "PX_CLARITY_MISSING_VALUES",
    "Gesamteinordnung, wenn Kernwerte fehlen",
    [
        "Eine eindeutige Einordnung (unauffällig/auffällig) ist aktuell nicht möglich, weil zentrale Messwerte fehlen.",
        "Weil zentrale Messwerte fehlen, können wir Ihre Befunde derzeit nicht eindeutig als unauffällig oder auffällig einordnen.",
        "Ohne die wichtigsten Messwerte lässt sich noch nicht sicher sagen, ob das Bild insgesamt unauffällig oder auffällig ist.",
        "Für eine belastbare Einordnung fehlen uns aktuell einige der zentralen Messgrößen — wir ergänzen das, sobald sie vorliegen.",
        "Aktuell lässt sich noch keine klare Einordnung treffen, weil wichtige Kernwerte fehlen; die fügen wir nach.",
        "Eine eindeutige Beurteilung ist mit der aktuellen Datenlage nicht möglich — zentrale Messwerte fehlen noch.",
    ],
)

_add(
    "PX_CLARITY_NO_PH",
    "Gesamteinordnung ohne Lungenhochdruck",
    [
        "Gesamteinordnung: Die Messwerte in Ruhe sind überwiegend unauffällig und eher untypisch für einen Lungenhochdruck in Ruhe.",
        "Gesamteinordnung: Ihre Ruhewerte wirken insgesamt unauffällig und sprechen nicht für einen manifesten Lungenhochdruck.",
        "Gesamteinordnung: In Ruhe zeigen sich keine klaren Zeichen eines Lungenhochdrucks.",
        "Gesamteinordnung: Die Messungen in Ruhe ergeben ein überwiegend unauffälliges Bild — kein typischer Lungenhochdruck.",
        "Gesamteinordnung: Das Gesamtbild in Ruhe ist unauffällig und passt nicht zu einem Lungenhochdruck.",
        "Gesamteinordnung: Die Ruhewerte sprechen gegen einen manifesten Lungenhochdruck in Ruhe.",
    ],
)

_add(
    "PX_CLARITY_PRECAP",
    "Gesamteinordnung bei prä-kapillärem Muster",
    [
        "Gesamteinordnung: Die Messwerte sind auffällig und eher typisch für eine Druckerhöhung in den Lungengefäßen selbst.",
        "Gesamteinordnung: Die Werte sprechen für eine Druckerhöhung, die in den Lungengefäßen selbst entsteht.",
        "Gesamteinordnung: Das Gesamtbild passt am besten zu einer Druckerhöhung mit Ursprung in den Lungengefäßen.",
        "Gesamteinordnung: Die Messungen sind auffällig und passen zu einem Muster, bei dem die Lungengefäße selbst betroffen sind.",
        "Gesamteinordnung: Die Werte sprechen für eine Druckerhöhung, deren Ursache primär in den Lungengefäßen liegt.",
        "Gesamteinordnung: Es ergibt sich das Bild einer prä-kapillären Druckerhöhung — also eines Drucks, der im Lungengefäßsystem selbst entsteht.",
    ],
)

_add(
    "PX_CLARITY_POSTCAP",
    "Gesamteinordnung bei Mitbeteiligung der linken Herzseite",
    [
        "Gesamteinordnung: Die Messwerte sind auffällig und eher typisch für eine Mitbeteiligung der linken Herzseite.",
        "Gesamteinordnung: Die Werte sprechen dafür, dass die linke Herzseite am Druckbild beteiligt ist.",
        "Gesamteinordnung: Das Gesamtbild passt zu einer Mitbeteiligung der linken Herzkammer oder des linken Vorhofs.",
        "Gesamteinordnung: Die Messwerte legen nahe, dass die linke Herzseite einen Anteil am erhöhten Druck hat.",
        "Gesamteinordnung: Das Druckmuster wirkt eher links-kardial mitbeteiligt — wir schauen das gezielt weiter an.",
        "Gesamteinordnung: Das Muster deutet auf eine (zumindest teilweise) links-kardiale Ursache der Druckerhöhung hin.",
    ],
)

_add(
    "PX_CLARITY_AMBIGUOUS",
    "Gesamteinordnung bei uneindeutigem Muster",
    [
        "Gesamteinordnung: Die Messwerte sind auffällig; die genaue Zuordnung ist noch nicht sicher und wird weiter abgeklärt.",
        "Gesamteinordnung: Die Werte sind auffällig — wohin genau sie gehören, klären wir mit zusätzlichen Untersuchungen.",
        "Gesamteinordnung: Die Befunde sind auffällig, die Ursache ist aber noch nicht eindeutig einzuordnen.",
        "Gesamteinordnung: Die Werte fallen auf; welche Ursache dominant ist, muss gezielt weiter geprüft werden.",
        "Gesamteinordnung: Die Werte sind auffällig, aber ein eindeutiger Mechanismus zeigt sich noch nicht — das arbeiten wir weiter auf.",
        "Gesamteinordnung: Es gibt auffällige Werte, aber die genaue Einordnung braucht weitere Informationen.",
    ],
)

_add(
    "PX_OVERALL_PRECAP",
    "Gesamteinordnung bei prä-kapillärem Muster",
    [
        "In der Zusammenschau spricht vieles dafür, dass der erhöhte Widerstand vor allem in den Lungengefäßen selbst entsteht. Entscheidend ist nun, warum das so ist.",
        "Das Bild passt am besten zu einem Widerstand, der primär in den Lungengefäßen selbst liegt. Unsere nächste Frage lautet: Was ist die Ursache?",
        "Zusammengefasst wirkt es so, als liege die Druckerhöhung eher im Lungengefäßsystem selbst. Wichtig ist jetzt, die dahinterliegende Ursache zu klären.",
        "Die Gesamtschau spricht für eine sogenannte prä-kapilläre Komponente — das heißt, der Widerstand entsteht in den Lungengefäßen. Warum genau, wollen wir nun näher klären.",
        "Die Messwerte passen zu einem Muster, bei dem die Lungengefäße selbst einen wesentlichen Anteil haben. Der nächste Schritt ist, die Ursache dafür gezielt zu suchen.",
        "In der Zusammenschau liegt die Druckbelastung vor allem auf Seiten der Lungengefäße. Jetzt geht es uns darum, zu verstehen, welcher Mechanismus dahintersteht.",
    ],
)

_add(
    "PX_OVERALL_POSTCAP",
    "Gesamteinordnung bei Links-Herz-Mitbeteiligung",
    [
        "In der Zusammenschau gibt es Hinweise auf eine Mitbeteiligung der linken Herzseite. Entscheidend ist nun, wie groß dieser Anteil ist und ob zusätzlich der Lungenkreislauf selbst betroffen ist.",
        "Das Bild spricht dafür, dass die linke Herzseite eine Rolle spielt. Wie groß dieser Anteil ist — und ob auch die Lungengefäße mitbetroffen sind — prüfen wir als nächstes.",
        "Die Messungen passen zu einer Beteiligung der linken Herzhälfte. Wir klären nun, wie stark dieser Einfluss ist und ob es zusätzlich eine Komponente der Lungengefäße gibt.",
        "Zusammenfassend deuten die Werte darauf hin, dass das linke Herz einen wesentlichen Anteil hat. Jetzt ist wichtig, den Umfang und mögliche zusätzliche Beiträge der Lungengefäße zu bestimmen.",
        "Das Gesamtbild zeigt Mitwirkung der linken Herzhälfte am Druck. Wie stark und in welcher Kombination mit den Lungengefäßen — das ist die nächste Frage, die wir klären.",
        "In der Zusammenschau erscheint eine links-kardiale Mitbeteiligung plausibel. Der nächste Schritt ist, den genauen Anteil und mögliche zusätzliche Veränderungen der Lungengefäße einzuordnen.",
    ],
)

_add(
    "PX_OVERALL_AMBIGUOUS",
    "Gesamteinordnung bei uneindeutigem Muster",
    [
        "In der Zusammenschau ist die Einordnung möglich, aber nicht alle Teilaspekte sind eindeutig. Wir stützen uns deshalb auf mehrere Bausteine (Messwerte, Bildgebung, Belastbarkeit).",
        "Die Gesamtschau erlaubt eine Einordnung, auch wenn nicht jedes Detail klar ist. Deshalb nutzen wir mehrere Informationsquellen gleichzeitig.",
        "Manche Teilaspekte sind noch nicht endgültig eindeutig. Eine belastbare Einordnung ergibt sich daher aus der Kombination aus Messung, Bildgebung und Belastbarkeit.",
        "Die Einordnung ist möglich, braucht aber mehrere Puzzleteile, weil einzelne Werte nicht alles erklären. Deshalb kombinieren wir verschiedene Befunde.",
        "Insgesamt lässt sich Ihre Situation einordnen; nicht alle Teilaspekte sind hierbei eindeutig. Für ein stabiles Bild ziehen wir daher mehrere Quellen heran.",
        "Wir können Ihre Befunde einordnen, auch wenn einige Teilfragen offen bleiben. Deshalb kombinieren wir Messwerte, Bildgebung und Ihre Belastbarkeit zu einem Gesamtbild.",
    ],
)

_add(
    "PX_OVERALL_NO_PH",
    "Gesamteinordnung ohne Lungenhochdruck in Ruhe",
    [
        "Die Messwerte in Ruhe sind unauffällig. Wenn Beschwerden vor allem unter Belastung auftreten, kann das trotzdem weiter eingeordnet werden – manche Veränderungen zeigen sich erst dann.",
        "In Ruhe zeigt sich kein Lungenhochdruck. Treten Beschwerden vor allem unter Belastung auf, können wir das gezielt unter Belastung nachprüfen.",
        "Die Messung in Ruhe liefert keine Hinweise auf Lungenhochdruck. Sollten Beschwerden primär bei Anstrengung auftreten, lohnt sich zusätzlich eine Belastungsdiagnostik.",
        "Gute Nachricht: In Ruhe ist kein Lungenhochdruck nachweisbar. Falls Sie bei Belastung Symptome bemerken, können wir auch dort gezielt messen.",
        "Im Ruhezustand finden wir keine Druckerhöhung. Beschwerden, die nur unter Belastung auftreten, können wir bei Bedarf mit einer eigenen Belastungsuntersuchung weiter einordnen.",
        "Die Messergebnisse in Ruhe sind beruhigend. Zeigen sich Beschwerden erst bei Anstrengung, besprechen wir gerne zusätzliche Untersuchungen unter Belastung.",
    ],
)

_add(
    "PX_CORE_VALUES_NOTE",
    "Hinweis zur Kombination der Kernwerte",
    [
        "Wichtig: Entscheidend ist die Kombination dieser Werte und der Verlauf. Eine einzelne Zahl erklärt Beschwerden selten vollständig.",
        "Das Zusammenspiel dieser Werte und der zeitliche Verlauf sagen am meisten aus — eine einzelne Zahl ist selten der komplette Schlüssel zur Situation.",
        "Bitte beachten Sie: Die Kernwerte sind wie Puzzleteile — erst zusammen und im Verlauf ergeben sie ein aussagekräftiges Bild.",
        "Jede einzelne Zahl ist nur ein Teil des Gesamtbilds. Erst die Kombination mit anderen Befunden und dem Verlauf lässt eine verlässliche Einordnung zu.",
        "Zur Orientierung: Wir bewerten selten einzelne Werte isoliert. Der Verlauf und das Zusammenspiel mehrerer Messgrößen sind wichtiger als einzelne Zahlen.",
        "Hinweis: Eine Einzelzahl kann beunruhigen oder beruhigen, ohne das ganze Bild zu zeigen. Wir schauen immer auf die Kombination und die Entwicklung.",
    ],
)

_add(
    "PX_ESC_RISK_UNAVAILABLE",
    "Hinweis, wenn ESC/ERS-Risikoeinstufung nicht berechenbar ist",
    [
        "Eine standardisierte ESC/ERS-Risikoeinstufung konnte aus den aktuellen Angaben nicht sicher berechnet werden.",
        "Die standardisierte Risikobewertung nach ESC/ERS lässt sich mit den derzeit verfügbaren Daten nicht zuverlässig bestimmen.",
        "Für eine formelle ESC/ERS-Risikoeinstufung fehlen aktuell wichtige Eingangsgrößen. Das holen wir nach, sobald die Datenlage vollständig ist.",
        "Eine standardisierte Risikoeinstufung (ESC/ERS) war auf Basis der aktuellen Angaben noch nicht stabil zu ermitteln.",
        "Die Risikokategorie nach ESC/ERS konnte noch nicht sicher berechnet werden — wir ergänzen sie, sobald die Datenlage das zulässt.",
        "Eine numerische ESC/ERS-Risikoeinstufung ist zurzeit nicht belastbar. Für Ihre Einschätzung nutzen wir zusätzlich das klinische Gesamtbild.",
    ],
)

_add(
    "PX_ETIOLOGY_UNCLEAR",
    "Einordnung, wenn Ursache noch nicht sicher feststeht",
    [
        "Welche Ursache im Vordergrund steht, lässt sich anhand der vorliegenden Angaben noch nicht sicher festlegen.",
        "Die wahrscheinlichste Ursache zu bestimmen, ist mit den aktuellen Daten noch nicht eindeutig möglich.",
        "Zu welcher Ursache die Befunde am besten passen, bleibt aktuell offen — wir brauchen dafür etwas mehr Information.",
        "Noch können wir nicht sicher sagen, welche Ursache die entscheidende Rolle spielt. Gezielte Zusatzuntersuchungen helfen beim Einordnen.",
        "Die Ursachenfrage ist derzeit nicht abschließend zu beantworten — ein paar weitere Bausteine helfen uns, das Bild zu schärfen.",
        "Welche Mechanismen hier im Vordergrund stehen, lässt sich noch nicht endgültig festlegen; das klären wir schrittweise.",
    ],
)

_add(
    "PX_ETIOLOGY_FURTHER_TESTS",
    "Hinweis auf weitere Untersuchungen zur Ursachenklärung",
    [
        "Deshalb ergänzen wir weitere Untersuchungen. Ziel ist, die Hauptursache zu klären und die Behandlung gezielt auszurichten.",
        "Aus diesem Grund planen wir gezielte Zusatzuntersuchungen — damit wir die Hauptursache finden und die Behandlung darauf abstimmen können.",
        "Wir ergänzen Schritt für Schritt weitere Untersuchungen, bis die Ursache klar ist und die Therapie zu Ihnen passt.",
        "Die folgenden Untersuchungen sollen uns helfen, das Bild zu vervollständigen und die Therapie gezielt zu planen.",
        "Um die Ursachenfrage zu klären, stimmen wir die nächsten diagnostischen Schritte auf Ihre Situation ab.",
        "Wir ergänzen gezielt weitere Diagnostik. Das Ziel: die wichtigste Ursache zuverlässig identifizieren und passend behandeln.",
    ],
)

_add(
    "PX_SHUNT_HINT",
    "Hinweis auf möglichen Shunt zwischen Herzhöhlen",
    [
        "Die Messungen geben Hinweise auf eine zusätzliche Verbindung zwischen Herzhöhlen. Das kann den Blutfluss beeinflussen und wird deshalb gezielt abgeklärt.",
        "In den Messwerten zeigt sich ein Hinweis, dass zwischen bestimmten Herzhöhlen eine ungewollte Verbindung bestehen könnte — das klären wir gezielt weiter ab.",
        "Es gibt Hinweise auf einen sogenannten Shunt — also eine zusätzliche Verbindung im Herzen. Weitere Untersuchungen zeigen, ob das tatsächlich so ist.",
        "Die Befunde lassen an eine zusätzliche Verbindung zwischen Herzkammern denken. Das ist keine Diagnose, aber ein wichtiger Punkt für die nächsten Tests.",
        "Ein möglicher Shunt wäre eine Verbindung zwischen Herzhöhlen, die den Blutfluss verändert. Die nächsten Untersuchungen zeigen, ob so etwas bei Ihnen vorliegt.",
        "Unsere Messungen passen zu einem möglichen Shunt. Bevor wir daraus Schlüsse ziehen, bestätigen wir das Bild mit weiteren Untersuchungen.",
    ],
)

_add(
    "PX_LIFESTYLE_HIGH_RISK",
    "Lebensstil-Hinweis bei erhöhtem Risiko",
    [
        "Bei höherem Risiko sollten körperliche Belastung, Trinkmenge und Tagesstruktur eng mit dem Behandlungsteam abgestimmt werden.",
        "Wenn das Risiko erhöht ist, lohnt es sich, Belastung, Trinkmenge und Tagesrhythmus gemeinsam mit uns sehr genau zu planen.",
        "Gerade bei erhöhtem Risiko helfen klar abgesprochene Regeln zu Belastung, Trinkmenge und Alltagsgestaltung — wir arbeiten das gemeinsam durch.",
        "Im Alltag kommen bei höherem Risiko Details stärker zum Tragen: Wie viel trinken? Wie sich belasten? Wie Pausen planen? Das besprechen wir sorgfältig.",
        "Bei Ihrem aktuellen Risiko ist es besonders wichtig, dass Belastung, Trinkmenge und Tagesablauf aufeinander abgestimmt sind. Wir begleiten Sie dabei.",
        "Höheres Risiko heißt nicht: nichts mehr tun. Es heißt: Bewegung, Trinkmenge und Alltag bewusst planen — gerne Schritt für Schritt mit uns zusammen.",
    ],
)

_add(
    "PX_FOLLOWUP_TIMING_DEFAULT",
    "Fallback, wenn kein strukturierter Nachsorge-Zeitpunkt vorliegt",
    [
        "Der genaue Zeitpunkt der nächsten klinischen Kontrolle wird im Behandlungsgespräch festgelegt.",
        "Wann genau die nächste klinische Kontrolle sinnvoll ist, besprechen wir individuell mit Ihnen im Behandlungsgespräch.",
        "Wir stimmen den nächsten Kontrolltermin persönlich mit Ihnen ab — abhängig vom Verlauf und Ihrer Situation.",
        "Den passenden Zeitpunkt für die nächste Kontrolle legen wir gemeinsam im Gespräch fest.",
        "Der nächste Kontrolltermin wird individuell geplant — sprechen Sie uns gern an, falls Sie konkrete Wünsche haben.",
        "Einen festen Kontrollzeitpunkt legen wir gemeinsam im Behandlungsgespräch fest, damit er zu Ihrer Situation passt.",
    ],
)

_add(
    "PX_INVASIVE_FOLLOWUP_DEFAULT",
    "Fallback für invasive Kontrolle ohne festen Zeitpunkt",
    [
        "Eine erneute invasive Kontrolle wird bei klinischer Verschlechterung oder bei Therapiefragen geprüft.",
        "Ob und wann eine erneute Rechtsherzkatheter-Untersuchung sinnvoll ist, entscheiden wir bei Verschlechterung oder wichtigen Therapiefragen gemeinsam.",
        "Eine weitere invasive Kontrolle erwägen wir, wenn sich Ihr Zustand verschlechtert oder wichtige Therapieentscheidungen anstehen.",
        "Invasive Verlaufsuntersuchungen planen wir nur, wenn der klinische Verlauf oder Therapieentscheidungen sie erfordern.",
        "Eine erneute invasive Kontrolle behalten wir als Option für den Fall vor, dass wir mit nicht-invasiven Mitteln nicht weiterkommen.",
        "Ob ein weiterer Rechtsherzkatheter nötig wird, entscheiden wir gemeinsam — meist erst dann, wenn der Verlauf oder eine Therapieumstellung es verlangen.",
    ],
)

_add(
    "PX_OBSERVE_WARNING_SIGNS",
    "Warnzeichen bis zum nächsten Termin",
    [
        "Bitte beobachten Sie bis zum nächsten Termin Luftnot, Belastbarkeit, Schwindel/Ohnmacht und mögliche Wassereinlagerungen.",
        "Achten Sie bis zum nächsten Termin besonders auf zunehmende Luftnot, nachlassende Belastbarkeit, Schwindel oder Ohnmacht sowie Schwellungen an Beinen oder Bauch.",
        "Bis zum nächsten Besuch hilft es, vier Dinge im Blick zu behalten: Ihre Luft, Ihre Belastbarkeit im Alltag, Schwindel- oder Ohnmachtsgefühle und mögliche Wassereinlagerungen.",
        "Falls sich bis zum nächsten Termin Luftnot, Belastbarkeit, Schwindel oder Schwellungen deutlich verändern, melden Sie sich bitte frühzeitig — lieber einmal zu viel als zu wenig.",
        "Viele Veränderungen spüren Sie selbst am frühesten: zunehmende Luftnot, weniger Kraft im Alltag, Schwindelgefühle oder Schwellungen. Notieren Sie solche Signale gerne und bringen Sie sie zum nächsten Termin mit.",
        "Unsere Bitte bis zum nächsten Termin: Beobachten Sie Luft, Belastbarkeit, Schwindel und eventuelle Schwellungen. Bei deutlichen Veränderungen rufen Sie bitte an.",
    ],
)

_add(
    "PX_NEXT_STEPS_INTRO",
    "Einleitung zur Liste der nächsten Schritte",
    [
        "Die folgenden Schritte sind, je nach Gesamtbild, geplant oder sinnvoll. Falls verfügbar, steht darunter kurz, warum das in Ihrer Situation relevant sein kann.",
        "Welche nächsten Schritte für Sie sinnvoll sind, hängt vom Gesamtbild ab. Wir listen die wichtigsten Empfehlungen kurz auf und erklären — wo möglich — den persönlichen Bezug.",
        "Hier kommen die empfohlenen oder bereits geplanten nächsten Schritte. Dort, wo es passt, begründen wir kurz, warum uns das in Ihrem Fall wichtig erscheint.",
        "Die folgende Liste bündelt, was für Ihre weitere Versorgung sinnvoll oder geplant ist. Wo passend, erläutern wir den Hintergrund in einem Satz.",
        "Im Folgenden finden Sie, was aus unserer Sicht an nächsten Schritten sinnvoll ist. Kürzere Erklärungen helfen dabei, den Bezug zu Ihrer Situation einzuordnen.",
        "Damit Sie nachvollziehen können, warum wir was empfehlen, ordnen wir die nächsten Schritte hier kurz ein.",
    ],
)

_add(
    "PX_NO_PH_MEDS_RECORDED",
    "Hinweis, wenn keine PH-Medikamente erfasst sind",
    [
        "Für diese Untersuchung sind keine strukturierten PH-Medikamente im Datensatz hinterlegt.",
        "Im Datensatz finden sich aktuell keine strukturiert erfassten Medikamente gegen Lungenhochdruck — was nicht bedeutet, dass Sie keine nehmen; nur dass sie nicht formal dokumentiert sind.",
        "Es liegen zu dieser Untersuchung keine strukturiert erfassten PH-Medikamente vor. Falls Sie welche einnehmen, bringen Sie gerne die aktuelle Medikamentenliste zum nächsten Termin mit.",
        "Strukturiert sind derzeit keine spezifischen PH-Medikamente dokumentiert. Das persönliche Gespräch ist ein guter Moment, die Therapie noch einmal gemeinsam zu sichten.",
        "Im System liegen für diesen Befund keine strukturiert hinterlegten PH-Medikamente vor — wir ergänzen das gerne mit Ihnen gemeinsam.",
        "Zur aktuellen Untersuchung gibt es keine formale Liste mit PH-Medikamenten. Das können wir beim nächsten Termin gemeinsam aktualisieren.",
    ],
)

_add(
    "PX_DOSE_NOTE",
    "Hinweis zur Medikamentendosierung",
    [
        "Wenn Dosierungen in den Daten fehlen, werden sie im persönlichen Gespräch ergänzt. Bitte Medikamente nicht selbstständig ändern.",
        "Sollten bei einzelnen Medikamenten Dosierungsangaben fehlen, klären wir das beim nächsten Termin. Bitte passen Sie Dosierungen niemals eigenmächtig an.",
        "Fehlen in der Übersicht Dosen, liegt das oft an der Dokumentation, nicht an Ihrer Therapie. Wir besprechen das im Gespräch — bitte nichts eigenständig umstellen.",
        "Manche Dosisangaben sind möglicherweise nicht vollständig erfasst. Bitte warten Sie mit jeder Änderung auf das ärztliche Gespräch.",
        "Falls Dosierungen in dieser Übersicht lückenhaft wirken, ergänzen wir die Informationen im persönlichen Termin. Medikamentenänderungen bitte nur in Absprache.",
        "Hinweis: Lücken bei Dosierungen liegen meist an der Datenerfassung. Bitte keine eigenständigen Änderungen — wir klären offene Punkte persönlich.",
    ],
)

_add(
    "PX_SYNCOPE_WARNING",
    "Warnhinweis bei dokumentierter Ohnmacht",
    [
        "Da bei Ihnen Ohnmacht oder Beinahe-Ohnmacht angegeben wurde, ist das ein besonders wichtiges Warnsignal. Bitte melden Sie sich bei erneuten Episoden zeitnah.",
        "In Ihrer Anamnese ist Ohnmacht oder Beinahe-Ohnmacht vermerkt — ein ernstzunehmendes Warnzeichen. Bitte lassen Sie uns zeitnah wissen, wenn Sie erneut solche Episoden bemerken.",
        "Ohnmachtsepisoden sind bei Erkrankungen wie der Ihren besonders ernst zu nehmen. Sollte eine weitere Episode auftreten, melden Sie sich bitte umgehend bei uns.",
        "Weil Ohnmacht oder Beinahe-Ohnmacht bereits aufgetreten ist, gilt ein besonderes Augenmerk: Jede neue Episode bitte umgehend mit uns besprechen.",
        "Berichtete Ohnmachtsneigung ist ein wichtiges Warnsignal. Bitte kontaktieren Sie uns rasch, wenn Sie erneut solche Gefühle erleben — auch wenn sie nur kurz sind.",
        "Da Ohnmacht zu Ihren dokumentierten Symptomen gehört, bitten wir Sie, jede weitere Episode zeitnah zu melden — gern telefonisch, damit wir schnell reagieren können.",
    ],
)

_add(
    "PX_DIZZINESS_WARNING",
    "Warnhinweis bei dokumentiertem Schwindel",
    [
        "Da bei Ihnen Schwindel angegeben wurde, ist es wichtig, Belastung so zu dosieren, dass keine Beinahe-Ohnmacht auftritt. Bei deutlicher Zunahme bitte frühzeitig Rücksprache halten.",
        "Weil in Ihrer Anamnese Schwindel dokumentiert ist, empfehlen wir, körperliche Belastung behutsam einzuteilen. Sollte der Schwindel zunehmen, melden Sie sich bitte rechtzeitig.",
        "Schwindel ist bei der Planung Ihres Alltags ein wichtiger Hinweis: Passen Sie das Tempo so an, dass Sie sich nie an die Grenze der Ohnmacht bringen.",
        "Da Schwindel vermerkt ist, achten Sie bitte auf gut dosierte Belastungen. Bei deutlicher Zunahme kontaktieren Sie uns frühzeitig — wir schauen dann gemeinsam, was dahintersteckt.",
        "Schwindelgefühle sind bei Ihrer Erkrankung ein Signal, dosiert und achtsam aktiv zu sein. Wenn der Schwindel spürbar stärker wird, bitte zeitnah Rücksprache halten.",
        "Weil Schwindel zu Ihren Beschwerden zählt, raten wir, Belastungen so zu steuern, dass Sie sicher durch den Tag kommen. Ausgeprägte Zunahme bitte nicht auf sich beruhen lassen — melden Sie sich dann bitte.",
    ],
)


# ---------------------------------------------------------------------------
# Nachsorge / Follow-up
# ---------------------------------------------------------------------------

_add(
    "PX_FOLLOWUP",
    "Nachsorge und Verlaufskontrollen",
    [
        "Regelmäßige Kontrollen sind ein wichtiger Teil der Behandlung. Sie helfen uns, Veränderungen frühzeitig zu erkennen und die Therapie bei Bedarf anzupassen.",
        "Wir planen Verlaufskontrollen in regelmäßigen Abständen. Dazu gehören Blutuntersuchungen, Herzultraschall und gegebenenfalls Belastungstests. So behalten wir Ihre Situation im Blick.",
        "Die Nachsorge ist genauso wichtig wie die Erstuntersuchung. Nur durch regelmäßige Kontrollen können wir sicherstellen, dass die Behandlung wirkt und keine neuen Probleme auftreten.",
        "Zwischen den Kontrollterminen sind Sie nicht allein: Bitte melden Sie sich, wenn sich Ihre Beschwerden verändern, neue Symptome auftreten oder Sie Fragen haben. Wir sind für Sie da.",
        "Die Kontrollen werden individuell geplant. In manchen Phasen sind engmaschigere Termine sinnvoll, in stabilen Phasen können die Abstände größer sein. Das besprechen wir gemeinsam.",
        "Ihre Mitwirkung ist ein wichtiger Teil der Nachsorge: Bitte nehmen Sie Ihre Medikamente regelmäßig ein, beobachten Sie Ihre Belastbarkeit und kommen Sie zu den vereinbarten Terminen.",
    ],
)


# ---------------------------------------------------------------------------
# Übergangs-Phrasen (Fließtext zwischen Blöcken, v27.4.26+)
# ---------------------------------------------------------------------------
# Diese kurzen Brücken-Sätze glätten Übergänge zwischen thematisch verbundenen
# Aussagen. Sie tragen keine neue medizinische Information, sondern geben dem
# Text eine menschliche Rhythmik: anstatt dass jeder Absatz neu ansetzt
# ("Mit X mmHg ..." / "Mit einem Y ..."), leitet eine kurze Brücke ruhig über.
# Auswahl erfolgt zur Laufzeit randomisiert (deterministisch pro Fall).

_add(
    "PX_BRIDGE_ADD",
    "Brücke: zusätzlicher paralleler Befund",
    [
        "Dazu passt der nächste Messwert.",
        "Ergänzend dazu ein weiterer Eckpunkt:",
        "Ein zweiter Wert rundet das Bild ab.",
        "Hinzu kommt ein weiterer Kernwert der Untersuchung.",
        "Auf derselben Linie liegt der nächste Messwert.",
        "Ein verwandter Wert fügt sich hier an.",
    ],
)

_add(
    "PX_BRIDGE_CONTRAST",
    "Brücke: kontrastierender / ergänzender Befund",
    [
        "Auf der anderen Seite lohnt sich der Blick auf die linke Herzseite.",
        "Gleichzeitig verhält sich ein anderer Wert anders, und das ist hilfreich:",
        "Dem gegenüber steht ein beruhigender Befund:",
        "Während der eine Wert erhöht ist, liefert ein anderer zusätzliche Orientierung:",
        "Um das Bild auszubalancieren, schauen wir auf den Gegenpol:",
        "Bevor wir tiefer gehen, ein kurzer Blick auf die andere Seite der Messung:",
    ],
)

_add(
    "PX_BRIDGE_CONSEQUENCE",
    "Brücke: ursächlich / folgernd",
    [
        "Daraus folgt für die Einordnung:",
        "Was sich daraus für Ihr Herz ableiten lässt, zeigt sich im nächsten Messwert:",
        "Wie stark das rechte Herz dadurch beansprucht wird, verrät der folgende Wert:",
        "Welche Konsequenz das für die Pumpleistung hat, sehen wir hier:",
        "Die Auswirkung auf den Kreislauf wird am nächsten Wert ablesbar:",
        "Ob und wie das Herz darauf reagiert, lässt sich am folgenden Wert erkennen:",
    ],
)

_add(
    "PX_BRIDGE_PUMP_FOCUS",
    "Brücke: Wechsel zu Pumpleistung (CI/CO)",
    [
        "Von den Drücken aus schauen wir nun auf die Pumpleistung des Herzens.",
        "Neben dem Druck zählt auch, wie viel Blut das Herz tatsächlich fördert.",
        "Nicht nur der Druck, auch der Fluss erzählt uns etwas:",
        "Der nächste Blick gilt der eigentlichen Leistung Ihres Herzens.",
        "Wie gut Ihr Herz trotz dieser Belastung pumpt, zeigt der folgende Wert:",
        "Jetzt zur Frage, wie viel Blut Ihr Herz pro Minute tatsächlich bewegt.",
    ],
)

_add(
    "PX_BRIDGE_RIGHT_HEART",
    "Brücke: Wechsel zur rechten Herzseite / venöse Seite",
    [
        "Ein kurzer Blick auf die rechte Herzseite rundet das Bild ab.",
        "Wie stark das rechte Herz die Mehrarbeit merkt, zeigt ein weiterer Wert:",
        "Der nächste Wert verrät, wie angespannt die rechte Herzseite aktuell ist.",
        "Weiter zur rechten Herzhälfte — sie steht im Lungenhochdruck besonders im Fokus.",
        "Wie sehr sich der Druck bis in den rechten Vorhof auswirkt, beschreibt der folgende Wert:",
        "Auch der Druck im rechten Vorhof liefert wichtige Hinweise:",
    ],
)

_add(
    "PX_BRIDGE_BIOMARKER",
    "Brücke: Wechsel zu Laborwerten / Biomarker",
    [
        "Neben den Messwerten aus dem Herzkatheter ist noch ein Blutwert wichtig.",
        "Zur Einordnung gehört auch ein Blick auf die Labor-Seite:",
        "Ergänzend liefert ein Blutwert eine weitere Information:",
        "Ein Blutwert hilft uns, das Bild vollständig zu machen:",
        "Den hämodynamischen Werten zur Seite steht ein wichtiger Labor-Parameter:",
        "Zum Abschluss noch ein Blick auf das Blut — es verrät, wie sehr das Herz gerade beansprucht ist.",
    ],
)

_add(
    "PX_BRIDGE_SECTION_CLOSE",
    "Brücke: Abschluss eines Abschnitts",
    [
        "Zusammengenommen zeichnet sich damit ein klares Bild ab.",
        "Unter dem Strich lässt sich die Messung wie folgt einordnen:",
        "Im Kern ergibt sich aus diesen Werten Folgendes:",
        "So entsteht das Gesamtbild dieser Untersuchung.",
        "Zusammen ergeben diese Werte die Grundlage für die weiteren Schritte.",
        "Aus der Summe dieser Messwerte lässt sich ein zusammenhängendes Bild lesen.",
    ],
)

_add(
    "PX_BRIDGE_TO_CAUSES",
    "Brücke: Überleitung zu Ursachen",
    [
        "Welche Ursachen dahinter stecken, ist die nächste wichtige Frage.",
        "Als Nächstes fragen wir: Woher kommen diese Veränderungen?",
        "Damit rückt die Frage nach der Ursache in den Vordergrund.",
        "Was hinter diesen Werten stecken könnte, schauen wir uns im Detail an.",
        "Der nächste Schritt ist zu verstehen, warum Ihre Werte so ausfallen.",
        "Von den Messwerten aus gehen wir nun einen Schritt weiter — zur Ursachenforschung.",
    ],
)

_add(
    "PX_BRIDGE_TO_THERAPY",
    "Brücke: Überleitung zur Therapie",
    [
        "Was das für Ihre Behandlung bedeutet, fassen wir im Folgenden zusammen.",
        "Auf Basis dieser Einordnung ergibt sich die folgende Behandlungsstrategie:",
        "Daraus leiten wir die nächsten therapeutischen Schritte ab:",
        "Wie wir darauf reagieren, beschreibt der nächste Abschnitt:",
        "Das beantwortet auch die Frage, welche Therapie für Sie sinnvoll ist.",
        "Welche Behandlung in Ihrer Situation passt, erklären wir jetzt:",
    ],
)

_add(
    "PX_BRIDGE_TO_EVERYDAY",
    "Brücke: Überleitung zum Alltag",
    [
        "Für Ihren Alltag heißt das konkret Folgendes:",
        "Was das in der Praxis bedeutet, übersetzen wir jetzt in Alltagstipps:",
        "Von der Theorie zum Alltag: Diese Hinweise helfen Ihnen im Tagesverlauf.",
        "Damit Sie das Gelesene im Alltag nutzen können, hier einige Anker:",
        "Übersetzt in Alltagssprache bedeutet das:",
        "Wie Sie selbst einen Beitrag leisten können, zeigen die nächsten Hinweise:",
    ],
)
