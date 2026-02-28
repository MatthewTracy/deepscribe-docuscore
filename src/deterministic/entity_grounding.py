"""
Entity grounding checker.

Extracts key clinical entities from the SOAP note and verifies each one
appears in the source transcript. Entities that appear in the note but
NOT in the transcript are potential hallucinations flagged for the LLM
judge to investigate deeper.

Uses scispacy (en_core_sci_md) for biomedical NER - extracts diseases,
medications, procedures, and lab values with better coverage than regex.
Falls back to regex patterns if scispacy is unavailable.

Synonym matching uses a curated clinical dictionary covering abbreviations,
lay-to-clinical term mappings, and common medical synonyms.
"""

import re
import logging

from src.models import EntityGroundingResult

logger = logging.getLogger(__name__)

# Load scispacy model once at module level.
# If scispacy or the model isn't installed, fall back to regex-only extraction.
_nlp = None
try:
    import spacy
    _nlp = spacy.load("en_core_sci_md")
except Exception as e:
    logger.warning(f"scispacy model not available, using regex-only extraction: {e}")

# Entities scispacy extracts that don't need transcript grounding.
# Two categories:
# 1. Generic non-clinical words (patient, daily, etc.)
# 2. O/A/P section terms - clinical findings, diagnoses, and plan items
#    that are the doctor's professional additions, not patient-reported.
#    These are expected to NOT appear in the transcript.
_STOP_ENTITIES = frozenset({
    # Generic non-clinical
    "patient", "patients", "doctor", "physician", "history", "daily",
    "twice", "once", "today", "week", "weeks", "month", "months",
    "year", "years", "day", "days", "time", "times", "follow-up",
    "follow up", "visit", "exam", "examination", "review", "noted",
    "reports", "reports taking", "denies", "presents", "states", "complains",
    "left", "right", "bilateral", "mild", "moderate", "severe",
    "acute", "chronic", "stable", "normal", "abnormal",
    "symptoms", "symptom", "treatment", "diagnosis", "condition",
    "medical", "clinical", "significant", "unremarkable",

    # Physical exam findings (O section - doctor's observation)
    "erythematous", "exudates", "tenderness", "swollen", "distended",
    "clear", "intact", "supple", "afebrile", "oriented", "alert",
    "nontender", "non-tender", "soft", "regular", "irregular",
    "diminished", "auscultation", "palpation", "percussion",
    "murmur", "rales", "rhonchi", "wheezing",
    "oropharynx", "oropharynx erythematous", "tympanic",
    "conjunctiva", "sclera", "mucosa", "pharynx",
    "lungs clear", "lungs clear bilaterally", "bowel sounds",
    "no acute distress", "well-appearing", "well appearing",
    "grossly normal", "within normal limits", "wnl",
    "sensation", "sensation intact", "no ulcers", "ulcers",
    "foot exam", "foot examination", "skin exam",
    "well-nourished", "well nourished", "well-developed",
    "cooperative", "comfortable", "distress",
    "obese", "obesity", "overweight",  # clinical assessment from BMI

    # Plan-specific items
    "diabetic eye exam", "eye exam", "recheck", "recheck a1c",
    "screening", "preventive", "counseling", "education",
    "continue", "discontinue", "taper", "titrate", "adjust",
    "prn", "as needed", "bid", "tid", "qid", "qd", "qhs",
    "bmi", "bmi over 30", "bmi over 25",

    # Clinical assessments (A section - doctor's judgment)
    "well-controlled", "well controlled", "poorly controlled",
    "uncontrolled", "viral", "bacterial", "benign", "malignant",
    "idiopathic", "etiology", "differential", "prognosis",
    "exacerbation", "remission", "recurrence", "progression",

    # Plan items (P section - doctor's orders)
    "supportive care", "conservative management", "return",
    "follow up", "referral", "workup", "monitoring",
    "rest", "fluids", "ice", "elevation", "reassurance",
    "worsening", "improvement",
    "reassess", "reevaluate", "recheck",
})


