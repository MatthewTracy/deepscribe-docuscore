"""
ICD-10 and HCC reference data (exploratory - not integrated into core pipeline).

Coding gap analysis: connect documentation quality to missed/incorrect ICD-10 codes
against ground-truth charts; initial work completed but not integrated pending further data.

In a production system, this would pull from CMS's official ICD-10-CM database
(~70,000 codes) and the HCC risk adjustment model V28. For this prototype,
we use a curated subset of the most common risk-adjustable diagnoses -
the ones that matter most for revenue impact.

This is intentionally a focused subset: ~70 codes covering the most common
risk-adjustable diagnoses and high-frequency primary care conditions.
"""

# HCC categories with approximate annual RAF values (2024 CMS-HCC V28)
# These are averages - actual values vary by patient demographics
HCC_CATEGORIES = {
    "HCC 1": {"description": "HIV/AIDS", "avg_annual_value": 5200},
    "HCC 6": {"description": "Opportunistic Infections", "avg_annual_value": 4800},
    "HCC 17": {"description": "Diabetes with Acute Complications", "avg_annual_value": 3400},
    "HCC 18": {"description": "Diabetes with Chronic Complications", "avg_annual_value": 3200},
    "HCC 19": {"description": "Diabetes without Complication", "avg_annual_value": 1200},
    "HCC 21": {"description": "Protein-Calorie Malnutrition", "avg_annual_value": 6100},
    "HCC 22": {"description": "Morbid Obesity", "avg_annual_value": 2100},
    "HCC 35": {"description": "End-Stage Liver Disease", "avg_annual_value": 7200},
    "HCC 37": {"description": "Chronic Hepatitis", "avg_annual_value": 2800},
    "HCC 38": {"description": "Intestinal Obstruction/Perforation", "avg_annual_value": 3100},
    "HCC 48": {"description": "Coagulation Defects", "avg_annual_value": 4500},
    "HCC 55": {"description": "Drug/Alcohol Use Disorder", "avg_annual_value": 3300},
    "HCC 56": {"description": "Drug/Alcohol Use with Complications", "avg_annual_value": 2600},
    "HCC 62": {"description": "Schizophrenia", "avg_annual_value": 3800},
    "HCC 63": {"description": "Major Depression", "avg_annual_value": 2400},
    "HCC 75": {"description": "Myasthenia Gravis/Muscular Dystrophy", "avg_annual_value": 3900},
    "HCC 76": {"description": "Spinal Cord Disorders", "avg_annual_value": 5600},
    "HCC 77": {"description": "Multiple Sclerosis", "avg_annual_value": 4100},
    "HCC 78": {"description": "Parkinson's Disease", "avg_annual_value": 3600},
    "HCC 79": {"description": "Seizure Disorders", "avg_annual_value": 2900},
    "HCC 80": {"description": "Quadriplegia", "avg_annual_value": 12500},
    "HCC 82": {"description": "Respirator Dependence/Tracheostomy", "avg_annual_value": 15800},
    "HCC 83": {"description": "Respiratory Arrest", "avg_annual_value": 8200},
    "HCC 84": {"description": "Cardio-Respiratory Failure", "avg_annual_value": 6400},
    "HCC 85": {"description": "Congestive Heart Failure", "avg_annual_value": 4200},
    "HCC 86": {"description": "Acute Myocardial Infarction", "avg_annual_value": 3800},
    "HCC 87": {"description": "Unstable Angina", "avg_annual_value": 3100},
    "HCC 96": {"description": "Specified Heart Arrhythmias", "avg_annual_value": 3500},
    "HCC 99": {"description": "Cerebral Hemorrhage", "avg_annual_value": 5700},
    "HCC 100": {"description": "Ischemic Stroke", "avg_annual_value": 4300},
    "HCC 103": {"description": "Hemiplegia/Hemiparesis", "avg_annual_value": 7100},
    "HCC 106": {"description": "Atherosclerosis of Arteries", "avg_annual_value": 2700},
    "HCC 108": {"description": "Vascular Disease", "avg_annual_value": 2500},
    "HCC 110": {"description": "Cystic Fibrosis", "avg_annual_value": 5800},
    "HCC 111": {"description": "Chronic Obstructive Pulmonary Disease", "avg_annual_value": 3600},
    "HCC 112": {"description": "Fibrosis of Lung", "avg_annual_value": 4200},
    "HCC 114": {"description": "Aspiration Pneumonia", "avg_annual_value": 5100},
    "HCC 115": {"description": "Pneumococcal Pneumonia", "avg_annual_value": 3400},
    "HCC 124": {"description": "Chronic Kidney Disease Stage 4", "avg_annual_value": 4600},
    "HCC 134": {"description": "Chronic Kidney Disease Stage 5/ESRD", "avg_annual_value": 9800},
    "HCC 135": {"description": "Dialysis Status", "avg_annual_value": 11200},
    "HCC 136": {"description": "Chronic Kidney Disease Stage 3", "avg_annual_value": 1800},
    "HCC 137": {"description": "Kidney Transplant Status", "avg_annual_value": 6700},
    "HCC 145": {"description": "Decubitus Ulcer Stage 3/4", "avg_annual_value": 8900},
    "HCC 161": {"description": "Chronic Ulcer (except pressure)", "avg_annual_value": 4100},
    "HCC 162": {"description": "Severe Skin Burn", "avg_annual_value": 6500},
    "HCC 166": {"description": "Severe Head Injury", "avg_annual_value": 5400},
    "HCC 176": {"description": "Major Organ Transplant", "avg_annual_value": 8600},
    "HCC 186": {"description": "Major Complications of Medical Care", "avg_annual_value": 4800},
    "HCC 188": {"description": "Artificial Openings for Feeding/Elimination", "avg_annual_value": 7300},
    "HCC 189": {"description": "Amputation Status (Lower Limb)", "avg_annual_value": 9100},
}


