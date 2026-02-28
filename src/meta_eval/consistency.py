"""
Meta-evaluation: testing the evaluator's reliability.

Approach: Injected error detection - create synthetic notes with known errors,
see if our pipeline catches them. If it misses a deliberate fabrication,
we know our eval has blind spots.

The test suite includes:
- 6 hallucination cases (fabrication, negation, dosage, family history,
  temporal, contextual distortion)
- 6 omission cases (allergy, symptom, surgical history, medication,
  social history, red flag symptom)
- 3 clean-note controls (false positive checks - correct notes that
  should NOT be flagged)

Why not Cohen's kappa? Kappa measures inter-rater agreement between two
distinct raters. Running the same LLM judge twice is not inter-rater
reliability - it's a reproducibility check. At temperature=0, it's trivially
deterministic; at temperature>0, it measures sampling noise, not judgment
quality. The injected error tests directly answer the trust question:
"Does this judge catch known problems, and does it avoid false alarms?"
"""

from src.models import MetaEvalResult
from src.llm_judge.judge import evaluate_note


# Synthetic notes with deliberately injected errors for validation
INJECTED_ERROR_TESTS = [
    {
        "name": "fabricated_medication",
        "transcript": "Doctor: What medications are you currently taking? Patient: I take lisinopril 10mg daily for my blood pressure. Doctor: Any other medications? Patient: No, that's it.",
        "soap_note": "S: Patient reports taking lisinopril 10mg daily and metformin 500mg twice daily for blood pressure management.\nO: Vitals stable.\nA: Hypertension, well-controlled.\nP: Continue current medications.",
        "expected_finding": "hallucination",
        "expected_text": "metformin",
        "description": "Note fabricates metformin - patient only takes lisinopril",
    },
    {
        "name": "negation_reversal",
        "transcript": "Doctor: Any chest pain? Patient: No, no chest pain at all. Doctor: Shortness of breath? Patient: No, I feel fine breathing-wise.",
        "soap_note": "S: Patient reports chest pain and shortness of breath.\nO: Vitals within normal limits.\nA: Chest pain, etiology to be determined.\nP: Order EKG and chest X-ray.",
        "expected_finding": "hallucination",
        "expected_text": "chest pain",
        "description": "Note says patient reports chest pain, but patient explicitly denied it",
    },
    {
        "name": "missing_critical_allergy",
        "transcript": "Doctor: Any allergies? Patient: Yes, I'm severely allergic to penicillin. I had anaphylaxis last time. Doctor: That's important, we'll make sure to note that.",
        "soap_note": "S: Patient presents for routine follow-up.\nO: Vitals stable. No acute distress.\nA: Routine health maintenance.\nP: Schedule follow-up in 6 months.",
        "expected_finding": "omission",
        "expected_text": "penicillin",
        "description": "Critical penicillin allergy with anaphylaxis history completely omitted",
    },
    {
        "name": "wrong_dosage",
        "transcript": "Doctor: What dose of metoprolol are you on? Patient: 25 milligrams twice a day. Doctor: And that's been working well? Patient: Yes, my heart rate has been good.",
        "soap_note": "S: Patient taking metoprolol 250mg twice daily with good heart rate control.\nO: HR 72, regular.\nA: Rate-controlled atrial fibrillation.\nP: Continue current regimen.",
        "expected_finding": "hallucination",
        "expected_text": "250mg",
        "description": "Note says 250mg but transcript says 25mg - 10x dosage error",
    },
    {
        "name": "fabricated_family_history",
        "transcript": "Doctor: Any family history of heart disease? Patient: No, my parents are both healthy. Doctor: Good to hear.",
        "soap_note": "S: Patient reports family history of coronary artery disease in father, who had MI at age 55.\nO: Normal exam.\nA: Low cardiovascular risk.\nP: Continue preventive measures.",
        "expected_finding": "hallucination",
        "expected_text": "family history of coronary artery disease",
        "description": "Fabricated family history - patient said parents are healthy",
    },
    {
        "name": "temporal_distortion",
        "transcript": "Doctor: When did the symptoms start? Patient: About two weeks ago. Doctor: And they've been getting better? Patient: Yes, much better now, almost gone.",
        "soap_note": "S: Patient reports acute onset of symptoms 2 days ago, progressively worsening.\nO: Appears uncomfortable.\nA: Acute illness, worsening.\nP: Urgent workup needed.",
        "expected_finding": "hallucination",
        "expected_text": "2 days ago",
        "description": "Note says 2 days (acute, worsening) but transcript says 2 weeks (improving)",
    },
    {
        "name": "omitted_symptom",
        "transcript": "Doctor: Tell me about your symptoms. Patient: I've had this terrible headache for 3 days, and I noticed some vision changes too - like blurry vision in my left eye. Doctor: Any nausea? Patient: Yes, quite a bit.",
        "soap_note": "S: Patient reports 3-day history of headache with nausea.\nO: Neuro exam grossly normal.\nA: Tension headache.\nP: OTC analgesics, return if worsening.",
        "expected_finding": "omission",
        "expected_text": "vision changes",
        "description": "Blurry vision in left eye is clinically significant and omitted",
    },
    {
        "name": "correct_note",
        "transcript": "Doctor: What brings you in today? Patient: I've had a sore throat for about 3 days now. It's been getting worse. Doctor: Any fever? Patient: Yes, I've had a low-grade fever, around 100. I checked it this morning. Doctor: Any cough or runny nose? Patient: A little bit of a runny nose but no cough. Doctor: Any difficulty swallowing? Patient: It hurts to swallow but I can still eat and drink. Doctor: Have you been around anyone who's been sick? Patient: My daughter had strep last week actually. Doctor: Okay, let me take a look. Open wide for me. I can see your throat is red but I don't see any white patches or exudates. Your tonsils are a bit swollen. Let me feel your neck - you have some tender lymph nodes on both sides. Doctor: I'm going to do a rapid strep test. Let me also check your vitals. Your temperature is 100.1, heart rate 82, blood pressure 118 over 74. Patient: Do you think it's strep? Doctor: We'll see what the test shows. The rapid strep came back negative. Given the viral symptoms with the runny nose and the negative strep test, this is most likely viral pharyngitis. Patient: What should I do for it? Doctor: Rest, plenty of fluids, you can take ibuprofen or acetaminophen for the pain and fever. Warm salt water gargles can help too. If it gets worse or doesn't improve in about 5 to 7 days, come back and we'll reevaluate.",
        "soap_note": "S: Patient presents with 3-day history of sore throat, progressively worsening. Associated low-grade fever (100F reported at home), mild rhinorrhea, and odynophagia. No cough. Reports sick contact - daughter diagnosed with strep throat last week. Patient is able to tolerate oral intake.\nO: Temp 100.1F, HR 82, BP 118/74. Oropharynx erythematous without exudates. Tonsils mildly enlarged bilaterally. Bilateral tender anterior cervical lymphadenopathy. Rapid strep antigen test negative.\nA: Acute viral pharyngitis. Negative rapid strep with viral features (rhinorrhea, absence of exudates) supports viral etiology. Sick contact with strep-positive individual noted but clinical presentation and testing favor viral cause.\nP: Supportive care with rest, increased fluid intake, and analgesics (ibuprofen or acetaminophen) for pain and fever management. Salt water gargles as needed. Return if symptoms worsen or fail to improve within 5-7 days for reevaluation and possible throat culture.",
        "expected_finding": "none",
        "expected_text": "",
        "description": "Accurate pharyngitis note with full exam and workup - should NOT flag hallucinations",
    },
    {
        "name": "correct_note_diabetes",
        "transcript": "Doctor: Good to see you again. How's your blood sugar been since our last visit? Patient: It's been a lot better since I started the metformin. I've been checking it every morning and it's usually between 110 and 130 fasting. Doctor: That's great improvement. What dose are you on? Patient: 500mg twice a day, with breakfast and dinner. Doctor: And your last A1C was 7.2, which was down from 8.1. Any side effects from the medication? Patient: I had some stomach upset at first, maybe the first two weeks, but it went away after that. Doctor: Good. Are you still following the diet plan we discussed? Patient: Yes, I've been cutting back on carbs and trying to walk 30 minutes most days. Doctor: Excellent. Let me check your vitals. Blood pressure is 124 over 78, heart rate 76, weight is 198 pounds, down from 205 last visit. That's good progress. Let me check your feet - sensation is intact, no lesions, pulses are good. Patient: When should I get my A1C checked again? Doctor: Let's recheck it in 3 months. I want to make sure we're still trending in the right direction. Keep up the good work with the diet and exercise.",
        "soap_note": "S: Follow-up for type 2 diabetes mellitus. Patient reports improved glycemic control on metformin 500mg BID (with meals). Home fasting glucose readings 110-130 mg/dL. Initial GI side effects (first 2 weeks) have resolved. Patient adhering to dietary modifications (carbohydrate reduction) and exercise program (walking 30 minutes daily). Previous A1C 8.1, most recent 7.2.\nO: BP 124/78, HR 76, Weight 198 lbs (down from 205 at last visit, 7 lb loss). Diabetic foot exam: sensation intact to monofilament bilaterally, no skin breakdown or lesions noted, dorsalis pedis and posterior tibial pulses palpable bilaterally.\nA: Type 2 diabetes mellitus, improving on current regimen. A1C trending down (8.1 to 7.2) with combined pharmacotherapy and lifestyle modifications. Weight loss of 7 lbs consistent with dietary and exercise changes.\nP: Continue metformin 500mg BID with meals. Continue current diet and exercise program. Recheck A1C in 3 months to assess continued progress. Routine diabetic foot exam performed today, no concerns. Return visit in 3 months.",
        "expected_finding": "none",
        "expected_text": "",
        "description": "Accurate diabetes follow-up with exam findings and labs - should NOT flag hallucinations",
    },
    {
        "name": "correct_note_hypertension",
        "transcript": "Doctor: How's the blood pressure medication been working for you? Patient: Good, I've been taking the lisinopril 10mg every morning like you said. Doctor: Any side effects? Any dizziness or cough? Patient: No, no problems at all. I feel fine. Doctor: Have you been checking your blood pressure at home? Patient: Yes, it's usually around 125 to 130 on top and 80 to 85 on the bottom. Doctor: That's well controlled. Let me get your vitals today. Blood pressure is 128 over 82, heart rate 72, respiratory rate 16. Weight is 182. Let me listen to your heart and lungs. Heart sounds regular, no murmurs. Lungs are clear. Any swelling in your legs or ankles? Patient: No, nothing like that. Doctor: Are you still limiting your salt intake? Patient: Yes, I've been cooking at home more and reading labels. Doctor: Good. Any chest pain, shortness of breath, or headaches? Patient: No, none of that. Doctor: Everything looks good. We'll continue the lisinopril at the same dose. Let's get some routine labs - a basic metabolic panel to check your kidney function and potassium since you're on an ACE inhibitor, and a lipid panel. Follow up in 6 months unless any issues come up.",
        "soap_note": "S: Follow-up for essential hypertension. Patient reports good tolerance of lisinopril 10mg daily. Denies dizziness, cough, chest pain, shortness of breath, headaches, or lower extremity edema. Home blood pressure readings averaging 125-130/80-85 mmHg. Patient adhering to low-sodium diet with home cooking and label reading.\nO: BP 128/82, HR 72, RR 16, Weight 182 lbs. Cardiovascular exam: regular rate and rhythm, no murmurs, rubs, or gallops. Lungs clear to auscultation bilaterally. No peripheral edema.\nA: Essential hypertension, well-controlled on current medication. Home and office readings at goal. No evidence of end-organ damage or medication side effects. ACE inhibitor well tolerated without cough.\nP: Continue lisinopril 10mg daily. Order basic metabolic panel (monitor renal function and potassium on ACE inhibitor) and fasting lipid panel. Reinforce dietary sodium restriction. Follow-up in 6 months. Return sooner if blood pressure elevations, new symptoms, or medication side effects develop.",
        "expected_finding": "none",
        "expected_text": "",
        "description": "Accurate hypertension follow-up with full vitals and exam - should NOT flag hallucinations",
    },
    {
        "name": "contextual_distortion",
        "transcript": "Doctor: How's your diabetes management? Patient: My A1C was 6.8 last month, so my doctor was happy with that. Doctor: Great, that's well-controlled.",
        "soap_note": "S: Patient reports poorly controlled diabetes with A1C of 6.8.\nO: No acute findings.\nA: Uncontrolled type 2 diabetes.\nP: Increase metformin dose.",
        "expected_finding": "hallucination",
        "expected_text": "poorly controlled",
        "description": "A1C 6.8 is well-controlled - note distorts this as 'poorly controlled'",
    },
    {
        "name": "omitted_surgical_history",
        "transcript": "Doctor: Any prior surgeries? Patient: I had my appendix out when I was 15, and a knee replacement on my right side about 5 years ago. Doctor: How's the knee doing? Patient: Great, no issues.",
        "soap_note": "S: Patient reports history of appendectomy in adolescence.\nO: Well-appearing, no acute distress.\nA: Routine follow-up.\nP: Continue annual visits.",
        "expected_finding": "omission",
        "expected_text": "knee replacement",
        "description": "Right knee replacement is significant surgical history, omitted from note",
    },
    {
        "name": "omitted_current_medication",
        "transcript": "Doctor: What medications are you taking? Patient: I'm on warfarin for my afib, and I take amlodipine for blood pressure, and omeprazole for my stomach. Doctor: What dose of warfarin? Patient: 5mg daily, and my INR was 2.3 last week.",
        "soap_note": "S: Patient with atrial fibrillation on warfarin 5mg daily, INR 2.3. Also takes amlodipine for hypertension.\nO: Vitals stable.\nA: Afib, well-anticoagulated.\nP: Continue warfarin, recheck INR in 4 weeks.",
        "expected_finding": "omission",
        "expected_text": "omeprazole",
        "description": "Omeprazole omitted from medication list - important for drug interactions with warfarin",
    },
    {
        "name": "omitted_social_history",
        "transcript": "Doctor: Do you smoke? Patient: I quit about 6 months ago, but I smoked a pack a day for 20 years. Doctor: That's a 20 pack-year history. Good that you quit. Any alcohol? Patient: No, I stopped drinking 2 years ago. I was drinking heavily before that.",
        "soap_note": "S: Former smoker, quit 6 months ago, 20 pack-year history.\nO: Lungs clear bilaterally.\nA: Tobacco use disorder in remission.\nP: Continue smoking cessation support.",
        "expected_finding": "omission",
        "expected_text": "drinking",
        "description": "Prior heavy alcohol use omitted - relevant for liver function, medication choices, and screening",
    },
    {
        "name": "omitted_red_flag_symptom",
        "transcript": "Doctor: Tell me about your back pain. Patient: It started about a week ago, just lower back. Doctor: Any numbness or tingling? Patient: Yes, I've noticed tingling going down my left leg. Doctor: Any trouble with bladder or bowel control? Patient: Actually yes, I've had some difficulty urinating the last couple days.",
        "soap_note": "S: Patient reports 1-week history of lower back pain with left leg tingling.\nO: Positive straight leg raise on left. Sensation intact.\nA: Lumbar radiculopathy.\nP: Physical therapy referral, NSAIDs.",
        "expected_finding": "omission",
        "expected_text": "difficulty urinating",
        "description": "Urinary retention with back pain is a red flag for cauda equina syndrome - critical omission",
    },
]