def extract_medical_entities(text: str) -> list[str]:
    """
    Extract medical entities using scispacy biomedical NER.

    Filters out noisy non-clinical entities and short tokens.
    Falls back to regex patterns if scispacy fails.
    """
    if _nlp is None:
        return _extract_entities_regex(text)

    entities = set()

    try:
        doc = _nlp(text)
        for ent in doc.ents:
            entity_text = ent.text.strip().lower()
            # Filter out non-clinical noise
            if len(entity_text) <= 2:
                continue
            if entity_text in _STOP_ENTITIES:
                continue
            # Also filter entities whose base term (without trailing numbers/values)
            # is a stop word, e.g. "bmi 31.2" → base "bmi" is in stop list
            base_term = re.sub(r"[\s:=]*[\d./%]+.*$", "", entity_text).strip()
            if base_term and base_term in _STOP_ENTITIES:
                continue
            # Filter pure numbers
            if re.match(r"^[\d./%]+$", entity_text):
                continue
            entities.add(entity_text)
    except Exception as e:
        logger.warning(f"scispacy extraction failed, using regex fallback: {e}")
        return _extract_entities_regex(text)

    # Supplement with regex for drug+dosage patterns scispacy sometimes misses
    drug_dose = re.compile(
        r"\b([A-Za-z][\w-]+)\s+(\d+\s*(?:mg|mcg|ml|units?|g)\b)",
        re.IGNORECASE,
    )
    for match in drug_dose.finditer(text):
        entities.add(match.group().lower().strip())

    # Supplement with vital sign patterns
    vital_pattern = re.compile(
        r"\b((?:blood\s+pressure|BP|heart\s+rate|HR|temperature|temp|"
        r"respiratory\s+rate|RR|SpO2|O2\s+sat|BMI|weight|height)"
        r"\s*[:=]?\s*[\d./]+(?:\s*(?:mmHg|bpm|[°]?[CF]|%|kg|lbs?|cm|in))?)\b",
        re.IGNORECASE,
    )
    for match in vital_pattern.finditer(text):
        entities.add(match.group().lower().strip())

    # Supplement with lab value patterns
    lab_pattern = re.compile(
        r"\b((?:A1[Cc]|hemoglobin|hgb|WBC|RBC|platelet|creatinine|BUN|glucose|"
        r"cholesterol|LDL|HDL|triglyceride|TSH|sodium|potassium|GFR|eGFR|ALT|"
        r"AST|INR|albumin)"
        r"\s*(?:of|:|\s|=)?\s*[\d.]+(?:\s*(?:mg/dL|mmol/L|%|g/dL|mEq/L|U/L))?)",
        re.IGNORECASE,
    )
    for match in lab_pattern.finditer(text):
        entities.add(match.group().lower().strip())

    # Final stop-word filter across ALL entities (scispacy + regex)
    filtered = set()
    for entity_text in entities:
        if entity_text in _STOP_ENTITIES:
            continue
        base_term = re.sub(r"[\s:=]*[\d./%]+.*$", "", entity_text).strip()
        if base_term and base_term in _STOP_ENTITIES:
            continue
        filtered.add(entity_text)

    return list(filtered)


def _extract_entities_regex(text: str) -> list[str]:
    """Regex-only fallback if scispacy is unavailable."""
    entities = set()

    # Medication mentions with context
    med_pattern = re.compile(
        r"(?:[\w-]+\s+){0,2}"
        r"(?:prescribed|taking|started?|administer|continued?|medication|dose)"
        r"(?:\s+[\w-]+){0,4}",
        re.IGNORECASE,
    )
    for match in med_pattern.finditer(text):
        phrase = match.group().strip()
        if len(phrase) > 8:
            entities.add(phrase.lower())

    # Drug name + dosage
    drug_dose = re.compile(
        r"\b([A-Za-z][\w-]+)\s+(\d+\s*(?:mg|mcg|ml|units?|g)\b)",
        re.IGNORECASE,
    )
    for match in drug_dose.finditer(text):
        entities.add(match.group().lower().strip())

    # Vital signs
    vital_pattern = re.compile(
        r"\b((?:blood\s+pressure|BP|heart\s+rate|HR|temperature|temp|"
        r"respiratory\s+rate|RR|SpO2|O2\s+sat|BMI|weight|height)"
        r"\s*[:=]?\s*[\d./]+(?:\s*(?:mmHg|bpm|[°]?[CF]|%|kg|lbs?|cm|in))?)",
        re.IGNORECASE,
    )
    for match in vital_pattern.finditer(text):
        entities.add(match.group().lower().strip())

    # Lab values
    lab_pattern = re.compile(
        r"\b((?:A1[Cc]|hemoglobin|hgb|WBC|RBC|platelet|creatinine|BUN|glucose|"
        r"cholesterol|LDL|HDL|triglyceride|TSH|sodium|potassium|GFR|eGFR|ALT|"
        r"AST|INR|albumin)"
        r"\s*(?:of|:|\s|=)?\s*[\d.]+(?:\s*(?:mg/dL|mmol/L|%|g/dL|mEq/L|U/L))?)",
        re.IGNORECASE,
    )
    for match in lab_pattern.finditer(text):
        entities.add(match.group().lower().strip())

    # Diagnosis mentions
    dx_pattern = re.compile(
        r"\b(?:diagnosed?\s+with|assessment|impression|history\s+of)"
        r"\s+([\w\s,'-]+?)(?:\.|,\s*(?:and|with|secondary)|$)",
        re.IGNORECASE,
    )
    for match in dx_pattern.finditer(text):
        dx = match.group(1).strip()
        if 5 < len(dx) < 100:
            entities.add(dx.lower())

    return list(entities)