# Common ICD-10 codes that map to HCCs - curated for the diagnoses
# most likely to appear in primary care / specialty notes
ICD10_HCC_MAP = [
    # Diabetes (HCC 17-19) - MOST COMMON coding gap
    {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications", "hcc": None, "specificity": "low"},
    {"code": "E11.65", "description": "Type 2 diabetes mellitus with hyperglycemia", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.21", "description": "Type 2 diabetes mellitus with diabetic nephropathy", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.22", "description": "Type 2 diabetes mellitus with diabetic chronic kidney disease", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.40", "description": "Type 2 diabetes mellitus with diabetic neuropathy, unspecified", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.42", "description": "Type 2 diabetes mellitus with diabetic polyneuropathy", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.51", "description": "Type 2 diabetes mellitus with diabetic peripheral angiopathy without gangrene", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.311", "description": "Type 2 diabetes mellitus with unspecified diabetic retinopathy with macular edema", "hcc": "HCC 18", "specificity": "high"},
    {"code": "E11.10", "description": "Type 2 diabetes mellitus with ketoacidosis without coma", "hcc": "HCC 17", "specificity": "high"},
    {"code": "E10.65", "description": "Type 1 diabetes mellitus with hyperglycemia", "hcc": "HCC 18", "specificity": "high"},

    # Heart failure (HCC 85)
    {"code": "I50.9", "description": "Heart failure, unspecified", "hcc": "HCC 85", "specificity": "low"},
    {"code": "I50.22", "description": "Chronic systolic (congestive) heart failure", "hcc": "HCC 85", "specificity": "high"},
    {"code": "I50.32", "description": "Chronic diastolic (congestive) heart failure", "hcc": "HCC 85", "specificity": "high"},
    {"code": "I50.42", "description": "Chronic combined systolic and diastolic heart failure", "hcc": "HCC 85", "specificity": "high"},

    # COPD (HCC 111)
    {"code": "J44.1", "description": "Chronic obstructive pulmonary disease with acute exacerbation", "hcc": "HCC 111", "specificity": "high"},
    {"code": "J44.0", "description": "Chronic obstructive pulmonary disease with acute lower respiratory infection", "hcc": "HCC 111", "specificity": "high"},
    {"code": "J44.9", "description": "Chronic obstructive pulmonary disease, unspecified", "hcc": "HCC 111", "specificity": "low"},

    # CKD (HCC 124, 134, 136)
    {"code": "N18.3", "description": "Chronic kidney disease, stage 3", "hcc": "HCC 136", "specificity": "high"},
    {"code": "N18.4", "description": "Chronic kidney disease, stage 4", "hcc": "HCC 124", "specificity": "high"},
    {"code": "N18.5", "description": "Chronic kidney disease, stage 5", "hcc": "HCC 134", "specificity": "high"},
    {"code": "N18.6", "description": "End stage renal disease", "hcc": "HCC 134", "specificity": "high"},
    {"code": "N18.9", "description": "Chronic kidney disease, unspecified", "hcc": None, "specificity": "low"},

    # Hypertension - no HCC but extremely common, useful as reference
    {"code": "I10", "description": "Essential (primary) hypertension", "hcc": None, "specificity": "low"},
    {"code": "I12.9", "description": "Hypertensive chronic kidney disease with CKD stage 1-4", "hcc": None, "specificity": "medium"},
    {"code": "I13.10", "description": "Hypertensive heart and chronic kidney disease without heart failure", "hcc": None, "specificity": "medium"},

    # Cerebrovascular (HCC 99, 100)
    {"code": "I63.9", "description": "Cerebral infarction, unspecified", "hcc": "HCC 100", "specificity": "low"},
    {"code": "I63.50", "description": "Cerebral infarction due to unspecified occlusion of cerebral artery", "hcc": "HCC 100", "specificity": "medium"},
    {"code": "I61.9", "description": "Nontraumatic intracerebral hemorrhage, unspecified", "hcc": "HCC 99", "specificity": "low"},
    {"code": "G45.9", "description": "Transient cerebral ischemic attack, unspecified", "hcc": None, "specificity": "low"},

    # Atrial fibrillation (HCC 96)
    {"code": "I48.91", "description": "Unspecified atrial fibrillation", "hcc": "HCC 96", "specificity": "low"},
    {"code": "I48.0", "description": "Paroxysmal atrial fibrillation", "hcc": "HCC 96", "specificity": "high"},
    {"code": "I48.2", "description": "Chronic atrial fibrillation", "hcc": "HCC 96", "specificity": "high"},

    # Vascular disease (HCC 106, 108)
    {"code": "I70.0", "description": "Atherosclerosis of aorta", "hcc": "HCC 106", "specificity": "high"},
    {"code": "I73.9", "description": "Peripheral vascular disease, unspecified", "hcc": "HCC 108", "specificity": "low"},

    # Obesity (HCC 22)
    {"code": "E66.01", "description": "Morbid (severe) obesity due to excess calories", "hcc": "HCC 22", "specificity": "high"},
    {"code": "E66.09", "description": "Other obesity due to excess calories", "hcc": None, "specificity": "low"},
    {"code": "E66.9", "description": "Obesity, unspecified", "hcc": None, "specificity": "low"},

    # Depression (HCC 63)
    {"code": "F33.1", "description": "Major depressive disorder, recurrent, moderate", "hcc": "HCC 63", "specificity": "high"},
    {"code": "F33.2", "description": "Major depressive disorder, recurrent, severe without psychotic features", "hcc": "HCC 63", "specificity": "high"},
    {"code": "F32.1", "description": "Major depressive disorder, single episode, moderate", "hcc": "HCC 63", "specificity": "high"},

    # Substance use (HCC 55, 56)
    {"code": "F10.20", "description": "Alcohol dependence, uncomplicated", "hcc": "HCC 55", "specificity": "high"},
    {"code": "F10.21", "description": "Alcohol dependence, in remission", "hcc": "HCC 55", "specificity": "high"},
    {"code": "F11.20", "description": "Opioid dependence, uncomplicated", "hcc": "HCC 55", "specificity": "high"},

    # Malnutrition (HCC 21)
    {"code": "E43", "description": "Unspecified severe protein-calorie malnutrition", "hcc": "HCC 21", "specificity": "high"},
    {"code": "E44.0", "description": "Moderate protein-calorie malnutrition", "hcc": "HCC 21", "specificity": "high"},

    # Coagulation (HCC 48)
    {"code": "D68.9", "description": "Coagulation defect, unspecified", "hcc": "HCC 48", "specificity": "low"},
    {"code": "D68.2", "description": "Hereditary deficiency of other clotting factors", "hcc": "HCC 48", "specificity": "high"},

    # Seizure (HCC 79)
    {"code": "G40.909", "description": "Epilepsy, unspecified, not intractable", "hcc": "HCC 79", "specificity": "low"},
    {"code": "G40.919", "description": "Epilepsy, unspecified, intractable", "hcc": "HCC 79", "specificity": "high"},

    # Parkinson's (HCC 78)
    {"code": "G20", "description": "Parkinson's disease", "hcc": "HCC 78", "specificity": "high"},

    # Rheumatoid arthritis
    {"code": "M05.79", "description": "Rheumatoid arthritis with rheumatoid factor of multiple sites", "hcc": None, "specificity": "high"},
    {"code": "M06.9", "description": "Rheumatoid arthritis, unspecified", "hcc": None, "specificity": "low"},

    # Pneumonia (HCC 114, 115)
    {"code": "J69.0", "description": "Pneumonitis due to inhalation of food and vomit (aspiration pneumonia)", "hcc": "HCC 114", "specificity": "high"},
    {"code": "J13", "description": "Pneumonia due to Streptococcus pneumoniae", "hcc": "HCC 115", "specificity": "high"},
    {"code": "J18.9", "description": "Pneumonia, unspecified organism", "hcc": None, "specificity": "low"},

    # Common non-HCC but frequently seen codes
    {"code": "J06.9", "description": "Acute upper respiratory infection, unspecified", "hcc": None, "specificity": "low"},
    {"code": "M54.5", "description": "Low back pain", "hcc": None, "specificity": "low"},
    {"code": "R10.9", "description": "Unspecified abdominal pain", "hcc": None, "specificity": "low"},
    {"code": "K21.0", "description": "Gastro-esophageal reflux disease with esophagitis", "hcc": None, "specificity": "high"},
    {"code": "J45.20", "description": "Mild intermittent asthma, uncomplicated", "hcc": None, "specificity": "low"},
    {"code": "J45.50", "description": "Severe persistent asthma, uncomplicated", "hcc": None, "specificity": "high"},
    {"code": "G43.909", "description": "Migraine, unspecified, not intractable", "hcc": None, "specificity": "low"},
    {"code": "N39.0", "description": "Urinary tract infection, site not specified", "hcc": None, "specificity": "low"},
    {"code": "L03.90", "description": "Cellulitis, unspecified", "hcc": None, "specificity": "low"},
    {"code": "Z87.39", "description": "Personal history of other diseases of the musculoskeletal system", "hcc": None, "specificity": "low"},

    # Cancer (various HCCs)
    {"code": "C50.919", "description": "Malignant neoplasm of unspecified site of unspecified female breast", "hcc": None, "specificity": "low"},
    {"code": "C34.90", "description": "Malignant neoplasm of unspecified part of unspecified bronchus or lung", "hcc": None, "specificity": "low"},
    {"code": "C18.9", "description": "Malignant neoplasm of colon, unspecified", "hcc": None, "specificity": "low"},

    # Meningitis / infectious (relevant to our dataset)
    {"code": "G00.1", "description": "Pneumococcal meningitis", "hcc": None, "specificity": "high"},
    {"code": "A39.0", "description": "Meningococcal meningitis", "hcc": None, "specificity": "high"},
    {"code": "A41.9", "description": "Sepsis, unspecified organism", "hcc": None, "specificity": "low"},
    {"code": "A40.3", "description": "Sepsis due to Streptococcus pneumoniae", "hcc": None, "specificity": "high"},
]
