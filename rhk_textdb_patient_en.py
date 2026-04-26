#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patient text blocks (EN) – varied, patient-friendly, print-ready.

Goal:
- The patient report should **complement the clinical physician report** in plain language.
- Medical jargon is avoided or **briefly explained**.
- Key measurements may optionally be mentioned for orientation (with classification "normal/elevated"),
  without turning the report into a wall of numbers.

Concept:
- PATIENT_BLOCKS: building blocks with multiple phrasing variants
- PATIENT_BUNDLES: mapping of rule-engine bundles (Kxx) → typical block sets
- PATIENT_MODULE_SUMMARY: patient-friendly brief descriptions of P-modules (P01–P25)
- PATIENT_GLOSSARY: short term explanations (for the printed report)
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

    # If a block is defined multiple times, merge variants instead of overwriting.
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
# Basic blocks
# ---------------------------------------------------------------------------

_add(
    "PX_INTRO",
    "Introduction",
    [
        "{salutation}\n\nWe performed a heart catheter test on you. During this procedure, we measure pressure values and blood flow in the heart and lungs.",
        "{salutation}\n\nHere is a plain-language summary of your heart catheter test. During this examination, we measure how blood flows through the heart and lungs and whether there are signs of elevated pressure.",
        "{salutation}\n\nWe would like to explain the results of your heart catheter test in simple terms. This test helps us better understand the causes of shortness of breath and reduced exercise tolerance.",
        "{salutation}\n\nBelow we summarize the results of your heart catheter test. Our goal is to explain the findings so that you are well informed for your next appointments.",
        "{salutation}\n\nDuring the heart catheter test, we measured how your blood flows through the heart and lungs. This report is designed to help you better understand the results.",
        "{salutation}\n\nThis summary explains the results of your heart catheter test in plain language. It focuses primarily on pressure values and blood flow in the lung vessels.",
    ],
)

_add(
    "PX_NO_PH",
    "No pulmonary hypertension at rest",
    [
        "At rest, the measurements show **no signs** of elevated pressure in the blood vessels of the lungs.",
        "The pressure values in the lung blood vessels are **not elevated at rest**. This is a reassuring finding.",
        "There is **no pulmonary hypertension at rest**. This means the pressure values in the lung vessels are within the normal range.",
        "The resting measurements show **no elevated pressure values** in the lung vessels. This is good news to start with.",
        "The pressure in the lung vessels is **normal at rest**. The right side of the heart is working under normal conditions.",
        "A normal resting pressure is a clearly reassuring finding. Depending on your symptoms we sometimes also look at how the circulation behaves during exercise — not because we expect problems, but to be thorough.",
    ],
)


# ---------------------------------------------------------------------------
# Patient report archetypes (H1...H6)
#
# Note:
# - These blocks shift the *focus* (emphasis), they are not diagnostic.
# - They are only used when `derived.p_archetype_id` is set.
# - Fallback always remains the standard text.
# ---------------------------------------------------------------------------

_add(
    "PX_ARCH_H1_FOCUS_MEASURED",
    "Archetype H1: no PH at rest, but risk/pre-existing condition – focus on measurement",
    [
        "Even though the values are normal at rest, this does not automatically mean there is nothing to watch for. With certain pre-existing conditions, it can be important to monitor trends and how things behave under exertion.",
        "A normal result at rest is a good sign in your situation, but it does not replace follow-up monitoring. Some changes show up first during physical activity or over time.",
        "The measured values at rest are within the normal range. That is encouraging. Nevertheless, given your medical history, we recommend regular check-ups so that we can catch any changes early.",
        "At rest, the pressure values are unremarkable. With pre-existing conditions that carry an increased risk, we pay especially close attention to the trend over time and to how things behave during exertion.",
        "The resting measurements show no abnormalities. With certain underlying conditions, however, changes can develop gradually. That is why we plan targeted follow-up evaluations.",
        "Normal pressures today do not rule out that other parts of the picture — oxygen levels, symptoms, or the response to exercise — still deserve attention. We look at the whole person, not just one number.",
    ],
)