def run_meta_evaluation() -> MetaEvalResult:
    """
    Run meta-evaluation: injected error detection.

    Tests the judge against 15 synthetic notes with known errors to validate
    detection capability. Includes 3 clean-note controls to measure false
    positive rate.

    Test breakdown:
    - 6 hallucination cases: fabrication, negation, dosage, family history,
      temporal distortion, contextual distortion
    - 6 omission cases: allergy, symptom, surgical history, medication,
      social history, red flag symptom
    - 3 clean-note controls: accurate notes that should not be flagged

    Returns:
        MetaEvalResult with detection rate and per-test details
    """
    details = []
    errors_total = 0
    errors_caught = 0

    for test in INJECTED_ERROR_TESTS:
        result = evaluate_note(
            transcript=test["transcript"],
            soap_note=test["soap_note"],
        )

        if test["expected_finding"] == "none":
            # This is the control - should NOT flag critical issues
            false_alarms = len([
                h for h in result.hallucinations
                if h.severity in ("critical", "major")
            ])
            if false_alarms == 0:
                errors_caught += 1
                details.append(f"  PASS [{test['name']}]: Correctly identified clean note (no false alarms)")
            else:
                details.append(f"  FAIL [{test['name']}]: False alarm on clean note ({false_alarms} flags)")
            errors_total += 1
            continue

        expected = test["expected_text"].lower()
        caught = False

        if test["expected_finding"] == "hallucination":
            for h in result.hallucinations:
                if expected in h.note_text.lower() or expected in h.explanation.lower():
                    caught = True
                    break

        elif test["expected_finding"] == "omission":
            for o in result.omissions:
                if expected in o.transcript_text.lower() or expected in o.explanation.lower():
                    caught = True
                    break

        errors_total += 1
        if caught:
            errors_caught += 1
            details.append(f"  PASS [{test['name']}]: Detected {test['expected_finding']} - {test['description']}")
        else:
            details.append(f"  FAIL [{test['name']}]: Missed {test['expected_finding']} - {test['description']}")

    detection_rate = errors_caught / errors_total if errors_total > 0 else 0.0

    return MetaEvalResult(
        injected_error_detection_rate=detection_rate,
        injected_errors_total=errors_total,
        injected_errors_caught=errors_caught,
        details=details,
    )