def normalize_for_comparison(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Medical synonym dictionary for entity grounding.
#
# Covers three categories that cause false "ungrounded" flags:
# 1. Abbreviations ↔ full terms (HTN ↔ hypertension)
# 2. Lay terms ↔ clinical terms (stomach ache ↔ abdominal pain)
# 3. Procedure names (knee replacement ↔ total knee arthroplasty)
#
# In production, this would be replaced by UMLS concept normalization
# via scispacy entity linking. The dictionary approach is used here
# because it's transparent, correct by construction, and the LLM judge
# (Layer 2) catches what the dictionary misses.
# ---------------------------------------------------------------------------
MEDICAL_SYNONYMS = {
    # Abbreviations ↔ full terms
    "htn": ["hypertension", "high blood pressure", "elevated blood pressure"],
    "hypertension": ["htn", "high blood pressure", "blood pressure"],
    "dm": ["diabetes mellitus", "diabetes", "diabetic"],
    "dm2": ["type 2 diabetes", "t2dm", "type ii diabetes"],
    "t2dm": ["type 2 diabetes", "dm2", "type ii diabetes", "diabetes mellitus type 2"],
    "type 2 diabetes mellitus": ["diabetes", "diabetic", "dm", "dm2", "t2dm", "type 2 diabetes"],
    "diabetes mellitus": ["diabetes", "diabetic", "dm", "sugar diabetes"],
    "diabetes": ["diabetes mellitus", "dm", "diabetic"],
    "chf": ["congestive heart failure", "heart failure"],
    "heart failure": ["chf", "congestive heart failure"],
    "copd": ["chronic obstructive pulmonary disease"],
    "chronic obstructive pulmonary disease": ["copd"],
    "mi": ["myocardial infarction", "heart attack"],
    "myocardial infarction": ["mi", "heart attack"],
    "cva": ["cerebrovascular accident", "stroke"],
    "stroke": ["cva", "cerebrovascular accident"],
    "afib": ["atrial fibrillation", "a fib", "a-fib"],
    "atrial fibrillation": ["afib", "a fib", "a-fib"],
    "ckd": ["chronic kidney disease", "renal disease"],
    "chronic kidney disease": ["ckd"],
    "gerd": ["gastroesophageal reflux", "acid reflux", "reflux disease"],
    "cad": ["coronary artery disease", "coronary disease"],
    "coronary artery disease": ["cad"],
    "dvt": ["deep vein thrombosis", "deep venous thrombosis"],
    "pe": ["pulmonary embolism"],
    "pulmonary embolism": ["pe"],
    "sob": ["shortness of breath", "dyspnea"],
    "shortness of breath": ["sob", "dyspnea"],
    "dyspnea": ["shortness of breath", "sob"],
    "uri": ["upper respiratory infection"],
    "uti": ["urinary tract infection"],
    "bph": ["benign prostatic hyperplasia", "enlarged prostate"],
    "osa": ["obstructive sleep apnea", "sleep apnea"],
    "r/o": ["rule out", "ruled out"],
    "hx": ["history"],
    "fx": ["fracture"],
    "sx": ["symptoms"],
    "dx": ["diagnosis"],
    "tx": ["treatment"],
    "rx": ["prescription", "medication"],
    "nkda": ["no known drug allergies"],
    "nsaid": ["nonsteroidal anti inflammatory", "anti inflammatory"],
    "ace inhibitor": ["angiotensin converting enzyme inhibitor"],
    "arb": ["angiotensin receptor blocker"],
    "ppi": ["proton pump inhibitor"],
    "ssri": ["selective serotonin reuptake inhibitor"],
    "bp": ["blood pressure"],
    "hr": ["heart rate"],
    "rr": ["respiratory rate"],
    "wbc": ["white blood cell", "white count"],
    "rbc": ["red blood cell"],
    "hgb": ["hemoglobin"],
    "plt": ["platelet", "platelets"],
    "bun": ["blood urea nitrogen"],
    "cr": ["creatinine"],
    "egfr": ["estimated glomerular filtration rate", "gfr"],
    "ast": ["aspartate aminotransferase"],
    "alt": ["alanine aminotransferase"],
    "inr": ["international normalized ratio"],
    "tsh": ["thyroid stimulating hormone"],
    "a1c": ["hemoglobin a1c", "hba1c", "glycated hemoglobin"],
    "hba1c": ["a1c", "hemoglobin a1c"],
    "bnp": ["brain natriuretic peptide", "b type natriuretic peptide"],
    "ekg": ["electrocardiogram", "ecg"],
    "ecg": ["electrocardiogram", "ekg"],

    # Lay term ↔ clinical term
    "high cholesterol": ["hyperlipidemia", "dyslipidemia", "elevated cholesterol"],
    "hyperlipidemia": ["high cholesterol", "dyslipidemia"],
    "high blood sugar": ["hyperglycemia", "elevated glucose"],
    "hyperglycemia": ["high blood sugar", "elevated glucose"],
    "low blood sugar": ["hypoglycemia"],
    "hypoglycemia": ["low blood sugar"],
    "high blood pressure": ["hypertension", "htn", "elevated blood pressure"],
    "low blood pressure": ["hypotension"],
    "hypotension": ["low blood pressure"],
    "kidney disease": ["renal disease", "nephropathy", "ckd", "chronic kidney disease"],
    "nephropathy": ["kidney disease", "renal disease"],
    "liver disease": ["hepatic disease", "hepatopathy"],
    "fatty liver": ["hepatic steatosis", "nafld", "steatosis"],
    "hepatic steatosis": ["fatty liver", "nafld"],
    "blood clot": ["thrombosis", "thrombus", "embolism", "dvt", "pe"],
    "thrombosis": ["blood clot", "thrombus"],
    "heart attack": ["myocardial infarction", "mi", "cardiac event"],
    "mini stroke": ["transient ischemic attack", "tia"],
    "tia": ["transient ischemic attack", "mini stroke"],
    "transient ischemic attack": ["tia", "mini stroke"],
    "irregular heartbeat": ["arrhythmia", "atrial fibrillation", "afib"],
    "arrhythmia": ["irregular heartbeat", "irregular rhythm"],
    "seizure": ["epilepsy", "convulsion", "seizure disorder"],
    "epilepsy": ["seizure disorder", "seizures"],
    "asthma": ["reactive airway disease", "bronchospasm"],
    "reactive airway disease": ["asthma"],
    "pneumonia": ["lung infection", "pulmonary infection"],
    "bronchitis": ["chest cold", "airway inflammation"],
    "pharyngitis": ["sore throat", "throat pain", "throat infection"],
    "sore throat": ["pharyngitis", "throat pain"],
    "acute pharyngitis": ["sore throat", "throat pain", "throat infection"],
    "sinusitis": ["sinus infection", "sinus congestion", "sinus pressure"],
    "sinus infection": ["sinusitis"],
    "otitis media": ["ear infection", "middle ear infection"],
    "ear infection": ["otitis media", "otitis"],
    "cellulitis": ["skin infection", "infected skin"],
    "conjunctivitis": ["pink eye", "eye infection"],
    "gastroenteritis": ["stomach flu", "stomach bug", "stomach virus"],
    "urticaria": ["hives"],
    "hives": ["urticaria"],
    "contusion": ["bruise", "bruising"],
    "laceration": ["cut", "wound"],
    "sprain": ["twisted", "strain"],
    "anemia": ["low blood count", "low hemoglobin", "low iron"],
    "low blood count": ["anemia"],
    "thyroid problem": ["thyroid disorder", "hypothyroidism", "hyperthyroidism"],
    "hypothyroidism": ["underactive thyroid", "low thyroid"],
    "hyperthyroidism": ["overactive thyroid", "high thyroid"],
    "arthritis": ["osteoarthritis", "degenerative joint disease", "oa", "joint disease"],
    "osteoarthritis": ["arthritis", "degenerative joint disease", "oa"],
    "degenerative joint disease": ["osteoarthritis", "arthritis", "oa"],
    "gout": ["gouty arthritis", "hyperuricemia"],
    "anxiety": ["anxiety disorder", "generalized anxiety", "gad"],
    "gad": ["generalized anxiety disorder", "anxiety"],
    "depression": ["major depressive disorder", "mdd", "depressive disorder"],
    "mdd": ["major depressive disorder", "depression"],
    "obesity": ["obese", "morbid obesity", "bmi over 30"],
    "overweight": ["elevated bmi", "bmi over 25"],

    # Symptoms: lay → clinical
    "stomach ache": ["abdominal pain", "epigastric pain", "gastric pain"],
    "abdominal pain": ["stomach ache", "belly pain", "stomach pain"],
    "heartburn": ["acid reflux", "gerd", "gastroesophageal reflux", "dyspepsia"],
    "dyspepsia": ["indigestion", "heartburn", "upset stomach"],
    "indigestion": ["dyspepsia", "heartburn"],
    "chest pain": ["angina", "chest discomfort", "substernal pain"],
    "angina": ["chest pain", "anginal pain"],
    "headache": ["cephalgia", "head pain", "migraine"],
    "cephalgia": ["headache", "head pain"],
    "migraine": ["headache", "migraine headache"],
    "dizziness": ["vertigo", "lightheadedness", "lightheaded"],
    "vertigo": ["dizziness", "room spinning"],
    "nausea": ["nauseous", "queasy", "upset stomach"],
    "swelling": ["edema", "oedema", "swollen"],
    "edema": ["swelling", "swollen", "fluid retention"],
    "numbness": ["paresthesia", "tingling", "neuropathy"],
    "paresthesia": ["numbness", "tingling", "pins and needles"],
    "neuropathy": ["nerve damage", "nerve pain", "numbness and tingling"],
    "rash": ["dermatitis", "skin eruption", "skin rash"],
    "dermatitis": ["rash", "skin inflammation"],
    "itching": ["pruritus", "itchy"],
    "pruritus": ["itching", "itchy", "itch"],
    "fatigue": ["tiredness", "tired", "exhaustion", "malaise"],
    "malaise": ["fatigue", "feeling unwell", "general weakness"],
    "constipation": ["difficulty with bowel movements", "hard stools"],
    "diarrhea": ["loose stools", "watery stools", "frequent bowel movements"],
    "painful urination": ["dysuria", "burning urination"],
    "dysuria": ["painful urination", "burning urination", "burning with urination"],
    "frequent urination": ["urinary frequency", "polyuria"],
    "polyuria": ["frequent urination", "excessive urination"],
    "joint pain": ["arthralgia", "joint ache"],
    "arthralgia": ["joint pain"],
    "muscle pain": ["myalgia", "muscle ache", "muscle soreness"],
    "myalgia": ["muscle pain", "muscle ache"],
    "back pain": ["lumbago", "lumbar pain", "dorsalgia"],
    "lumbago": ["back pain", "lower back pain", "lumbar pain"],

    # Procedures: lay → clinical
    "knee replacement": ["total knee arthroplasty", "tka", "knee arthroplasty"],
    "total knee arthroplasty": ["knee replacement", "tka"],
    "tka": ["total knee arthroplasty", "knee replacement"],
    "hip replacement": ["total hip arthroplasty", "tha", "hip arthroplasty"],
    "total hip arthroplasty": ["hip replacement", "tha"],
    "tha": ["total hip arthroplasty", "hip replacement"],
    "appendix out": ["appendectomy", "appendix removed"],
    "appendectomy": ["appendix removed", "appendix out"],
    "gallbladder out": ["cholecystectomy", "gallbladder removed"],
    "cholecystectomy": ["gallbladder removed", "gallbladder out"],
    "colonoscopy": ["colon scope", "colon screening"],
    "endoscopy": ["upper endoscopy", "egd", "scope"],
    "egd": ["esophagogastroduodenoscopy", "upper endoscopy", "upper scope"],
    "cabg": ["coronary artery bypass graft", "bypass surgery", "heart bypass"],
    "bypass surgery": ["cabg", "coronary artery bypass"],
    "stent": ["stent placement", "coronary stent", "pci"],
    "pci": ["percutaneous coronary intervention", "stent", "angioplasty"],
    "angioplasty": ["pci", "balloon angioplasty", "stent placement"],
    "c section": ["cesarean section", "cesarean delivery", "c-section"],
    "cesarean section": ["c section", "c-section", "cesarean"],
    "hysterectomy": ["uterus removed", "uterus removal"],

    # Medication classes: lay → clinical
    "blood thinner": ["anticoagulant", "anticoagulation", "warfarin", "coumadin", "eliquis", "xarelto"],
    "anticoagulant": ["blood thinner", "anticoagulation"],
    "pain killer": ["analgesic", "pain medication", "pain reliever"],
    "analgesic": ["pain killer", "pain medication"],
    "water pill": ["diuretic", "fluid pill"],
    "diuretic": ["water pill", "fluid pill"],
    "steroid": ["corticosteroid", "prednisone", "glucocorticoid"],
    "corticosteroid": ["steroid", "glucocorticoid"],
    "insulin": ["insulin injection", "insulin therapy"],
    "statin": ["cholesterol medication", "cholesterol medicine", "lipid lowering"],
    "beta blocker": ["beta-blocker", "metoprolol", "atenolol", "carvedilol"],
    "calcium channel blocker": ["ccb", "amlodipine", "nifedipine"],
    "ccb": ["calcium channel blocker"],
}


def _expand_with_synonyms(text: str) -> list[str]:
    """Return the text plus any known synonym expansions."""
    norm = text.lower().strip()
    expansions = [norm]
    # Check if any synonym key appears as a whole word in the text
    for abbrev, synonyms in MEDICAL_SYNONYMS.items():
        if re.search(r"\b" + re.escape(abbrev) + r"\b", norm):
            expansions.extend(synonyms)
    return expansions


def check_entity_in_transcript(entity: str, transcript: str) -> tuple[bool, str | None]:
    """
    Check if an entity from the note can be grounded in the transcript.
    Uses normalized substring matching with medical synonym expansion.
    Returns (found, evidence_quote).
    """
    norm_entity = normalize_for_comparison(entity)
    norm_transcript = normalize_for_comparison(transcript)

    # Direct substring match (extract evidence from normalized text to avoid offset mismatch)
    if norm_entity in norm_transcript:
        idx = norm_transcript.find(norm_entity)
        start = max(0, idx - 40)
        end = min(len(norm_transcript), idx + len(norm_entity) + 40)
        evidence = norm_transcript[start:end].strip()
        return True, f"...{evidence}..."

    # Synonym expansion: check if any synonym of the entity appears in transcript
    for synonym in _expand_with_synonyms(norm_entity):
        norm_syn = normalize_for_comparison(synonym)
        if norm_syn in norm_transcript:
            idx = norm_transcript.find(norm_syn)
            start = max(0, idx - 40)
            end = min(len(norm_transcript), idx + len(norm_syn) + 40)
            evidence = norm_transcript[start:end].strip()
            return True, f"...{evidence}... (synonym: {synonym})"

    # Try matching key terms (for cases like "metformin 500mg" vs "metformin 500 mg"
    # or "a1c of 6.8" vs "a1c was 6.8")
    key_terms = [t for t in norm_entity.split()
                 if len(t) > 2 and t not in {"the", "and", "for", "with", "was", "are", "has", "had", "not"}]
    if key_terms:
        matches = sum(1 for t in key_terms if t in norm_transcript)
        if matches >= len(key_terms) * 0.6:  # 60% of key terms found
            return True, None  # found but can't pinpoint exact quote

    return False, None


def check_entity_grounding(
    note: str, transcript: str
) -> tuple[list[EntityGroundingResult], float]:
    """
    Extract entities from the note, check each against the transcript.
    Returns the results and the grounding rate (fraction found).
    """
    entities = extract_medical_entities(note)

    if not entities:
        return [], 1.0  # no entities to check = vacuously grounded

    results = []
    for entity in entities:
        found, evidence = check_entity_in_transcript(entity, transcript)
        results.append(EntityGroundingResult(
            entity=entity,
            found_in_transcript=found,
            transcript_evidence=evidence,
        ))

    grounded = sum(1 for r in results if r.found_in_transcript)
    rate = grounded / len(results) if results else 1.0

    return results, rate