_add(
    "PX_ARCH_H1_FOCUS_MEANING",
    "Archetype H1: no PH at rest, but risk/pre-existing condition – focus on meaning",
    [
        "The goal now is primarily to detect changes early. What matters most are symptoms, exercise tolerance, and follow-up tests — not just a single measurement at one point in time.",
        "In situations like this, the combination of symptoms, trends, and additional tests is often decisive. That way we can act promptly if something changes.",
        "Even though everything looks normal today, we will keep a close eye on your situation. Early detection means early action.",
        "A normal result today is a good starting point. We plan check-ups so that we can be confident going forward that nothing has changed.",
        "What matters is not just today's value, but the trend over time. Together, we watch whether symptoms or exercise tolerance change.",
        "A single reassuring measurement is a snapshot, not a guarantee. That is why regular follow-up is so valuable — it lets us catch shifts early and react calmly.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEASURED",
    "Archetype H2: borderline values / early PH – focus on measurement",
    [
        "Some values are in a borderline range. This could be a very early stage or a temporary fluctuation. That is why the trend is often more important than a single snapshot.",
        "The measurements are near the threshold. That alone does not tell us how stable the situation will remain. The trend, together with your symptoms, is what matters most.",
        "Some values are just above or at the boundary of what is considered abnormal. In such cases, it is especially important to monitor the trend and plan a follow-up measurement.",
        "The pressure values are in a range that is not clearly normal, but also not clearly elevated. A single measurement is often not enough for a definitive classification.",
        "The results show borderline values. This does not necessarily mean anything threatening, but it does require careful monitoring to assess how things develop.",
        "Borderline numbers sit in the grey zone between 'clearly normal' and 'clearly abnormal'. The point of following them closely is to act early if the picture shifts — and to avoid over-treating if it does not.",
    ],
)

_add(
    "PX_ARCH_H2_FOCUS_MEANING",
    "Archetype H2: borderline values / early PH – focus on meaning",
    [
        "At an early stage, the focus is often on properly classifying the causes and monitoring the trend. Any treatment is always weighed against its benefits and risks.",
        "With borderline findings, it is especially important to recognize trends: Are values or symptoms getting worse, staying stable, or improving? That is how we determine the next steps.",
        "Borderline values mean we stay especially vigilant. In many cases, careful observation is sufficient before treatment steps are initiated.",
        "The significance of borderline values can only be properly assessed over time. That is why careful follow-up monitoring is the priority right now.",
        "In a situation like this, we first determine whether the values are moving in a particular direction or staying stable. That forms the basis for all further decisions.",
        "Borderline findings are not a reason to worry, but they are a reason to stay observant. Small regular check-ins are far more useful than one big evaluation far down the line.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEASURED",
    "Archetype H3: established precapillary PH – focus on measurement",
    [
        "The values indicate that the lung vessels are offering increased resistance. As a result, the right side of the heart has to work harder to pump blood through.",
        "The main finding is increased strain on the right heart due to resistance in the lung vessels. That explains why exercise capacity and fitness level are so important to monitor.",
        "The measurements show that the blood vessels in the lungs are narrowed or stiffened. The right heart must work harder to push blood through the lungs.",
        "The elevated resistance in the lung vessels places measurably greater strain on the right heart. This test helps us assess the severity precisely.",
        "The measurement confirms a clear pressure elevation in the lung vessels. This tells us how much the right side of the heart is currently being taxed.",
        "The result does not tell us how long the pressure elevation has been there or how fast it is progressing — that is why we combine it with your symptoms, your exercise capacity, and imaging to get a complete picture.",
    ],
)

_add(
    "PX_ARCH_H3_FOCUS_MEANING",
    "Archetype H3: established precapillary PH – focus on meaning",
    [
        "The focus is now less on the question of *whether* pulmonary hypertension is present, and more on how well the right heart is coping and what treatment goals we pursue together.",
        "What matters is reducing the strain on the right heart and stabilizing or improving your exercise capacity. Regular check-ups help us detect treatment effects early.",
        "The priority now is finding the right treatment and monitoring how well it works. Your exercise capacity in daily life is an important measure of progress.",
        "Together we set treatment goals and regularly check whether the therapy is making a real difference in your daily life. Relieving the right heart as much as possible is the central aim.",
        "In this situation, targeted treatments are available. Which one is best suited for you depends on the exact cause and how you are feeling.",
        "Modern therapies for pulmonary hypertension have improved substantially. The goal is not just to lower numbers, but to give you back daily capacity and confidence. We pick the path that fits your life, not only your chart.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEASURED",
    "Archetype H4: postcapillary / combined PH – focus on measurement",
    [
        "There are signs that the pressure rise is (also) caused by back-pressure from the left side of the heart. This changes which treatment approaches take priority.",
        "The pattern suggests that the left side of the heart plays an important role. Assessing left heart function and fluid balance is therefore particularly relevant.",
        "The measurements suggest that the elevated pressure in the lungs is at least partly caused by the left side of the heart. This is a common pattern that we can treat in a targeted way.",
        "We see in the measurements that pressure from the left side of the heart is being transmitted to the lung vessels. This is an important clue for choosing the right therapy.",
        "The catheter measurement shows that the left side of the heart plays a significant role in the pressure elevation. This influences which treatment strategy makes the most sense.",
        "When the left heart drives most of the problem, treating the lung vessels alone would miss the point. The main target is therefore to support and unload the left heart — that is often where we can achieve the biggest benefit for you.",
    ],
)

_add(
    "PX_ARCH_H4_FOCUS_MEANING",
    "Archetype H4: postcapillary / combined PH – focus on meaning",
    [
        "In situations like this, treating the left heart and accompanying conditions is often the key. Specific pulmonary hypertension therapy is not automatically the first step.",
        "The most important lever is often to reduce the back-pressure and support left heart function as well as possible. Which medications are appropriate is decided on an individual basis.",
        "When the left side of the heart is involved, the priority is optimizing heart treatment and fluid balance. This can often noticeably relieve symptoms.",
        "Treatment here focuses primarily on the left side of the heart and accompanying conditions. Often, good adjustment of existing medications already helps noticeably.",
        "In this pattern, close collaboration between different medical specialties is especially important. That way we can address all causes and coordinate treatment effectively.",
        "When both the left heart and the lung vessels are involved, the sequence of treatment steps matters. We usually start with what is most likely to bring relief quickly and add other measures in a planned way, not all at once.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEASURED",
    "Archetype H5: thromboembolic pattern / CTEPH – focus on measurement",
    [
        "There are signs that older blood clots in the lung vessels could (also) be playing a role. In that case, the focus is particularly on the mechanics of blood flow through the lungs.",
        "With this pattern, it is important to check whether blockages from older clots are present. This can often be evaluated very well with targeted imaging.",
        "The measurements fit a pattern where older blood clots in the lung vessels may be obstructing blood flow. Targeted imaging can help clarify this further.",
        "The pressure distribution in the measurements suggests that mechanical obstructions in the lung vessels could be playing a role. This can be checked well with specialized tests.",
        "We see signs that point toward a circulation problem in the lungs. Whether older blood clots are the cause can be specifically investigated with additional imaging.",
        "The picture is suggestive but not yet final. A targeted scan — often a ventilation/perfusion scan or pulmonary angiography — helps us separate older clot-related disease from other causes of pulmonary hypertension.",
    ],
)

_add(
    "PX_ARCH_H5_FOCUS_MEANING",
    "Archetype H5: thromboembolic pattern / CTEPH – focus on meaning",
    [
        "If the suspicion is confirmed, there are special treatment options beyond medication that can directly improve blood flow in the lungs. Which one is right depends on the exact distribution of the blockages.",
        "In this context, certain tests such as the ventilation/perfusion scan are particularly helpful. They show how evenly the lungs are supplied with blood.",
        "If older blood clots are the cause, there are now well-established treatment options. These include medications as well as specialized procedures that can restore blood flow.",
        "A thorough evaluation is especially important here because targeted therapies are available for this form of pulmonary hypertension that can be very effective.",
        "If the suspicion is confirmed, the specialized team will discuss which treatment is best suited. The options range from medications to specialized procedures.",
        "For this specific form of pulmonary hypertension there are, in selected cases, even procedures that can reopen affected vessels or directly address the underlying cause. Not every patient is a candidate for every option — that is exactly what the specialist discussion is for.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEASURED",
    "Archetype H6: right heart in focus with moderate pressure – focus on measurement",
    [
        "Although the pressure values are not extremely high, markers of the right heart show significant strain. This can explain why symptoms may still be prominent.",
        "Sometimes pressure alone does not reflect the full picture. Signs of right heart strain or back-pressure can then be especially telling.",
        "The pressure values are only moderately elevated, but the right heart still shows signs of significant strain. We take this seriously and monitor it closely.",
        "Even with moderate pressure values, the right heart can be noticeably strained. The measurements show that we should look more closely here.",
        "Pressure alone does not tell the whole story. The signs of right heart strain complete the picture and help us assess the situation realistically.",
        "How the right heart copes with the increased workload often matters more than the absolute pressure number. Two patients with similar pressures can need very different treatments depending on right heart function.",
    ],
)

_add(
    "PX_ARCH_H6_FOCUS_MEANING",
    "Archetype H6: right heart in focus with moderate pressure – focus on meaning",
    [
        "What matters most is looking at function, exercise capacity, and the trend over time. Treatment decisions often depend on how well the right heart can compensate.",
        "In such cases, we pay especially close attention to the trend, exercise capacity, and signs of back-pressure. This helps us tailor treatment to what is most relevant for your daily life.",
        "In this situation, we focus particularly on the performance of the right heart. Treatment is guided by how well the heart is coping with the strain.",
        "The condition of the right heart largely determines how you feel in daily life. That is why follow-up monitoring and targeted treatment are the priorities.",
        "We base our treatment planning primarily on how the right heart is functioning and how fit you feel. That gives us the best guidance for the next steps.",
        "When right heart function is the leading concern, the goal is to reduce its workload and give it room to recover. That can involve fine-tuning medications, managing fluids, and sometimes adding targeted pulmonary vasodilators.",
    ],
)


# ---------------------------------------------------------------------------
# Vertical refinement: symptom weighting, discordance explanations, trend types
# ---------------------------------------------------------------------------

_add(
    "PX_SYMPTOMS_LOW",
    "Symptoms: rather mild",
    [
        "Your symptoms appear rather mild. That is a good sign. Still, we monitor the trend because lung vessel conditions can sometimes change gradually.",
        "Your current exercise capacity appears fairly good. For classification purposes, it is then especially important whether anything changes over time and how you tolerate exertion in daily life.",
        "The fact that your symptoms are currently minor is encouraging. We use this as a good baseline for future check-ups.",
        "Mild symptoms mean you are not significantly limited in daily life. Still, we keep the situation in view because changes sometimes develop slowly.",
        "Your symptoms are mild at present, which is reassuring for now. Please pay attention to any changes in your exercise tolerance and mention them at your next appointment.",
        "Having few symptoms despite abnormal measurements is common — the body often compensates well for a long time before anything becomes noticeable. That is exactly why regular check-ups remain important, even in good phases.",
    ],
)

_add(
    "PX_SYMPTOMS_MODERATE",
    "Symptoms: moderate",
    [
        "Your symptoms are noticeable but not at their worst. For treatment planning, it is important whether you remain stable in daily life or whether your exercise tolerance continues to decrease.",
        "The symptoms are consistent with a moderate limitation. We use measurements and trends together to decide whether and when adjustments are needed.",
        "Your symptoms are in the moderate range. This means you notice the limitation in daily life but can still manage many activities well. The key question is whether this remains stable.",
        "With moderate symptoms, we look closely at which activities are difficult for you. This helps us tailor treatment specifically to your needs.",
        "Your symptoms are noticeably present but not at their strongest level. This gives us the opportunity to aim for improvement with targeted measures.",
        "Moderate symptoms usually still leave meaningful room for improvement — targeted medication, structured exercise, and sometimes small adjustments to daily routines can together add up to a noticeable difference.",
    ],
)

_add(
    "PX_SYMPTOMS_HIGH",
    "Symptoms: significant",
    [
        "Your symptoms appear significant. In such situations, the clinical picture often carries as much weight as individual measurements. We plan check-ups and treatment to keep you safe in daily life.",
        "With significantly reduced exercise capacity, it is especially important to take warning signs seriously and discuss changes early. That way, we can intervene in time.",
        "Your symptoms noticeably affect daily life. We take this very seriously and focus treatment on giving you back as much quality of life as possible.",
        "When everyday activities become difficult, that takes the highest priority in treatment planning. We are working to stabilize the situation as quickly as possible.",
        "Significant symptoms mean we look beyond just the numbers and put your quality of life at the center. We will discuss what can help you the most.",
        "When symptoms are this prominent, we often do not want to wait months — we aim to build an effective treatment more quickly and schedule check-ins at closer intervals.",
    ],
)

_add(
    "PX_SYMPTOMS_SYNCOPE",
    "Symptoms: syncope",
    [
        "Fainting or near-fainting is an important warning sign in lung vessel conditions. It does not automatically mean you are in immediate danger, but it should be investigated promptly and thoroughly.",
        "When fainting or near-fainting occurs, it may indicate that the heart and circulation are reaching their limits during exertion. Please always report new episodes promptly.",
        "Dizzy spells or brief loss of consciousness are a serious signal. We investigate this specifically to ensure your safety in daily life.",
        "Fainting episodes can occur in pulmonary hypertension when the heart temporarily cannot pump enough blood into the circulation. This requires timely evaluation and possible treatment adjustment.",
        "If you experience dizzy spells, blackouts, or loss of consciousness, please always report them immediately. These symptoms carry significant weight in our treatment planning.",
        "Even a single fainting episode — even if everything ended well — is a thread we follow. It can change how urgent our risk assessment is, which therapy we choose, and how soon we want to see you again.",
    ],
)

_add(
    "PX_DISCORDANCE_HIGH_MPAP_LOW_BNP",
    "Discordance: high pressure but low BNP",
    [
        "Sometimes the pressure values are significantly elevated while the blood marker BNP or NT-proBNP remains rather low. This can happen when the right heart is still compensating well or when the blood marker is influenced by other factors. What matters then is the overall picture including symptoms, exercise capacity, and trend.",
        "A low BNP or NT-proBNP level does not rule out a significant pressure elevation. Conversely, high pressure does not always mean the heart is already overloaded. That is why we look at measurements, symptoms, and trends together.",
    ],
)

_add(
    "PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS",
    "Discordance: rather low pressure but significant symptoms",
    [
        "It can happen that pressure values at rest are only mildly elevated or unremarkable, while symptoms are significant. Often, exertion, accompanying lung or left heart conditions, anemia, or physical fitness level play a role. That is why the evaluation is often broader than just the pressure values.",
        "When symptoms are more pronounced than a single number would suggest, we look especially at exercise tests, lung function, imaging, and the trend. This usually clarifies which factor has the greatest impact on daily life.",
    ],
)

_add(
    "PX_DISCORDANCE_ECHO_GOOD_CATH_HIGH",
    "Discordance: echocardiogram looks normal, catheter shows higher values",
    [
        "Ultrasound (echo) and the heart catheter measure different things. The echo estimates pressure values indirectly and can appear normal even when the catheter shows elevated pressure. For pressure measurement, the catheter is the more reliable test.",
        "When echo and catheter do not match perfectly, that is not unusual. We then use the catheter as the reference and additionally look at how the right heart functions on echo and how exercise capacity develops.",
        "The echo is a good tool for assessing heart function, but for exact pressure measurement the heart catheter is more reliable. The seemingly contradictory findings complement each other in the overall assessment.",
        "A calm-looking echo does not mean it was wrong — it shows that heart function is preserved. The catheter adds information about blood flow through the lungs that ultrasound can only capture indirectly.",
        "Mild to moderate pressure elevations are often missed by echo because the acoustic window is limited and the estimate depends on jet quality. The catheter fills that gap with a direct measurement.",
        "For the path forward this means: we rely on the catheter values and use the echo mainly to track changes in heart function over time. The two examinations complement each other in a meaningful way.",
    ],
)

_add(
    "PX_TREND_SUBTYPE_PRESSURE_BETTER_PVR_WORSE",
    "Trend type: pressure better, resistance worse",
    [
        "Some values are better while others are less favorable. When pressure drops slightly but resistance rises, this can be due to measurement variability, fluid balance, or altered blood flow through the lungs. What matters is which change best matches your symptoms.",
        "When pressure and resistance point in different directions, we pay special attention to pumping function, back-pressure, and exercise capacity. From that, we determine which part is clinically decisive.",
        "Divergent changes in pressure and resistance are not uncommon. For treatment decisions, we focus on the value that best matches your symptoms and the overall picture.",
        "What ultimately matters is not a single number but the impression in daily life: if you feel equally well or more able to exert yourself and no warning signs appear, that is an important, reassuring signal in this constellation.",
        "Pressure and resistance are not rigidly linked — they are shaped by flow, filling state, and the condition of the lung vessel bed. A divergence is therefore often explainable and not automatically a setback.",
        "For further planning, a follow-up measurement under identical conditions together with your feedback on exercise capacity helps. Only in combination does it become clear whether the trend is real or reflects measurement variability.",
    ],
)

_add(
    "PX_TREND_SUBTYPE_EFFECT_UNCLEAR",
    "Trend type: treatment effect unclear",
    [
        "When individual values change only slightly or point in different directions, the treatment effect may still be unclear. A follow-up with the same measurement methods and a look at exercise capacity and symptoms often helps.",
        "Not every change is immediately clear-cut. What matters is whether you feel more stable in daily life and whether warning signs appear. We discuss this in detail during follow-up.",
        "An unclear treatment effect does not mean that the therapy has failed. Sometimes it simply takes more time, or a follow-up measurement under identical conditions, to judge the effect correctly.",
        "Early follow-up checks often do not yet show a clear signal — medications can take weeks, sometimes months, to develop their full effect. Patience and consistent intake are what matter most right now.",
        "We place great value on your own perception: do you climb stairs more easily? Do you sleep more quietly? Can you sustain longer distances? Such everyday cues are sometimes more meaningful than a single number.",
        "An unclear interim result is a reason for careful observation, not for worry. We plan a follow-up under identical conditions and then decide together whether the therapy should be adjusted.",
    ],
)

_add(
    "PX_INCOMPLETE",
    "Classification not yet clear",
    [
        "The measurements are **not yet complete** or fall in a range that cannot be clearly classified. This is not unusual — it typically means additional information is needed.",
        "At present, the measurements do **not allow a definitive classification**. In such situations, your symptoms and additional tests are especially important.",
        "Some values are still missing or fall in a borderline range. This can happen and does not mean that anything has been overlooked. We will complete the missing information to enable a reliable classification.",
        "For a complete assessment we still need additional information. Once it is available, we can classify your situation more clearly and plan the next steps.",
        "A result that cannot yet be clearly categorized is a common situation in this field — the human body does not always fit neatly into textbook categories. Targeted additional testing usually provides the clarity we need.",
        "Please understand that it sometimes takes more than one visit to arrive at a complete picture. The measurements so far are valuable building blocks; we just need a few more pieces to put the puzzle together reliably.",
    ],
)

_add(
    "PX_WHAT_IS_PH",
    "What does pulmonary hypertension mean?",
    [
        "When the blood pressure in the lung vessels is elevated, the right side of the heart has to **work harder**. This can explain shortness of breath, fatigue, or fluid retention.",
        "Elevated pressure in the lung blood vessels can have **various causes**. What matters is *where* the pressure rise originates — for example, in the lung vessels themselves, from the left side of the heart, or from older blood clots.",
        "Pulmonary hypertension is **not a single disease**. The cause can vary widely. That is why precise classification is important so that we can choose the right treatment.",
        "Important for the classification: Not every pressure elevation means the same thing. Only the interplay of measurements, symptoms, and accompanying conditions reveals the most likely cause.",
        "In pulmonary hypertension, the blood vessels in the lungs are narrowed or stiffened. The right heart must pump harder to push blood through the lungs. That is why symptoms like shortness of breath and exhaustion can occur.",
        "There are different forms of pulmonary hypertension. Some arise from the lung vessels themselves, others from diseases of the left heart or the lungs. The precise distinction is important because the treatment depends on it.",
        "Put simply: with every heartbeat, blood must flow through the lungs. When the vessels there become narrower or stiffer, the pressure rises and the right heart is put under greater strain. The goal of treatment is to reduce this strain.",
        "Pulmonary hypertension means the right side of the heart has to work against increased resistance. This can manifest as shortness of breath, rapid fatigue, or fluid retention. Identifying the cause is the first step toward the right therapy.",
    ],
)


_add(
    "PX_HEMO_EXPLAIN",
    title="Brief explanation: what the key numbers mean",
    templates=[
        "The key measurements can be understood as follows: "
        "**mPAP** describes the average pressure in the lung vessels. "
        "**PAWP** indicates whether blood is \"backing up\" in front of the left side of the heart. "
        "**PVR** describes the resistance in the lung vessels (elevated, for example, when vessels are narrowed or stiffened). "
        "**CI** describes the pumping capacity relative to body size. "
        "**RAP** indicates back-pressure in the body's circulation. "
        "What always matters is the combination of these values — not any single number alone.",
        "For orientation: mPAP = pressure in the lungs, PAWP = back-pressure before the left heart, "
        "PVR = resistance in the lung vessels, CI = pumping capacity, RAP = back-pressure in the body. "
        "The pattern of these values tells us which causes are more likely and which next steps make sense.",
        "During the heart catheter test, several values are measured. "
        "The **lung pressure** shows how hard the right side of the heart has to work. "
        "The **filling pressure** on the left helps determine whether the left side of the heart is involved. "
        "The **vascular resistance** shows how narrow or stiff the lung vessels are. "
        "The **pumping capacity** shows whether the heart is delivering enough blood to the body. "
        "Together, these values form a complete picture.",
        "You will find some abbreviations in your report. "
        "**mPAP** stands for the average pressure in the lungs. "
        "**PAWP** shows whether blood is backing up before the left heart. "
        "**PVR** measures the resistance in the lung vessels. "
        "**CI** indicates how well the heart is pumping. "
        "No single number tells the whole story — only the overall pattern is meaningful.",
        "Think of these numbers as different vantage points on the same circulatory system: "
        "pressure (how hard the right heart pushes), resistance (how open the lung vessels are), flow (how much blood actually moves) and back-pressure (whether the left heart is contributing). "
        "Taken together, they tell us which levers will help you most.",
        "We know these abbreviations can feel overwhelming at first. "
        "You do not need to memorize them — our job is to translate the values into a clear picture of your situation and the most sensible next steps for you.",
    ],
)



_add(
    "PX_VOLUME_CHALLENGE",
    "Volume challenge",
    [
        "Sometimes during the procedure we deliberately give a defined amount of fluid through the vein. This lets us check whether the pressure on the left side of the heart rises noticeably. It can help us better assess whether the left heart is contributing to the problem.",
        "During a volume challenge, fluid is given in a controlled manner. We then observe whether the filling pressure in the left heart rises significantly. This is a sign that under higher blood volume, back-pressure into the lungs occurs more easily.",
        "The volume test simulates a more demanding everyday situation — such as after a large meal or during exertion — in which the heart has to handle more blood. This reveals weaknesses that might remain hidden at rest.",
        "By giving a controlled amount of fluid, we unmask a left-sided contribution that normal resting values may not show. It is an established, safe method that significantly sharpens the diagnosis in selected cases.",
        "Not every patient receives this test — we use it when resting values are borderline and we want to know whether the left heart plays a role under greater load. The result helps us choose the right treatment strategy.",
        "You may notice during the test that you feel slightly fuller or have a brief urge to urinate afterwards. This is harmless and a normal reaction to the added fluid.",
    ],
)

_add(
    "PX_VASOREACTIVITY",
    "Vasoreactivity testing",
    [
        "During the vasoreactivity test, a short-acting test medication is used. This lets us check whether the lung vessels relax significantly in response. In selected cases, this can influence treatment planning.",
        "In this additional test, we observe whether the lung vessels respond noticeably to a briefly administered medication. A significant response can be therapeutically important.",
        "A clearly positive vasoreactivity response is rare, but when it occurs it opens up treatment options that are not suitable for most patients. That is why this targeted test is worthwhile in selected situations.",
        "The test substance works only for a few minutes and leaves the body quickly. You may briefly feel a slight change — a light-headedness or mild headache — which subsides on its own.",
        "What we are really checking is the flexibility of your lung vessels: can they still relax? The answer gives us a clue about how the vessels will respond to certain long-term medications.",
        "Even a test that does not show a marked response provides valuable information — it helps us narrow down which therapy groups are most promising for you and which are unlikely to bring benefit.",
    ],
)

_add(
    "PX_INTERPRETATION",
    "How do we interpret this?",
    [
        "The measurements are an important piece of the puzzle. For the overall assessment, we also look at imaging, heart ultrasound, lung function, and your symptoms.",
        "The key is looking at the whole picture: measurements, symptoms, and additional tests belong together. Only from this combination do we derive the most appropriate course of action.",
        "In addition to the numbers, we consider how well you manage daily activities and how the findings develop over time. This leads to an assessment that better fits your personal situation.",
        "A single measurement is always just one piece of the puzzle. Together with your symptoms, the heart ultrasound, and your medical history, a complete picture emerges on which we base the therapy.",
        "For the assessment, we do not look at the catheter measurement alone. Lab values, imaging, lung function, and above all your personal exercise capacity all factor into the evaluation.",
        "We place the test results in the context of everything we know about your health. Only in this way can we arrive at an assessment that truly fits your situation.",
    ],
)


# ---------------------------------------------------------------------------
# Hemodynamic classification (rest)
# ---------------------------------------------------------------------------

_add(
    "PX_PRECAP_MILD",
    "Precapillary pressure elevation – rather mild",
    [
        "The measurements suggest a **mild pressure elevation** in the lung blood vessels. This indicates that the cause may lie in the lung vessels or in the lungs themselves.",
        "There are signs of a **mild pressure elevation** in the lung blood vessels. This type of change often arises from changes in the lung vessels or from a lung condition.",
        "The pressure in the lung vessels is **mildly elevated**. The cause appears to lie in the lung vessels themselves rather than in the left side of the heart. We will investigate the exact cause further.",
        "The measurement shows a **mild pressure elevation** in the lung vessels. This is a finding we will monitor and investigate further, but it does not necessarily require immediate treatment.",
        "There is a **mild pressure elevation** in the lung blood vessels. The left side of the heart does not appear to be the main cause. Additional tests will help determine the exact classification.",
        "Even a mild elevation deserves a careful look. It does not automatically require strong medication, but it does ask us to understand why it is there — because the right treatment depends on the right diagnosis.",
    ],
)

_add(
    "PX_PRECAP_MOD",
    "Precapillary pressure elevation – moderate",
    [
        "The measurements suggest a **pressure elevation** that arises in the lung blood vessels or in the lungs themselves.",
        "The test shows signs of pulmonary hypertension where the cause lies **upstream** of the left side of the heart — that is, in the lungs or the lung vessels.",
        "There is a **moderate pressure elevation** in the lung vessels. The cause appears to lie in the lung vessels themselves or in the lungs.",
        "The measurement confirms **moderate pulmonary hypertension**. The left side of the heart does not appear to be the main cause. A structured investigation and treatment plan are now important.",
        "The pressure in the lung vessels is **clearly above the normal range**. This pattern suggests that the change originates in the lung vessels themselves. A systematic evaluation helps find the best treatment.",
        "A moderate elevation is the range where modern pulmonary hypertension therapies often make the biggest difference. Precise classification now pays off in clearer, more targeted treatment choices later.",
    ],
)

_add(
    "PX_PRECAP_SEV",
    "Precapillary pressure elevation – significant",
    [
        "The measurements suggest a **significant pressure elevation** in the lung blood vessels. This should be further evaluated promptly by a specialized team.",
        "There is evidence of **severe pressure elevation** in the lung blood vessels. A structured investigation and treatment plan are important.",
        "The pressure values in the lung vessels are **significantly elevated**. This means the right heart has to work considerably harder. Prompt initiation of treatment and specialized care are advisable.",
        "There is a **severe pressure elevation** in the lung vessels. The cause does not lie in the left side of the heart but in the lung vessels themselves. Targeted treatment options are available at a specialized center.",
        "The measurement shows a **severe pressure elevation** in the lung blood vessels. This requires rapid and targeted investigation of the cause and initiation of appropriate treatment.",
        "At this level, we typically begin combination therapy — sometimes with more than one medication at once — and review effectiveness closely. The aim is to relieve the right heart as quickly and safely as possible.",
    ],
)

_add(
    "PX_POSTCAP",
    "Pressure elevation due to the left side of the heart",
    [
        "The measurements suggest that the pressure rise is primarily caused by the **left side of the heart**. This can lead to back-pressure toward the lungs.",
        "The measurements fit a situation where the **left side of the heart** plays an important role. This can cause pressure to be transmitted toward the lung vessels.",
        "The test shows that the pressure elevation in the lungs is primarily caused by **back-pressure from the left side of the heart**. Treatment therefore focuses primarily on the left heart.",
        "The elevated pressure in the lung vessels is mainly caused by the **left side of the heart**. This is a common pattern for which established treatment approaches exist.",
        "The measurement shows a typical pattern: the left side of the heart cannot move blood forward efficiently, and pressure backs up into the lung vessels. Treatment therefore primarily addresses the left side of the heart.",
        "In this setting, classical 'lung hypertension medication' typically is not the right first step. Optimising blood pressure, rhythm control, fluid balance, and other left-heart therapies usually brings the most benefit — sometimes surprisingly quickly.",
    ],
)

_add(
    "PX_CPCPH",
    "Combined pressure elevation",
    [
        "The measurements suggest a **mixed pattern**: there are signs of pressure from the left side of the heart and additional signs of narrowing in the lung vessels.",
        "The findings fit a **combined situation**: pressure transmitted from the left side of the heart and, at the same time, additional strain on the lung vessels.",
        "This is a **combined pressure elevation**: both the left side of the heart and the lung vessels contribute to the elevated pressure. Treatment must therefore address both sides.",
        "The measurement shows a **combined pattern**: on one hand, the left side of the heart transmits pressure to the lungs; on the other, the lung vessels themselves react with additional narrowing. This requires a differentiated approach to treatment.",
        "The pressure elevation has **two components**: strain from the left side of the heart and an independent change in the lung vessels. Both must be considered in treatment.",
        "A mixed pattern like this means that a single therapy is rarely enough. We usually address the left heart first and then cautiously add treatments aimed at the lung vessels — always watching carefully how you respond.",
    ],
)

# ---------------------------------------------------------------------------
# Hemodynamics during exercise
# ---------------------------------------------------------------------------

_add(
    "PX_EX_LEFT",
    "Abnormal pressure response during exercise – left side of the heart",
    [
        "At rest, the values were not clearly abnormal. However, **during physical exertion**, there is a pressure rise that fits with strain on the left side of the heart.",
        "The measurement during exercise suggests that the left side of the heart comes under greater pressure during physical activity. This can explain shortness of breath during exertion.",
        "Not every heart condition is visible at rest — that is exactly why we test during exertion. In your case, the exercise data show that the left heart does not adapt optimally under load.",
        "A normal resting measurement does not rule out a problem that only appears during exertion. The exercise test uncovered exactly such a pattern for you, which helps explain your symptoms.",
        "Under exertion, the heart has to handle more blood flow in less time. That is when an impaired adaptation of the left heart becomes apparent — which is valuable information for targeted treatment.",
        "The good news: because we detected this pattern, we can now address it specifically. Many causes of left-heart exercise intolerance respond well to medication, training, and lifestyle measures.",
    ],
)

_add(
    "PX_EX_PVASC",
    "Abnormal pressure response during exercise – lung vessels",
    [
        "At rest, the values were not clearly abnormal. However, **during physical exertion**, there is a pattern that fits with strain on the lung vessels.",
        "During exercise, the pressure in the lung vessels rises more than expected. This can help detect an early lung vessel condition.",
        "Resting measurements can appear normal while a disease process in the lung vessels is already beginning. The exercise test made this early change visible, which gives us a head start on treatment planning.",
        "The exercise measurement helps us recognize a lung vessel condition at an early stage — often before symptoms become severe. Early awareness can meaningfully influence the course of the condition.",
        "An abnormal pressure rise in the lung vessels under exertion can explain why you feel more short of breath during activity than the resting findings would suggest. It is a subtle but clinically meaningful signal.",
        "In many cases, this pattern is an early warning sign that allows us to act preventively — through closer monitoring, lifestyle recommendations, and selected medications when appropriate.",
    ],
)

_add(
    "PX_UNCLASSIFIED",
    "Constellation that cannot be clearly categorized",
    [
        "The measured values fall in a range that cannot be clearly assigned to a specific form of pulmonary hypertension. "
        "This does not mean everything remains unclear — it means we carefully consider the overall situation and gather further information if needed.",
        "The pressure values are elevated, but the pattern does not clearly fit into a single category. "
        "We see such constellations regularly, and they require a particularly thorough overall assessment including medical history, imaging, and lab results.",
        "The results show elevated pressure, but the exact cause cannot yet be reliably determined from the catheter measurements alone. "
        "This is no cause for concern — it is a normal step on the way to the right classification.",
        "In your case, the measurement shows a picture that lies between different patterns. "
        "This occurs and requires a step-by-step evaluation to find the right cause and the best path forward.",
        "A pattern that is not immediately clear is not a failure of the examination — it simply tells us that more information is needed to reach a confident conclusion. "
        "We will plan the next steps together so the picture becomes sharper.",
        "Medicine is not always black and white, and pulmonary circulation in particular has many facets. "
        "We take the time to understand your individual pattern rather than forcing it into a category that does not fit.",
    ],
)

_add(
    "PX_HIGH_FLOW",
    "Pressure elevation due to high blood flow",
    [
        "The pressure elevation in your case appears to be related to an **unusually high blood flow**. "
        "This means the lung vessels themselves may not be narrowed, but are being overwhelmed by the volume of blood flowing through them.",
        "When the heart pumps particularly large volumes of blood, the pressure in the lung vessels can rise from this alone. "
        "In such cases, we look for the cause of the increased blood flow — this can be, for example, anemia, an overactive thyroid, or other conditions.",
        "The measurement shows high blood flow through the lung vessels. This likely explains part of the pressure elevation. "
        "Treatment is primarily directed at the cause of the increased blood flow.",
        "The pressure in the lung vessels is elevated, but the resistance is not significantly increased. "
        "This suggests that mainly the volume of blood flowing through is responsible for the pressure readings. We will investigate the underlying cause.",
        "High-flow pressure elevation is an important distinction, because the treatment differs fundamentally from other forms. "
        "We will clarify which underlying trigger — for example thyroid, anemia, or a shunt — is causing the increased flow.",
        "If high blood flow is mainly responsible for the pressure readings, that is good news: "
        "The underlying cause can usually be treated well, and the pressure situation in the lung vessels normalizes accordingly.",
    ],
)

_add(
    "PX_SOTATERCEPT_INFO",
    "New treatment approach: Sotatercept",
    [
        "Your treatment plan mentions a newer medication called **Sotatercept**. "
        "This medication works through a special signaling pathway (BMPR2/activin pathway) and can lower the pressure in the lung vessels and improve exercise capacity in certain forms of pulmonary arterial hypertension.",
        "Sotatercept is a novel treatment approach that works at a different point than previous medications. "
        "It is used as an add-on to existing treatment and is prescribed at specialized PH centers.",
        "In your case, Sotatercept is being discussed as a treatment option. This medication specifically targets changes in the walls of the lung vessels. "
        "It is administered as an injection under the skin and closely monitored.",
        "The medication Sotatercept is a new building block in treatment. "
        "It can help relieve the lung vessels in addition to existing medications. Whether it is suitable in your situation is individually assessed at the PH center.",
        "With Sotatercept, a treatment option is now available that directly addresses the abnormal remodeling of the lung vessels. "
        "Studies show: Many patients become more resilient, and pressure values improve noticeably.",
        "To decide whether Sotatercept is right for you, we need a precise classification of your condition and the therapies already in place. "
        "This is carefully evaluated at the specialized PH center and discussed with you in detail.",
    ],
)

# ---------------------------------------------------------------------------
# Additional findings / cause indicators (cautiously worded)
# ---------------------------------------------------------------------------


_add(
    "PX_GROUP1_HINT",
    title="Possible rarer cause: disease of the lung vessels themselves",
    templates=[
        "In some situations, a disease of the small lung vessels themselves may (also) play a role. "
        "This can occur, for example, in connection with certain autoimmune/rheumatic conditions, rare genetic changes, "
        "or certain infections. "
        "To classify this reliably, specialized lab tests, detailed imaging, and evaluation at a specialized pulmonary hypertension center are often advisable.",
        "If, in addition to other causes, a so-called \"pulmonary arterial\" form is being considered, "
        "targeted additional testing is often recommended (e.g., autoimmune and viral tests, possibly genetic evaluation). "
        "This is primarily aimed at finding the best possible, individually tailored therapy.",
        "The small lung vessels are not directly visible on routine imaging — their condition shows up indirectly, through pressure patterns and targeted lab work. A specialized PH center has the experience and tools to evaluate them reliably.",
        "There are effective therapies specifically for this form of pulmonary hypertension. Whether any of them suits your situation depends on further testing, which is best organized together with a specialized center.",
        "In this form, genetic factors are sometimes involved, although most cases are not hereditary. A careful family history helps us decide whether genetic counselling would be reasonable for you.",
        "Evaluation at a specialized center does not mean your condition is especially severe — it means the diagnosis benefits from particular expertise and from a team that regularly sees this rare constellation.",
    ],
)

_add(
    "PX_GROUP2_HINT",
    "Indication of left heart involvement",
    [
        "Some of the findings suggest that the **left side of the heart** may be involved. This will be further evaluated by cardiology.",
        "There are signs that the left side of the heart may be playing a role. Often, optimization of cardiac treatment is then advisable.",
        "Left heart involvement is by far the most common cause of pulmonary hypertension — and the good news is that many cardiac treatments have a direct effect on lung pressure as well.",
        "When the left side of the heart has difficulty filling or pumping efficiently, blood can back up into the lungs and raise pressure there. The treatment focus shifts toward the underlying cardiac condition.",
        "Further clarification typically involves cardiac imaging, sometimes advanced ultrasound or MRI, to understand which part of the left heart is affected — valves, muscle, or filling pressures.",
        "Even when left heart involvement is confirmed, much can be done: medication, controlled blood pressure, weight and sleep optimization, sometimes cardiac rehabilitation. Each of these can meaningfully improve your daily life.",
    ],
)

_add(
    "PX_GROUP3_HINT",
    "Indication of lung / oxygen involvement",
    [
        "There are signs that a **lung condition** or low oxygen supply may be involved. In that case, lung function testing and imaging are especially important.",
        "Some of the findings may be consistent with lung involvement. In such cases, a pulmonary medicine assessment helps optimize treatment.",
        "When the lungs do not deliver enough oxygen, the lung vessels tighten in response — that is a natural reflex that, over time, can raise lung pressure. Treating the underlying lung problem therefore also helps the lung vessels.",
        "Supplemental oxygen and optimizing lung therapy (inhalers, pulmonary rehab, sometimes sleep-related testing) are usually the most impactful steps here — often with a noticeable effect on breathlessness.",
        "A combination of findings from lung function testing, imaging, and possibly a sleep study gives us the clearest picture. Each piece helps decide which treatment lever has the strongest effect.",
        "Even when lung involvement is the main driver, we do not overlook other factors. The goal is to treat the whole person, not just the dominant diagnosis.",
    ],
)

_add(
    "PX_GROUP4_HINT",
    "Indication of older blood clots",
    [
        "There are signs that could be consistent with **older or chronic blood clots** in the lung vessels. This should be specifically investigated further.",
        "Some of the findings suggest a chronic circulation problem in the lungs, for example from older blood clots. Specialized evaluation is then important.",
        "Chronic clots in the lung vessels are a treatable form of pulmonary hypertension — in selected cases, specialized surgery or catheter-based procedures can substantially improve the condition. That is why targeted evaluation is so important.",
        "To confirm or rule out this cause, we typically use a ventilation-perfusion scan, sometimes combined with CT angiography or pulmonary angiography at a specialized center. These tests are decisive for the next treatment steps.",
        "Even when clots cannot be removed directly, effective medications are available that specifically address this form of pulmonary hypertension. A specialized center can best assess which option fits you.",
        "This form is often overlooked because older clots do not always cause classic symptoms. Detecting them now — rather than later — opens up treatment pathways that may significantly improve your long-term outlook.",
    ],
)

_add(
    "PX_SHUNT_HINT",
    "Indication of an additional connection between heart chambers",
    [
        "The oxygen measurements in the heart suggest that there may be an **additional connection between heart chambers**. This can often be clarified well with specialized ultrasound.",
        "The measurements in the heart suggest a possible additional connection between heart chambers. This can affect blood flow and should be specifically investigated.",
        "An additional connection — sometimes a small opening between chambers that has been there since birth — can shift blood flow in ways that influence lung pressure. Clarifying this early is important for choosing the right treatment.",
        "Specialized ultrasound, sometimes with a contrast agent (bubble study), can usually answer this question reliably. The examination is safe and takes only a few minutes.",
        "Not every such connection requires treatment — many are small and clinically harmless. But when pulmonary hypertension is present, the interaction matters, so we look carefully.",
        "If a relevant connection is confirmed, there are several ways to address it, from medication to catheter-based closure procedures. The path depends on the size of the connection and the overall picture.",
    ],
)

_add(
    "PX_ANEMIA",
    "Anemia",
    [
        "The blood work suggests **anemia** (low red blood cells). This can affect exercise tolerance and should be specifically evaluated and treated.",
        "There are signs of anemia. Treatment can help improve your stamina and energy levels.",
        "Anemia makes the heart work harder to deliver enough oxygen to the body — which in turn raises blood flow through the lungs. Correcting it often noticeably improves breathlessness and fatigue.",
        "Finding out why red blood cells are low is just as important as treating it. Common causes include iron deficiency, chronic inflammation, or certain medications — each requiring a different approach.",
        "Iron deficiency is especially common in pulmonary hypertension and responds well to treatment, sometimes with iron infusions. The benefit on exercise capacity can be meaningful.",
        "Addressing anemia is often one of the simplest, most effective steps we can take. You may notice more energy and steadier breathing within weeks of starting treatment.",
    ],
)

_add(
    "PX_CONGESTION",
    "Fluid retention / back-pressure",
    [
        "There are signs of **fluid retention or back-pressure**. It is then important to manage fluid balance well and keep an eye on kidney values.",
        "Some of the findings are consistent with fluid retention. Often, adjusting diuretic therapy (water pills) and regular monitoring of values can help.",
        "Daily weight monitoring is a simple but powerful tool: a rise of more than one to two kilograms within a few days often signals fluid retention before you feel it.",
        "A modest reduction in salt intake — together with tailored diuretic therapy — can make a real difference in how you breathe and move through daily life.",
        "Kidney values shift with diuretic use, which is why regular blood tests are important. The goal is to find the dose that reduces swelling without stressing the kidneys.",
        "Congestion is not a personal failure — it reflects how the heart and lungs are currently interacting. With the right treatment and monitoring, it can usually be managed well.",
    ],
)

_add(
    "PX_SAFETY_NET",
    "Safety advisory",
    [
        "If new or severe symptoms occur (for example, fainting, significantly worsening shortness of breath, or chest pain), please seek medical help promptly.",
        "Please seek medical help quickly if you experience sudden severe shortness of breath, fainting, chest pain, or coughing up blood.",
        "Please seek immediate medical attention if you suddenly become very short of breath, develop chest pain, faint, or cough up blood. When in doubt, it is better to go once too often than too seldom.",
        "Should your symptoms suddenly and significantly worsen, do not hesitate to call emergency services or go to an emergency room. Fainting, severe shortness of breath, and chest pain in particular require swift action.",
        "We want you to feel safe. If between appointments you suddenly experience severe shortness of breath, dizziness, fainting, or chest pain, please seek medical help immediately.",
        "A simple rule to remember: new or clearly worsened symptoms are always a reason to get in touch — better once too early than once too late. Our outpatient clinic and the emergency number exist for exactly these situations.",
    ],
)

_add(
    "PX_NEXT_STEPS",
    "What happens next?",
    [
        "We will discuss the results with you and plan the next steps. This may include additional tests, medication adjustments, and follow-up appointments.",
        "Next, we will plan the further steps together with you. Depending on the cause, additional tests, treatment adjustments, and follow-up monitoring may be advisable.",
        "The results will now be reviewed by the team. From this, we determine which additional tests or treatment steps will help most in your case.",
        "In the next step, we combine your symptoms, the measurements, and your previous findings into a clear plan. This makes it clear which action is most important first and what can be monitored for now.",
        "Based on these results, we will work out an individualized plan together with you. This may include further tests, therapy adjustments, and regular follow-ups.",
        "You will not be left on your own: we will discuss the findings thoroughly with you and decide together which steps make the most sense next.",
    ],
)

_add(
    "PX_DISCLAIMER",
    "Disclaimer",
    [
        "This text is a plain-language summary and does not replace a discussion with your doctor. Please raise any open questions at your next appointment.",
        "Note: This summary is intended for orientation. Individual classification and treatment take place in your personal consultation.",
        "This summary is meant to help you better understand the findings. It does not replace the personal conversation with your doctor, where all questions will be discussed in detail.",
        "Please note: This text is a simplified summary. The precise classification and all treatment decisions are made together with you in your medical consultation.",
        "These pages are meant as support for you — to read at your own pace and to use as a basis for our conversations. "
        "All important decisions are made together in consultation, tailored to your personal situation.",
        "If questions come up while reading, please feel free to note them and bring them to your next appointment. "
        "Medical contexts can be complex, and we will take the time to explain the results to you in an understandable way.",
    ],
)


# ---------------------------------------------------------------------------
# Age-adapted context
# ---------------------------------------------------------------------------

_add(
    "PX_AGE_YOUNG",
    "Age context: younger patients",
    [
        "As a younger person, a diagnosis like this often raises special questions — for example, about work, sports, family planning, or planning for the future. We take these aspects into account in our counseling.",
        "Especially at a younger age, a diagnosis like this can feel particularly distressing. We want to assure you that there are good treatment options and that we will accompany you in the long term.",
        "For younger people, it is especially important to manage the condition well early on. That way, we can help ensure that your daily life, ability to work, and life plans are affected as little as possible.",
        "At your age, we have the chance to act early and in a targeted way. This can make a big difference in the long run. Topics like career, travel, and family planning are ones we are happy to discuss together.",
        "We know that a diagnosis like this raises many questions at a younger age. Our goal is for you to live as normally as possible — with the right support.",
        "Work, relationships, family planning, travel — as a younger patient, you are probably wondering how this diagnosis affects all of that. Please bring up those questions openly. Most of them have clearer answers than you might think.",
    ],
)

_add(
    "PX_AGE_ELDERLY",
    "Age context: older patients",
    [
        "At a more advanced age, quality of life and safety in daily living are often the top priorities. We tailor treatment to what helps you most in your daily life.",
        "With advancing age, several conditions may interact. We pay special attention to keeping treatment as simple and well-tolerated as possible.",
        "At your age, we place particular emphasis on treatment being well-tolerated and minimally burdensome to your daily routine. Quality of life is the highest priority here.",
        "We take into account that at an older age, other conditions and medications play a role. Our goal is treatment that fits well into your daily life and supports your independence.",
        "Especially for older adults, it is important to weigh the benefit of every measure against possible burdens. We discuss openly with you which steps are truly helpful.",
        "Age alone does not determine how aggressively we treat. What matters is your overall condition, your quality of life, and what you yourself consider important. We make those decisions together.",
    ],
)

# ---------------------------------------------------------------------------
# Comorbidity context
# ---------------------------------------------------------------------------

_add(
    "PX_COMORBID_DIABETES",
    "Comorbidity context: diabetes",
    [
        "Diabetes can strain the heart and blood vessels in various ways. Good blood sugar control is therefore also important for the lung vessels.",
        "With diabetes, we pay especially close attention to how metabolism affects the heart and vessels. Close coordination with your diabetes care is advisable here.",
        "Diabetes and pulmonary hypertension can influence each other. That is why it is important to keep both conditions in view and coordinate their treatment.",
        "Good diabetes management can help protect the blood vessels and reduce the strain on the heart. We coordinate treatment of both conditions with each other.",
        "Keeping long-term sugar, blood pressure, and cholesterol well-controlled together is one of the most effective ways to protect the lung vessels. "
        "Small, consistent improvements often matter more than short-term adjustments.",
        "With diabetes, we also watch for low blood sugar and fluid retention, because some diabetes medications affect fluid balance. "
        "That way we can choose the therapy that best supports your heart and kidneys.",
    ],
)

_add(
    "PX_COMORBID_COPD",
    "Comorbidity context: COPD / lung disease",
    [
        "An existing lung condition can affect the pressure values in the lung vessels. That is why we always consider lung function and lung pressure together.",
        "With an accompanying lung condition, it can sometimes be harder to pinpoint the exact cause of the pressure elevation. A careful evaluation helps choose the right treatment.",
        "Lung disease and pulmonary hypertension can overlap. We work closely with pulmonary medicine to treat both aspects as well as possible.",
        "When a lung condition is present, oxygen supply may also play a role. We specifically check whether optimizing lung treatment can positively influence the pressure in the lung vessels.",
        "The combination of lung disease and elevated pressure in the lung vessels requires particularly careful coordination of treatment. Not every therapy that helps with one form of pulmonary hypertension is suitable when a lung condition is also present.",
        "Getting the underlying lung condition well controlled — through consistent inhaler use, vaccinations, and, when needed, supplemental oxygen — is often the single most effective lever when pulmonary hypertension is also present. We will review where the biggest gains for you are likely to come from.",
    ],
)

_add(
    "PX_COMORBID_RENAL",
    "Comorbidity context: kidney disease",
    [
        "Impaired kidney function can affect fluid balance and thereby also the pressure in the circulatory system. We take this into account in treatment planning.",
        "With kidney disease, we pay special attention to fluid balance and medication tolerability. Some medications need to be adjusted to kidney function.",
        "The kidneys and circulation are closely linked. When kidney function is reduced, this can influence the pressure values in the lung vessels. That is why we include kidney values in the overall assessment.",
        "With accompanying kidney disease, managing fluid balance is especially important. Good coordination can relieve both the kidneys and the heart.",
        "Some contrast agents and medications can place additional strain on the kidneys. "
        "That is why we plan examinations and treatment to protect your kidneys as much as possible.",
        "Regular monitoring of kidney values — together with weight and fluid intake — helps us detect changes early and intervene in time, before symptoms develop.",
    ],
)

_add(
    "PX_COMORBID_OBESITY",
    "Comorbidity context: obesity",
    [
        "Excess weight can increase the strain on the heart and lungs and affect some measurements. Weight loss can have a positive effect on symptoms.",
        "With significant excess weight, breathing mechanics, blood volume, and cardiac workload can be altered. We take this into account when interpreting the measurements.",
        "Excess weight is a factor that can worsen shortness of breath and circulatory strain. A structured weight loss program is therefore often part of the overall treatment plan.",
        "When excess weight is present, we look especially at how much of the symptoms can be explained by the weight itself and how much is due to the pressure elevation. This helps target treatment appropriately.",
        "Excess weight and pulmonary hypertension can reinforce each other. Weight loss can be an important building block for improving exercise capacity and positively influencing pressure values.",
        "We know that weight is a sensitive topic and that losing weight with limited exercise capacity is genuinely hard. That is why our approach combines structured support, realistic goals, and — where appropriate — modern options such as medication-based or surgical therapies. You are not expected to do this alone.",
    ],
)

# ---------------------------------------------------------------------------
# WHO functional class – everyday description
# ---------------------------------------------------------------------------

_add(
    "PX_FC_I",
    "Functional class I: no limitation",
    [
        "You are currently not noticeably limited in daily life. You can manage normal physical activities without shortness of breath or exhaustion. That is a good sign.",
        "Your exercise capacity is currently well preserved. Ordinary daily activities do not cause any particular symptoms. We will continue to monitor the situation nonetheless.",
        "You report that you notice no significant limitations in daily life. This suggests that the heart and circulation are handling the situation well at present.",
        "Currently, you can climb stairs, go for walks, and go about your daily routine without unusual shortness of breath. That is a good starting point.",
        "The fact that you feel comfortable during everyday exertion is an important part of our follow-up assessment. "
        "We use this baseline to detect early on if something changes.",
        "Good exercise tolerance in daily life is a valuable signal — it suggests that the heart and pulmonary circulation are working well together right now. "
        "That does not mean we neglect check-ups: precisely then, it pays to stay on top of things.",
    ],
)

_add(
    "PX_FC_II",
    "Functional class II: mild limitation",
    [
        "At rest, you have no symptoms. With greater exertion, such as climbing stairs or walking briskly, shortness of breath or fatigue may occur.",
        "You manage well in everyday life. With greater effort, such as walking uphill or carrying heavy groceries, you notice a limitation.",
        "Light daily activities go well. More strenuous activities like sports or longer walks in hilly terrain can trigger symptoms.",
        "You notice the limitation mainly with greater exertion. At rest and with light activity, you feel fine. This is a mild limitation that we monitor over time.",
        "In daily life, you feel largely normal. Only with significant physical effort do symptoms like shortness of breath or rapid fatigue occur.",
        "Many patients at this stage find that they manage the day well but need to pace intense or prolonged activities. That is a sensible, not a limiting, way to live with a mild restriction.",
    ],
)

_add(
    "PX_FC_III",
    "Functional class III: marked limitation",
    [
        "Even with everyday activities, such as getting dressed, short walks around the house, or light stair climbing, shortness of breath or exhaustion can occur. At rest, you feel better.",
        "Your exercise capacity is markedly limited. Many daily activities are harder than usual. We are working to improve your situation through treatment.",
        "You notice symptoms already with minor exertion. This shows that the heart and circulation are under greater strain. Treatment aims to give you more exercise capacity again.",
        "Everyday tasks like shopping, cooking, or a short walk can already be tiring. We take this very seriously and target treatment specifically at this.",
        "The limitation in daily life is clearly noticeable. We do everything we can to give you back more quality of life and safety in your daily routine through the right treatment.",
        "At this stage, it really helps to structure the day deliberately — plan rests, shorten routes, ask for help carrying things. That is not weakness; it is a smart strategy while treatment takes effect.",
    ],
)

_add(
    "PX_FC_IV",
    "Functional class IV: severe limitation",
    [
        "Symptoms can occur even at rest. Any physical activity worsens them. In this situation, close medical monitoring is especially important.",
        "Your symptoms are present even at rest or occur with the slightest exertion. This requires intensive treatment and close support from the care team.",
        "The limitation is severe. We know how burdensome this is and are using all available means to stabilize and improve your condition.",
        "At this stage, collaboration between you and the specialized care team is especially close. Any worsening is discussed and addressed promptly.",
        "Even though the situation is burdensome: there are treatment options even in advanced stages that can improve your quality of life. We will discuss together which steps make sense for you.",
        "At this point our priority shifts toward relieving symptoms and preserving as much quality of life as possible. Not every step is aimed at the disease itself — many are aimed quite deliberately at you as a person.",
    ],
)

# ---------------------------------------------------------------------------
# Emotional framing
# ---------------------------------------------------------------------------

_add(
    "PX_REASSURANCE",
    "Reassurance",
    [
        "We understand that findings like these can sound worrying at first. What matters is: we have the situation in view and will plan the next steps together with you.",
        "This may sound concerning at first. But many of these findings can be treated well, and we will be with you along the way.",
        "It is understandable if you feel worried after an examination like this. We will take the time to discuss everything calmly with you.",
        "Please do not let the medical terms unsettle you. We are happy to explain everything step by step and answer your questions.",
        "Even though the results may seem alarming at first: thanks to this test, we now know exactly where we stand and can take targeted action. That is an important advantage.",
        "It is normal to have many questions or worries after a test like this. Take your time — we are happy to answer questions that only come up later, at your next visit or by phone.",
    ],
)

_add(
    "PX_ENCOURAGEMENT",
    "Encouragement with stable / positive trend",
    [
        "The results give reason for optimism. Your situation is stable, and the current treatment appears to be working well.",
        "These are encouraging findings. They show that we are on the right track. We will continue to monitor the situation closely.",
        "The current trend is positive. This confirms that we are heading in the right direction. Together, we will make sure it stays that way.",
        "We are pleased to tell you that the findings overall look favorable. We will use this good starting point to continue your care optimally.",
        "The results show encouraging stability. This gives us the opportunity to continue treatment calmly and pursue further improvements.",
        "Stable numbers over a longer period are not a coincidence — they reflect your consistent treatment and our shared planning. We see that as a genuine success worth protecting.",
    ],
)

_add(
    "PX_EMPATHY_BURDEN",
    "Acknowledging the burden",
    [
        "We know that a diagnosis like this and the associated tests can be stressful. Your concerns are valid, and we take them seriously.",
        "We are aware that this finding may represent an additional burden. Please do not hesitate to let us know if you need support — beyond just the medical treatment.",
        "A chronic condition affects not just the body but also the mind. If you feel the burden is becoming too much, please talk to us. There are support services available.",
        "We understand that the diagnosis and the regular check-ups can be exhausting. You are not alone in this — we are here to support you every step of the way.",
        "Findings like these can be unsettling. We want you to know: you will not be left alone. Our goal is to support you in the best possible way, both medically and personally.",
        "The combination of a diagnosis, appointments, and waiting for results can be exhausting. If it starts to feel like too much, please tell us. Psychological and social support are a regular part of good care here, not a last resort.",
    ],
)

# ---------------------------------------------------------------------------
# Trend / course / follow-up
# ---------------------------------------------------------------------------

_add(
    "PX_TREND_IMPROVED",
    "Trend: improved",
    [
        "Compared to the last examination, the values have **improved**. This suggests that the treatment is working and your situation is developing positively.",
        "The current measurements are **more favorable** than last time. This is an encouraging result and confirms the chosen treatment path.",
        "There is a **positive trend** compared to the previous findings. The treatment appears to be working well. We will continue the current approach.",
        "The values have **improved** over time. That is a good sign and a reason to continue the therapy consistently.",
        "Compared to the previous examination, we see an **improvement**. Together, we will make sure this positive trend continues.",
        "A favourable course in pulmonary hypertension is not self-evident — it reflects consistent treatment and good collaboration. Please take this development as encouragement to stick with the path you are on.",
    ],
)

_add(
    "PX_TREND_STABLE",
    "Trend: stable",
    [
        "The measurements have **remained stable** compared to the last examination. This means the situation has not worsened, which is a reassuring sign.",
        "Over time, the values show no significant change. **Stability** in this situation is a good outcome and shows that the current treatment is doing its job.",
        "The findings are **largely unchanged** compared to the previous results. This suggests that the current therapy is keeping the situation well controlled.",
        "Stable values mean the condition is not progressing under the current treatment. We will continue the therapy and check in regularly.",
        "In a chronic condition, stability is often the most important treatment goal — and achieving it is a shared success. "
        "It shows that the current approach is protecting you effectively.",
        "The fact that nothing has worsened gives us time to work on other levers: lifestyle, concomitant diseases, and precise dosing. "
        "Small optimizations now can preserve your reserves for the long term.",
    ],
)

_add(
    "PX_TREND_WORSENED",
    "Trend: worsened",
    [
        "Compared to the last examination, some values have **changed unfavorably**. This does not automatically mean everything has gotten worse, but we take it as a reason to review the therapy.",
        "There is a **worsening** of some measurements compared to the previous findings. We will discuss with you which adjustments are now appropriate.",
        "Some values have **shifted** over time. This calls for a careful review of the current treatment. We will look together at where adjustments can help.",
        "The trend in the measurements suggests that we should **adjust the therapy**. Various options are available, and we will discuss the next steps with you.",
        "A change in values in an unfavorable direction means we need to look more closely and possibly act. We discuss this openly and plan the next steps together.",
        "A less favourable course is not unusual in a chronic pulmonary vascular disease — and it does not mean something has been done wrong. It is a signal to revisit the plan together and consider new options.",
    ],
)

_add(
    "PX_FIRST_EXAM",
    "First examination – no comparison available",
    [
        "This is your first heart catheter test at our center. A comparison with previous values is therefore not yet possible. Today's measurements serve as an important baseline for your ongoing care.",
        "Since this is the first measurement, there are no comparison values yet. We use today's results as a reference against which we can measure future changes.",
        "A trend assessment requires at least two measurement points. Today's examination provides the baseline on which we build.",
        "This is the baseline measurement. Only at a follow-up examination can we assess whether the values have changed. This is a normal part of the diagnostic process.",
        "In a first diagnostic workup, today's numbers are especially valuable — they form the basis against which every future check-up will be measured. "
        "This way, we can detect changes early and fine-tune the treatment.",
        "In the first examination, the focus is on precise classification: Which type of pressure elevation is present, which causes play a role, and where can we act most effectively? "
        "Today's results create the foundation for your personal treatment strategy.",
    ],
)

# ---------------------------------------------------------------------------
# Transition phrases
# ---------------------------------------------------------------------------

_add(
    "PX_TRANSITION_TO_DETAILS",
    "Transition: from introduction to details",
    [
        "Below, we explain what the individual measurements mean and how we interpret them.",
        "Now we would like to explain the results in more detail.",
        "Let us take a closer look at the findings:",
        "What exactly was measured and what it means for you is explained in the next section.",
        "In the following, we go through the most important results step by step.",
        "So that the numbers and terms are easier to place, we will now walk through them in the order that matters most for your situation.",
    ],
)

_add(
    "PX_TRANSITION_TO_NEXT_STEPS",
    "Transition: from findings to next steps",
    [
        "What does this mean for the next steps?",
        "Based on these results, the following recommendations arise:",
        "From these findings, we now work out the next steps together with you.",
        "Now to the question of what comes next:",
        "Based on these results, we recommend the following measures:",
        "To close, we summarise the concrete steps that make sense for you and the order in which we plan to take them.",
    ],
)

_add(
    "PX_TRANSITION_TO_RISK",
    "Transition: to risk discussion",
    [
        "An important aspect is also how we assess risk and what you should watch for.",
        "Beyond the measurements, it is important to discuss possible risks and warning signs together.",
        "We would also like to address some points that are important for your safety.",
        "Before we wrap up, we would like to highlight some important safety aspects.",
        "Please do not think of risk assessment as a judgment, but as a tool: "
        "It helps us tailor treatment precisely and monitor more intensively where it makes sense.",
        "Good care means naming both opportunities and risks openly. "
        "That way, we can choose together the steps that give you the greatest benefit with the least possible burden.",
    ],
)

# ---------------------------------------------------------------------------
# Bundles: mapping to rule-engine bundles (Kxx)
# ---------------------------------------------------------------------------
# Rule-engine bundles in rhk_rules.yaml: K00, K01, K05, K06, K07, K09, K10, K11, K14, K15, K16
PATIENT_BUNDLES: Dict[str, List[str]] = {
    # no pulmonary hypertension at rest
    "K00": ["PX_NO_PH", "PX_REASSURANCE"],

    # incomplete / not clear
    "K01": ["PX_INCOMPLETE", "PX_REASSURANCE"],

    # exercise response left-cardiac
    "K02": ["PX_EX_LEFT", "PX_REASSURANCE"],

    # exercise response pulmonary-vascular
    "K03": ["PX_EX_PVASC", "PX_REASSURANCE"],

    # unclassified / borderline
    "K04": ["PX_UNCLASSIFIED", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # precapillary (mild / moderate / significant)
    "K05": ["PX_PRECAP_MILD", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K06": ["PX_PRECAP_MOD",  "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K07": ["PX_PRECAP_SEV",  "PX_WHAT_IS_PH", "PX_EMPATHY_BURDEN", "PX_TRANSITION_TO_NEXT_STEPS"],

    # postcapillary / combined
    "K14": ["PX_POSTCAP", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],
    "K15": ["PX_CPCPH",  "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # exercise pressure response
    "K09": ["PX_EX_PVASC", "PX_REASSURANCE"],
    "K10": ["PX_EX_LEFT", "PX_REASSURANCE"],

    # precapillary + indication of older blood clots
    "K11": ["PX_PRECAP_MOD", "PX_GROUP4_HINT", "PX_WHAT_IS_PH", "PX_TRANSITION_TO_NEXT_STEPS"],

    # shunt suspicion
    "K16": ["PX_SHUNT_HINT", "PX_REASSURANCE"],
}


# ---------------------------------------------------------------------------
# Patient explanations for P-modules (P01–P30)
# ---------------------------------------------------------------------------

# Note: These texts appear in the patient report as "Why this step?"
# The goal is not completeness but an understandable added value (Why / What / What for).

PATIENT_MODULE_SUMMARY: Dict[str, str] = {
    "P01": "**Complete the baseline evaluation:** We supplement standard tests to better classify the cause and severity and to choose the right treatment.",
    "P02": "**Intensify diuresis (active decongestion):** Current signs of fluid build-up (swollen legs, weight gain, shortness of breath) mean we adjust your water pills so your body can excrete the excess fluid.",
    "P03": "**Medication to relieve the lung vessels (PDE5 inhibitor):** A cornerstone of baseline therapy for certain forms of pulmonary hypertension. We monitor blood pressure and tolerability; interactions with other medications (e.g., nitrates) are avoided.",
    "P04": "**Medication to relieve the lung vessels (ERA):** A second key class of drugs. We check liver values regularly and watch for side effects such as leg swelling. Pregnancy is not possible during ERA therapy.",
    "P05": "**Riociguat:** Specialised medication, mainly for pulmonary hypertension caused by chronic blood clots (CTEPH) or as an alternative. Important: never taken simultaneously with PDE5 inhibitors — we keep wash-out intervals between the preparations.",
    "P06": "**Consider more intensive (including infusion) therapy:** If oral therapy is not enough or the right heart is severely strained, we discuss stronger options at the PH centre — including continuous drug delivery via a permanent catheter.",
    "P07": "**Consider clinical trial participation:** Sometimes there are studies that offer additional treatment options or closer monitoring.",
    "P08": "**Interdisciplinary review (lung/imaging):** Findings are jointly evaluated (radiology/pulmonary medicine/PH team) to more reliably determine the cause.",
    "P09": "**Cardiology assessment:** Evaluation of heart valves, heart rhythm, and blood supply — especially important when the left side of the heart may be involved.",
    "P10": "**Clarify/optimize blood thinning (anticoagulation):** When blood clots are suspected, this is a central component.",
    "P11": "**Short-interval follow-up (after therapy change or instability):** Because something has just changed or the situation is not yet stable, we schedule short-term checks (e.g., echo, labs) in addition to your regular clinic appointment.",
    "P12": "**Lung function and diffusion:** Determines whether the lungs (airways/tissue) contribute to shortness of breath or pressure elevation.",
    "P13": "**Anaemia / iron deficiency — diagnostic work-up:** We measure full blood count, ferritin and transferrin saturation. Anaemia and iron deficiency often worsen breathlessness and fatigue — first we need to confirm whether a deficiency is really present.",
    "P14": "**Assess the right side of the heart more closely:** Ultrasound markers help evaluate how much strain the right heart is under — this influences monitoring and treatment intensity.",
    "P15": "**Exercise testing:** A stress test can show why symptoms occur mainly during activity and whether the heart, lungs, or circulation are the limiting factor.",
    "P16": "**Sleep medicine (sleep apnea) evaluation:** Breathing pauses during sleep can strain the heart and lungs — treatment can improve symptoms and blood pressure.",
    "P17": "**Autoimmune/rheumatic evaluation:** Certain connective tissue diseases can cause PH — blood tests and evaluation help detect this.",
    "P18": "**Infectious disease screening:** Certain infections (e.g., HIV, hepatitis) may be relevant — this is checked as appropriate.",
    "P19": "**Evaluate liver/portal hypertension:** When there are signs of liver or portal vein problems, this may be important for determining the cause.",
    "P20": "**Evaluate genetic aspects:** With a family history or very early onset, genetic counseling/testing may be advisable.",
    "P21": "**Discuss pregnancy/contraception:** With PH, pregnancy can be risky — good counseling provides protection.",
    "P22": "**Rehabilitation/exercise training:** Supervised, tailored exercise can improve everyday fitness (often better than \"taking it easy\").",
    "P23": "**Vaccination status/infection prevention:** Respiratory infections can worsen symptoms — preventive measures are reviewed.",
    "P24": "**Measure oxygen levels:** At rest, during exertion, and possibly at night — so that therapy (e.g., supplemental oxygen) can be tailored precisely.",
    "P25": "**Evaluate advanced therapies / transplant options early:** In severe disease, it is helpful to discuss options at a specialized center early on.",
    "P26": "**Fluid restriction and volume management:** When the body retains fluid, clear fluid intake limits, daily weighing, and a consistent plan help prevent shortness of breath and swelling.",
    "P27": "**Reduce cardiovascular risk factors:** Blood pressure, blood sugar, and cholesterol are optimized, smoking cessation is supported, and accompanying conditions are treated to relieve the heart and blood vessels long term.",
    "P28": "**Weight reduction:** A structured weight loss program can improve exercise capacity, breathing, and reduce circulatory strain, especially when excess weight worsens symptoms.",
    "P29": "**Start long-term oxygen therapy (LTOT):** When oxygen in the blood is persistently too low, we prescribe long-term oxygen. We set up the device with you and explain how to use it.",
    "P30": "**Discuss CT findings with the interdisciplinary team:** Pending or unclear CT findings are reviewed in a joint conference (radiology and pulmonary medicine) so that the next steps can be planned in a targeted manner.",
    "P31": "**Lifestyle building blocks:** Exercise, diet, non-smoking and management of co-existing conditions protect your cardiovascular system long term — we suggest concrete steps for daily life.",
    "P32": "**Pinpoint flow versus pressure:** Your pressure elevation may be mainly a consequence of increased blood flow (e.g., in anaemia, thyroid over-activity, liver disease or shunt connections). We test for these causes because the treatment then differs from classic pulmonary hypertension.",
    "P33": "**Heart valve team discussion:** Given signs of a relevant valve condition, cardiology, cardiac surgery and the PH team jointly decide whether and when an intervention makes sense.",
    "P34": "**CTEPH case conference:** When we suspect pulmonary hypertension caused by chronic clots, a specialised team (PH, surgery, catheter, radiology) decides the best therapy for you: surgery, catheter-based balloon dilatation (BPA) or medication.",
    "P35": "**Shunt evaluation:** The oxygen step in your measurements suggests blood may be taking an abnormal route between heart chambers or vessels. We check with contrast ultrasound and, where needed, cardiac MRI or CT.",
    "P36": "**Examine heart-muscle stiffness more closely:** An unusual pressure pattern in the catheter suggests possible stiffness of the heart chamber or pericardium. Cardiac MRI helps to characterise this more clearly.",
    "P37": "**Detailed cross-sectional imaging of the lung:** A high-resolution CT (potentially dual-energy) shows lung vessels and tissue in detail — essential to reliably detect clots, vessel narrowings or other changes.",
    "P38": "**Rule out high-flow causes:** Before expanding therapy, we check for anaemia, thyroid over-activity, liver disease and shunt connections — each can raise pulmonary pressures but needs a different treatment.",
    "P39": "**Aortic follow-up:** The main artery is mildly dilated. Regular imaging tracks whether it changes — giving us confidence and allowing timely decisions.",
    "P40": "**Maintain fluid balance (ambulatory maintenance):** Fluid balance is currently good — we want to keep it that way. Daily weighing, steady fluid intake and quarterly labs help us intervene early if anything shifts.",
    "P41": "**Clarify liver values:** Before starting any liver-sensitive medication, we investigate the elevated liver values (abdominal ultrasound, and gastroenterology consult where needed) so therapy can be prescribed safely.",
    "P42": "**Treat iron deficiency (iron infusion):** Iron deficiency is confirmed. We usually administer iron as a short infusion — it works faster and more reliably than tablets, and often improves exercise capacity within weeks.",
    "P43": "**Cardiopulmonary exercise testing (CPET):** An exercise test with breath-gas analysis reveals whether your symptoms originate mainly from the lungs, heart or muscles — guiding the next steps precisely.",
    "P44": "**Six-minute walk test:** A simple test to measure your current exercise capacity: you walk six minutes on a level corridor and we record the distance. Good for comparisons over time.",
    "P45": "**Review lung tissue findings together:** Existing or external CT images of the lung are discussed in a pulmonary-radiology conference to confirm the correct interpretation (e.g., fibrosis, emphysema).",
    "P46": "**Sleep study:** Obesity or noticeable daytime sleepiness raise the suspicion of sleep apnoea. A night recording clarifies whether treatment (e.g., CPAP mask) is advisable.",
    "P47": "**Complete the autoimmune panel:** We add blood tests (e.g., ANA, ENA, scleroderma markers) to confidently include or exclude an autoimmune cause of pulmonary hypertension.",
    "P48": "**Optimise oxygen therapy:** You already use long-term oxygen. We check with blood-gas measurements at rest, during exercise and at night whether the current flow is optimal and adjust it as needed.",
    "P49": "**Close PH clinic interval (every 3 months):** Because of your elevated risk we see you more often — every three months — for labs, echo and a consultation. This lets us react promptly if anything changes.",
    "P50": "**Consistent blood pressure control:** Elevated systemic blood pressure adds strain on the heart and lung vessels. We optimise the blood-pressure medication to improve the overall picture.",
    "P51": "**Regular PH clinic visits (every 6 months):** The current situation is stable enough for a six-month routine rhythm: labs, echo and a consultation. You can reach us between appointments whenever questions come up.",
    "P52": "**Clinical trial coordination:** When you are enrolled in a trial, we align appointments and tests with the study clinic so everything runs smoothly.",
}


# ---------------------------------------------------------------------------
# Glossary – short explanations of key terms
# ---------------------------------------------------------------------------

PATIENT_GLOSSARY: Dict[str, str] = {
    "PH": "Pulmonary hypertension: high blood pressure in the blood vessels of the lungs.",
    "PAH": "Pulmonary arterial hypertension: a subtype of pulmonary hypertension primarily affecting the lung vessels.",
    "CTEPH": "Chronic thromboembolic pulmonary hypertension: pulmonary hypertension caused by older blood clots in the lung vessels.",
    "Right heart catheterization": "A test in which a thin tube is used to measure pressures and blood flow in the heart and lungs.",
    "mPAP": "Mean pulmonary artery pressure (a key value for pulmonary hypertension).",
    "PAWP": "A measurement that can indicate whether the left side of the heart is contributing to the pressure elevation.",
    "PVR": "Pulmonary vascular resistance — simply put: how \"tight\" or narrow the lung vessels are.",
    "WU": "Wood Units: the unit of measurement for resistance in the lung vessels (PVR).",
    "CO": "Cardiac output: the amount of blood the heart pumps per minute.",
    "CI": "Cardiac index — how much blood the heart pumps per minute relative to body size.",
    "RAP": "Right atrial pressure — can be elevated with fluid retention or back-pressure.",
    "sPAP": "Systolic pulmonary artery pressure (the upper pressure value).",
    "dPAP": "Diastolic pulmonary artery pressure (the lower pressure value).",
    "Precapillary": "A pattern in which the pressure rise originates mainly in the lung vessels themselves.",
    "Postcapillary": "A pattern in which the left side of the heart contributes to the pressure rise.",
    "IpcPH": "Isolated postcapillary pulmonary hypertension: pressure rise predominantly caused by the left side of the heart.",
    "CpcPH": "Combined post- and precapillary pulmonary hypertension: pressure transmitted from the left heart plus vascular changes in the lungs.",
    "HFpEF": "Heart failure with preserved pumping strength: the heart is often \"stiffer\" and fills less well, especially during exertion.",
    "Dyspnea": "Shortness of breath.",
    "Syncope": "Brief fainting due to temporarily reduced blood flow to the brain.",
    "WHO-FC": "WHO functional class: a classification of how much symptoms limit daily activities.",
    "6MWD": "Six-minute walk distance: the distance walked in six minutes; shows current exercise capacity.",
    "V/Q": "Ventilation/perfusion scan: a test of lung blood flow (important when older blood clots are suspected).",
    "CT": "Computed tomography: a cross-sectional imaging study, for example of the lungs and lung vessels.",
    "Anticoagulation": "Blood thinning (clot prevention) to prevent or treat blood clots.",
    "NT-proBNP": "A blood marker that can indicate strain on the heart.",
    "NT pro BNP": "Alternative spelling of NT-proBNP; a blood marker indicating heart strain.",
    "DLCO": "Diffusion capacity: shows how well oxygen passes from the lungs into the blood.",
    "Tiffeneau": "FEV1/FVC ratio from lung function testing. A low value may indicate narrowed airways.",
    "ILD": "Interstitial lung disease (e.g., pulmonary fibrosis): a disease of the lung tissue.",
    "ERA": "A class of medication used in certain forms of PH/PAH (we will explain in person whether this is appropriate for you).",
    "PDE5": "A class of medication that can relax the lung vessels (e.g., sildenafil/tadalafil).",
    "Echocardiography": "Ultrasound examination of the heart: shows the size, function, and valves of both sides of the heart.",
    "Vasoreactivity": "A test during heart catheterization that checks whether the lung vessels respond to a medication.",
    "Volume challenge": "A targeted fluid test during heart catheterization to uncover hidden involvement of the left side of the heart.",
    "Functional class": "A classification (I–IV) of how much symptoms limit daily life (I = no limitation, IV = symptoms at rest).",
    "Prostacyclin": "A naturally occurring substance in the body that widens lung vessels. Used as a medication in various forms.",
    "BPA": "Balloon pulmonary angioplasty: a catheter procedure in which narrowed lung vessels are widened with a balloon (for chronic blood clots).",
    "PEA": "Pulmonary endarterectomy: an operation in which chronic blood clots are removed from the lung vessels.",
    "Iron deficiency": "A common accompanying condition in pulmonary hypertension that can worsen fatigue and shortness of breath. It is treatable.",
    "Diuretic": "A water pill: helps reduce fluid retention and relieve strain on the heart.",
    "Edema": "Fluid retention, especially in the legs, ankles, or abdomen. Can be a sign of back-pressure in the circulation.",
    "Oxygen saturation": "Shows how well the blood is loaded with oxygen. Usually measured at the finger.",
    "Shunt": "An abnormal connection between two heart chambers or blood vessels through which blood flows along an unusual path.",
    "Compliance": "Distensibility of the lung vessels: describes how elastic the vessels still are.",
    "Right heart failure": "A condition in which the right heart can no longer adequately cope with the increased strain.",
}



# ---------------------------------------------------------------------------
# Vertical refinement: symptom weighting (sub-layer)
# ---------------------------------------------------------------------------

_add(
    "PX_SYMPTOM_PROFILE_LOW",
    "Symptom profile: rather mild symptoms",
    [
        "Your answers suggest rather mild limitations in daily life. Still, it is important to notice changes early and not focus only on individual measurements.",
        "Overall, your exercise capacity appears fairly stable. What matters is whether shortness of breath or fitness level change over time.",
        "In daily life, you seem to have few limitations. That is a positive signal. Please watch for any changes.",
        "Mild symptoms in the presence of certain findings can be a sign that the body is still compensating well. Regular check-ups help us monitor this.",
        "The fact that your symptoms are currently minor is a good starting point for your ongoing care. Changes over time are still important to recognize.",
        "Mild everyday symptoms are encouraging but not a reason to skip follow-up — the value of steady check-ins is precisely that we can catch a shift early, while it is still easy to respond to.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_MODERATE",
    "Symptom profile: moderate limitations",
    [
        "Your symptoms are noticeable in daily life. We therefore base the next steps not only on numbers but also on what bothers you most in your everyday routine.",
        "With moderate symptoms, the combination of measurements, exercise capacity, and trend is often decisive. That is exactly what we base our monitoring and treatment planning on.",
        "Your symptoms affect daily life noticeably. This is an important signal that we factor into treatment planning.",
        "Moderate limitations show that the body is still coping with the strain but is approaching its limits. Targeted measures can often bring noticeable improvement here.",
        "When everyday activities become somewhat harder than usual, that is a reason to look more closely. We use this information to adjust treatment so that you feel more comfortable in daily life.",
        "Moderate limitations suggest the body is managing but already under strain. Targeted measures at this stage often deliver more benefit than waiting for symptoms to get worse.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_HIGH",
    "Symptom profile: significant limitations",
    [
        "You report significant limitations. In that case, it is especially important not just to look at the numbers but to specifically determine what is driving your symptoms and how we can stabilize the situation quickly.",
        "When everyday activities are clearly difficult, that carries great weight in treatment planning. We therefore discuss at close intervals which steps can help the most.",
        "Significant symptoms in daily life are an important signal. We take this very seriously and prioritize the measures that can bring you relief fastest.",
        "Your limitations appear substantial. In this situation, we work especially closely with you to reduce the burden as quickly as possible.",
        "With pronounced symptoms, your quality of life is at the center of treatment. We explore every option to make your daily life as manageable as possible.",
        "Clear symptoms usually mean we act faster and see you more often — the goal is to relieve the burden on your daily life, not only to improve numbers on a chart.",
    ],
)

_add(
    "PX_SYMPTOM_PROFILE_SYNCOPE",
    "Symptom profile: syncope as a warning sign",
    [
        "Fainting or near-fainting is an important warning sign in lung vessel conditions. Please always report such episodes promptly, even if individual values may not seem alarming at first glance.",
        "Syncope is a serious signal because it means that temporarily, not enough blood may be reaching the circulation. This influences how we assess risk and treatment.",
        "Loss of consciousness or brief blackouts are taken especially seriously in lung vessel conditions. Please report every such episode without delay.",
        "Fainting episodes show that the circulation is temporarily not supplying the body adequately. This carries significant weight in our assessment of urgency.",
        "If fainting or near-fainting has occurred, we interpret the findings with particular care. Such episodes influence how closely we monitor and how quickly we act.",
        "Syncope is the kind of symptom where we clearly prefer to err on the side of caution: tighter follow-up, sometimes an earlier start of therapy, and a low threshold to review what is going on if anything like this repeats.",
    ],
)

# ---------------------------------------------------------------------------
# Vertical refinement: discordance explanations (sub-layer)
# ---------------------------------------------------------------------------

_add(
    "PX_DISCORDANCE_HIGH_MPAP_LOW_BNP",
    "Discordance: high pressure, low BNP",
    [
        "Sometimes the pressure in the lung circulation is significantly elevated while the blood marker BNP or NT-proBNP remains low. This can happen when the right heart is still compensating well or when the blood marker is influenced by other factors. What matters then is the overall picture including exercise capacity and echocardiogram.",
        "A low BNP or NT-proBNP level does not rule out elevated pressure. We use this value as a reference point for the trend, but not as the sole explanation of your situation.",
        "BNP levels can be influenced by kidney function, body weight, age, and certain medications. That is one reason why we never interpret a single value in isolation but always in the context of the whole picture.",
        "A low BNP in the context of elevated pressure can be good news: it often indicates that the right heart is still adapting well. We keep an eye on this balance to act early if it shifts.",
    ],
)

_add(
    "PX_DISCORDANCE_LOW_PRESSURE_HIGH_SYMPTOMS",
    "Discordance: rather low pressure but pronounced symptoms",
    [
        "Pronounced symptoms can also occur when pressure values are only moderate. Reasons may include reduced pumping capacity, back-pressure, lung disease, anemia, or an interplay of several factors. That is why we always look at the full picture.",
        "When symptoms and pressure values do not match, that is not a contradiction. We then specifically check for other causes that affect exercise capacity in daily life.",
        "Your symptoms are real, and we take them seriously — even when a single number looks reassuring. Shortness of breath and fatigue often have several contributors, and we want to identify each of them.",
        "Sometimes pressure values at rest appear unremarkable but rise significantly under exertion. That is why we often look at exercise tests in addition to the resting measurement — they capture what everyday life demands of you.",
    ],
)

_add(
    "PX_DISCORDANCE_ECHO_OK_CATH_HIGH",
    "Discordance: echocardiogram looks reassuring, catheter shows high values",
    [
        "The echo can sometimes appear normal even though the heart catheter shows elevated pressure values. This is because the echo estimates values indirectly and cannot always reliably capture every situation. For classification, the catheter is then especially important.",
        "When echo and catheter send different signals, we rely on the most reliable measurements and additionally look at the trend and symptoms.",
        "The heart catheter measures pressures directly and is therefore considered more accurate. A reassuring echo does not mean the catheter finding is any less important — both examinations complement each other.",
        "We understand that such a contrast can feel unsettling at first — perhaps you left the echo thinking everything was fine. The catheter now provides a more precise assessment, and we plan the next steps on that basis.",
        "Because the heart catheter measures pressures directly within the lung vessels, it is the gold standard for diagnosis. The echo remains important for follow-up but does not replace direct measurement in critical situations.",
        "Mild to moderate pressure elevations can look normal on echo — this is a known limitation of the method, not an error. That is precisely why we performed the catheter: to classify reliably what ultrasound could not yet show.",
    ],
)

# ---------------------------------------------------------------------------
# Measurement variants (v27.4.24+): user-friendly sentences with placeholders.
# Placeholders:
#   {mpap_str}, {pawp_str}, {pvr_str}, {ci_str}, {rap_str}
# ---------------------------------------------------------------------------

_add(
    "PX_MEASURE_MPAP_ELEVATED",
    "Measurement: elevated mPAP (with value)",
    [
        "An elevated pressure in the pulmonary circulation was measured in your case (mPAP {mpap_str} mmHg; pulmonary hypertension starts at >20 mmHg). This means: the right side of the heart has to pump blood against increased resistance toward the lungs.",
        "The direct measurement during the catheter showed a mean pulmonary pressure of {mpap_str} mmHg. Above 20 mmHg we call this pulmonary hypertension — your value is above that threshold. Practically, your right ventricle has more work to move blood toward the lungs.",
        "The mean pulmonary artery pressure was {mpap_str} mmHg, which is above the threshold of 20 mmHg. Your right heart therefore needs more force to push blood into the lungs.",
        "During the catheter an elevated mean pulmonary pressure was recorded (mPAP {mpap_str} mmHg). Values up to 20 mmHg are considered normal; anything above is classified as pulmonary hypertension, which puts additional strain on the right heart.",
        "The measurement confirms pulmonary hypertension: your mean pulmonary pressure is {mpap_str} mmHg (threshold 20 mmHg). The right heart needs more pressure to move blood into the pulmonary vessels.",
        "During catheterization, your mean pulmonary artery pressure was {mpap_str} mmHg. This is above the normal range and shows that the right heart has to pump against an increased resistance toward the lungs.",
    ],
)

_add(
    "PX_MEASURE_PH_NO_MPAP",
    "Measurement: pulmonary hypertension without an mPAP value",
    [
        "The measurements show pulmonary hypertension. This means: the right side of the heart has to pump blood against increased resistance toward the lungs.",
        "The values indicate pulmonary hypertension. Your right heart therefore has to work against a higher resistance when it moves blood toward the lungs.",
        "The examination shows that pulmonary pressure is elevated. The right heart therefore needs more force to push blood into the pulmonary vessels.",
        "In summary, the picture is one of pulmonary hypertension. For you this means: the right side of your heart is under more strain than in a normal circulation.",
        "Based on the current measurements, pulmonary hypertension is present. In practical terms, the right ventricle has to overcome a higher resistance to move blood into the lungs.",
        "Overall the values show elevated pressure in the pulmonary circulation. Because of that the right heart has more work to do than normal.",
    ],
)

_add(
    "PX_MEASURE_PRECAP_PATTERN",
    "Measurement: precapillary pattern (PAWP normal, PVR elevated)",
    [
        "The pressure before the left side of the heart is not elevated (PAWP {pawp_str} mmHg). At the same time, the resistance in the pulmonary vessels is clearly elevated (PVR {pvr_str} WU; elevated above >2 WU). This pattern suggests that the cause is more likely in the pulmonary circulation itself or related to a lung condition.",
        "On the left side of the heart the pressure is within the normal range (PAWP {pawp_str} mmHg). The resistance in the small pulmonary vessels, however, is elevated (PVR {pvr_str} WU). This combination points to a form where the pulmonary vessels or the lungs themselves are in the foreground.",
        "The PAWP (pressure before the left chamber) is within the normal range at {pawp_str} mmHg. The pulmonary vascular resistance (PVR) is elevated at {pvr_str} WU. This is called a precapillary pattern — the left side of the heart is therefore not the main cause.",
        "Typical for a disease of the pulmonary vessels: the PAWP is normal ({pawp_str} mmHg), the PVR is elevated ({pvr_str} WU). The cause is therefore more likely upstream of the left heart — in the pulmonary arteries themselves.",
        "What we see here is called a precapillary pattern: the pressure immediately before the left heart is normal (PAWP {pawp_str} mmHg), while the resistance in the pulmonary vessels is elevated (PVR {pvr_str} WU). That fits a disease of the pulmonary vessels or the lungs.",
        "The combination of a normal PAWP ({pawp_str} mmHg) and an elevated PVR ({pvr_str} WU) is called precapillary. In plain terms: the left side of the heart is working cleanly — the bottleneck is in the pulmonary vessels.",
    ],
)

_add(
    "PX_MEASURE_POSTCAP_PAWP_HIGH",
    "Measurement: postcapillary pattern (PAWP elevated)",
    [
        "The pressure before the left side of the heart is elevated (PAWP {pawp_str} mmHg). This can contribute to fluid backing up into the lungs and is taken into account during classification.",
        "On the left side of the heart the pressure is elevated at {pawp_str} mmHg. This back-pressure can extend into the lungs and is factored into the classification.",
        "The PAWP (a measure of the pressure before the left chamber) is {pawp_str} mmHg and therefore above the normal range. This means that part of the elevated lung pressure is explained by back-pressure from the left heart.",
        "An elevated PAWP of {pawp_str} mmHg suggests that the left heart is contributing to the pulmonary hypertension. We take this share into account when planning therapy.",
        "Your pattern is postcapillary: the PAWP is {pawp_str} mmHg, above the normal range. That indicates that the blood congestion toward the lungs is co-caused by the left side of the heart.",
        "The measurement shows back-pressure from the left heart toward the lungs (PAWP {pawp_str} mmHg). This is an important piece for classifying the cause of your pulmonary hypertension more precisely.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW",
    "Measurement: reduced pumping capacity (CI low or borderline)",
    [
        "Cardiac output is rather reduced (CI {ci_str} l/min/m²). This may explain why exertion becomes difficult more quickly or dizziness may occur.",
        "Your cardiac index (CI), a measure of pumping capacity, is {ci_str} l/min/m² and therefore at or just below the normal range. This fits with reaching your limits quickly during exertion.",
        "The measurements show a rather low pumping capacity (CI {ci_str} l/min/m²). For you this can mean that physical activity becomes demanding sooner, or that dizziness may occur.",
        "The pumping capacity per square meter of body surface is {ci_str} l/min/m² and therefore rather low. This often explains symptoms such as fatigue or light-headedness with exertion.",
        "Your heart is moving less blood than we would like under resting conditions (CI {ci_str} l/min/m²). This can explain part of your everyday complaints, particularly reduced exercise tolerance.",
        "The CI (Cardiac Index) is reduced at {ci_str} l/min/m². It describes how much blood your heart pumps per minute relative to your body size — a lower value means less reserve during exertion.",
    ],
)

_add(
    "PX_MEASURE_CI_OK",
    "Measurement: preserved pumping capacity (CI normal)",
    [
        "Cardiac output is not clearly reduced in this measurement (CI {ci_str} l/min/m²).",
        "The cardiac index is {ci_str} l/min/m² and therefore not clearly reduced. Pumping capacity is preserved from this perspective.",
        "The pumping capacity of the heart is unremarkable in this measurement (CI {ci_str} l/min/m²). That is a good starting point for further therapy.",
        "Based on the CI value ({ci_str} l/min/m²) no clear pump weakness can be identified. The pumping capacity of the heart is okay in this snapshot.",
        "Your CI (Cardiac Index) is {ci_str} l/min/m², which is in the acceptable range. Your heart's pumping capacity is not impaired at the time of measurement.",
        "The measurement of pumping capacity yields a CI of {ci_str} l/min/m². We do not currently see a clear pump weakness.",
    ],
)

_add(
    "PX_MEASURE_RAP_HIGH",
    "Measurement: elevated right atrial pressure (RAP)",
    [
        "The right atrial pressure (RAP) is {rap_str} mmHg and is elevated. This may indicate increased strain on the right side of the heart.",
        "We measured {rap_str} mmHg in the right atrium — that is elevated. It points to the right side of the heart already working against a higher resistance.",
        "The RAP (pressure in the right atrium) is {rap_str} mmHg, above the usual range. An elevated RAP is a sign that the right heart is under strain.",
        "An elevated right atrial pressure of {rap_str} mmHg shows us that pressure is building up in front of the right chamber. That is a warning signal for right-heart strain and is incorporated into the risk assessment.",
        "The measured value in the right atrium is elevated at {rap_str} mmHg. The higher this value, the more the right heart works against a counter-pressure. We take that into account in therapy planning.",
        "The RAP is one of the central risk markers. Yours is elevated at {rap_str} mmHg, and we take it as an indication of marked strain on the right side of the heart.",
    ],
)

_add(
    "PX_MEASURE_PRECAP_ONLY_CATEGORY",
    "Measurement: precapillary without numeric values (category)",
    [
        "The measurement pattern is more consistent with a form where the pulmonary vessels or the lungs themselves are primarily involved.",
        "Summarized, the pattern best fits a disease that originates in the pulmonary vessels.",
        "The values suggest that the pulmonary vessels or the lungs themselves are the main cause — not the left side of the heart.",
        "Overall the pattern is what we call precapillary: the actual cause lies in the pulmonary circulation, not in the left heart.",
        "The combined values point to a form primarily affecting the pulmonary vessels. The left side of the heart seems to play a secondary role.",
        "For further therapy the key point is: the measurements fit a form that starts in the pulmonary vessels — and therefore a vessel-targeted treatment.",
    ],
)

_add(
    "PX_MEASURE_POSTCAP_ONLY_CATEGORY",
    "Measurement: left-heart involvement (category)",
    [
        "The measurement pattern is more consistent with a form where the left side of the heart may also be involved.",
        "The values suggest that the left side of the heart is co-involved in the pulmonary hypertension.",
        "Taken together, the pattern indicates that the left heart also contributes to the elevated pressure.",
        "Overall your finding fits a form in which the left side of the heart plays a role. That influences the choice of therapy.",
        "The combination of values shows that the left side of the heart is likely involved. We take that into account in your continued treatment.",
        "The pattern supports that not only the pulmonary vessels but also the left side of the heart contribute to the pulmonary hypertension.",
    ],
)


# ---------------------------------------------------------------------------
# Severity-graded measurement blocks (v27.4.25+)
# Rendered only when a specific metric crosses mild / moderate / severe bands.
# Tone scales with severity: mild = reassuring, moderate = matter-of-fact
# actionable, severe = clear but not alarmist.
# ---------------------------------------------------------------------------

_add(
    "PX_MEASURE_MPAP_MILD",
    "Measurement: mPAP mildly elevated (20–30 mmHg)",
    [
        "The average pressure in the pulmonary arteries (mPAP {mpap_str} mmHg) is mildly elevated — just above the pulmonary-hypertension threshold of 20 mmHg. That is a clear but moderate early sign.",
        "With an mPAP of {mpap_str} mmHg, your pulmonary pressure is in the lower end of the pulmonary-hypertension range. Good news: at this level we often have more treatment options to slow the progression.",
        "Your pulmonary pressure is mildly elevated ({mpap_str} mmHg). That means: the right heart is noticing the extra load, but is still working reliably.",
        "The value of {mpap_str} mmHg lies just above the normal range. Mild elevations are important to recognise — and in many cases good to monitor and treat in time.",
        "The mPAP is mildly elevated ({mpap_str} mmHg). Even modest values are meaningful — they let us act early and often prevent the pressure from climbing further.",
        "An mPAP of {mpap_str} mmHg is only moderately raised. This kind of value is a signal to act carefully, not to panic.",
    ],
)

_add(
    "PX_MEASURE_MPAP_MOD",
    "Measurement: mPAP moderately elevated (31–45 mmHg)",
    [
        "The mean pressure in the pulmonary arteries is clearly elevated at {mpap_str} mmHg. Medically this falls into the moderate range — a level where we take active treatment decisions.",
        "Your mPAP of {mpap_str} mmHg is well above the normal range. That puts a meaningful extra load on the right side of the heart, which we can address with targeted therapy.",
        "The measurement shows a distinct elevation in pulmonary pressure ({mpap_str} mmHg). At this level several therapy options exist, and the further work-up helps pick the right ones.",
        "With an mPAP of {mpap_str} mmHg the pulmonary circulation is clearly under pressure. The right heart is working against visibly higher resistance, so we want to act decisively.",
        "{mpap_str} mmHg mean pressure is a moderate elevation. That is a level we take seriously — but also one for which there are proven therapeutic strategies.",
        "The mPAP of {mpap_str} mmHg is not extreme, but clearly outside the normal range. At this level it is crucial to clarify the exact cause and plan the treatment accordingly.",
    ],
)

_add(
    "PX_MEASURE_MPAP_SEV",
    "Measurement: mPAP severely elevated (>45 mmHg)",
    [
        "At {mpap_str} mmHg the mean pulmonary pressure is markedly elevated. That places a serious strain on the right heart — and it is exactly the constellation where consistent therapy makes the biggest difference.",
        "An mPAP of {mpap_str} mmHg is in the high range. Please don't be alarmed — there are tried-and-tested treatment pathways for exactly this situation. The key is to start and adjust treatment carefully.",
        "Your mPAP is severely elevated at {mpap_str} mmHg. This is a clear call to act — but also an area where modern PH therapy has made the biggest progress in recent years.",
        "The measurement shows a markedly elevated mean pulmonary pressure ({mpap_str} mmHg). Such values require close accompaniment — and call for treatment options that can noticeably lower both pressure and symptoms.",
        "With {mpap_str} mmHg the pressure in the pulmonary circulation is high. The right heart is working hard — our goal is to relieve it and improve quality of life step by step.",
        "An mPAP of {mpap_str} mmHg is an urgent signal to optimise therapy. Encouraging: even at this level many patients respond well to combined approaches.",
    ],
)

_add(
    "PX_MEASURE_PAWP_MILD",
    "Measurement: PAWP mildly elevated (16–20 mmHg)",
    [
        "The pressure in front of the left side of the heart (PAWP {pawp_str} mmHg) is mildly elevated. That can be a hint of early left-heart involvement — often reversible with treatment.",
        "Your PAWP is slightly above the normal range ({pawp_str} mmHg). That fits a picture where the left heart is making a modest contribution to the pressure rise.",
        "With a PAWP of {pawp_str} mmHg a mild back-pressure from the left heart is visible. In this range we can often improve symptoms substantially with well-established heart medications.",
        "The PAWP ({pawp_str} mmHg) is just above the normal range. That allows for targeted optimisation — often without major changes to everyday life.",
        "A PAWP of {pawp_str} mmHg is a small but real hint that the left heart is being taxed. Such values are the right moment for subtle therapy fine-tuning.",
        "With {pawp_str} mmHg your PAWP is mildly elevated. That is an early signal, not a cause for immediate concern — but one we do act on.",
    ],
)

_add(
    "PX_MEASURE_PAWP_MOD",
    "Measurement: PAWP moderately elevated (21–25 mmHg)",
    [
        "The pressure in front of the left heart is clearly elevated (PAWP {pawp_str} mmHg). That indicates more substantial left-heart involvement — something we can address specifically with medication.",
        "Your PAWP is moderately elevated at {pawp_str} mmHg. That means fluid tends to back up into the lungs; fluid balance and heart medications will be the centrepieces of treatment.",
        "With a PAWP of {pawp_str} mmHg the left side of the heart is a relevant driver. Many patients feel markedly better once therapy is consistently titrated.",
        "The PAWP of {pawp_str} mmHg is a clear sign of moderate congestion from the left heart. This is a treatable area where medication, weight control and blood-pressure management work together.",
        "A PAWP value of {pawp_str} mmHg signals that the left heart currently needs more support. We optimise fluid balance and medication step by step to relieve the lungs.",
        "The PAWP of {pawp_str} mmHg is clearly elevated. That markedly influences therapy: instead of only targeting the lung vessels, we also deliberately optimise the left heart.",
    ],
)

_add(
    "PX_MEASURE_PAWP_SEV",
    "Measurement: PAWP severely elevated (>25 mmHg)",
    [
        "With a PAWP of {pawp_str} mmHg there is marked congestion from the left side of the heart. That often explains shortness of breath and fluid retention — and is a key target of our therapy.",
        "The PAWP of {pawp_str} mmHg is markedly elevated. The left side of the heart cannot cope with the blood volume, and the congestion reaches back into the lungs. We will therefore set diuretics and cardiac medication firmly.",
        "Your PAWP is far above the normal range at {pawp_str} mmHg. At this magnitude the left heart is the driving force. Close cardiology follow-up with weight tracking and medication adjustment is important now.",
        "The measurement showed a severely elevated PAWP ({pawp_str} mmHg). That is serious — but precisely in this constellation there are well-established strategies (diuresis, blood-pressure and cardiac therapy) that often bring rapid relief.",
        "With {pawp_str} mmHg there is severe pressure build-up in front of the left heart. The good news: post-capillary elevations often respond well to proven heart medications when used consistently.",
        "A PAWP of {pawp_str} mmHg signals marked congestion — it can feel like “water in the lungs”. We counteract it decisively with medication and behavioural measures (e.g. fluid intake, daily weights).",
    ],
)

_add(
    "PX_MEASURE_PVR_MILD",
    "Measurement: PVR mildly elevated (2.1–3.0 WU)",
    [
        "The resistance in the lung vessels (PVR {pvr_str} WU) is mildly elevated (threshold >2 WU). That is a gentle hint of changes in the pulmonary arteries — usually early and observable.",
        "Your PVR of {pvr_str} WU is just above the normal range. That means the pulmonary vessels are showing an early rise in resistance. We work through the cause systematically — in this early stage a lot can often be achieved.",
        "With a PVR of {pvr_str} WU there is a mild resistance elevation in the pulmonary circulation. This is not a value that needs immediate treatment, but one that justifies regular follow-up.",
        "The vessels in your lungs are working with a slightly increased resistance (PVR {pvr_str} WU). We often find such values in concomitant conditions or early in the course — the exact assessment guides next steps.",
        "The PVR is only mildly elevated at {pvr_str} WU. That gives us a measurable but still reassuring finding — ideal for preventive action rather than reactive treatment.",
        "With {pvr_str} WU your pulmonary vascular resistance is borderline to mildly elevated. That is an early sign we pay attention to, without immediately pulling every therapeutic lever.",
    ],
)

_add(
    "PX_MEASURE_PVR_MOD",
    "Measurement: PVR moderately elevated (3.1–5.0 WU)",
    [
        "The resistance in the pulmonary vessels is clearly elevated at {pvr_str} WU. That indicates a relevant change in the small pulmonary arteries — an area where vasodilating medications are often used.",
        "With a PVR of {pvr_str} WU there is moderate resistance elevation. The pulmonary vessels have noticeably “narrowed”. That is treatable: several well-established medications can demonstrably help here.",
        "Your PVR of {pvr_str} WU falls into the moderate range. That clearly influences the treatment decision: at this level targeted vascular therapy is often indicated.",
        "The measurement showed an elevated pulmonary vascular resistance ({pvr_str} WU). That is an important sign of a pulmonary-arterial component — i.e. changes that primarily affect the lung vessels and can be treated specifically.",
        "A PVR of {pvr_str} WU shows that the pulmonary vessels are clearly pushing back. For you that means more work for the right heart — for us, a definite treatment criterion.",
        "With {pvr_str} WU your vascular resistance is noticeably elevated. The right heart has to work against this resistance. Modern PH medications can often reduce both pressure and resistance in several steps.",
    ],
)

_add(
    "PX_MEASURE_PVR_SEV",
    "Measurement: PVR severely elevated (>5.0 WU)",
    [
        "The pulmonary vascular resistance of {pvr_str} WU is markedly elevated. That is a clear signal of advanced changes in the lung vessels — and reason for decisive, often combined therapy.",
        "With a PVR of {pvr_str} WU the vessels in your lungs are heavily narrowed. The right heart needs more support — modern PH drugs can lower this value substantially over time.",
        "Your pulmonary vascular resistance is severely elevated ({pvr_str} WU). That is serious — and at the same time a clear indication for specialist PH treatment, which has become dramatically more effective in recent years.",
        "The measurement showed a severely increased PVR ({pvr_str} WU). This is exactly the constellation where combination therapies typically show the biggest benefit — we will plan the next steps carefully.",
        "A PVR of {pvr_str} WU is a heavy signal — but not a hopeless one. The right therapy can bring the value down step by step and noticeably relieve the right heart.",
        "With {pvr_str} WU the resistance in the lungs is gravely elevated. Please don't lose heart: exactly in this situation a specialised PH centre can open up multiple treatment paths.",
    ],
)

_add(
    "PX_MEASURE_RAP_MILD",
    "Measurement: RAP mildly elevated (8–12 mmHg)",
    [
        "The right atrial pressure (RAP) is mildly elevated at {rap_str} mmHg. That is a subtle sign that the right side of the heart is carrying a little extra load.",
        "Your RAP is just above the normal range ({rap_str} mmHg). That is an early indication of modest right-heart strain — a value we take seriously, without setting off alarm bells.",
        "With a RAP of {rap_str} mmHg you are just above the normal range. At this level targeted therapy can often prevent further increase.",
        "The measurement in the right atrium is slightly elevated ({rap_str} mmHg). That is a helpful warning — we use it to fine-tune the therapy.",
        "The RAP of {rap_str} mmHg is in the mildly elevated range. Such values typically don't cause symptoms on their own, but give us important information.",
        "With {rap_str} mmHg the RAP is a little elevated. The right heart is signalling a subtle increase in workload — one we address pre-emptively.",
    ],
)

_add(
    "PX_MEASURE_RAP_MOD",
    "Measurement: RAP moderately elevated (13–15 mmHg)",
    [
        "The pressure in the right atrium is clearly elevated at {rap_str} mmHg. That is a sign that the right heart is being noticeably taxed and should be unburdened.",
        "Your RAP of {rap_str} mmHg falls into the moderately elevated range. In combination with the other values that steers our therapy: the right heart gets targeted support.",
        "A RAP of {rap_str} mmHg shows that pressure is backing up in front of the right heart. That can show up as water retention or shortness of breath — which we address specifically.",
        "With {rap_str} mmHg your RAP is clearly elevated. That signals moderate right-heart load — a key point in therapy planning that we take into account.",
        "The measurement shows {rap_str} mmHg in the right atrium and thus a clear elevation. We will actively support the right heart and aim to optimise fluid balance.",
        "A RAP of {rap_str} mmHg is not yet extreme, but meaningful. It is one of our most important control values — and we use it to shape therapy decisions.",
    ],
)

_add(
    "PX_MEASURE_RAP_SEV",
    "Measurement: RAP severely elevated (>15 mmHg)",
    [
        "The right atrial pressure is markedly elevated at {rap_str} mmHg. That shows the right heart is under major strain — and is a central target for our treatment.",
        "Your RAP of {rap_str} mmHg is severely elevated. That signals relevant right-heart involvement — but it is also an area where consistent treatment demonstrably changes the course of the disease.",
        "With a RAP of {rap_str} mmHg there is marked congestion in front of the right heart. Such values need our full attention — we adjust therapy consistently to take the load off the right heart.",
        "The measurement shows a markedly elevated RAP ({rap_str} mmHg). That is a serious signal — and at the same time a clear criterion for specialist right-heart therapy, close follow-up and often combination approaches.",
        "A RAP of {rap_str} mmHg is well outside the normal range. The right heart needs active relief. Please keep in mind: this value often responds well once the underlying cause is addressed.",
        "With {rap_str} mmHg the RAP is severely elevated — an important marker of right-heart decompensation. We will escalate therapy carefully to bring this value down.",
    ],
)

_add(
    "PX_MEASURE_CI_BORDERLINE",
    "Measurement: CI borderline (2.0–2.5 l/min/m²)",
    [
        "The heart's pumping power (CI {ci_str} l/min/m²) is in the lower normal range. That means there is still reserve — but also that we should monitor trends.",
        "Your cardiac index of {ci_str} l/min/m² is borderline low. In daily life that may feel like quicker fatigue; therapeutically it is an early signal to act.",
        "With a CI of {ci_str} l/min/m² the pumping performance is borderline. We do not need to treat this acutely, but we do factor it into our overall picture.",
        "The CI of {ci_str} l/min/m² is on the lower side. That is a subtle sign that we can act on early — often without immediately introducing new medications.",
        "A cardiac index of {ci_str} l/min/m² sits at the edge of the normal range. We use this information mainly to tune the course of treatment carefully.",
        "With {ci_str} l/min/m² the CI is in the grey zone. Your heart is still delivering a solid output; we stay attentive so that it remains that way.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW_MOD",
    "Measurement: CI moderately reduced (1.8–2.0 l/min/m²)",
    [
        "The heart's pumping power is reduced at CI {ci_str} l/min/m². That can explain exertional intolerance and light-headedness — and is something our therapy can improve.",
        "Your CI of {ci_str} l/min/m² is in the moderately reduced range. That means the right heart currently needs our support — medications that lower resistance and strengthen pump function typically help.",
        "With a CI of {ci_str} l/min/m² the heart's output is noticeably limited. We take this seriously and will plan therapy accordingly — the goal is to actively relieve the heart.",
        "The measurement shows a clearly reduced pumping power ({ci_str} l/min/m²). In daily life this often translates into reduced exercise tolerance; with therapy that can be improved step by step.",
        "A CI of {ci_str} l/min/m² is below the usual range. That is a clear therapy criterion — and at the same time a value that often improves quickly once we unload the right heart.",
        "With {ci_str} l/min/m² the heart's performance is moderately reduced. Please remember: this is a value that typically responds well to medication.",
    ],
)

_add(
    "PX_MEASURE_CI_LOW_SEV",
    "Measurement: CI severely reduced (<1.8 l/min/m²)",
    [
        "The pumping power of the heart is severely reduced at CI {ci_str} l/min/m². That is a clear signal to support the right heart decisively — with close follow-up and, if needed, combination therapy.",
        "Your CI of {ci_str} l/min/m² is critically low. That is serious — but you are now in exactly the setting where specialised PH therapy and supportive measures can make the biggest difference.",
        "With a CI of {ci_str} l/min/m² the heart's output is severely diminished. We therefore aim for fast, careful therapy adjustments — the goal is that you feel more stable again as soon as possible.",
        "The measurement showed a severely reduced pumping performance ({ci_str} l/min/m²). That requires close cardiology accompaniment — and often opens the door to intensified or combined treatment.",
        "A CI of {ci_str} l/min/m² is markedly below the usual range. The good news: we now have clearer evidence of what is needed and can plan therapy accordingly.",
        "With {ci_str} l/min/m² the heart's pumping power is heavily limited. That is a demanding situation — but with the right therapy many patients show marked improvement in the following weeks.",
    ],
)


# ---------------------------------------------------------------------------
# Transitions / connecting prose (v27.4.25+)
# ---------------------------------------------------------------------------

_add(
    "PX_DETAILS_INTRO",
    "Transition to detail section",
    [
        "The following sections explain the findings in more detail.",
        "The next pages go through the findings point by point.",
        "Below we explain each result one by one, at a comfortable pace.",
        "The sections that follow break the most important points down in more depth.",
        "We have laid out the details so that you can read each section in your own time and come back to it whenever you like.",
        "To keep everything as understandable as possible, the next step is a more detailed explanation of the individual findings.",
    ],
)

_add(
    "PX_TRANSPARENCY_INTRO",
    "What this patient report is",
    [
        "This patient report is a plain-language supplement to the medical report. It is meant to support your conversation with your primary care doctor and cardiology team.",
        "This report is meant as a readable summary — something to read at your own pace and to prepare for your next appointment. It does not replace a personal consultation.",
        "This summary puts your findings into everyday language. It is meant to help you understand the connections and to formulate your own questions.",
        "You are reading a patient report — a bridge between the medical report and your own perspective. Anything that stays unclear we can go through together.",
        "This text complements the medical report and is written for you personally. Take your time reading it; we can always go deeper into the details together.",
        "This explanation is written so you can follow it without a medical background. It complements — rather than replaces — the personal conversation with your care team.",
    ],
)

_add(
    "PX_TRANSPARENCY_DATA_NOTE",
    "What the assessment is based on",
    [
        "Important: The assessment is based on the recorded values and information. Not all information is available as structured codes; that is why the personal consultation remains crucial.",
        "A note on the data: the report draws on the values stored in the system. Some aspects of your story can only be put in context during a conversation — that is why direct dialogue remains important.",
        "Transparency: We use the documented measurements and information. Some nuances — for example how you feel during daily activities — can only be assessed fully in conversation.",
        "Limits of this assessment: it is based on structured data and therefore cannot capture every particular of your story. That is why the detailed consultation remains central.",
        "An important caveat: not all relevant information is captured as structured data. Please bring your everyday observations to the next appointment — they help us complete the picture.",
        "For context: this report uses the values captured in the system. Because not everything fits into codes, your own experience remains an important part of the assessment.",
    ],
)

_add(
    "PX_REASON_MISSING",
    "Fallback when no structured reason is recorded",
    [
        "No specific reason for the examination was recorded in a structured format in the dataset.",
        "The exact reason for the examination is not separately documented in the data.",
        "There is no specifically marked examination reason in the record — we will happily add it together during the next conversation.",
        "Nothing detailed is stored in the dataset regarding the reason for the examination; we can document it together when the opportunity arises.",
        "The examination reason is not captured in a structured way — if you wish, we can add it together at the next visit.",
        "There is currently no structured entry for the specific reason. Happy to walk through it with you if any questions come up.",
    ],
)

_add(
    "PX_SUMMARY_MISSING",
    "Fallback when a summary is not yet possible",
    [
        "A concise assessment is currently not possible because key data is missing.",
        "For a reliable summary, several key values are still missing.",
        "We cannot yet give a clear short summary because some important data are still pending.",
        "Before we give you a firm overall assessment, we would like to fill in the missing values.",
        "For a clear summary, some data are currently still missing; we will add them at the next visit.",
        "With the available data we cannot yet write a clean short summary — we will add it once the open values are in.",
    ],
)


# ---------------------------------------------------------------------------
# Follow-up section (v27.4.24+): variants with personal tone
# ---------------------------------------------------------------------------

_add(
    "PX_REASSURE_HIGH_RISK",
    "Context for higher risk",
    [
        "These findings may be concerning. We will discuss the next steps with you calmly, transparently, and without unnecessary alarm.",
        "It is understandable if results like these cause worry. We will walk through the next steps with you step by step, without sugar-coating anything or adding to the burden.",
        "These results are not easy to read. Please know: we will take the time to explain everything clearly and work out a plan with you.",
        "We know findings like this can feel unsettling at first. Our goal is that you fully understand what we see and what is possible from here.",
        "Even though the results are to be taken seriously: you are not alone. We will plan the next steps together with you and leave room for your questions.",
        "Findings like this can raise many questions. Please reach out whenever something is unclear — we will take the time you need.",
    ],
)

_add(
    "PX_EXERCISE_GUIDANCE",
    "Everyday movement guidance",
    [
        "Studies in patients with pulmonary vascular disease show that regular, moderate exercise can improve exercise capacity and quality of life. What matters is not speed, but consistent, well-tolerated regularity.",
        "Exercise is good for the heart and circulation — even with pulmonary hypertension. What matters is a comfortable pace: better short and regular than long and overwhelming.",
        "Regular activity helps you stay fit. A simple guide: if you can still hold a conversation while moving, the intensity is about right.",
        "Many patients benefit from small, regular bouts of activity in their daily routine — for example a 15–20 minute walk each day, if possible without severe shortness of breath.",
        "Studies show: light to moderate exercise, tailored to your personal capacity, can improve quality of life. In the beginning, it often helps to keep the pace low and build up gradually.",
        "Exercise should help, not feel like a fight. A rule of thumb: you should feel refreshed afterwards, not drained. If shortness of breath, dizziness, or chest pressure appear, take a break.",
    ],
)

_add(
    "PX_CONGESTION_PRESENT",
    "Signs of fluid congestion",
    [
        "There are signs of fluid congestion. New swelling or rapid weight gain over a few days should be discussed with your care team promptly.",
        "We currently see signs that fluid is building up in your body. Please pay special attention to your legs, ankles, and abdomen — and contact us if swelling increases.",
        "The findings suggest some congestion. Weighing yourself daily in the morning can help catch changes early: 2 kg within a few days is a signal we want to know about.",
        "There are signs of fluid retention. This is treatable — what matters is that we can react early to any changes. Please reach out if swelling or weight gain become noticeable.",
        "The assessment shows signs of a congestive component. Typical warning signs are increasing swelling of the legs, a larger abdomen, or a sudden rise in weight.",
        "A mild beginning congestion is visible. Please watch for swelling in the feet and legs and for your weight — and contact us quickly if either changes noticeably.",
    ],
)

_add(
    "PX_CONGESTION_WATCH",
    "Preventive note without current congestion",
    [
        "If new swelling, rapid weight gain, or noticeably increasing shortness of breath occur, this should be evaluated early.",
        "Right now we do not see any congestion — that is good. But if new swelling in your legs or abdomen appears, or if your weight goes up markedly within a few days, please reach out.",
        "No congestion is detectable at the moment. For orientation going forward: swelling, rapid weight gain, or increasing shortness of breath are warning signs we want to hear about.",
        "So far there are no signs of fluid retention. If this changes — for example through swelling or rapid weight gain — that is a reason to contact us early.",
        "We currently do not see any congestion. Even so, keep an eye on your weight and possible swelling: you will often notice changes earliest yourself.",
        "No congestion is visible at present. Still, it is worth keeping an eye on weight and swelling — we spot early changes best together.",
    ],
)


_add(
    "PX_CLARITY_MISSING_VALUES",
    "Overall framing when core values are missing",
    [
        "A clear assessment is currently not possible because key measurements are missing.",
        "Because key measurements are missing, we cannot yet clearly classify your findings as normal or abnormal.",
        "Without the most important measurements, it is not yet possible to say whether the picture is overall normal or abnormal.",
        "For a robust assessment we are currently missing some of the core measurements — we will add these once they are available.",
        "A clear assessment is not yet possible because key values are missing; we will complete them.",
        "A definitive evaluation is not possible with the current data — key measurements are still missing.",
    ],
)

_add(
    "PX_CLARITY_NO_PH",
    "Overall framing when there is no PH",
    [
        "Overall assessment: The resting values are largely normal and not typical for pulmonary hypertension at rest.",
        "Overall assessment: Your resting values look largely normal and are not typical of resting pulmonary hypertension.",
        "Overall assessment: At rest there are no clear signs of pulmonary hypertension.",
        "Overall assessment: The measurements at rest combine to a mostly unremarkable picture and are not typical of pulmonary hypertension.",
        "Overall assessment: The picture at rest is unremarkable and rather atypical for pulmonary hypertension.",
        "Overall assessment: The resting values speak against manifest pulmonary hypertension at rest.",
    ],
)

_add(
    "PX_CLARITY_PRECAP",
    "Overall framing for pre-capillary pattern",
    [
        "Overall assessment: The values are abnormal and typical for pressure elevation originating in the pulmonary vessels themselves.",
        "Overall assessment: The values speak for a pressure elevation arising in the pulmonary vessels themselves.",
        "Overall assessment: The picture fits best with a pressure elevation originating in the pulmonary vessels.",
        "Overall assessment: The measurements are abnormal and fit a pattern in which the pulmonary vessels themselves are affected.",
        "Overall assessment: The findings point to a pressure elevation whose cause lies primarily in the pulmonary vessels.",
        "Overall assessment: The picture is consistent with a pre-capillary pressure elevation — that is, pressure originating in the pulmonary vascular bed.",
    ],
)

_add(
    "PX_CLARITY_POSTCAP",
    "Overall framing for left-heart involvement",
    [
        "Overall assessment: The values are abnormal and typical for involvement of the left side of the heart.",
        "Overall assessment: The values indicate that the left side of the heart is involved in the pressure picture.",
        "Overall assessment: The picture fits with involvement of the left ventricle or left atrium.",
        "Overall assessment: The findings suggest that the left side of the heart contributes to the elevated pressure.",
        "Overall assessment: The pressure pattern looks more left-cardiac — we will examine this specifically further.",
        "Overall assessment: The pattern points to an (at least partial) left-cardiac cause of the pressure elevation.",
    ],
)

_add(
    "PX_CLARITY_AMBIGUOUS",
    "Overall framing for an ambiguous pattern",
    [
        "Overall assessment: The values are abnormal; the precise classification is not yet certain and will be further investigated.",
        "Overall assessment: The values are abnormal — exactly where they fit best, we will clarify with additional investigations.",
        "Overall assessment: The findings are abnormal, but the cause cannot yet be unambiguously placed.",
        "Overall assessment: The values stand out; which cause dominates needs to be further tested specifically.",
        "Overall assessment: The values are abnormal, but a clear mechanism does not emerge yet — we are still working on this.",
        "Overall assessment: There are abnormal values, but the exact classification needs further information.",
    ],
)

_add(
    "PX_OVERALL_PRECAP",
    "Overall framing for a pre-capillary pattern",
    [
        "Overall, the findings strongly suggest that the increased resistance primarily originates in the pulmonary vessels themselves. The key question now is why.",
        "The picture fits best with resistance that lies primarily in the pulmonary vessels themselves. Our next question: what is the cause?",
        "Taken together, the findings look like the pressure elevation sits mainly in the pulmonary vessels themselves. The important next step is to clarify the underlying cause.",
        "The overall picture speaks for a so-called pre-capillary component — meaning the resistance originates in the pulmonary vessels. Exactly why we now want to explore further.",
        "The measurements fit a pattern in which the pulmonary vessels themselves contribute substantially. The next step is to search specifically for the cause.",
        "On balance, the pressure burden lies mainly on the side of the pulmonary vessels. Our focus now is on understanding the underlying mechanism.",
    ],
)

_add(
    "PX_OVERALL_POSTCAP",
    "Overall framing for left-heart involvement",
    [
        "Overall, there are indications that the left side of the heart is also involved. The key question now is how large this contribution is and whether the pulmonary circulation itself is also affected.",
        "The picture suggests that the left side of the heart plays a role. How large that contribution is — and whether the pulmonary vessels are also involved — is what we examine next.",
        "The measurements fit with involvement of the left side of the heart. We now clarify how strong this influence is and whether there is an additional pulmonary-vessel component.",
        "Summed up, the values suggest the left heart contributes substantially. It is now important to establish the extent and any additional pulmonary-vessel contribution.",
        "The overall picture shows a role of the left heart in driving the pressure. How strong, and in what combination with the pulmonary vessels, is the next question we clarify.",
        "Overall, left-cardiac involvement seems plausible. The next step is to place the exact contribution and any additional pulmonary-vessel changes.",
    ],
)

_add(
    "PX_OVERALL_AMBIGUOUS",
    "Overall framing for an ambiguous pattern",
    [
        "Overall, classification is possible, but not all aspects are clear-cut. We therefore rely on multiple building blocks (measurements, imaging, exercise capacity).",
        "A classification is possible overall, even if not every detail is fully clear-cut. That is why we use several sources of information at the same time.",
        "Some aspects are not yet definitively clear. A robust classification therefore comes from combining measurements, imaging, and your exercise capacity.",
        "A classification is possible, but it takes several puzzle pieces because no single value explains everything. That is why we combine different findings.",
        "Your situation can be placed overall; not every aspect is unambiguous. For a stable picture, we therefore use multiple sources together.",
        "We can classify your findings even though some sub-questions remain open. We therefore combine measurements, imaging, and your exercise capacity into one overall picture.",
    ],
)

_add(
    "PX_OVERALL_NO_PH",
    "Overall framing when there is no PH at rest",
    [
        "The resting measurements are unremarkable. If symptoms occur mainly during exertion, this can still be further evaluated — some changes only become apparent under stress.",
        "At rest, there is no pulmonary hypertension. If symptoms arise mainly on exertion, we can follow up specifically with exercise testing.",
        "The resting measurement shows no signs of pulmonary hypertension. If your symptoms are mainly on exertion, it may be worth adding exercise-based testing.",
        "Good news: at rest, no pulmonary hypertension is detectable. If you notice symptoms on exertion, we can measure specifically during exercise.",
        "At rest, there is no pressure elevation. Symptoms that appear only on exertion can, if needed, be further classified with a dedicated exercise study.",
        "The resting results are reassuring. If symptoms only appear on exertion, we can gladly discuss additional exercise-based assessments.",
    ],
)

_add(
    "PX_CORE_VALUES_NOTE",
    "Note on how the core values fit together",
    [
        "Important: What matters is the combination of these values and how they change over time. A single number rarely explains symptoms fully.",
        "How these values interact and how they evolve over time says the most — a single figure is seldom the complete key to the situation.",
        "Please note: The core values are like puzzle pieces — only together and over time do they form a meaningful picture.",
        "Every individual number is only part of the overall picture. Only in combination with other findings and the course of your condition can a reliable assessment be made.",
        "For context: We rarely judge individual values in isolation. The overall course and how several measures interact matters more than any single number.",
        "A note: A single figure can worry or reassure without showing the whole picture. We always look at the combination and how things develop.",
    ],
)

_add(
    "PX_ESC_RISK_UNAVAILABLE",
    "Note when the ESC/ERS risk score cannot be calculated",
    [
        "A standardized ESC/ERS risk stratification could not be reliably calculated from the available data.",
        "The standardized ESC/ERS risk assessment cannot be reliably determined with the data currently available.",
        "A formal ESC/ERS risk stratification is currently missing important inputs. We will fill this in as soon as the dataset is complete.",
        "A standardized risk stratification (ESC/ERS) could not yet be established reliably from the current information.",
        "The ESC/ERS risk category could not yet be determined with confidence — we will add it as soon as the data allow.",
        "A numeric ESC/ERS risk stratification is currently not solid. For your assessment, we additionally rely on the overall clinical picture.",
    ],
)

_add(
    "PX_ETIOLOGY_UNCLEAR",
    "Framing when the cause is not yet certain",
    [
        "Which cause is predominant cannot yet be determined with certainty based on the available information.",
        "Identifying the most likely cause is not yet clearly possible with the current data.",
        "Which cause best fits the findings is currently open — we need a little more information to tell.",
        "We cannot yet say with certainty which cause plays the decisive role. Targeted additional tests will help us place things.",
        "The question of cause cannot yet be answered conclusively — a few more pieces will help us sharpen the picture.",
        "Which mechanisms are in the foreground here is not yet finally settled; we will clarify this step by step.",
    ],
)

_add(
    "PX_ETIOLOGY_FURTHER_TESTS",
    "Note on further tests to clarify the cause",
    [
        "Therefore, we are adding further tests. The goal is to identify the main cause and tailor treatment accordingly.",
        "For this reason, we are planning targeted additional tests — so we can find the main cause and match the treatment to it.",
        "We are adding further tests step by step until the cause is clear and the therapy fits your situation.",
        "The following tests are meant to help us complete the picture and plan therapy in a targeted way.",
        "To clarify the question of cause, we align the next diagnostic steps with your situation.",
        "We are adding targeted further diagnostics. The goal: to reliably identify the most important cause and treat it appropriately.",
    ],
)

_add(
    "PX_SHUNT_HINT",
    "Note on a possible shunt between heart chambers",
    [
        "The measurements suggest an additional connection between heart chambers. This can affect blood flow and will therefore be specifically investigated.",
        "The measurements give a hint that there could be an unintended connection between certain heart chambers — we will clarify this specifically.",
        "There are hints of what is called a shunt — an additional connection in the heart. Further tests will show whether this is indeed the case.",
        "The findings raise the question of an additional connection between heart chambers. This is not a diagnosis, but an important point for the next tests.",
        "A possible shunt would be a connection between heart chambers that changes blood flow. The next tests will show whether such a connection is present in you.",
        "Our measurements are consistent with a possible shunt. Before drawing conclusions, we will confirm the picture with further tests.",
    ],
)

_add(
    "PX_LIFESTYLE_HIGH_RISK",
    "Lifestyle note at higher risk",
    [
        "At higher risk, physical activity, fluid intake, and daily routine should be closely coordinated with your care team.",
        "When risk is elevated, it pays to plan exercise, fluid intake, and your daily rhythm together with us in detail.",
        "Especially at higher risk, clearly agreed rules about exertion, fluid intake, and daily routine help — we will work through these with you.",
        "In daily life, small details matter more at higher risk: How much to drink? How to exert yourself? How to plan breaks? We go through this carefully.",
        "At your current risk, it is particularly important that exertion, fluid intake, and daily structure are well aligned. We will support you.",
        "Higher risk does not mean doing nothing. It means deliberately planning movement, fluid intake, and everyday life — gladly step by step with us.",
    ],
)

_add(
    "PX_FOLLOWUP_TIMING_DEFAULT",
    "Fallback when no structured follow-up date is available",
    [
        "The exact timing of the next clinical follow-up will be determined during the treatment discussion.",
        "When exactly the next clinical check-up makes sense will be agreed with you individually during the treatment conversation.",
        "We will set the next follow-up appointment with you personally — based on the course of your condition and your situation.",
        "The right timing for the next check-up will be determined together during your consultation.",
        "The next follow-up appointment is planned individually — feel free to let us know if you have specific wishes.",
        "We will fix a definite follow-up date together in the treatment discussion so it fits your situation.",
    ],
)

_add(
    "PX_INVASIVE_FOLLOWUP_DEFAULT",
    "Fallback for invasive follow-up without fixed date",
    [
        "A repeat invasive assessment will be considered if there is clinical deterioration or if treatment questions arise.",
        "Whether and when another right heart catheterization is sensible is something we decide together when your condition worsens or important therapy decisions are pending.",
        "We will consider another invasive assessment if your condition deteriorates or important therapy decisions need to be made.",
        "Invasive follow-up studies are only planned if the clinical course or therapy decisions make them necessary.",
        "We keep an invasive follow-up in reserve as an option, in case non-invasive tools are not enough.",
        "Whether another right heart catheterization is needed is decided together — usually only when the course or a therapy change requires it.",
    ],
)

_add(
    "PX_OBSERVE_WARNING_SIGNS",
    "Warning signs to watch for until the next appointment",
    [
        "Please monitor shortness of breath, exercise capacity, dizziness/fainting, and possible fluid retention until your next appointment.",
        "Until your next appointment, pay particular attention to increasing shortness of breath, reduced exercise tolerance, dizziness or fainting, and swelling in your legs or abdomen.",
        "Four things are worth watching until your next visit: your breathing, your day-to-day stamina, any feelings of dizziness or fainting, and possible fluid retention.",
        "If shortness of breath, exercise tolerance, dizziness, or swelling change noticeably before the next appointment, please let us know early — better once too often than too late.",
        "You often notice changes earliest yourself: increasing shortness of breath, less energy in daily life, dizziness, or swelling. Feel free to write such signals down and bring them to your next appointment.",
        "Our request until the next appointment: keep an eye on breathing, stamina, dizziness, and any swelling. If changes are marked, please call us.",
    ],
)

_add(
    "PX_NEXT_STEPS_INTRO",
    "Introduction to the list of next steps",
    [
        "The following steps are planned or recommended depending on the overall picture. Where available, a brief explanation is given below as to why this may be relevant in your situation.",
        "Which next steps make sense for you depends on the overall picture. We briefly list the most important recommendations and — where possible — explain their personal relevance.",
        "Here are the recommended or already planned next steps. Where appropriate, we briefly explain why we think this is important in your case.",
        "The list below gathers what we believe makes sense or is already planned for your further care. Where fitting, we add a one-line rationale.",
        "Below you will find what we see as the next sensible steps. Short explanations help to put them in the context of your situation.",
        "So that you can see why we recommend what, we briefly frame the next steps here.",
    ],
)

_add(
    "PX_NO_PH_MEDS_RECORDED",
    "Note when no PH medications are recorded",
    [
        "No structured PH medications are recorded in the dataset for this examination.",
        "No structured pulmonary hypertension medications are currently recorded in the dataset — which does not necessarily mean you are not taking any, only that they are not formally documented.",
        "No structured PH medications are stored for this examination. If you are taking any, please bring your current medication list to your next appointment.",
        "No specific PH medications are currently documented in structured form. The personal consultation is a good moment to review therapy together.",
        "There are no structured PH medications in the system for this finding — we are happy to fill that in together with you.",
        "For the current examination there is no formal PH medication list. We can update this together at the next appointment.",
    ],
)

_add(
    "PX_DOSE_NOTE",
    "Note about medication dosing",
    [
        "If dosing information is missing from the data, it will be clarified during your personal consultation. Please do not change medications on your own.",
        "If dose information is missing for individual medications, we will clarify this at the next appointment. Please never adjust doses on your own initiative.",
        "Missing doses in the overview are often a documentation issue rather than a therapy change. We will discuss them in person — please do not adjust anything on your own.",
        "Some dose entries may not be fully recorded. Please wait for the consultation before making any change.",
        "If doses look incomplete in this overview, we will complete the information during the in-person appointment. Medication changes only in agreement with us.",
        "Please note: gaps in dosing are usually due to data entry. No changes on your own, please — we will clarify open points in person.",
    ],
)

_add(
    "PX_SYNCOPE_WARNING",
    "Warning note for documented syncope",
    [
        "Since fainting or near-fainting has been reported in your case, this is a particularly important warning sign. Please contact your care team promptly if episodes recur.",
        "Your history includes fainting or near-fainting — a warning sign we take seriously. Please let us know promptly if you notice such episodes again.",
        "Fainting episodes are particularly important in conditions like yours. If another episode occurs, please contact us without delay.",
        "Because fainting or near-fainting has already occurred, we pay close attention here: please discuss any new episode with us promptly.",
        "Reported fainting spells are an important warning sign. Please contact us quickly if you feel faint again — even if it is only brief.",
        "Since fainting is part of your documented symptoms, we ask you to report any further episode promptly — by phone, ideally, so we can react quickly.",
    ],
)

_add(
    "PX_DIZZINESS_WARNING",
    "Warning note for documented dizziness",
    [
        "Since dizziness has been reported in your case, it is important to pace physical activity so that near-fainting does not occur. If symptoms increase noticeably, please consult your care team early.",
        "Because dizziness is documented in your history, we recommend pacing physical activity carefully. If the dizziness increases, please contact us in good time.",
        "Dizziness is an important signal when planning your daily life: keep the pace such that you never come close to the edge of fainting.",
        "Since dizziness is recorded, please watch the dosing of effort. If symptoms increase noticeably, contact us early — we will take a look together.",
        "Dizziness is a signal to stay active with care and awareness. If dizziness becomes clearly stronger, please consult us promptly.",
        "Because dizziness is among your symptoms, we advise pacing activities so that you can safely get through the day. Don't let marked increases go unreported — please let us know.",
    ],
)


_add(
    "PX_FOLLOWUP",
    "Follow-up and monitoring",
    [
        "Regular check-ups are an important part of your treatment. They help us detect changes early and adjust your therapy if needed.",
        "We plan follow-up visits at regular intervals. These include blood tests, echocardiography, and possibly exercise tests. This way we keep track of your situation.",
        "Follow-up care is just as important as the initial assessment. Only through regular monitoring can we ensure that the treatment is effective and that no new problems arise.",
        "Between appointments you are not on your own: please contact us if your symptoms change, new symptoms appear, or you have questions. We are here for you.",
        "The monitoring schedule is tailored to you individually. During some phases, closer follow-up is advisable; in stable phases the intervals can be longer. We will discuss this together.",
        "Your participation is an important part of follow-up care: please take your medications regularly, observe your exercise tolerance, and attend scheduled appointments.",
    ],
)


# ---------------------------------------------------------------------------
# Bridging phrases (inter-block transitions, v27.4.26+)
# ---------------------------------------------------------------------------
# Short connector sentences that smooth transitions between thematically
# related findings. They carry no new clinical information; they give the
# text a human rhythm so the report doesn't feel like a bulleted list of
# standalone sentences. Variant selection is randomised deterministically
# per case.

_add(
    "PX_BRIDGE_ADD",
    "Bridge: additional parallel finding",
    [
        "The next measurement fits right in.",
        "In addition, another key number completes the picture:",
        "A second value rounds out the picture here.",
        "There is one more core value from the examination:",
        "On the same note, the next measurement reads as follows:",
        "A related value joins in here:",
    ],
)

_add(
    "PX_BRIDGE_CONTRAST",
    "Bridge: contrasting / complementary finding",
    [
        "On the other side, the left heart is worth a look.",
        "At the same time, another value behaves differently, which is useful:",
        "Balancing that, there is a more reassuring finding:",
        "While one value is elevated, another gives us additional orientation:",
        "To balance the picture, let's look at the opposite side:",
        "Before going deeper, a brief glance at the other side of the measurement:",
    ],
)

_add(
    "PX_BRIDGE_CONSEQUENCE",
    "Bridge: causal / consequential",
    [
        "This leads us to the following assessment:",
        "What this means for your heart is shown in the next measurement:",
        "The next value reveals how much the right heart is being taxed by this:",
        "What this implies for the pumping performance, we see here:",
        "The knock-on effect on the circulation becomes visible in the next value:",
        "Whether and how the heart responds can be read from the following value:",
    ],
)

_add(
    "PX_BRIDGE_PUMP_FOCUS",
    "Bridge: switching focus to pump output (CI/CO)",
    [
        "From pressures we now turn to the heart's pumping performance.",
        "Beyond pressure, what matters is how much blood the heart actually delivers.",
        "It's not only pressure — flow tells us something too:",
        "The next thing to look at is the actual output of your heart.",
        "How well your heart is pumping despite this load is shown next:",
        "Now to the question of how much blood your heart moves per minute.",
    ],
)

_add(
    "PX_BRIDGE_RIGHT_HEART",
    "Bridge: switching focus to right heart / venous side",
    [
        "A brief look at the right side of the heart rounds out the picture.",
        "How strongly the right heart notices the extra work is shown by one more value:",
        "The next value tells us how much strain the right side of the heart is under right now.",
        "Moving on to the right heart — it stands centre-stage in pulmonary hypertension.",
        "How far the pressure backs up into the right atrium is described by the following value:",
        "The pressure in the right atrium also provides important information:",
    ],
)

_add(
    "PX_BRIDGE_BIOMARKER",
    "Bridge: switching to lab marker",
    [
        "Alongside the catheter values, one blood marker is important.",
        "A quick look at the laboratory side adds to the picture:",
        "A blood value adds another piece of information:",
        "A laboratory value helps to complete the picture:",
        "Paired with the hemodynamic values is an important laboratory parameter:",
        "Finally a look at the blood — it shows how much the heart is currently taxed.",
    ],
)

_add(
    "PX_BRIDGE_SECTION_CLOSE",
    "Bridge: closing a section",
    [
        "Taken together, a clear picture emerges.",
        "In summary, the measurement can be placed as follows:",
        "At the core, these values point to the following:",
        "This is how the overall picture of this examination forms.",
        "Taken together, these values form the basis for the next steps.",
        "From the sum of these measurements a coherent picture reads through.",
    ],
)

_add(
    "PX_BRIDGE_TO_CAUSES",
    "Bridge: transition to causes",
    [
        "Which causes underlie this is the next important question.",
        "Next we ask: where do these changes come from?",
        "That brings the question of the underlying cause to the foreground.",
        "What might lie behind these values we examine in detail next.",
        "The next step is to understand why your values look the way they do.",
        "From measurements we now step further — to looking for the cause.",
    ],
)

_add(
    "PX_BRIDGE_TO_THERAPY",
    "Bridge: transition to therapy",
    [
        "What this means for your treatment is summarised in the following.",
        "Based on this assessment, the following treatment strategy emerges:",
        "From this we derive the next therapeutic steps:",
        "How we respond is described in the next section:",
        "This also answers which therapy is sensible for you.",
        "Which treatment fits your situation we explain now:",
    ],
)

_add(
    "PX_BRIDGE_TO_EVERYDAY",
    "Bridge: transition to daily life",
    [
        "For your daily life, this concretely means the following:",
        "What this means in practice we now translate into everyday tips:",
        "From theory to daily life: these pointers will help you through the day.",
        "So that you can use what you have read at home, a few anchors:",
        "Translated into everyday language, this means:",
        "How you can contribute yourself is shown by the pointers below:",
    ],
)
