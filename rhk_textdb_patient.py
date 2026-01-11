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
    PATIENT_BLOCKS[block_id] = PatientBlock(
        id=block_id,
        title=title,
        templates=_as_list(templates),
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
    ],
)

_add(
    "PX_NO_PH",
    "Kein Lungenhochdruck in Ruhe",
    [
        "In Ruhe zeigen die Messwerte **keinen Hinweis** auf eine Druckerhöhung in den Blutgefäßen der Lunge.",
        "Die Druckwerte in den Blutgefäßen der Lunge sind **in Ruhe nicht erhöht**. Das ist ein beruhigender Befund.",
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
    ],
)

_add(
    "PX_ARCH_H1_FOCUS_MEANING",
    "Archetyp H1: kein PH in Ruhe, aber Risiko/Vorerkrankung – Fokus Bedeutung",
    [
        "Das Ziel ist jetzt vor allem, Veränderungen früh zu erkennen. Wichtig sind dabei Beschwerden, Belastbarkeit und Kontrolluntersuchungen, nicht nur ein einzelner Messzeitpunkt.",
        "In solchen Situationen ist oft die Kombination aus Symptomen, Verlauf und ergänzenden Untersuchungen entscheidend. So können wir rechtzeitig handeln, falls sich etwas verändert.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEASURED",
    "Archetyp H2: Grenzwerte/frühe PH – Fokus Messung",
    [
        "Einige Werte liegen in einem Grenzbereich. Das kann ein sehr frühes Stadium sein oder eine vorübergehende Schwankung. Deshalb ist Dynamik oft wichtiger als eine Momentaufnahme.",
        "Die Messwerte bewegen sich nahe an den Grenzbereichen. Das allein ist noch keine Aussage darüber, wie stabil die Situation bleibt. Entscheidend ist der Verlauf zusammen mit Ihren Beschwerden.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEANING",
    "Archetyp H2: Grenzwerte/frühe PH – Fokus Bedeutung",
    [
        "In einem Frühstadium geht es häufig darum, Ursachen sauber einzuordnen und den Verlauf zu beobachten. Eine Behandlung wird immer gegen Nutzen und Risiken abgewogen.",
        "Bei grenzwertigen Befunden ist es besonders wichtig, Trends zu erkennen: Werden Werte oder Beschwerden schlechter, bleibt alles stabil oder verbessert es sich? Daraus leiten wir die nächsten Schritte ab.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEASURED",
    "Archetyp H3: etablierte präkapilläre PH – Fokus Messung",
    [
        "Die Werte sprechen dafür, dass die Lungengefäße einen erhöhten Widerstand bieten. Das rechte Herz muss dadurch gegen eine höhere Nachlast arbeiten.",
        "Im Vordergrund steht eine erhöhte Belastung des rechten Herzens durch den Widerstand in den Lungengefäßen. Das erklärt, warum Belastung und Leistungsfähigkeit so wichtig sind.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEANING",
    "Archetyp H3: etablierte präkapilläre PH – Fokus Bedeutung",
    [
        "Der Schwerpunkt liegt nun weniger auf der Frage *ob* Lungenhochdruck vorliegt, sondern darauf, wie gut das rechte Herz damit zurechtkommt und welche Therapieziele wir gemeinsam verfolgen.",
        "Wichtig ist, die Belastung des rechten Herzens zu senken und die Belastbarkeit zu stabilisieren oder zu verbessern. Kontrollen helfen, Therapieeffekte früh zu erkennen.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEASURED",
    "Archetyp H4: postkapilläre/kombinierte PH – Fokus Messung",
    [
        "Es gibt Hinweise, dass der Druckanstieg (auch) durch einen Rückstau von der linken Herzseite mitbedingt ist. Das verändert, welche Behandlungsansätze im Vordergrund stehen.",
        "Das Muster spricht dafür, dass die linke Herzhälfte eine wichtige Rolle spielt. Dann ist die Einordnung der linken Herzfunktion und der Flüssigkeitsbalance besonders relevant.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEANING",
    "Archetyp H4: postkapilläre/kombinierte PH – Fokus Bedeutung",
    [
        "In solchen Konstellationen ist oft die Behandlung des linken Herzens und der Begleiterkrankungen entscheidend. Eine spezifische PH‑Therapie ist nicht automatisch der erste Schritt.",
        "Der wichtigste Hebel ist häufig, den Rückstau zu reduzieren und die linke Herzfunktion bestmöglich zu unterstützen. Welche Medikamente sinnvoll sind, wird individuell entschieden.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEASURED",
    "Archetyp H5: thromboembolische Konstellation/CTEPH – Fokus Messung",
    [
        "Es gibt Hinweise, dass (auch) ältere Blutgerinnsel in den Lungengefäßen eine Rolle spielen könnten. Dann geht es besonders um die Mechanik des Blutflusses durch die Lunge.",
        "Bei diesem Muster ist wichtig zu prüfen, ob Engstellen durch ältere Gerinnsel bestehen. Das kann man mit gezielter Bildgebung oft sehr gut beurteilen.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEANING",
    "Archetyp H5: thromboembolische Konstellation/CTEPH – Fokus Bedeutung",
    [
        "Wenn sich der Verdacht bestätigt, gibt es neben Medikamenten auch spezielle Behandlungsoptionen, die die Durchblutung der Lunge direkt verbessern können. Welche davon passt, hängt von der genauen Verteilung ab.",
        "In diesem Zusammenhang sind bestimmte Untersuchungen wie die Ventilations/Perfusions‑Szintigraphie besonders hilfreich. Sie zeigen, wie gleichmäßig die Lunge durchblutet wird.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEASURED",
    "Archetyp H6: rechtes Herz im Vordergrund bei moderatem Druck – Fokus Messung",
    [
        "Obwohl die Druckwerte nicht extrem hoch sind, zeigen Marker des rechten Herzens eine relevante Belastung. Das kann erklären, warum Beschwerden dennoch deutlich sein können.",
        "Manchmal spiegelt der Druck allein nicht die gesamte Situation wider. Hinweise auf eine Belastung des rechten Herzens oder Rückstau können dann besonders aussagekräftig sein.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEANING",
    "Archetyp H6: rechtes Herz im Vordergrund bei moderatem Druck – Fokus Bedeutung",
    [
        "Dann ist besonders wichtig, Funktion, Belastbarkeit und Verlauf zu betrachten. Therapieentscheidungen orientieren sich oft daran, wie gut das rechte Herz die Situation kompensieren kann.",
        "In solchen Fällen achten wir besonders auf Verlauf, Belastbarkeit und Zeichen von Rückstau. Das hilft, die Behandlung an das anzupassen, was für Sie im Alltag relevant ist.",
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
    ],
)

_add(
    "PX_SYMPTOMS_MODERATE",
    "Symptome: moderat",
    [
        "Ihre Beschwerden wirken spürbar, aber nicht maximal ausgeprägt. Für die Therapieplanung ist wichtig, ob Sie im Alltag stabil bleiben oder ob die Belastbarkeit weiter abnimmt.",
        "Die Symptome passen zu einer moderaten Einschränkung. Wir nutzen Messwerte und Verlauf gemeinsam, um zu entscheiden, ob und wann Anpassungen nötig sind.",
    ],
)

_add(
    "PX_SYMPTOMS_HIGH",
    "Symptome: deutlich",
    [
        "Ihre Beschwerden wirken deutlich. In solchen Situationen hat die klinische Situation oft das gleiche Gewicht wie einzelne Messwerte. Wir planen Kontrollen und Therapie so, dass Sie im Alltag sicher bleiben.",
        "Bei deutlich eingeschränkter Belastbarkeit ist besonders wichtig, Warnzeichen ernst zu nehmen und Veränderungen früh zu besprechen. Dann kann man rechtzeitig gegensteuern.",
    ],
)

_add(
    "PX_SYMPTOMS_SYNCOPE",
    "Symptome: Synkope",
    [
        "Ohnmacht oder Beinahe-Ohnmacht ist bei Lungengefäß-Erkrankungen ein wichtiges Warnsignal. Das bedeutet nicht automatisch Gefahr im Moment, sollte aber konsequent und zeitnah abgeklärt werden.",
        "Wenn es zu Ohnmacht oder Beinahe-Ohnmacht kommt, kann das darauf hinweisen, dass Kreislauf und rechtes Herz unter Belastung an Grenzen kommen. Bitte sprechen Sie neue Episoden immer zeitnah an.",
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
    ],
)

_add(
    "PX_TREND_SUBTYPE_PRESSURE_BETTER_PVR_WORSE",
    "Verlaufstyp: Druck besser, Widerstand schlechter",
    [
        "Ein Teil der Werte ist besser, ein anderer ungünstiger. Wenn der Druck etwas fällt, der Widerstand aber steigt, kann das zum Beispiel an Messstreuung, dem Flüssigkeitshaushalt oder einer veränderten Durchblutung der Lunge liegen. Wichtig ist dann, welche Veränderung am besten zu Ihren Beschwerden passt.",
        "Wenn Druck und Widerstand unterschiedliche Richtungen zeigen, schauen wir besonders auf Pumpleistung, Rückstau und Belastbarkeit. Daraus ergibt sich, welcher Teil klinisch entscheidend ist.",
    ],
)

_add(
    "PX_TREND_SUBTYPE_EFFECT_UNCLEAR",
    "Verlaufstyp: Therapieeffekt unklar",
    [
        "Wenn sich einzelne Werte nur wenig verändern oder unterschiedliche Richtungen zeigen, kann der Therapieeffekt noch unklar sein. Dann hilft oft eine Verlaufskontrolle mit denselben Messmethoden und ein Blick auf Belastbarkeit und Symptome.",
        "Nicht jede Veränderung ist sofort eindeutig. Entscheidend ist, ob Sie sich im Alltag stabiler fühlen und ob Warnzeichen auftreten. Das besprechen wir gezielt im Verlauf.",
    ],
)

_add(
    "PX_INCOMPLETE",
    "Einordnung derzeit nicht eindeutig",
    [
        "Die Messwerte sind noch **nicht vollständig** oder liegen in einem Bereich, der sich nicht eindeutig einordnen lässt. Das ist nicht ungewöhnlich – dann braucht es meist zusätzliche Informationen.",
        "Aktuell lässt sich aus den Messwerten **keine eindeutige Einordnung** ableiten. In solchen Situationen sind Ihre Beschwerden und ergänzende Untersuchungen besonders wichtig.",
    ],
)

_add(
    "PX_WHAT_IS_PH",
    "Was bedeutet Lungenhochdruck?",
    [
        "Wenn der Blutdruck in den Gefäßen der Lunge erhöht ist, muss die rechte Herzhälfte **mehr arbeiten**. Das kann Luftnot, Müdigkeit oder Wassereinlagerungen erklären.",
        "Eine Druckerhöhung in den Blutgefäßen der Lunge kann **verschiedene Ursachen** haben. Entscheidend ist, *wo* der Druckanstieg entsteht – zum Beispiel eher in den Lungengefäßen selbst, durch die linke Herzseite oder durch ältere Blutgerinnsel.",
        "Lungenhochdruck ist **kein einzelnes Krankheitsbild**. Die Ursache kann sehr unterschiedlich sein. Darum ist die genaue Einordnung wichtig, damit wir die passende Behandlung auswählen.",
    ],
)


_add(
    "PX_HEMO_EXPLAIN",
    title="Kurz erklärt: was die wichtigsten Zahlen bedeuten",
    templates=[
        "Die wichtigsten Messwerte lassen sich so verstehen: "
        "**mPAP** beschreibt den durchschnittlichen Druck in den Lungengefäßen. "
        "**PAWP** ist ein Hinweis darauf, ob sich Blut vor der linken Herzhälfte „staut“. "
        "**PVR** beschreibt den Widerstand in den Lungengefäßen (erhöht z. B. bei verengten/steifen Gefäßen). "
        "**CI** beschreibt die Pumpleistung bezogen auf die Körpergröße. "
        "**RAP** ist ein Hinweis auf Rückstau im Körperkreislauf. "
        "Entscheidend ist immer die Kombination dieser Werte – nicht eine Zahl allein.",
        "Kurz zur Orientierung: mPAP = Druck in der Lunge, PAWP = Rückstau vor dem linken Herzen, "
        "PVR = Widerstand in den Lungengefäßen, CI = Pumpleistung, RAP = Rückstau im Körper. "
        "Aus dem Muster dieser Werte lässt sich ableiten, welche Ursachen wahrscheinlicher sind und welche nächsten Schritte sinnvoll sind.",
    ],
)



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

_add(
    "PX_INTERPRETATION",
    "Wie ordnen wir das ein?",
    [
        "Die Messwerte sind ein wichtiger Baustein. Für die Gesamtbeurteilung schauen wir zusätzlich auf Bildgebung, Ultraschall des Herzens, Lungenfunktion und Ihre Beschwerden.",
        "Wichtig ist die Zusammenschau: Messwerte, Beschwerden und weitere Untersuchungen gehören zusammen. Erst daraus leiten wir das sinnvollste Vorgehen ab.",
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
    ],
)

_add(
    "PX_PRECAP_MOD",
    "Präkapilläre Druckerhöhung – mittel",
    [
        "Die Messwerte sprechen für eine **Druckerhöhung**, die eher in den Blutgefäßen der Lunge oder in der Lunge selbst entsteht.",
        "Die Untersuchung zeigt Hinweise auf einen Lungenhochdruck, bei dem die Ursache eher **vor** der linken Herzseite liegt – also eher in der Lunge bzw. den Lungengefäßen.",
    ],
)

_add(
    "PX_PRECAP_SEV",
    "Präkapilläre Druckerhöhung – deutlich",
    [
        "Die Messwerte sprechen für eine **deutliche Druckerhöhung** in den Blutgefäßen der Lunge. Das sollte zeitnah in einem spezialisierten Team weiter eingeordnet werden.",
        "Es liegt eine **ausgeprägte Druckerhöhung** in den Blutgefäßen der Lunge nahe. Dafür ist eine strukturierte Ursachenabklärung und Therapieplanung wichtig.",
    ],
)

_add(
    "PX_POSTCAP",
    "Druckerhöhung durch die linke Herzseite",
    [
        "Die Messwerte sprechen dafür, dass der Druckanstieg vor allem durch die **linke Herzseite** mitbedingt ist. Das kann zu einer Rückstau-Situation Richtung Lunge führen.",
        "Die Messwerte passen eher zu einer Situation, bei der die **linke Herzseite** eine wichtige Rolle spielt. Dadurch kann sich Druck in Richtung Lungengefäße übertragen.",
    ],
)

_add(
    "PX_CPCPH",
    "Gemischte Druckerhöhung",
    [
        "Die Messwerte sprechen für eine **Mischkonstellation**: Es gibt Anzeichen für einen Druckanstieg durch die linke Herzseite und zusätzlich Hinweise auf eine zusätzliche Verengung in den Lungengefäßen.",
        "Die Befunde passen zu einer **kombinierten Situation**: Druckübertragung von der linken Herzseite und zugleich eine zusätzliche Belastung der Lungengefäße.",
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
    ],
)

_add(
    "PX_EX_PVASC",
    "Auffällige Druckantwort unter Belastung – eher Lungengefäße",
    [
        "In Ruhe waren die Werte nicht eindeutig auffällig. **Unter körperlicher Belastung** zeigt sich aber ein Muster, das eher zu einer Belastung der Lungengefäße passt.",
        "Bei Belastung steigt der Druck in den Lungengefäßen stärker an als erwartet. Das kann helfen, eine beginnende Erkrankung der Lungengefäße früh zu erkennen.",
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
        "Das kann z. B. im Zusammenhang mit bestimmten Autoimmun-/Rheuma-Erkrankungen, seltenen genetischen Veränderungen "
        "oder bestimmten Infektionen auftreten. "
        "Um das sicher einzuordnen, sind oft spezielle Laborwerte, eine genaue Bildgebung und die Beurteilung im spezialisierten PH‑Zentrum sinnvoll.",
        "Wenn neben anderen Ursachen auch eine sogenannte „pulmonal-arterielle“ Form in Frage kommt, "
        "wird häufig eine gezielte Zusatzdiagnostik empfohlen (z. B. Autoimmun- und Virus-Tests, ggf. genetische Abklärung). "
        "Das dient vor allem dazu, die bestmögliche, individuell passende Therapie zu finden.",
    ],
)

_add(
    "PX_GROUP2_HINT",
    "Hinweis auf linke Herzseite",
    [
        "Ein Teil der Befunde passt dazu, dass die **linke Herzseite** mitbeteiligt sein könnte. Das wird kardiologisch weiter eingeordnet.",
        "Es gibt Hinweise, dass eine Belastung der linken Herzseite eine Rolle spielen könnte. Oft ist dann eine kardiologische Therapieoptimierung sinnvoll.",
    ],
)

_add(
    "PX_GROUP3_HINT",
    "Hinweis auf Lunge / Sauerstoff",
    [
        "Es gibt Hinweise, dass eine **Lungenerkrankung** oder eine niedrige Sauerstoffversorgung mitbeteiligt sein könnte. Dann sind Lungenfunktion und Bildgebung besonders wichtig.",
        "Ein Teil der Befunde kann zu einer Beteiligung der Lunge passen. In solchen Fällen hilft eine pneumologische Mitbeurteilung, um die Behandlung zu optimieren.",
    ],
)

_add(
    "PX_GROUP4_HINT",
    "Hinweis auf ältere Blutgerinnsel",
    [
        "Es gibt Hinweise, die zu **älteren oder chronischen Blutgerinnseln** in den Lungengefäßen passen könnten. Das sollte gezielt weiter abgeklärt werden.",
        "Ein Teil der Befunde lässt an eine chronische Durchblutungsstörung der Lunge denken, zum Beispiel durch ältere Blutgerinnsel. Dann ist eine spezialisierte Abklärung wichtig.",
    ],
)

_add(
    "PX_SHUNT_HINT",
    "Hinweis auf zusätzliche Verbindung zwischen Herzhöhlen",
    [
        "Die Sauerstoffmessungen im Herzen sprechen dafür, dass es möglicherweise eine **zusätzliche Verbindung zwischen Herzhöhlen** gibt. Das ist oft gut weiter abklärbar, zum Beispiel mit einem spezialisierten Ultraschall.",
        "Die Messungen im Herzen geben Hinweise auf eine mögliche zusätzliche Verbindung zwischen Herzhöhlen. Das kann den Blutfluss beeinflussen und sollte gezielt abgeklärt werden.",
    ],
)

_add(
    "PX_ANEMIA",
    "Blutarmut",
    [
        "Im Blutbild gibt es Hinweise auf eine **Blutarmut**. Das kann die Belastbarkeit beeinflussen und sollte gezielt abgeklärt und behandelt werden.",
        "Es bestehen Hinweise auf eine Blutarmut. Eine Behandlung kann helfen, die Leistungsfähigkeit zu verbessern.",
    ],
)

_add(
    "PX_CONGESTION",
    "Wassereinlagerung / Rückstau",
    [
        "Es gibt Hinweise auf **Wassereinlagerung oder Rückstau**. Dann ist es wichtig, den Flüssigkeitshaushalt gut einzustellen und die Nierenwerte im Blick zu behalten.",
        "Ein Teil der Befunde passt zu Wassereinlagerung. Oft hilft eine Anpassung der Entwässerung und eine regelmäßige Kontrolle der Werte.",
    ],
)

_add(
    "PX_SAFETY_NET",
    "Sicherheitshinweis",
    [
        "Wenn neue oder starke Beschwerden auftreten (zum Beispiel Ohnmacht, stark zunehmende Luftnot oder Brustschmerz), suchen Sie bitte zeitnah ärztliche Hilfe.",
        "Bitte holen Sie rasch ärztliche Hilfe, wenn es zu plötzlich starker Luftnot, Ohnmacht, Brustschmerz oder blutigem Auswurf kommt.",
    ],
)

_add(
    "PX_NEXT_STEPS",
    "Wie geht es weiter?",
    [
        "Wir besprechen die Ergebnisse mit Ihnen und planen die nächsten Schritte. Das kann zusätzliche Untersuchungen, eine Anpassung der Medikamente und Verlaufskontrollen beinhalten.",
        "Als nächstes planen wir gemeinsam mit Ihnen die weiteren Schritte. Je nach Ursache können weitere Tests, eine Therapieanpassung und Verlaufskontrollen sinnvoll sein.",
        "Die Ergebnisse werden nun im Team eingeordnet. Daraus leiten wir ab, welche weiteren Untersuchungen oder Therapieschritte in Ihrem Fall am meisten helfen.",
    ],
)

_add(
    "PX_DISCLAIMER",
    "Hinweis",
    [
        "Dieser Text ist eine verständliche Zusammenfassung und ersetzt kein ärztliches Gespräch. Bitte klären Sie offene Fragen im nächsten Termin.",
        "Hinweis: Diese Zusammenfassung dient der Orientierung. Die individuelle Einordnung und Behandlung erfolgt im persönlichen Gespräch.",
    ],
)


# ---------------------------------------------------------------------------
# Bündel: Zuordnung an Rulebook-Bundles (Kxx)
# ---------------------------------------------------------------------------
# Rulebook-Bundles in rhk_rules.yaml: K00, K01, K05, K06, K07, K09, K10, K11, K14, K15, K16
PATIENT_BUNDLES: Dict[str, List[str]] = {
    # kein Lungenhochdruck in Ruhe
    # (Der ausführliche Ablauf/Plan steht im generierten Patientenbericht; hier nur die Kernaussage.)
    "K00": ["PX_NO_PH"],

    # unvollständig / nicht eindeutig
    "K01": ["PX_INCOMPLETE"],

    # präkapillär (leicht / mittel / deutlich)
    "K05": ["PX_PRECAP_MILD", "PX_WHAT_IS_PH"],
    "K06": ["PX_PRECAP_MOD",  "PX_WHAT_IS_PH"],
    "K07": ["PX_PRECAP_SEV",  "PX_WHAT_IS_PH"],

    # postkapillär / kombiniert
    "K14": ["PX_POSTCAP", "PX_WHAT_IS_PH"],
    "K15": ["PX_CPCPH",  "PX_WHAT_IS_PH"],

    # Belastungsdruckantwort
    "K09": ["PX_EX_PVASC"],
    "K10": ["PX_EX_LEFT"],

    # präkapillär + Hinweis auf ältere Blutgerinnsel
    "K11": ["PX_PRECAP_MOD", "PX_GROUP4_HINT", "PX_WHAT_IS_PH"],

    # Shunt-Verdacht
    "K16": ["PX_SHUNT_HINT"],
}


# ---------------------------------------------------------------------------
# Patientenerklärungen zu den P‑Modulen (P01–P25)
# ---------------------------------------------------------------------------

# Hinweis: Diese Texte werden im Patientenbericht als "Warum dieser Schritt?" ausgegeben.
# Ziel ist nicht Vollständigkeit, sondern ein verständlicher Mehrwert (Warum / Was / Wofür).

PATIENT_MODULE_SUMMARY: Dict[str, str] = {
    "P01": "**Basisabklärung vervollständigen:** Wir ergänzen Standard‑Untersuchungen, um Ursache und Schweregrad besser einzuordnen und die passende Behandlung zu wählen.",
    "P02": "**Entwässerung optimieren:** Wenn der Körper Wasser einlagert, kann eine Anpassung von Entwässerungs‑Medikamenten helfen (z. B. weniger Schwellungen, bessere Luft).",
    "P03": "**Medikament zur Entlastung der Lungengefäße (PDE5‑Hemmer):** Kann den Druck in den Lungengefäßen senken und die Belastbarkeit verbessern – falls in Ihrer Situation passend.",
    "P04": "**Medikament zur Entlastung der Lungengefäße (ERA):** Eine weitere Wirkstoffgruppe, die bei bestimmten Formen von PH/PAH sinnvoll sein kann.",
    "P05": "**Riociguat (Therapieoption):** Wird z. B. bei bestimmten Formen (u. a. chronische Gerinnsel‑PH) eingesetzt oder wenn ein Wechsel/Anpassung nötig ist.",
    "P06": "**Stärkere Therapieoptionen (Prostacyclin‑Therapie):** Bei ausgeprägter Erkrankung kann eine intensivierte Behandlung nötig sein – das bespricht man in einem spezialisierten Zentrum.",
    "P07": "**Studienteilnahme prüfen:** Manchmal gibt es Studien, die zusätzliche Therapie‑Optionen oder engmaschige Betreuung ermöglichen.",
    "P08": "**Interdisziplinäre Besprechung (Lunge/Bildgebung):** Befunde werden gemeinsam (Radiologie/Pneumologie/PH‑Team) bewertet, um die Ursache sicherer festzulegen.",
    "P09": "**Kardiologische Mitbeurteilung:** Prüfung von Herzklappen, Herzrhythmus und Durchblutung – besonders wichtig, wenn die linke Herzseite mitbeteiligt ist.",
    "P10": "**Blutverdünnung (Antikoagulation) klären/optimieren:** Bei Verdacht auf Gerinnsel‑Problematik ist das ein zentraler Baustein.",
    "P11": "**Verlaufskontrolle planen:** Wir legen fest, wann die nächsten Kontrollen sinnvoll sind (z. B. Echo, Labor, ggf. erneute Messung).",
    "P12": "**Lungenfunktion & Diffusion:** Klärt, ob die Lunge (Atemwege/Gewebe) zur Luftnot oder Druckerhöhung beiträgt.",
    "P13": "**Eisenmangel/Blutarmut behandeln:** Kann Luftnot und Müdigkeit verstärken – eine Korrektur verbessert oft die Belastbarkeit.",
    "P14": "**Rechte Herzhälfte genauer einschätzen:** Ultraschall‑Kennzeichen helfen zu beurteilen, wie stark das rechte Herz belastet ist – das beeinflusst Kontrollen und Therapieintensität.",
    "P15": "**Belastungsdiagnostik:** Ein Belastungstest kann zeigen, warum Beschwerden vor allem bei Aktivität auftreten und ob Herz, Lunge oder Kreislauf limitieren.",
    "P16": "**Schlafmedizin (Schlafapnoe) prüfen:** Atemaussetzer in der Nacht können Herz und Lunge belasten – Behandlung kann Symptome und Blutdruck verbessern.",
    "P17": "**Autoimmun-/Rheuma‑Abklärung:** Manche Bindegewebserkrankungen können PH verursachen – Bluttests/Abklärung helfen, das zu erkennen.",
    "P18": "**Infektiologisches Screening:** Bestimmte Infektionen (z. B. HIV, Hepatitis) können relevant sein – je nach Situation wird dies überprüft.",
    "P19": "**Leber/Portale Hypertonie abklären:** Bei Hinweisen auf Leber‑/Pfortader‑Probleme kann das für die Ursache wichtig sein.",
    "P20": "**Genetische Aspekte prüfen:** Bei Familienhinweisen oder sehr frühem Beginn kann eine genetische Beratung/Testung sinnvoll sein.",
    "P21": "**Schwangerschaft/Verhütung besprechen:** Bei PH kann eine Schwangerschaft riskant sein – eine gute Beratung schützt.",
    "P22": "**Reha/Training:** Angepasstes, betreutes Training kann die Alltagsbelastbarkeit verbessern (oft besser als „Schonung“).",
    "P23": "**Impfstatus/Infektprophylaxe:** Atemwegsinfekte können Beschwerden verschlechtern – Schutzmaßnahmen werden geprüft.",
    "P24": "**Sauerstoffversorgung messen:** In Ruhe, bei Belastung und ggf. nachts – damit Therapie (z. B. Sauerstoff) gezielt eingestellt werden kann.",
    "P25": "**Advanced Therapies / Transplant‑Optionen früh prüfen:** Bei schwerer Erkrankung ist es hilfreich, frühzeitig Optionen in einem Zentrum zu besprechen.",
"P26": "**Trinkmengenrestriktion & Volumenmanagement:** Wenn der Körper Wasser einlagert, helfen klare Trinkmengen, tägliches Wiegen und ein konsequenter Plan, um Luftnot und Schwellungen zu vermeiden.",
"P27": "**Kardiovaskuläre Risikofaktoren reduzieren:** Blutdruck, Blutzucker und Blutfette werden optimiert, Nikotinkarenz unterstützt und Begleiterkrankungen behandelt, damit Herz und Gefäße langfristig entlastet werden.",
"P28": "**Gewichtsreduktion:** Eine strukturierte Gewichtsreduktion kann Belastbarkeit, Atmung und den Kreislauf entlasten, besonders wenn Übergewicht die Symptome verstärkt.",
"P29": "**LTOT konsequent anwenden:** Wenn Langzeitsauerstoff verordnet ist, ist die regelmäßige Anwendung wichtig, damit die Sauerstoffversorgung stabil bleibt, auch bei Belastung oder nachts.",
"P30": "**CT Befunde interdisziplinär besprechen:** Ausstehende oder unklare CT Befunde werden in einer gemeinsamen Konferenz (Radiologie und Pneumologie) eingeordnet, damit das weitere Vorgehen gezielt geplant werden kann.",
}


# ---------------------------------------------------------------------------
# Glossar – kurze Erklärungen zentraler Begriffe
# ---------------------------------------------------------------------------

PATIENT_GLOSSARY: Dict[str, str] = {
    "PH": "Pulmonale Hypertonie (Lungenhochdruck): Erhöhter Blutdruck in den Gefäßen der Lunge.",
    "Rechtsherzkatheter": "Untersuchung, bei der über einen dünnen Schlauch Drücke und Blutfluss in Herz und Lunge gemessen werden.",
    "mPAP": "Mittlerer Druck in der Lungenarterie (ein Kernwert für Lungenhochdruck).",
    "PAWP": "Messwert, der Hinweise darauf geben kann, ob die linke Herzseite an der Druckerhöhung beteiligt ist.",
    "PVR": "Widerstand der Lungengefäße – vereinfacht: wie stark die Gefäße „eng“ sind.",
    "CI": "Herzindex – wie viel Blut das Herz pro Minute (bezogen auf Körpergröße) fördert.",
    "RAP": "Druck im rechten Vorhof – kann bei Wassereinlagerung/„Rückstau“ erhöht sein.",
    "HFpEF": "Herzschwäche trotz normaler Pumpkraft: Das Herz ist oft „steifer“ und füllt sich schlechter, vor allem bei Belastung.",
    "V/Q": "Ventilations-/Perfusionsszintigrafie: Untersuchung der Lungen‑Durchblutung (wichtig bei Verdacht auf ältere Blutgerinnsel).",
    "CT": "Computertomographie: Schnittbild‑Untersuchung, z. B. von Lunge und Lungengefäßen.",
    "Antikoagulation": "Blutverdünnung (Gerinnungshemmung), um Blutgerinnsel zu verhindern oder zu behandeln.",
    "DLCO": "Diffusionskapazität: zeigt, wie gut Sauerstoff über die Lunge ins Blut gelangt.",
    "Tiffeneau": "FEV1/FVC‑Quotient aus der Lungenfunktion. Ein niedriger Wert kann für verengte Atemwege sprechen.",
    "ILD": "Interstitielle Lungenerkrankung (z. B. Lungenfibrose): Erkrankung des Lungengewebes.",
    "ERA": "Medikamentengruppe bei bestimmten Formen von PH/PAH (wir erklären im Gespräch, ob das für Sie passt).",
    "PDE5": "Medikamentengruppe, die Lungengefäße entspannen kann (z. B. Sildenafil/Tadalafil).",
}



# ---------------------------------------------------------------------------
# Vertikale Verfeinerung: Symptom-Gewichtung (Sub-Layer)
# ---------------------------------------------------------------------------

_add(
    "PX_SYMPTOM_PROFILE_LOW",
    "Symptomprofil: eher milde Beschwerden",
    [
        "Ihre Angaben sprechen eher für milde Einschränkungen im Alltag. Wichtig ist trotzdem, Veränderungen früh zu bemerken und nicht nur auf einzelne Messwerte zu schauen.",
        "Die Belastbarkeit wirkt insgesamt eher stabil. Entscheidend ist, ob sich Luftnot oder Leistungsfähigkeit im Verlauf verändern.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_MODERATE",
    "Symptomprofil: mittlere Einschränkungen",
    [
        "Ihre Beschwerden wirken im Alltag spürbar. Wir richten die nächsten Schritte deshalb nicht nur nach Zahlen aus, sondern auch nach dem, was Sie im täglichen Leben belastet.",
        "Bei mittleren Beschwerden ist oft die Kombination aus Messwerten, Belastbarkeit und Verlauf entscheidend. Genau darauf stützen wir die Planung der Kontrollen und Therapie.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_HIGH",
    "Symptomprofil: deutliche Einschränkungen",
    [
        "Sie berichten über deutliche Einschränkungen. Dann ist besonders wichtig, dass wir nicht nur die Messwerte betrachten, sondern gezielt klären, was Ihre Beschwerden antreibt und wie wir die Situation rasch stabilisieren.",
        "Wenn Alltagstätigkeiten deutlich schwerfallen, hat das für die Therapieplanung ein hohes Gewicht. Wir besprechen deshalb engmaschig, welche Schritte am meisten helfen können.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_SYNCOPE",
    "Symptomprofil: Synkope als Warnsignal",
    [
        "Ohnmacht oder Beinahe Ohnmacht ist bei Lungengefäßerkrankungen ein wichtiges Warnsignal. Bitte melden Sie solche Episoden immer zeitnah, auch wenn einzelne Werte auf den ersten Blick nicht dramatisch wirken.",
        "Synkopen sind ein ernstes Signal, weil kurzfristig weniger Blut im Kreislauf ankommen kann. Das beeinflusst, wie wir Risiko und Therapie einschätzen.",
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
    ],
)

_add(
    "PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS",
    "Diskrepanz: eher niedriger Druck, aber starke Beschwerden",
    [
        "Starke Beschwerden können auch auftreten, wenn die Druckwerte nur moderat sind. Gründe können zum Beispiel eine eingeschränkte Pumpleistung, Rückstau, eine Lungenerkrankung, Blutarmut oder ein Zusammenspiel mehrerer Faktoren sein. Deshalb betrachten wir immer das Gesamtbild.",
        "Wenn Symptome und Druckwerte nicht zusammenpassen, ist das kein Widerspruch. Dann prüfen wir gezielt andere Ursachen, die die Belastbarkeit im Alltag beeinflussen.",
    ],
)

_add(
    "PX_DISCORDANCE_ECHO_OK_CATH_HIGH",
    "Diskrepanz: Echo wirkt beruhigend, Katheter zeigt hohe Werte",
    [
        "Das Echo kann manchmal unauffällig wirken, obwohl der Herzkatheter erhöhte Druckwerte zeigt. Das liegt daran, dass Echo Werte indirekt schätzt und nicht immer jede Konstellation sicher abbilden kann. Für die Einordnung ist der Katheter dann besonders wichtig.",
        "Wenn Echo und Katheter unterschiedliche Signale geben, orientieren wir uns an den zuverlässigsten Messungen und schauen zusätzlich auf Verlauf und Beschwerden.",
    ],
)
