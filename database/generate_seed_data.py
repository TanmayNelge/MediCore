#!/usr/bin/env python3
"""
MediCore HCMS - realistic seed-data generator
=============================================

Produces ``04_sample_data.sql``: one consistent, realistic data set that
fills EVERY table of the schema (departments -> doctors -> patients ->
appointments -> diagnoses -> prescriptions -> lab orders -> bills ->
payments -> queue ...).

Why a generator instead of hand-typed INSERTs?
  * 15,000+ rows cannot be typed by hand without mistakes.
  * Every row respects every PK / FK / UNIQUE / CHECK constraint
    (validated in ``validate()`` before the SQL file is written).
  * It is deterministic (fixed random seed) - everyone in the team gets
    the exact same data, so screenshots / reports / viva answers match.

Why relative dates (TRUNC(SYSDATE,'IW') +/- n)?
  The data is anchored to the Monday of the week in which you install it.
  History is always in the past, upcoming appointments are always in the
  future, so the queue, "today's appointments" and the ML "upcoming
  no-show risk" screen are never empty no matter when you run the
  installer. Anchoring to a Monday (and not to SYSDATE) keeps the
  weekday of every appointment fixed (Sunday = OPD closed, etc.).

How are the NO_SHOW labels produced?
  Not with a coin flip. Each patient has a hidden "reliability" and each
  appointment's no-show probability follows effects that are documented
  in outpatient no-show studies: long booking lead time, previous
  no-shows, young adults, Monday/Saturday slots, late afternoon slots,
  first (NEW) visits, no insurance cover, living out of town. The ML model
  therefore has a real (but noisy, never perfect) signal to learn - the
  original 04b_bulk_data.sql used DBMS_RANDOM < 0.12, i.e. labels that
  were statistically independent of every feature, so nothing could be
  learned from them.

Usage:
    python generate_seed_data.py                 # writes 04_sample_data.sql
    python generate_seed_data.py --dump data.pkl # also dumps the tables
                                                 # (used by ml/ offline tests)
"""
import argparse
import math
import os
import pickle
import random
from collections import defaultdict

SEED = 2026
R = random.Random(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Date helpers.  "off" is an integer/float day offset from BASE where
# BASE = TRUNC(SYSDATE,'IW')  (Monday of the install week).
#   off % 7 == 0 -> Monday ... 5 -> Saturday, 6 -> Sunday
# --------------------------------------------------------------------------
BASE = "TRUNC(SYSDATE,'IW')"
TODAY = "TRUNC(SYSDATE)"
HIST_START = -455          # ~15 months of history
HIST_END = -1              # last Sunday
FUT_START, FUT_END = 7, 27  # next 3 weeks (always in the future)


def d(off):
    """DATE expression for an integer day offset."""
    off = int(off)
    return BASE if off == 0 else f"{BASE}{off:+d}"


def dt(off_float):
    """DATE/TIMESTAMP expression for a fractional day offset (time of day)."""
    return f"{BASE}{off_float:+.4f}"


def weekday(off):
    return int(off) % 7


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
DEPARTMENTS = [
    # name, location
    ("General Medicine", "Block A - Ground Floor"),
    ("Cardiology", "Block B - 2nd Floor"),
    ("Orthopedics", "Block B - 1st Floor"),
    ("Pediatrics", "Block A - 2nd Floor"),
    ("Dermatology", "Block C - 1st Floor"),
    ("ENT", "Block C - 2nd Floor"),
    ("Gynecology", "Block A - 3rd Floor"),
    ("Emergency", "Block D - Ground Floor"),
    ("Neurology", "Block B - 3rd Floor"),
    ("Ophthalmology", "Block C - Ground Floor"),
]
DEPT_ID = {name: i + 1 for i, (name, _) in enumerate(DEPARTMENTS)}

MALE = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karan", "Siddharth", "Rahul", "Amit",
        "Vikram", "Sanjay", "Rajesh", "Suresh", "Mahesh", "Nikhil", "Pranav", "Omkar", "Tejas",
        "Yash", "Harsh", "Kunal", "Abhishek", "Manoj", "Prakash", "Ganesh", "Sachin", "Akash",
        "Varun", "Ishaan", "Kabir", "Dhruv", "Atharva", "Shreyas", "Ritesh", "Anil", "Ramesh",
        "Deepak", "Vinod", "Ajay", "Gaurav", "Sameer", "Imran", "Faisal", "Joseph", "Thomas",
        "Gurpreet", "Harpreet", "Venkatesh", "Srinivas", "Arun", "Kiran", "Mohan", "Dattatray",
        "Vaibhav", "Tanmay", "Vansh", "Chinmay", "Mihir", "Parth", "Soham"]
FEMALE = ["Ananya", "Diya", "Saanvi", "Aadhya", "Priya", "Sneha", "Pooja", "Neha", "Kavya",
          "Riya", "Shruti", "Anjali", "Meera", "Sunita", "Lata", "Asha", "Rekha", "Vaishali",
          "Swati", "Madhuri", "Aishwarya", "Isha", "Tanvi", "Rutuja", "Sayali", "Gauri", "Pallavi",
          "Shweta", "Nisha", "Kiran", "Fatima", "Ayesha", "Mary", "Sarah", "Simran", "Harleen",
          "Lakshmi", "Padma", "Divya", "Deepa", "Radha", "Sujata", "Manisha", "Archana", "Varsha",
          "Smita", "Komal", "Mrunal", "Ketaki", "Aarya", "Myra", "Anika", "Prachi", "Bhakti"]
SURNAMES = ["Sharma", "Verma", "Patil", "Deshmukh", "Kulkarni", "Joshi", "Jadhav", "Pawar",
            "Shinde", "More", "Gaikwad", "Chavan", "Kale", "Bhosale", "Deshpande", "Gokhale",
            "Mehta", "Shah", "Patel", "Desai", "Iyer", "Nair", "Menon", "Pillai", "Reddy",
            "Rao", "Naidu", "Singh", "Gupta", "Agarwal", "Mishra", "Tiwari", "Pandey", "Yadav",
            "Khan", "Shaikh", "Qureshi", "D'Souza", "Fernandes", "Gill", "Sandhu", "Banerjee",
            "Chatterjee", "Mukherjee", "Das", "Bose", "Kapoor", "Malhotra", "Saxena", "Thakur",
            "Wagh", "Salunkhe", "Mane", "Kadam", "Sawant", "Apte", "Bapat", "Phadke", "Ranade"]

PUNE_AREAS = [
    ("Kothrud", "411038"), ("Aundh", "411007"), ("Baner", "411045"), ("Hadapsar", "411028"),
    ("Viman Nagar", "411014"), ("Wakad", "411057"), ("Hinjewadi", "411057"),
    ("Kharadi", "411014"), ("Shivajinagar", "411005"), ("Deccan Gymkhana", "411004"),
    ("Koregaon Park", "411001"), ("Pimpri", "411018"), ("Chinchwad", "411033"),
    ("Katraj", "411046"), ("Bibwewadi", "411037"), ("Warje", "411058"), ("Yerawada", "411006"),
    ("Sinhagad Road", "411041"), ("Wagholi", "412207"), ("Magarpatta", "411013"),
    ("Kondhwa", "411048"), ("Erandwane", "411004"), ("Sadashiv Peth", "411030"),
    ("Camp", "411001"), ("Pashan", "411021"), ("Balewadi", "411045"),
]
OUTSTATION = [("Satara", "415001"), ("Nashik", "422001"), ("Ahmednagar", "414001"),
              ("Solapur", "413001"), ("Baramati", "413102"), ("Lonavala", "410401"),
              ("Kolhapur", "416003"), ("Sangli", "416416"), ("Mumbai", "400076")]
STREETS = ["Lane No. 3", "Lane No. 7", "Main Road", "Society Road", "Station Road",
           "Link Road", "Market Road", "Temple Road", "Ring Road", "Gaothan"]
BUILDINGS = ["Shanti Niwas", "Sai Krupa Apts", "Ganga Heights", "Sunshine Residency",
             "Mayur Park", "Akshay Classic", "Shree Ganesh CHS", "Om Sai Society",
             "Green Valley", "Royal Palms", "Kalpataru Towers", "Laxmi Niwas", "Vrindavan Apts"]

BLOOD = [("B+", 32), ("O+", 29), ("A+", 21), ("AB+", 8), ("O-", 3), ("B-", 3), ("A-", 2.5), ("AB-", 1.5)]

INSURERS = ["Star Health", "HDFC ERGO", "ICICI Lombard", "Niva Bupa", "Care Health",
            "Bajaj Allianz", "Ayushman Bharat PM-JAY", "CGHS"]

# Symptom catalogue
SYMPTOMS = ["Fever", "Cough", "Sore throat", "Runny nose", "Headache", "Body ache", "Fatigue",
            "Chest pain", "Breathlessness", "Palpitations", "Dizziness", "Nausea", "Vomiting",
            "Diarrhoea", "Abdominal pain", "Joint pain", "Knee pain", "Back pain", "Swelling",
            "Skin rash", "Itching", "Ear pain", "Hearing loss", "Nasal congestion",
            "Blurred vision", "Red eye", "Excessive thirst", "Frequent urination",
            "Pelvic pain", "Irregular periods", "Seizure", "Numbness", "Weakness of limb",
            "Wheezing", "Loss of appetite", "Weight loss"]
SYM_ID = {s: i + 1 for i, s in enumerate(SYMPTOMS)}

# Medicines: code, name, category, unit price (INR), stock, reorder, expiry months from now
MEDICINES = [
    ("MED-001", "Paracetamol 500mg Tablet", "Analgesic/Antipyretic", 1.20, 4200, 500, 26),
    ("MED-002", "Paracetamol 250mg/5ml Syrup", "Analgesic/Antipyretic", 38.00, 180, 40, 14),
    ("MED-003", "Ibuprofen 400mg Tablet", "NSAID", 2.10, 1600, 200, 22),
    ("MED-004", "Diclofenac 50mg Tablet", "NSAID", 1.80, 1100, 150, 19),
    ("MED-005", "Diclofenac Gel 30g", "NSAID (Topical)", 95.00, 75, 30, 17),
    ("MED-006", "Amoxicillin + Clavulanate 625mg Tablet", "Antibiotic", 18.50, 900, 150, 12),
    ("MED-007", "Azithromycin 500mg Tablet", "Antibiotic", 21.00, 640, 100, 15),
    ("MED-008", "Cefixime 200mg Tablet", "Antibiotic", 11.00, 520, 100, 11),
    ("MED-009", "Amoxicillin 250mg/5ml Suspension", "Antibiotic", 62.00, 95, 30, 8),
    ("MED-010", "Doxycycline 100mg Capsule", "Antibiotic", 4.50, 380, 80, 20),
    ("MED-011", "Cetirizine 10mg Tablet", "Antihistamine", 1.10, 2100, 300, 30),
    ("MED-012", "Levocetirizine 5mg Tablet", "Antihistamine", 1.60, 1300, 200, 27),
    ("MED-013", "Montelukast 10mg Tablet", "Anti-asthmatic", 9.50, 700, 120, 21),
    ("MED-014", "Salbutamol 100mcg Inhaler", "Bronchodilator", 145.00, 48, 25, 16),
    ("MED-015", "Pantoprazole 40mg Tablet", "Proton Pump Inhibitor", 6.20, 2400, 300, 25),
    ("MED-016", "Ondansetron 4mg Tablet", "Antiemetic", 5.40, 600, 100, 18),
    ("MED-017", "ORS Sachet 21g", "Electrolyte", 21.00, 520, 100, 24),
    ("MED-018", "Amlodipine 5mg Tablet", "Antihypertensive", 2.30, 1800, 250, 28),
    ("MED-019", "Telmisartan 40mg Tablet", "Antihypertensive", 4.80, 1500, 250, 23),
    ("MED-020", "Metoprolol Succinate 25mg Tablet", "Beta Blocker", 5.60, 900, 150, 20),
    ("MED-021", "Atorvastatin 10mg Tablet", "Statin", 6.90, 1250, 200, 24),
    ("MED-022", "Aspirin 75mg Tablet", "Antiplatelet", 0.90, 1400, 200, 29),
    ("MED-023", "Clopidogrel 75mg Tablet", "Antiplatelet", 7.80, 160, 150, 18),
    ("MED-024", "Metformin 500mg Tablet", "Antidiabetic", 1.70, 3100, 400, 26),
    ("MED-025", "Glimepiride 1mg Tablet", "Antidiabetic", 3.90, 800, 150, 22),
    ("MED-026", "Insulin Glargine 100IU/ml Pen", "Antidiabetic", 690.00, 22, 15, 6),
    ("MED-027", "Levothyroxine 50mcg Tablet", "Thyroid Hormone", 1.40, 1100, 200, 19),
    ("MED-028", "Vitamin D3 60000 IU Capsule", "Supplement", 32.00, 450, 80, 21),
    ("MED-029", "Calcium + Vitamin D3 Tablet", "Supplement", 6.50, 1300, 200, 23),
    ("MED-030", "Ferrous Ascorbate + Folic Acid Tablet", "Haematinic", 7.20, 950, 150, 20),
    ("MED-031", "Fluconazole 150mg Tablet", "Antifungal", 14.00, 260, 60, 25),
    ("MED-032", "Clotrimazole 1% Cream 20g", "Antifungal (Topical)", 68.00, 140, 40, 18),
    ("MED-033", "Mupirocin 2% Ointment 5g", "Antibiotic (Topical)", 120.00, 34, 30, 13),
    ("MED-034", "Adapalene 0.1% Gel 15g", "Retinoid (Topical)", 165.00, 58, 20, 16),
    ("MED-035", "Moisturising Cream (Ceramide) 100g", "Emollient", 310.00, 42, 20, 22),
    ("MED-036", "Moxifloxacin 0.5% Eye Drops 5ml", "Ophthalmic Antibiotic", 98.00, 88, 30, 10),
    ("MED-037", "Carboxymethylcellulose 0.5% Eye Drops", "Lubricant Eye Drops", 135.00, 120, 30, 14),
    ("MED-038", "Xylometazoline 0.1% Nasal Spray", "Decongestant", 92.00, 70, 25, 15),
    ("MED-039", "Ciprofloxacin + Dexamethasone Ear Drops", "Otic", 54.00, 64, 25, 9),
    ("MED-040", "Sumatriptan 50mg Tablet", "Antimigraine", 24.00, 130, 40, 21),
    ("MED-041", "Levetiracetam 500mg Tablet", "Antiepileptic", 12.50, 520, 100, 24),
    ("MED-042", "Pregabalin 75mg Capsule", "Neuropathic Pain", 11.80, 410, 80, 20),
    ("MED-043", "Mefenamic Acid 250mg Tablet", "NSAID", 2.40, 680, 100, 22),
    ("MED-044", "Dydrogesterone 10mg Tablet", "Progestogen", 46.00, 110, 40, 17),
    ("MED-045", "Folic Acid 5mg Tablet", "Supplement", 0.80, 1600, 200, 27),
    ("MED-046", "Prednisolone 10mg Tablet", "Corticosteroid", 1.90, 14, 60, 4),
    ("MED-047", "Thiocolchicoside 4mg Capsule", "Muscle Relaxant", 9.20, 380, 80, 2),
]
MED_ID = {m[0]: i + 1 for i, m in enumerate(MEDICINES)}
MED_BY_CODE = {m[0]: m for m in MEDICINES}

# Lab tests: code, name, normal range, price, result generator key
LAB_TESTS = [
    ("LAB-CBC", "Complete Blood Count (CBC)", "Hb 12-17 g/dL; WBC 4-11 x10^3/uL", 350),
    ("LAB-FBS", "Fasting Blood Sugar", "70-100 mg/dL", 120),
    ("LAB-HBA1C", "Glycated Haemoglobin (HbA1c)", "< 5.7 %", 550),
    ("LAB-LIPID", "Lipid Profile", "LDL < 100; HDL > 40 mg/dL", 650),
    ("LAB-LFT", "Liver Function Test", "ALT 7-56 U/L; Bilirubin 0.1-1.2", 700),
    ("LAB-KFT", "Kidney Function Test", "Creatinine 0.6-1.3 mg/dL", 650),
    ("LAB-TSH", "Thyroid Stimulating Hormone", "0.4-4.0 mIU/L", 400),
    ("LAB-URINE", "Urine Routine & Microscopy", "Pus cells 0-5 /hpf", 200),
    ("LAB-ECG", "Electrocardiogram (12-lead)", "Normal sinus rhythm", 300),
    ("LAB-ECHO", "2D Echocardiography", "LVEF 55-70 %", 2200),
    ("LAB-CXR", "X-Ray Chest PA View", "No active lesion", 450),
    ("LAB-XRK", "X-Ray Knee AP/Lateral", "Normal joint space", 500),
    ("LAB-NS1", "Dengue NS1 Antigen", "Negative", 600),
    ("LAB-CRP", "C-Reactive Protein", "< 6 mg/L", 450),
    ("LAB-VITD", "Vitamin D (25-OH)", "30-100 ng/mL", 1200),
    ("LAB-USG", "Ultrasound Abdomen & Pelvis", "No abnormality", 1500),
    ("LAB-MRI", "MRI Brain (Plain)", "No abnormality", 6500),
    ("LAB-AUD", "Pure Tone Audiometry", "Hearing threshold < 25 dB", 700),
]
LAB_ID = {t[0]: i + 1 for i, t in enumerate(LAB_TESTS)}
LAB_BY_CODE = {t[0]: t for t in LAB_TESTS}

# Disease catalogue per department:
# (disease, ICD-10, weight, (min_age, max_age), gender or None,
#  symptoms, medicines [(code, dosage, days, qty_per_day)], labs, severity weights (M, Mo, S),
#  flags)
DISEASES = {
    "General Medicine": [
        ("Acute upper respiratory infection", "J06.9", 22, (5, 90), None,
         ["Fever", "Cough", "Sore throat", "Runny nose"],
         [("MED-001", "500mg thrice daily", 3, 3), ("MED-011", "10mg once at night", 5, 1)],
         ["LAB-CBC"], (70, 27, 3), {"fever": True}),
        ("Type 2 diabetes mellitus", "E11.9", 18, (32, 90), None,
         ["Excessive thirst", "Frequent urination", "Fatigue"],
         [("MED-024", "500mg twice daily after meals", 30, 2), ("MED-025", "1mg once before breakfast", 30, 1)],
         ["LAB-HBA1C", "LAB-FBS"], (40, 50, 10), {"diabetes": True, "chronic": True}),
        ("Essential (primary) hypertension", "I10", 16, (35, 90), None,
         ["Headache", "Dizziness"],
         [("MED-018", "5mg once daily", 30, 1), ("MED-019", "40mg once daily", 30, 1)],
         ["LAB-KFT", "LAB-ECG"], (45, 45, 10), {"htn": True, "chronic": True}),
        ("Acute gastroenteritis", "A09", 12, (5, 85), None,
         ["Diarrhoea", "Vomiting", "Abdominal pain"],
         [("MED-017", "1 sachet in 1L water as needed", 3, 3), ("MED-016", "4mg as needed for vomiting", 3, 2)],
         ["LAB-CBC"], (55, 40, 5), {}),
        ("Dengue fever", "A90", 7, (8, 75), None,
         ["Fever", "Headache", "Body ache", "Skin rash"],
         [("MED-001", "500mg every 6 hours", 5, 4), ("MED-017", "1 sachet in 1L water daily", 5, 1)],
         ["LAB-NS1", "LAB-CBC"], (35, 45, 20), {"fever": True}),
        ("Hypothyroidism", "E03.9", 8, (20, 80), "F",
         ["Fatigue", "Weight loss"],
         [("MED-027", "50mcg once daily empty stomach", 30, 1)],
         ["LAB-TSH"], (70, 28, 2), {"chronic": True}),
        ("Iron deficiency anaemia", "D50.9", 8, (14, 70), None,
         ["Fatigue", "Dizziness", "Weakness of limb"],
         [("MED-030", "1 tablet once daily after lunch", 30, 1)],
         ["LAB-CBC"], (50, 42, 8), {}),
        ("Vitamin D deficiency", "E55.9", 9, (18, 85), None,
         ["Body ache", "Fatigue", "Back pain"],
         [("MED-028", "60000 IU once weekly", 56, 0.15)],
         ["LAB-VITD"], (75, 23, 2), {}),
    ],
    "Cardiology": [
        ("Stable angina pectoris", "I20.9", 22, (40, 90), None,
         ["Chest pain", "Breathlessness"],
         [("MED-022", "75mg once daily after lunch", 30, 1), ("MED-021", "10mg once at night", 30, 1),
          ("MED-020", "25mg once daily", 30, 1)],
         ["LAB-ECG", "LAB-LIPID", "LAB-ECHO"], (30, 55, 15), {"cardiac": True, "chronic": True}),
        ("Hypertensive heart disease", "I11.9", 22, (40, 90), None,
         ["Breathlessness", "Palpitations", "Headache"],
         [("MED-019", "40mg once daily", 30, 1), ("MED-018", "5mg once daily", 30, 1)],
         ["LAB-ECG", "LAB-ECHO", "LAB-KFT"], (35, 50, 15), {"htn": True, "chronic": True}),
        ("Atrial fibrillation", "I48.91", 10, (50, 92), None,
         ["Palpitations", "Dizziness", "Fatigue"],
         [("MED-020", "25mg twice daily", 30, 2)],
         ["LAB-ECG", "LAB-ECHO"], (20, 55, 25), {"cardiac": True, "chronic": True}),
        ("Mixed hyperlipidaemia", "E78.2", 18, (30, 85), None,
         ["Fatigue"],
         [("MED-021", "10mg once at night", 30, 1)],
         ["LAB-LIPID", "LAB-LFT"], (60, 38, 2), {"chronic": True}),
        ("Heart failure", "I50.9", 8, (55, 92), None,
         ["Breathlessness", "Swelling", "Fatigue"],
         [("MED-020", "25mg once daily", 30, 1), ("MED-022", "75mg once daily", 30, 1)],
         ["LAB-ECHO", "LAB-KFT", "LAB-CXR"], (10, 50, 40), {"cardiac": True, "chronic": True}),
    ],
    "Orthopedics": [
        ("Primary osteoarthritis of knee", "M17.1", 26, (42, 90), None,
         ["Knee pain", "Swelling", "Joint pain"],
         [("MED-004", "50mg twice daily after meals", 10, 2), ("MED-005", "Apply locally thrice daily", 14, 0.1),
          ("MED-029", "1 tablet once daily", 30, 1)],
         ["LAB-XRK", "LAB-VITD"], (40, 50, 10), {"chronic": True}),
        ("Low back pain (lumbago)", "M54.5", 24, (20, 80), None,
         ["Back pain"],
         [("MED-047", "4mg twice daily", 5, 2), ("MED-003", "400mg twice daily after meals", 5, 2)],
         [], (55, 40, 5), {}),
        ("Fracture of distal radius", "S52.5", 9, (6, 85), None,
         ["Swelling", "Joint pain"],
         [("MED-003", "400mg thrice daily after meals", 7, 3), ("MED-029", "1 tablet once daily", 30, 1)],
         ["LAB-CXR"], (10, 60, 30), {}),
        ("Frozen shoulder (adhesive capsulitis)", "M75.0", 10, (40, 75), None,
         ["Joint pain"],
         [("MED-004", "50mg twice daily after meals", 10, 2)],
         [], (40, 55, 5), {}),
        ("Cervical spondylosis", "M47.812", 12, (35, 85), None,
         ["Back pain", "Numbness", "Headache"],
         [("MED-042", "75mg once at night", 14, 1), ("MED-047", "4mg twice daily", 5, 2)],
         ["LAB-CXR"], (45, 48, 7), {"chronic": True}),
    ],
    "Pediatrics": [
        ("Acute bronchiolitis", "J21.9", 18, (0, 3), None,
         ["Cough", "Wheezing", "Fever"],
         [("MED-002", "15mg/kg every 6 hours", 3, 4)],
         ["LAB-CBC"], (55, 38, 7), {"fever": True, "resp": True}),
        ("Acute otitis media", "H66.9", 16, (1, 12), None,
         ["Ear pain", "Fever"],
         [("MED-009", "5ml thrice daily", 7, 3), ("MED-002", "5ml as needed for fever", 3, 3)],
         [], (65, 33, 2), {"fever": True}),
        ("Viral gastroenteritis", "A08.4", 18, (0, 14), None,
         ["Diarrhoea", "Vomiting", "Loss of appetite"],
         [("MED-017", "Small sips after every loose stool", 3, 3)],
         [], (60, 35, 5), {}),
        ("Acute tonsillitis", "J03.90", 16, (3, 14), None,
         ["Sore throat", "Fever", "Loss of appetite"],
         [("MED-009", "5ml thrice daily", 7, 3), ("MED-002", "5ml as needed for fever", 3, 3)],
         ["LAB-CBC"], (60, 37, 3), {"fever": True}),
        ("Childhood asthma", "J45.909", 12, (4, 14), None,
         ["Wheezing", "Cough", "Breathlessness"],
         [("MED-014", "2 puffs as needed with spacer", 30, 0.05), ("MED-013", "5mg once at night", 30, 1)],
         [], (45, 45, 10), {"resp": True, "chronic": True}),
        ("Routine well-child check-up", "Z00.129", 20, (0, 12), None,
         ["Fatigue"], [], [], (100, 0, 0), {"routine": True}),
    ],
    "Dermatology": [
        ("Acne vulgaris", "L70.0", 24, (13, 32), None,
         ["Skin rash"],
         [("MED-034", "Apply thin layer at night", 30, 0.05), ("MED-010", "100mg once daily after food", 30, 1)],
         [], (60, 35, 5), {}),
        ("Tinea corporis (ringworm)", "B35.4", 24, (5, 75), None,
         ["Skin rash", "Itching"],
         [("MED-032", "Apply twice daily", 21, 0.05), ("MED-031", "150mg once weekly", 21, 0.15)],
         [], (55, 40, 5), {}),
        ("Atopic dermatitis", "L20.9", 16, (1, 60), None,
         ["Itching", "Skin rash"],
         [("MED-035", "Apply twice daily after bath", 30, 0.03), ("MED-012", "5mg once at night", 14, 1)],
         [], (50, 43, 7), {"chronic": True}),
        ("Urticaria", "L50.9", 14, (10, 70), None,
         ["Itching", "Skin rash", "Swelling"],
         [("MED-012", "5mg once at night", 10, 1)],
         ["LAB-CBC"], (60, 35, 5), {}),
        ("Impetigo", "L01.0", 8, (2, 14), None,
         ["Skin rash", "Itching"],
         [("MED-033", "Apply thrice daily", 7, 0.1)],
         [], (70, 28, 2), {}),
    ],
    "ENT": [
        ("Acute sinusitis", "J01.90", 24, (12, 75), None,
         ["Nasal congestion", "Headache", "Runny nose"],
         [("MED-006", "625mg twice daily after meals", 7, 2), ("MED-038", "2 sprays twice daily", 5, 0.1)],
         [], (55, 40, 5), {}),
        ("Acute tonsillitis", "J03.90", 18, (5, 45), None,
         ["Sore throat", "Fever"],
         [("MED-007", "500mg once daily", 3, 1), ("MED-001", "500mg thrice daily", 3, 3)],
         ["LAB-CBC"], (60, 37, 3), {"fever": True}),
        ("Impacted cerumen", "H61.20", 16, (5, 90), None,
         ["Hearing loss", "Ear pain"],
         [("MED-039", "3 drops thrice daily", 5, 0.1)],
         [], (85, 15, 0), {}),
        ("Allergic rhinitis", "J30.9", 22, (6, 70), None,
         ["Runny nose", "Nasal congestion"],
         [("MED-013", "10mg once at night", 30, 1), ("MED-011", "10mg once at night", 10, 1)],
         [], (65, 33, 2), {"chronic": True}),
        ("Sensorineural hearing loss", "H90.5", 8, (45, 92), None,
         ["Hearing loss", "Dizziness"],
         [], ["LAB-AUD"], (40, 45, 15), {"chronic": True}),
    ],
    "Gynecology": [
        ("Polycystic ovarian syndrome", "E28.2", 22, (16, 38), "F",
         ["Irregular periods", "Weight loss"],
         [("MED-024", "500mg twice daily after meals", 30, 2)],
         ["LAB-USG", "LAB-TSH"], (50, 45, 5), {"chronic": True}),
        ("Primary dysmenorrhoea", "N94.4", 18, (14, 35), "F",
         ["Pelvic pain", "Abdominal pain"],
         [("MED-043", "250mg thrice daily during periods", 3, 3)],
         [], (60, 37, 3), {}),
        ("Supervision of normal pregnancy", "Z34.90", 32, (19, 40), "F",
         ["Nausea", "Fatigue"],
         [("MED-045", "5mg once daily", 30, 1), ("MED-030", "1 tablet once daily", 30, 1)],
         ["LAB-USG", "LAB-CBC"], (100, 0, 0), {"routine": True, "pregnancy": True}),
        ("Urinary tract infection", "N39.0", 16, (16, 80), "F",
         ["Frequent urination", "Pelvic pain", "Fever"],
         [("MED-008", "200mg twice daily", 5, 2)],
         ["LAB-URINE"], (55, 40, 5), {"fever": True}),
        ("Threatened abortion", "O20.0", 5, (19, 40), "F",
         ["Pelvic pain"],
         [("MED-044", "10mg twice daily", 14, 2)],
         ["LAB-USG"], (10, 50, 40), {"pregnancy": True}),
    ],
    "Neurology": [
        ("Migraine without aura", "G43.009", 30, (14, 65), None,
         ["Headache", "Nausea", "Blurred vision"],
         [("MED-040", "50mg at onset of attack", 10, 0.3), ("MED-016", "4mg as needed", 5, 1)],
         [], (40, 50, 10), {"chronic": True}),
        ("Epilepsy, unspecified", "G40.909", 16, (5, 75), None,
         ["Seizure"],
         [("MED-041", "500mg twice daily", 30, 2)],
         ["LAB-MRI"], (20, 55, 25), {"chronic": True}),
        ("Peripheral neuropathy", "G62.9", 18, (40, 88), None,
         ["Numbness", "Weakness of limb"],
         [("MED-042", "75mg once at night", 30, 1)],
         ["LAB-HBA1C"], (35, 55, 10), {"chronic": True}),
        ("Tension-type headache", "G44.209", 22, (16, 70), None,
         ["Headache"],
         [("MED-001", "500mg as needed", 5, 2)],
         [], (75, 23, 2), {}),
        ("Sequelae of cerebral infarction", "I69.30", 8, (50, 92), None,
         ["Weakness of limb", "Numbness"],
         [("MED-023", "75mg once daily", 30, 1), ("MED-021", "10mg once at night", 30, 1)],
         ["LAB-MRI", "LAB-LIPID"], (5, 45, 50), {"cardiac": True, "chronic": True}),
    ],
    "Ophthalmology": [
        ("Myopia", "H52.1", 28, (7, 50), None,
         ["Blurred vision", "Headache"], [], [], (90, 10, 0), {"routine": True}),
        ("Acute conjunctivitis", "H10.9", 24, (3, 75), None,
         ["Red eye", "Itching"],
         [("MED-036", "1 drop four times daily", 7, 0.05)],
         [], (65, 33, 2), {}),
        ("Age-related cataract", "H25.9", 22, (50, 92), None,
         ["Blurred vision"], [("MED-037", "1 drop four times daily", 30, 0.05)],
         [], (40, 50, 10), {"chronic": True}),
        ("Dry eye syndrome", "H04.123", 18, (25, 85), None,
         ["Red eye", "Blurred vision"],
         [("MED-037", "1 drop four times daily", 30, 0.05)],
         [], (65, 33, 2), {"chronic": True}),
        ("Primary open-angle glaucoma", "H40.11", 8, (45, 92), None,
         ["Blurred vision", "Headache"], [], [], (25, 55, 20), {"chronic": True}),
    ],
}

ADMISSION_CASES = [
    # dept, reason, disease, icd, days(min,max), room types preferred, labs, meds
    ("Cardiology", "Acute chest pain - rule out myocardial infarction", "NSTEMI (non-ST elevation MI)", "I21.4",
     (3, 7), ["ICU", "PRIVATE"], ["LAB-ECG", "LAB-ECHO", "LAB-LIPID"], ["MED-022", "MED-023", "MED-021"]),
    ("Cardiology", "Acute decompensated heart failure", "Heart failure", "I50.9",
     (4, 9), ["ICU", "GENERAL"], ["LAB-ECHO", "LAB-KFT", "LAB-CXR"], ["MED-020", "MED-022"]),
    ("General Medicine", "High-grade fever with thrombocytopenia", "Dengue fever with warning signs", "A91",
     (3, 6), ["GENERAL", "PRIVATE"], ["LAB-NS1", "LAB-CBC"], ["MED-001", "MED-017"]),
    ("General Medicine", "Uncontrolled blood sugar", "Type 2 diabetes with hyperglycaemia", "E11.65",
     (2, 5), ["GENERAL"], ["LAB-HBA1C", "LAB-KFT"], ["MED-024", "MED-026"]),
    ("General Medicine", "Community-acquired pneumonia", "Pneumonia, unspecified organism", "J18.9",
     (4, 8), ["GENERAL", "PRIVATE"], ["LAB-CXR", "LAB-CBC", "LAB-CRP"], ["MED-006", "MED-007", "MED-001"]),
    ("Orthopedics", "Fall at home - hip fracture", "Fracture of neck of femur", "S72.0",
     (5, 12), ["GENERAL", "PRIVATE"], ["LAB-CXR", "LAB-CBC"], ["MED-003", "MED-029"]),
    ("Orthopedics", "Elective total knee replacement", "Primary osteoarthritis of knee", "M17.1",
     (4, 7), ["PRIVATE"], ["LAB-XRK", "LAB-CBC", "LAB-ECG"], ["MED-003", "MED-004"]),
    ("Neurology", "Sudden right-sided weakness", "Cerebral infarction", "I63.9",
     (5, 11), ["ICU", "GENERAL"], ["LAB-MRI", "LAB-LIPID", "LAB-ECG"], ["MED-023", "MED-021"]),
    ("Pediatrics", "Severe dehydration due to diarrhoea", "Viral gastroenteritis", "A08.4",
     (2, 4), ["GENERAL"], ["LAB-CBC"], ["MED-017"]),
    ("Gynecology", "Admitted for delivery", "Single spontaneous delivery", "O80",
     (2, 4), ["PRIVATE", "GENERAL"], ["LAB-CBC", "LAB-USG"], ["MED-045", "MED-030"]),
    ("Emergency", "Road traffic accident - multiple injuries", "Multiple injuries, unspecified", "T07",
     (3, 10), ["EMERGENCY", "ICU"], ["LAB-CXR", "LAB-CBC"], ["MED-003", "MED-006"]),
]


def wchoice(items, weights):
    return R.choices(items, weights=weights, k=1)[0]


def sql_str(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, Raw):
        return v.expr
    return "'" + str(v).replace("'", "''") + "'"


class Raw:
    """A raw SQL expression (e.g. a date expression) that must not be quoted."""
    def __init__(self, expr, sortkey=None):
        self.expr = expr
        self.key = sortkey  # numeric day offset, for validation / dumps

    def __repr__(self):
        return self.expr


class DB:
    def __init__(self):
        self.tables = defaultdict(list)   # name -> list of dict rows (insert order)
        self.columns = {}

    def add(self, table, row):
        if table not in self.columns:
            self.columns[table] = list(row.keys())
        self.tables[table].append(row)
        return row


db = DB()

# ==========================================================================
# 1. Departments
# ==========================================================================
for i, (name, loc) in enumerate(DEPARTMENTS, start=1):
    db.add("department", {"department_id": i, "department_name": name, "head_doctor_id": None,
                          "location": loc, "created_at": Raw(d(-1800 - i * 7), -1800)})

# ==========================================================================
# 2. Doctors (24) - working days, sessions, fees
# ==========================================================================
DOCTOR_SPEC = [
    # dept, specialization, qualification, fee, days(list of weekday ints), sessions
    ("General Medicine", "Internal Medicine", "MBBS, MD (Medicine)", 600, [0, 1, 2, 3, 4, 5], ["AM", "PM"]),
    ("General Medicine", "Family Medicine", "MBBS, DNB (Family Medicine)", 500, [0, 2, 4, 5], ["AM", "PM"]),
    ("General Medicine", "Diabetology", "MBBS, MD, Fellowship in Diabetology", 800, [1, 3, 5], ["AM"]),
    ("Cardiology", "Interventional Cardiology", "MBBS, MD, DM (Cardiology)", 1500, [0, 2, 4], ["AM"]),
    ("Cardiology", "Clinical Cardiology", "MBBS, MD, DNB (Cardiology)", 1200, [1, 3, 5], ["AM", "PM"]),
    ("Cardiology", "Non-invasive Cardiology", "MBBS, MD (Medicine), FACC", 1000, [0, 1, 3, 4], ["PM"]),
    ("Orthopedics", "Joint Replacement", "MBBS, MS (Ortho), Fellowship Arthroplasty", 1100, [0, 2, 4], ["AM", "PM"]),
    ("Orthopedics", "Spine Surgery", "MBBS, MS (Ortho), Fellowship Spine", 1200, [1, 3], ["AM"]),
    ("Orthopedics", "Trauma & Sports Medicine", "MBBS, D.Ortho, DNB", 900, [0, 1, 3, 5], ["PM"]),
    ("Pediatrics", "General Pediatrics", "MBBS, MD (Pediatrics)", 700, [0, 1, 2, 3, 4, 5], ["AM"]),
    ("Pediatrics", "Pediatric Pulmonology", "MBBS, DCH, DNB (Pediatrics)", 800, [1, 3, 5], ["PM"]),
    ("Dermatology", "Clinical Dermatology", "MBBS, MD (DVL)", 700, [0, 2, 4, 5], ["AM", "PM"]),
    ("Dermatology", "Cosmetic Dermatology", "MBBS, DDVL", 900, [1, 3, 5], ["PM"]),
    ("ENT", "Otorhinolaryngology", "MBBS, MS (ENT)", 700, [0, 1, 3, 4], ["AM"]),
    ("ENT", "Head & Neck Surgery", "MBBS, DLO, DNB (ENT)", 800, [2, 4, 5], ["PM"]),
    ("Gynecology", "Obstetrics & Gynecology", "MBBS, MS (OBGY)", 900, [0, 1, 2, 3, 4], ["AM", "PM"]),
    ("Gynecology", "Reproductive Medicine", "MBBS, DGO, DNB, FRM", 1100, [1, 3, 5], ["AM"]),
    ("Emergency", "Emergency Medicine", "MBBS, MD (Emergency Medicine)", 800, [0, 1, 2, 3, 4, 5], ["AM"]),
    ("Emergency", "Critical Care", "MBBS, MD (Anaesthesia), IDCCM", 900, [0, 2, 4], ["PM"]),
    ("Neurology", "Clinical Neurology", "MBBS, MD, DM (Neurology)", 1300, [0, 2, 4], ["AM"]),
    ("Neurology", "Stroke & Epilepsy", "MBBS, DNB (Neurology)", 1200, [1, 3, 5], ["PM"]),
    ("Ophthalmology", "Cataract & Refractive Surgery", "MBBS, MS (Ophthalmology)", 600, [0, 1, 2, 3, 4], ["AM"]),
    ("Ophthalmology", "Glaucoma & Medical Retina", "MBBS, DO, DNB (Ophthalmology)", 700, [1, 3, 5], ["PM"]),
    ("General Medicine", "Infectious Diseases", "MBBS, MD (Medicine), DM (ID)", 900, [0, 2, 4], ["PM"]),
]
SESSION_SLOTS = {
    "AM": [f"{h:02d}:{m:02d}" for h in range(9, 13) for m in (0, 15, 30, 45)],   # 09:00-12:45
    "PM": [f"{h:02d}:{m:02d}" for h in range(14, 18) for m in (0, 15, 30, 45)],  # 14:00-17:45
}
SESSION_TIMES = {"AM": ("09:00", "13:00"), "PM": ("14:00", "18:00")}

used_names = set()


def person_name(gender):
    while True:
        first = R.choice(MALE if gender == "M" else FEMALE)
        last = R.choice(SURNAMES)
        if (first, last) not in used_names:
            used_names.add((first, last))
            return first, last


def email_of(first, last, domain, n=None):
    base = f"{first}.{last}".lower().replace("'", "").replace(" ", "")
    return f"{base}{n or ''}@{domain}"


doctors = []
for i, (dept, spec, qual, fee, days, sess) in enumerate(DOCTOR_SPEC, start=1):
    g = "F" if i % 3 != 0 and R.random() < 0.5 else "M"
    if dept == "Gynecology":
        g = "F"
    first, last = person_name(g)
    joined = -R.randint(400, 5200)
    lic_state = R.choice(["MMC", "MMC", "MMC", "KMC", "DMC", "TNMC"])
    row = db.add("doctor", {
        "doctor_id": i, "first_name": first, "last_name": last, "department_id": DEPT_ID[dept],
        "specialization": spec, "qualification": qual,
        "license_no": f"{lic_state}-{R.randint(1998, 2019)}-{R.randint(10000, 99999)}",
        "phone": f"98{R.randint(20000000, 99999999)}",
        "email": email_of(first, last, "medicore.in"),
        "consultation_fee": float(fee),
        "joining_date": Raw(d(joined), joined),
    })
    doctors.append({"id": i, "dept": dept, "days": days, "sess": sess, "fee": fee, "row": row})

DOCS_BY_DEPT = defaultdict(list)
for doc in doctors:
    DOCS_BY_DEPT[doc["dept"]].append(doc)

# department heads (most senior doctor = smallest joined offset)
for dep in db.tables["department"]:
    cands = [x for x in doctors if DEPT_ID[x["dept"]] == dep["department_id"]]
    head = min(cands, key=lambda x: x["row"]["joining_date"].key)
    dep["head_doctor_id"] = head["id"]

# ==========================================================================
# 3. Nurses (20)
# ==========================================================================
NURSE_DEPTS = ["General Medicine"] * 3 + ["Cardiology"] * 2 + ["Orthopedics"] * 2 + ["Pediatrics"] * 2 + \
              ["Dermatology", "ENT"] + ["Gynecology"] * 2 + ["Emergency"] * 3 + ["Neurology"] * 2 + ["Ophthalmology"]
for i, dept in enumerate(NURSE_DEPTS, start=1):
    g = "F" if R.random() < 0.82 else "M"
    first, last = person_name(g)
    joined = -R.randint(200, 4000)
    db.add("nurse", {
        "nurse_id": i, "first_name": first, "last_name": last, "department_id": DEPT_ID[dept],
        "license_no": f"MNC-{R.randint(2005, 2023)}-{R.randint(1000, 9999)}{i:02d}",
        "phone": f"97{R.randint(20000000, 99999999)}",
        "email": email_of(first, last, "medicore.in"),
        "shift": ["MORNING", "EVENING", "NIGHT"][i % 3],
        "joining_date": Raw(d(joined), joined),
    })

# ==========================================================================
# 4. Patients (300) + hidden behavioural traits
# ==========================================================================
N_PATIENTS = 420
patients = []
used_phones = set()
used_emails = set()


def unique_phone(prefixes=("98", "99", "97", "96", "95", "94", "93", "91", "90", "88", "87", "86", "85", "84", "83", "82", "81", "80", "79", "78", "77", "76", "75", "73", "70")):
    while True:
        p = R.choice(prefixes) + f"{R.randint(0, 99999999):08d}"
        if p not in used_phones:
            used_phones.add(p)
            return p


def age_bucket():
    return wchoice([(0, 5), (5, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 92)],
                   [7, 9, 20, 24, 20, 14, 6])


for pid in range(1, N_PATIENTS + 1):
    lo, hi = age_bucket()
    age = R.uniform(lo, hi)
    gender = "O" if R.random() < 0.006 else ("F" if R.random() < 0.51 else "M")
    first, last = person_name("F" if gender == "F" else "M") if gender != "O" else person_name(R.choice("MF"))
    # dob as an absolute date (age must not drift with install date for kids)
    dob_days = int(age * 365.25) + R.randint(0, 200)
    outstation = R.random() < 0.13
    area, pin = R.choice(OUTSTATION) if outstation else R.choice(PUNE_AREAS)
    addr = f"Flat {R.randint(1, 30)}{R.choice('0123')}{R.randint(1, 9)}, {R.choice(BUILDINGS)}, {R.choice(STREETS)}" + \
           (f", {area} - {pin}" if not outstation else f" - {pin}")
    city = area if outstation else "Pune"
    insured = R.random() < (0.30 if age < 18 else 0.47)
    email = None
    if age >= 16 and R.random() < 0.72:
        e = email_of(first, last, R.choice(["gmail.com", "gmail.com", "yahoo.co.in", "outlook.com", "rediffmail.com"]))
        n = 1
        while e in used_emails:
            n += 1
            e = email_of(first, last, e.split("@")[1], n)
        used_emails.add(e)
        email = e
    ec_rel_gender = R.choice("MF")
    ec_first, _ = (R.choice(MALE), None) if ec_rel_gender == "M" else (R.choice(FEMALE), None)
    patients.append({
        "id": pid, "age": age, "gender": gender, "outstation": outstation, "insured": insured,
        # latent reliability: positive = more likely to miss appointments
        "z": R.gauss(0, 0.45),
        "first": first, "last": last, "dob_days": dob_days, "email": email,
        "addr": addr, "city": city, "ec_name": f"{ec_first} {last}", "phone": unique_phone(),
        "ec_phone": unique_phone(),
    })

# primary department preference per patient
def pick_departments(p):
    a, g = p["age"], p["gender"]
    if a < 14:
        opts = {"Pediatrics": 70, "Dermatology": 8, "ENT": 10, "Ophthalmology": 7, "Orthopedics": 5}
    else:
        opts = {"General Medicine": 26, "Cardiology": 5 + (14 if a > 45 else 0), "Orthopedics": 10 + (8 if a > 45 else 0),
                "Dermatology": 9 + (6 if a < 35 else 0), "ENT": 9, "Neurology": 6 + (3 if a > 55 else 0),
                "Ophthalmology": 6 + (8 if a > 50 else 0), "Gynecology": (16 if g == "F" and 15 < a < 50 else (4 if g == "F" else 0))}
    names = list(opts)
    return names, [opts[n] for n in names]


# ==========================================================================
# 5. Room / beds (40)
# ==========================================================================
BED_LAYOUT = [
    # dept, room_no prefix, type, rate, beds
    ("General Medicine", "101", "GENERAL", 1500, "ABCD"), ("General Medicine", "102", "GENERAL", 1500, "ABCD"),
    ("General Medicine", "103", "PRIVATE", 3500, "A"), ("General Medicine", "104", "PRIVATE", 3500, "A"),
    ("Cardiology", "201", "ICU", 7500, "ABC"), ("Cardiology", "202", "PRIVATE", 4500, "A"),
    ("Cardiology", "203", "GENERAL", 1800, "AB"),
    ("Orthopedics", "301", "GENERAL", 1600, "ABC"), ("Orthopedics", "302", "PRIVATE", 4000, "A"),
    ("Pediatrics", "401", "GENERAL", 1400, "ABC"), ("Pediatrics", "402", "PRIVATE", 3200, "A"),
    ("Gynecology", "501", "PRIVATE", 4200, "A"), ("Gynecology", "502", "GENERAL", 1600, "ABC"),
    ("Emergency", "E01", "EMERGENCY", 2500, "ABCD"), ("Emergency", "E02", "ICU", 8000, "AB"),
    ("Neurology", "601", "GENERAL", 1800, "AB"), ("Neurology", "602", "ICU", 7800, "A"),
]
beds = []
bid = 0
for dept, room, rtype, rate, letters in BED_LAYOUT:
    for L in letters:
        bid += 1
        beds.append({"id": bid, "dept": dept, "room": room, "bed": L, "type": rtype, "rate": rate, "busy": []})

# ==========================================================================
# 6. Appointments (history + today + upcoming)
# ==========================================================================
doc_slots_taken = defaultdict(set)    # (doctor_id, day_off) -> set(times)
pat_slots_taken = defaultdict(set)    # (patient_id, day_off) -> set(times)
appointments = []                     # dicts


def lead_time_days(appt_type):
    if appt_type == "FOLLOW_UP":
        return wchoice([R.randint(0, 1), R.randint(2, 7), R.randint(8, 21), R.randint(22, 45)], [10, 30, 42, 18])
    return wchoice([R.randint(0, 1), R.randint(2, 7), R.randint(8, 21), R.randint(22, 60)], [30, 38, 22, 10])


def noshow_probability(p, appt_type, lead, wd, t, dept, prev_noshow, n_prev):
    """Behavioural model used ONLY to generate the historic labels.
    The ML model never sees this function - it must re-discover the
    pattern from the data in Oracle."""
    a = p["age"]
    x = -2.30 + p["z"]
    x += -1.0 if lead <= 1 else (0.0 if lead <= 7 else (0.75 if lead <= 21 else 1.3))
    x += 1.0 if prev_noshow else 0.0
    x += (-0.45 if a < 15 else 0.50 if a < 30 else 0.10 if a < 45 else -0.15 if a < 60 else -0.40 if a < 75 else 0.15)
    x += {0: 0.25, 5: 0.35}.get(wd, 0.0)
    hh = int(t[:2])
    x += 0.30 if hh >= 16 else (-0.20 if hh == 9 else 0.0)
    x += 0.30 if appt_type == "NEW" else 0.0
    x += -0.65 if p["insured"] else 0.0
    x += 0.80 if p["outstation"] else 0.0
    x += {"Dermatology": 0.30, "Cardiology": -0.30, "Gynecology": -0.20, "Pediatrics": -0.15,
          "Neurology": -0.05, "Ophthalmology": 0.10}.get(dept, 0.0)
    x += -0.20 if n_prev >= 6 else 0.0          # loyal regular patients
    return 1.0 / (1.0 + math.exp(-x))


def find_slot(doc, day_off, patient_id, prefer=None):
    sessions = list(doc["sess"])
    R.shuffle(sessions)
    for s in sessions:
        slots = SESSION_SLOTS[s][:]
        if prefer:
            slots.sort(key=lambda t: abs(int(t[:2]) * 60 + int(t[3:]) - prefer))
        else:
            R.shuffle(slots)
        for t in slots:
            if t not in doc_slots_taken[(doc["id"], day_off)] and t not in pat_slots_taken[(patient_id, day_off)]:
                return t
    return None


def working(doc, off):
    return weekday(off) in doc["days"]


def book(p, dept, day_off, appt_type, doc=None, future=False, today=False):
    cands = DOCS_BY_DEPT[dept]
    # move forward to a day where some doctor of the department works
    for shift in range(0, 8):
        off = day_off + shift
        if today:
            off = day_off
        if not today and weekday(off) == 6:
            continue
        pool = [doc] if doc and (today or working(doc, off)) else [c for c in cands if today or working(c, off)]
        R.shuffle(pool)
        for c in pool:
            t = find_slot(c, off, p["id"], prefer=R.choice([None, 600, 840, 960]))
            if t:
                return c, off, t
        if today:
            return None
    return None


for p in patients:
    names, weights = pick_departments(p)
    primary = wchoice(names, weights)
    # registration date: somewhere before first visit
    chronic_bias = 1.0 + (0.6 if p["age"] > 50 else 0.0)
    n_visits = max(2, min(26, int(R.expovariate(1 / (9.5 * chronic_bias))) + 2))
    first_off = R.randint(HIST_START, -200) if R.random() < 0.7 else R.randint(HIST_START, HIST_END - 3)
    p["reg_off"] = min(first_off - R.randint(0, 20), -2) if R.random() < 0.85 else -R.randint(460, 1500)
    off = first_off
    history = []
    pref_doc = None
    dept = primary
    for v in range(n_visits):
        if off > HIST_END:
            break
        # new episode in a different department?
        if v > 0 and R.random() < 0.18:
            dept = wchoice(names, weights)
            pref_doc = None
        appt_type = "NEW" if (v == 0 or pref_doc is None) else ("FOLLOW_UP" if R.random() < 0.8 else "NEW")
        res = book(p, dept, off, appt_type, doc=pref_doc)
        if not res:
            off += R.randint(7, 30)
            continue
        doc, aoff, t = res
        if aoff > HIST_END:
            break
        lead = lead_time_days(appt_type)
        prev_ns = bool(history) and history[-1]["status"] == "NO_SHOW"
        prob = noshow_probability(p, appt_type, lead, weekday(aoff), t, dept, prev_ns, len(history))
        r = R.random()
        if r < 0.065:
            status = "CANCELLED"
        elif R.random() < prob:
            status = "NO_SHOW"
        else:
            status = "COMPLETED"
        created = aoff - lead + R.choice([9.25, 10.5, 11.75, 13.0, 15.5, 17.25, 19.5]) / 24
        if lead == 0:
            created = aoff + 8.0 / 24 + R.random() * 0.03     # same-day walk-in booking (before slot)
        a = {"patient": p["id"], "doctor": doc["id"], "dept": dept, "off": aoff, "time": t,
             "type": appt_type, "status": status, "created": created, "lead": lead, "prob": prob}
        appointments.append(a)
        history.append(a)
        doc_slots_taken[(doc["id"], aoff)].add(t)
        pat_slots_taken[(p["id"], aoff)].add(t)
        pref_doc = doc if status != "CANCELLED" else pref_doc
        # gap to next visit: follow-up 1-6 weeks, chronic monthly, else long
        if status == "NO_SHOW" and R.random() < 0.55:
            off = aoff + R.randint(2, 14)          # re-booked soon after missing
        else:
            off = aoff + wchoice([R.randint(7, 21), R.randint(25, 45), R.randint(60, 150)], [40, 35, 25])
    p["history"] = history
    p["primary"] = primary
    if history:
        p["reg_off"] = min(p["reg_off"], int(math.floor(min(h["created"] for h in history))) - 1)
    p["names"], p["weights"] = names, weights

# Today's appointments: ~22 SCHEDULED at TRUNC(SYSDATE)
TODAY_KEY = "TODAY"
today_appts = []
cands = R.sample([p for p in patients if p["history"]], 26)
for p in cands:
    dept = p["primary"]
    doc = R.choice(DOCS_BY_DEPT[dept])
    t = None
    free = [tt for s in doc["sess"] for tt in SESSION_SLOTS[s]
            if tt not in doc_slots_taken[(doc["id"], TODAY_KEY)] and tt not in pat_slots_taken[(p["id"], TODAY_KEY)]]
    if free:
        t = R.choice(free)
    if not t:
        continue
    doc_slots_taken[(doc["id"], TODAY_KEY)].add(t)
    pat_slots_taken[(p["id"], TODAY_KEY)].add(t)
    a = {"patient": p["id"], "doctor": doc["id"], "dept": dept, "off": TODAY_KEY, "time": t,
         "type": R.choice(["FOLLOW_UP", "FOLLOW_UP", "NEW"]), "status": "SCHEDULED",
         "created": None, "lead": R.randint(1, 12)}
    today_appts.append(a)
today_appts = today_appts[:22]

# Upcoming appointments B+7 .. B+27 (scored by the ML pipeline)
upcoming = []
for p in R.sample(patients, 260):
    dept = p["primary"] if R.random() < 0.8 else wchoice(p["names"], p["weights"])
    last_doc = None
    if p["history"]:
        ld = [h for h in p["history"] if h["dept"] == dept]
        if ld:
            last_doc = next(dd for dd in doctors if dd["id"] == ld[-1]["doctor"])
    appt_type = "FOLLOW_UP" if (last_doc and R.random() < 0.75) else "NEW"
    off = R.randint(FUT_START, FUT_END)
    res = book(p, dept, off, appt_type, doc=last_doc)
    if not res:
        continue
    doc, aoff, t = res
    if aoff > FUT_END + 6:
        continue
    lead = lead_time_days(appt_type)
    doc_slots_taken[(doc["id"], aoff)].add(t)
    pat_slots_taken[(p["id"], aoff)].add(t)
    created = aoff - lead + R.choice([9.5, 11.0, 12.5, 16.0, 18.5]) / 24
    upcoming.append({"patient": p["id"], "doctor": doc["id"], "dept": dept, "off": aoff, "time": t,
                     "type": appt_type, "status": "SCHEDULED", "created": created, "lead": lead})

# order: chronological history, then today, then upcoming -> appointment ids
appointments.sort(key=lambda a: (a["off"], a["time"], a["doctor"]))
all_appts = appointments + today_appts + sorted(upcoming, key=lambda a: (a["off"], a["time"], a["doctor"]))
for i, a in enumerate(all_appts, start=1):
    a["id"] = i

PAT = {p["id"]: p for p in patients}
DOC = {doc["id"]: doc for doc in doctors}

# ==========================================================================
# 7. Patients rows (needs reg_off from appointments)
# ==========================================================================
for p in patients:
    reg = p.get("reg_off", -30)
    db.add("patient", {
        "patient_id": p["id"], "first_name": p["first"], "last_name": p["last"],
        "dob": None,  # set below (absolute date)
        "gender": p["gender"], "blood_group": wchoice([b for b, _ in BLOOD], [w for _, w in BLOOD]),
        "phone": p["phone"], "email": p["email"], "address": p["addr"], "city": p["city"],
        "emergency_contact_name": p["ec_name"], "emergency_contact_phone": p["ec_phone"],
        "registered_date": Raw(d(reg), reg),
    })

# DOB: absolute dates computed against a reference "today" of 2026-10-21 so
# ages stay realistic; children were generated with a precise age.
import datetime as _dt
REF_TODAY = _dt.date(2026, 10, 21)
for row, p in zip(db.tables["patient"], patients):
    dob = REF_TODAY - _dt.timedelta(days=p["dob_days"])
    row["dob"] = Raw(f"DATE '{dob.isoformat()}'", dob.isoformat())
    p["dob"] = dob

# ==========================================================================
# 8. Staff schedule: B-14 .. B+27 for every working day/session
# ==========================================================================
sid = 0
for doc in doctors:
    for off in range(-14, FUT_END + 1):
        if weekday(off) == 6 or not working(doc, off):
            continue
        for s in doc["sess"]:
            sid += 1
            st, en = SESSION_TIMES[s]
            db.add("staff_schedule", {"schedule_id": sid, "doctor_id": doc["id"], "schedule_date": Raw(d(off), off),
                                      "start_time": st, "end_time": en, "max_patients": 16})

# ==========================================================================
# 9. Clinical data for COMPLETED appointments
# ==========================================================================
diag_rows, ds_rows, vital_rows, note_rows = [], [], [], []
presc_rows, pitem_rows, lab_rows = [], [], []
bill_rows, bitem_rows, pay_rows = [], [], []
med_used = defaultdict(int)


def pick_disease(dept, p):
    opts = [x for x in DISEASES[dept]
            if x[3][0] <= p["age"] <= x[3][1] and (x[4] is None or x[4] == p["gender"])]
    if not opts:
        opts = [x for x in DISEASES[dept] if x[4] is None] or DISEASES[dept]
    return wchoice(opts, [x[2] for x in opts])


def vitals_for(p, flags):
    a = p["age"]
    fever = flags.get("fever") and R.random() < 0.75
    temp = round(R.uniform(38.0, 39.6), 1) if fever else round(R.uniform(36.3, 37.2), 1)
    if a < 1:
        pulse = R.randint(110, 150)
    elif a < 6:
        pulse = R.randint(90, 130)
    elif a < 13:
        pulse = R.randint(75, 115)
    else:
        pulse = R.randint(62, 98)
    if fever:
        pulse = min(pulse + R.randint(8, 20), 180)
    if flags.get("cardiac") and R.random() < 0.3:
        pulse = R.randint(96, 128)
    if a < 13:
        sbp, dbp = R.randint(90, 112), R.randint(55, 72)
    else:
        sbp = int(R.gauss(112 + 0.45 * max(0, a - 30), 9))
        dbp = int(R.gauss(72 + 0.15 * max(0, a - 30), 6))
        if flags.get("htn"):
            sbp, dbp = sbp + R.randint(18, 38), dbp + R.randint(8, 20)
    sbp = max(80, min(sbp, 220)); dbp = max(50, min(dbp, 125))
    if dbp >= sbp - 20:
        dbp = sbp - 25
    spo2 = round(R.uniform(91.0, 95.5), 1) if flags.get("resp") else round(R.uniform(96.0, 99.5), 1)
    # height / weight by age
    if a < 2:
        h = 50 + a * 25 + R.uniform(-3, 3); w = 3.3 + a * 6.5 + R.uniform(-0.8, 0.8)
    elif a < 18:
        h = 75 + (a - 2) * 6.2 + R.uniform(-6, 6); w = 10 + (a - 2) * 2.9 + R.uniform(-3, 4)
    else:
        h = (171 if p["gender"] == "M" else 157) + R.gauss(0, 6.5)
        bmi = R.gauss(25.2 if flags.get("diabetes") or flags.get("htn") else 23.4, 3.6)
        w = bmi * (h / 100) ** 2
    return temp, pulse, sbp, dbp, spo2, round(h, 1), round(w, 1)


def lab_result(code, disease_flags, p):
    f = disease_flags
    if code == "LAB-CBC":
        hb = round(R.uniform(9.2, 11.4) if R.random() < 0.3 else R.uniform(11.8, 15.8), 1)
        wbc = round(R.uniform(11.5, 16.5) if f.get("fever") and R.random() < 0.5 else R.uniform(4.5, 10.5), 1)
        plt = R.randint(45, 110) if f.get("dengue") else R.randint(160, 390)
        return f"Hb {hb} g/dL; WBC {wbc} x10^3/uL; Platelets {plt} x10^3/uL"
    if code == "LAB-FBS":
        return f"{R.randint(128, 210) if f.get('diabetes') else R.randint(78, 104)} mg/dL"
    if code == "LAB-HBA1C":
        return f"{round(R.uniform(7.0, 10.4), 1) if f.get('diabetes') else round(R.uniform(5.0, 6.2), 1)} %"
    if code == "LAB-LIPID":
        ldl = R.randint(128, 196) if R.random() < 0.6 else R.randint(80, 125)
        return f"TC {ldl + R.randint(60, 90)}; LDL {ldl}; HDL {R.randint(32, 55)}; TG {R.randint(110, 260)} mg/dL"
    if code == "LAB-LFT":
        return f"ALT {R.randint(18, 72)} U/L; AST {R.randint(16, 60)} U/L; Bilirubin {round(R.uniform(0.4, 1.4), 1)} mg/dL"
    if code == "LAB-KFT":
        return f"Creatinine {round(R.uniform(0.7, 1.6), 2)} mg/dL; Urea {R.randint(18, 48)} mg/dL"
    if code == "LAB-TSH":
        return f"{round(R.uniform(5.2, 11.8), 2) if R.random() < 0.6 else round(R.uniform(0.9, 3.8), 2)} mIU/L"
    if code == "LAB-URINE":
        return R.choice(["Pus cells 25-30 /hpf; Nitrite positive", "Pus cells 10-12 /hpf",
                         "Pus cells 2-3 /hpf; No abnormality"])
    if code == "LAB-ECG":
        return R.choice(["Normal sinus rhythm", "Sinus tachycardia", "ST depression in V4-V6",
                         "Left ventricular hypertrophy pattern", "Atrial fibrillation with controlled rate"])
    if code == "LAB-ECHO":
        return f"LVEF {R.randint(32, 64)} %; " + R.choice(["Grade I diastolic dysfunction", "Concentric LVH", "No RWMA", "Mild MR"])
    if code == "LAB-CXR":
        return R.choice(["No active lesion", "Right lower zone consolidation", "Cardiomegaly (CTR 0.58)",
                         "Bilateral hilar prominence", "No fracture seen"])
    if code == "LAB-XRK":
        return R.choice(["Reduced medial joint space, osteophytes (KL grade 2)",
                         "Reduced joint space, subchondral sclerosis (KL grade 3)", "Normal joint space"])
    if code == "LAB-NS1":
        return "Positive" if f.get("dengue") and R.random() < 0.8 else "Negative"
    if code == "LAB-CRP":
        return f"{round(R.uniform(12, 96), 1)} mg/L"
    if code == "LAB-VITD":
        return f"{round(R.uniform(8, 27), 1) if R.random() < 0.7 else round(R.uniform(31, 62), 1)} ng/mL"
    if code == "LAB-USG":
        return R.choice(["Bulky ovaries with multiple peripheral follicles", "Single live intrauterine pregnancy, CRL appropriate",
                         "No abnormality detected", "Fatty liver grade I"])
    if code == "LAB-MRI":
        return R.choice(["No abnormality detected", "Acute infarct in left MCA territory",
                         "Chronic small vessel ischaemic changes", "Right mesial temporal sclerosis"])
    if code == "LAB-AUD":
        return f"Bilateral SNHL - {R.choice(['mild', 'moderate', 'moderately severe'])} ({R.randint(30, 65)} dB)"
    return "Within normal limits"


SEVERITY = ["MILD", "MODERATE", "SEVERE"]

NOTE_PLANS = ["Advised rest and plenty of oral fluids.", "Review after one week with reports.",
              "Lifestyle modification counselled - diet and 30 min daily walk.",
              "Red-flag symptoms explained; to report to Emergency if worse.",
              "Medication adherence discussed.", "Follow-up in 2 weeks.", "Continue current medication.",
              "Physiotherapy referral given.", "Diet chart provided."]

diag_id = presc_id = pitem_id = lab_id = vital_id = note_id = bill_id = bitem_id = pay_id = 0
completed = [a for a in appointments if a["status"] == "COMPLETED"]
DISEASE_SEEN = {}   # ICD-10 code -> (name, chronic flag)  => DISEASE table (3NF: code -> name)


def add_bill(patient, appt_id, adm_id, day_off, items, insured, age_days_ago):
    """items: list of (desc, category, amount). Creates bill + payments with a
    status consistent with what trg_bill_status_update would compute."""
    global bill_id, bitem_id, pay_id
    bill_id += 1
    total = round(sum(x[2] for x in items), 2)
    # payment behaviour
    r = R.random()
    if age_days_ago > 30:
        plan = "PAID" if r < 0.94 else ("PARTIALLY_PAID" if r < 0.98 else "UNPAID")
    elif age_days_ago > 7:
        plan = "PAID" if r < 0.78 else ("PARTIALLY_PAID" if r < 0.9 else "UNPAID")
    else:
        plan = "PAID" if r < 0.55 else ("PARTIALLY_PAID" if r < 0.7 else "UNPAID")
    bill_rows.append({"bill_id": bill_id, "patient_id": patient, "appointment_id": appt_id,
                      "admission_id": adm_id, "bill_date": Raw(d(day_off), day_off), "status": plan})
    for desc, cat, amt in items:
        bitem_id += 1
        bitem_rows.append({"bill_item_id": bitem_id, "bill_id": bill_id, "item_description": desc[:150],
                           "item_category": cat, "amount": round(amt, 2)})
    payments = []
    if plan == "PAID":
        if insured and (adm_id or total > 2500) and R.random() < 0.8:
            ins = round(total * R.uniform(0.7, 0.9), 2)
            payments = [(ins, "INSURANCE"), (round(total - ins, 2), wchoice(["UPI", "CARD", "CASH"], [55, 30, 15]))]
        else:
            payments = [(total, wchoice(["UPI", "CASH", "CARD", "NET_BANKING"], [48, 25, 21, 6]))]
    elif plan == "PARTIALLY_PAID":
        part = round(total * R.uniform(0.3, 0.7), 2)
        payments = [(part, wchoice(["UPI", "CASH", "CARD"], [50, 30, 20]))]
    for k, (amt, mode) in enumerate(payments):
        if amt <= 0:
            continue
        pay_id += 1
        poff = day_off + (0 if k == 0 and not adm_id else R.randint(0, 3))
        poff = min(poff, -1) if isinstance(day_off, int) and day_off < 0 else poff
        pay_rows.append({"payment_id": pay_id, "bill_id": bill_id, "amount_paid": amt,
                         "payment_mode": mode, "paid_date": Raw(d(poff), poff)})


for a in completed:
    p = PAT[a["patient"]]
    doc = DOC[a["doctor"]]
    dis = pick_disease(a["dept"], p)
    name, icd, _w, _ages, _g, syms, meds, labs, sev_w, flags = dis
    flags = dict(flags)
    if "Dengue" in name:
        flags["dengue"] = True
    items = [("Consultation - Dr. " + doc["row"]["first_name"] + " " + doc["row"]["last_name"]
              + f" ({a['dept']})", "CONSULTATION", float(doc["fee"]))]
    hh, mm = int(a["time"][:2]), int(a["time"][3:])
    # vitals (most visits)
    if R.random() < 0.8:
        vital_id += 1
        temp, pulse, sbp, dbp, spo2, h, w = vitals_for(p, flags)
        t_off = a["off"] + (hh * 60 + mm - 10) / 1440
        vital_rows.append({"vital_id": vital_id, "patient_id": p["id"], "appointment_id": a["id"], "admission_id": None,
                           "recorded_at": Raw(dt(t_off), t_off), "temperature_c": temp, "pulse_rate": pulse,
                           "systolic_bp": sbp, "diastolic_bp": dbp, "spo2_percent": spo2,
                           "height_cm": h, "weight_kg": w})
    if R.random() < 0.88:
        diag_id += 1
        sev = wchoice(SEVERITY, sev_w)
        diag_rows.append({"diagnosis_id": diag_id, "patient_id": p["id"], "doctor_id": doc["id"],
                          "appointment_id": a["id"], "admission_id": None,
                          "disease_code": icd, "severity": sev, "diagnosis_date": Raw(d(a["off"]), a["off"])})
        DISEASE_SEEN.setdefault(icd, (name, "Y" if flags.get("chronic") else "N"))
        for s in R.sample(syms, k=min(len(syms), R.randint(1, 3))):
            ds_rows.append({"diagnosis_id": diag_id, "symptom_id": SYM_ID[s]})
        # clinical note
        if R.random() < 0.55:
            note_id += 1
            ns = ", ".join(s.lower() for s in syms[:3])
            text = (f"Patient presented with {ns}. Examination findings consistent with {name.lower()} "
                    f"({icd}), severity {sev.lower()}. " + R.choice(NOTE_PLANS))
            n_off = a["off"] + (hh * 60 + mm + 12) / 1440
            note_rows.append({"note_id": note_id, "patient_id": p["id"], "doctor_id": doc["id"],
                              "appointment_id": a["id"], "admission_id": None, "note_text": text,
                              "created_at": Raw(dt(n_off), n_off)})
        # prescription
        if meds and R.random() < 0.9:
            presc_id += 1
            status = "FULFILLED" if a["off"] < -7 else "ACTIVE"
            if R.random() < 0.03:
                status = "CANCELLED"
            presc_rows.append({"prescription_id": presc_id, "patient_id": p["id"], "doctor_id": doc["id"],
                               "appointment_id": a["id"], "prescribed_date": Raw(d(a["off"]), a["off"]),
                               "status": status})
            chosen = meds if len(meds) <= 2 else R.sample(meds, R.randint(2, len(meds)))
            for code, dosage, days, perday in chosen:
                pitem_id += 1
                qty = max(1, int(math.ceil(days * perday)))
                if p["age"] < 12 and MED_BY_CODE[code][3] < 5:
                    qty = max(1, qty // 2)
                pitem_rows.append({"prescription_item_id": pitem_id, "prescription_id": presc_id,
                                   "medicine_id": MED_ID[code], "dosage": dosage[:50], "duration_days": days,
                                   "quantity": qty})
                med_used[code] += qty
                if status == "FULFILLED" and R.random() < 0.75:
                    m = MED_BY_CODE[code]
                    items.append((f"{m[1]} x {qty}", "MEDICINE", round(m[3] * qty, 2)))
        # labs
        if labs and R.random() < 0.55:
            for code in R.sample(labs, k=min(len(labs), R.randint(1, 2))):
                lab_id += 1
                t = LAB_BY_CODE[code]
                res_off = a["off"] + R.choice([0, 0, 1, 1, 2])
                pending = a["off"] >= -3 and R.random() < 0.6
                if res_off > -1:
                    res_off = -1 if a["off"] <= -1 else a["off"]
                lab_rows.append({"lab_order_id": lab_id, "patient_id": p["id"], "doctor_id": doc["id"],
                                 "lab_test_id": LAB_ID[code], "order_date": Raw(d(a["off"]), a["off"]),
                                 "status": ("SAMPLE_COLLECTED" if R.random() < 0.5 else "ORDERED") if pending else "RESULT_READY",
                                 "result_value": None if pending else lab_result(code, flags, p),
                                 "result_date": None if pending else Raw(d(max(res_off, a["off"])), max(res_off, a["off"]))})
                items.append((t[1], "LAB_TEST", float(t[3])))
    add_bill(p["id"], a["id"], None, a["off"], items, p["insured"], -a["off"])

# ==========================================================================
# 10. Admissions (historical discharged + currently admitted)
# ==========================================================================
admissions = []
adm_id = 0


def bed_free(bed, start, end):
    return all(end < s or start > e for s, e in bed["busy"])


def pick_bed(dept, types, start, end):
    pool = [b for b in beds if b["type"] in types and (b["dept"] == dept or (dept == "Emergency" and b["dept"] == "Emergency"))]
    pool += [b for b in beds if b["dept"] == "General Medicine" and b["type"] in ("GENERAL", "PRIVATE")]
    R.shuffle(pool)
    for b in pool:
        if bed_free(b, start, end):
            return b
    return None


MAINTENANCE_BEDS = {7, 31}  # two beds under maintenance today


def make_admission(current):
    global adm_id, diag_id, vital_id, note_id, lab_id
    dept, reason, dname, icd, (dmin, dmax), types, labs, meds = R.choice(ADMISSION_CASES)
    elig = [p for p in patients if
            (dept != "Pediatrics" or p["age"] < 14) and (dept == "Pediatrics" or p["age"] >= 16) and
            (dept != "Gynecology" or (p["gender"] == "F" and 19 <= p["age"] <= 40)) and
            (dept not in ("Cardiology", "Neurology") or p["age"] >= 40) and
            ("knee" not in reason or p["age"] >= 50) and ("hip" not in reason or p["age"] >= 60)]
    p = R.choice(elig)
    los = R.randint(dmin, dmax)
    if current:
        start = -R.randint(1, max(2, dmax - 1))
        end = 10_000
    else:
        start = R.randint(HIST_START + 10, -10)
        end = start + los
        if end >= 0:
            return None
    if any(not (end + 3 < s0 or start > e0 + 3) for s0, e0 in p.setdefault("adm_busy", [])):
        return None
    bed = None
    for _ in range(20):
        bed = pick_bed(dept, types, start, end)
        if bed and bed["id"] not in MAINTENANCE_BEDS:
            break
        bed = None
    if not bed:
        return None
    bed["busy"].append((start, end))
    p["adm_busy"].append((start, end))
    adm_id += 1
    doc = R.choice(DOCS_BY_DEPT[dept])
    adm = {"admission_id": adm_id, "patient_id": p["id"], "room_bed_id": bed["id"], "admitting_doctor_id": doc["id"],
           "admit_date": Raw(dt(start + R.uniform(0.3, 0.9)), start), "discharge_date":
               None if current else Raw(dt(end + R.uniform(0.40, 0.6)), end),
           "status": "ADMITTED" if current else "DISCHARGED", "admission_reason": reason}
    admissions.append((adm, p, bed, doc, dname, icd, labs, meds, start, end, current, los))
    return adm


for _ in range(90):
    make_admission(False)
cur = 0
while cur < 13:
    if make_admission(True):
        cur += 1

for adm, p, bed, doc, dname, icd, labs, meds, start, end, current, los in admissions:
    DISEASE_SEEN.setdefault(icd, (dname, "N"))
    diag_id += 1
    diag_rows.append({"diagnosis_id": diag_id, "patient_id": p["id"], "doctor_id": doc["id"], "appointment_id": None,
                      "admission_id": adm["admission_id"], "disease_code": icd,
                      "severity": wchoice(SEVERITY, [5, 45, 50]), "diagnosis_date": Raw(d(start), start)})
    for s in R.sample(["Chest pain", "Breathlessness", "Fever", "Weakness of limb", "Swelling", "Vomiting",
                       "Dizziness", "Fatigue"], 2):
        ds_rows.append({"diagnosis_id": diag_id, "symptom_id": SYM_ID[s]})
    span = (0 if current else los)
    last_day = (-0.0 if current else end)
    for k in range(R.randint(2, 4)):
        vital_id += 1
        if current:
            tday = start + 0.95 + k * (-start - 1.0) / 4.0
        else:
            tday = start + 0.95 + k * (span - 0.5) / 4.0
        temp, pulse, sbp, dbp, spo2, h, w = vitals_for(p, {"fever": "fever" in adm["admission_reason"].lower(),
                                                           "cardiac": "Cardio" in DEPARTMENTS[DEPT_ID[doc["dept"]] - 1][0]})
        vital_rows.append({"vital_id": vital_id, "patient_id": p["id"], "appointment_id": None,
                           "admission_id": adm["admission_id"], "recorded_at": Raw(dt(tday), tday),
                           "temperature_c": temp, "pulse_rate": pulse, "systolic_bp": sbp, "diastolic_bp": dbp,
                           "spo2_percent": spo2, "height_cm": h, "weight_kg": w})
    note_id += 1
    note_rows.append({"note_id": note_id, "patient_id": p["id"], "doctor_id": doc["id"], "appointment_id": None,
                      "admission_id": adm["admission_id"],
                      "note_text": f"Admitted with {adm['admission_reason'].lower()}. Provisional diagnosis: {dname} ({icd}). "
                                   + ("Patient stable, under observation." if current else
                                      f"Treated for {los} day(s); discharged in stable condition with advice."),
                      "created_at": Raw(dt(start + 0.5), start)})
    items = []
    for code in labs:
        lab_id += 1
        t = LAB_BY_CODE[code]
        pend = current and R.random() < 0.35
        lab_rows.append({"lab_order_id": lab_id, "patient_id": p["id"], "doctor_id": doc["id"], "lab_test_id": LAB_ID[code],
                         "order_date": Raw(d(start), start),
                         "status": "SAMPLE_COLLECTED" if pend else "RESULT_READY",
                         "result_value": None if pend else lab_result(code, {"dengue": "Dengue" in dname, "fever": True}, p),
                         "result_date": None if pend else Raw(d(start if current else min(start + 1, end)), start)})
        items.append((t[1], "LAB_TEST", float(t[3])))
    if not current:
        items.insert(0, (f"Room charges - {bed['type'].title()} ward, Room {bed['room']}-{bed['bed']} x {los} day(s)",
                         "ROOM_CHARGE", float(bed["rate"] * los)))
        if "replacement" in adm["admission_reason"] or "fracture" in dname.lower():
            items.append(("Surgical procedure & OT charges", "PROCEDURE", float(R.choice([85000, 120000, 145000]))))
        for code in meds:
            m = MED_BY_CODE[code]
            q = R.randint(6, 20)
            items.append((f"{m[1]} x {q} (inpatient)", "MEDICINE", round(m[3] * q, 2)))
        items.append(("Nursing & consumables", "OTHER", float(R.randint(8, 30) * 100)))
        add_bill(p["id"], None, adm["admission_id"], end, items, p["insured"], -end)

# ==========================================================================
# 11. Insurance policies
# ==========================================================================
pol = 0
for p in patients:
    if not p["insured"]:
        continue
    pol += 1
    prov = wchoice(INSURERS, [18, 14, 14, 12, 12, 10, 12, 8])
    months = R.choice([2, 5, 8, 11, 14, 18, 23]) if R.random() < 0.9 else -R.randint(1, 6)
    cover = R.choice([200000, 300000, 500000, 500000, 700000, 1000000]) if "PM-JAY" not in prov else 500000
    db.add("insurance_policy", {"policy_id": pol, "patient_id": p["id"],
                                "policy_no": f"{''.join(w[0] for w in prov.split()[:2]).upper()}/{R.randint(2019, 2026)}/{R.randint(100000, 999999)}",
                                "provider_name": prov, "coverage_amount": float(cover),
                                "valid_until": Raw(f"ADD_MONTHS(TRUNC(SYSDATE),{months})", months * 30)})

# ==========================================================================
# 12. Service queue: last 6 days (completed) + today (live)
# ==========================================================================
queue_rows = []
qid = 0
qnum = defaultdict(int)
for a in appointments:
    if a["off"] < -6 or a["status"] not in ("COMPLETED", "NO_SHOW"):
        continue
    key = ("OPD", a["off"])
    qnum[key] += 1
    qid += 1
    hh, mm = int(a["time"][:2]), int(a["time"][3:])
    arr = a["off"] + (hh * 60 + mm - R.randint(5, 35)) / 1440
    p = PAT[a["patient"]]
    queue_rows.append({"queue_id": qid, "queue_type": "OPD", "queue_number": qnum[key],
                       "queue_date": Raw(d(a["off"]), a["off"]), "patient_id": a["patient"], "doctor_id": a["doctor"],
                       "department_id": DEPT_ID[a["dept"]],
                       "priority_level": 2 if (p["age"] < 12 or p["age"] > 65) else 3,
                       "arrival_time": Raw(dt(arr), arr),
                       "called_time": Raw(dt(arr + R.randint(5, 40) / 1440), arr) if a["status"] == "COMPLETED" else None,
                       "status": "COMPLETED" if a["status"] == "COMPLETED" else "CANCELLED"})
# today: OPD from today's appointments, with a realistic live mix
today_q = []
for i, a in enumerate(sorted(today_appts, key=lambda x: x["time"])):
    p = PAT[a["patient"]]
    mins_ago = max(2, 160 - i * 7 + R.randint(-3, 3))
    st = "COMPLETED" if i < 6 else ("CALLED" if i < 8 else "WAITING")
    today_q.append(("OPD", a["patient"], a["doctor"], DEPT_ID[a["dept"]],
                    2 if (p["age"] < 12 or p["age"] > 65) else 3, mins_ago, st))
for p in R.sample([x for x in patients if x["age"] > 18], 4):
    today_q.append(("EMERGENCY", p["id"], None, DEPT_ID["Emergency"], R.choice([1, 1, 2]), R.randint(4, 50), "WAITING"))
for p in R.sample(patients, 5):
    today_q.append(("LAB", p["id"], None, None, 3, R.randint(5, 90), R.choice(["WAITING", "WAITING", "COMPLETED"])))
for p in R.sample(patients, 5):
    today_q.append(("PHARMACY", p["id"], None, None, 3, R.randint(3, 70), R.choice(["WAITING", "COMPLETED"])))
tq_num = defaultdict(int)
for qt, pid_, did, dep, prio, mins_ago, st in sorted(today_q, key=lambda x: -x[5]):
    tq_num[qt] += 1
    qid += 1
    queue_rows.append({"queue_id": qid, "queue_type": qt, "queue_number": tq_num[qt],
                       "queue_date": Raw(TODAY, "TODAY"), "patient_id": pid_, "doctor_id": did, "department_id": dep,
                       "priority_level": prio,
                       "arrival_time": Raw(f"SYSTIMESTAMP - NUMTODSINTERVAL({mins_ago},'MINUTE')", "TODAY"),
                       "called_time": Raw(f"SYSTIMESTAMP - NUMTODSINTERVAL({max(1, mins_ago - R.randint(5, 25))},'MINUTE')", "TODAY")
                       if st in ("CALLED", "COMPLETED") else None,
                       "status": st})

# ==========================================================================
# 13. Emit rows into DB in FK-safe order
# ==========================================================================
for i, s in enumerate(SYMPTOMS, start=1):
    db.add("symptom", {"symptom_id": i, "symptom_name": s})

for i, m in enumerate(MEDICINES, start=1):
    code, name, cat, price, stock, reorder, exp_m = m
    db.add("medicine", {"medicine_id": i, "medicine_code": code, "medicine_name": name, "category": cat,
                        "unit_price": float(price), "stock_quantity": stock, "reorder_level": reorder,
                        "expiry_date": Raw(f"ADD_MONTHS(TRUNC(SYSDATE),{exp_m})", exp_m * 30)})

for i, t in enumerate(LAB_TESTS, start=1):
    db.add("lab_test_catalog", {"lab_test_id": i, "test_code": t[0], "test_name": t[1],
                                "normal_range": t[2], "price": float(t[3])})

current_beds = {adm["room_bed_id"] for adm, *_rest in admissions if adm["status"] == "ADMITTED"}
for b in beds:
    st = "OCCUPIED" if b["id"] in current_beds else ("MAINTENANCE" if b["id"] in MAINTENANCE_BEDS else "AVAILABLE")
    db.add("room_bed", {"room_bed_id": b["id"], "room_no": b["room"], "bed_no": b["bed"],
                        "department_id": DEPT_ID[b["dept"]], "room_type": b["type"], "status": st,
                        "daily_rate": float(b["rate"])})

for a in all_appts:
    if a["off"] == TODAY_KEY:
        date_expr = Raw(TODAY, "TODAY")
        created_expr = Raw(f"SYSTIMESTAMP - NUMTODSINTERVAL({a['lead']},'DAY')", "TODAY")
    else:
        date_expr = Raw(d(a["off"]), a["off"])
        if a["status"] == "SCHEDULED":
            created_expr = Raw(f"LEAST({dt(a['created'])}, SYSDATE)", a["created"])
        else:
            created_expr = Raw(dt(a["created"]), a["created"])
    reason_map = {
        "General Medicine": ["Fever and cough", "Follow-up for sugar control", "BP check", "Weakness and fatigue",
                             "Stomach upset", "Routine health check", "Body ache and fever"],
        "Cardiology": ["Chest discomfort on exertion", "BP follow-up", "Palpitations", "Post-angioplasty review",
                       "ECG/Echo review", "Breathlessness on walking"],
        "Orthopedics": ["Knee pain", "Lower back pain", "Shoulder stiffness", "Post-fracture review", "Neck pain"],
        "Pediatrics": ["Fever and cold", "Vaccination and growth check", "Cough and wheeze", "Loose motions", "Ear pain"],
        "Dermatology": ["Acne", "Itchy skin rash", "Fungal infection", "Hair fall", "Skin allergy"],
        "ENT": ["Blocked nose", "Throat pain", "Ear wax / ear pain", "Recurrent sneezing", "Reduced hearing"],
        "Gynecology": ["Antenatal check-up", "Irregular periods", "Painful periods", "Urine burning", "PCOS follow-up"],
        "Emergency": ["Minor injury", "Acute pain", "Fever with vomiting"],
        "Neurology": ["Headache", "Seizure follow-up", "Numbness in feet", "Post-stroke review", "Giddiness"],
        "Ophthalmology": ["Blurred vision", "Red eye", "Cataract evaluation", "Spectacle check", "Eye pressure check"],
    }
    db.add("appointment", {"appointment_id": a["id"], "patient_id": a["patient"], "doctor_id": a["doctor"],
                           "appt_date": date_expr, "appt_time": a["time"], "appt_type": a["type"],
                           "status": a["status"], "reason": R.choice(reason_map[a["dept"]]),
                           "created_at": created_expr})

for adm, *_rest in sorted(admissions, key=lambda x: x[0]["admission_id"]):
    db.add("admission", adm)

# every code must map to exactly ONE name (that is the functional dependency
# disease_code -> disease_name that justifies the separate DISEASE table)
_names = defaultdict(set)
for dept_list in DISEASES.values():
    for x in dept_list:
        _names[x[1]].add(x[0])
for x in ADMISSION_CASES:
    _names[x[3]].add(x[2])
_bad = {k: v for k, v in _names.items() if len(v) > 1}
assert not _bad, f"ICD code mapped to several names: {_bad}"
for code in sorted(DISEASE_SEEN):
    name, chronic = DISEASE_SEEN[code]
    db.add("disease", {"disease_code": code, "disease_name": name, "is_chronic": chronic})
for row in diag_rows:
    db.add("diagnosis", row)
seen = set()
for row in ds_rows:
    k = (row["diagnosis_id"], row["symptom_id"])
    if k in seen:
        continue
    seen.add(k)
    db.add("diagnosis_symptom", row)
for row in vital_rows:
    db.add("vital_sign", row)
for row in note_rows:
    db.add("clinical_note", row)

# make sure stock never goes below what we "dispensed" historically (stock is current stock)
for row in presc_rows:
    db.add("prescription", row)
for row in pitem_rows:
    db.add("prescription_item", row)
for row in lab_rows:
    db.add("lab_order", row)
for row in bill_rows:
    db.add("bill", row)
for row in bitem_rows:
    db.add("bill_item", row)
for row in pay_rows:
    db.add("payment", row)
for row in queue_rows:
    db.add("service_queue", row)

APP_USERS = [("admin1", "ADMIN", None, None), ("doctor1", "DOCTOR", 1, None), ("nurse1", "NURSE", None, 1),
             ("receptionist1", "RECEPTIONIST", None, None), ("labtech1", "LAB", None, None),
             ("pharmacist1", "PHARMACY", None, None), ("billingclerk1", "BILLING", None, None),
             ("readonly1", "READONLY", None, None)]
for i, (u, role, ldoc, lnur) in enumerate(APP_USERS, start=1):
    db.add("app_user", {"user_id": i, "username": u, "role_name": role, "linked_doctor_id": ldoc,
                        "linked_nurse_id": lnur, "linked_patient_id": None, "is_active": "Y",
                        "created_at": Raw(d(-200), -200)})

# ==========================================================================
# 14. Validation (PK / FK / UNIQUE / CHECK) before writing anything
# ==========================================================================
def validate():
    T = db.tables
    errs = []

    def pk(table, col):
        vals = [r[col] for r in T[table]]
        if len(vals) != len(set(vals)):
            errs.append(f"duplicate PK in {table}")
        return set(vals)

    ids = {t: pk(t, c) for t, c in [
        ("department", "department_id"), ("doctor", "doctor_id"), ("nurse", "nurse_id"), ("patient", "patient_id"),
        ("room_bed", "room_bed_id"), ("staff_schedule", "schedule_id"), ("appointment", "appointment_id"),
        ("admission", "admission_id"), ("symptom", "symptom_id"), ("diagnosis", "diagnosis_id"),
        ("vital_sign", "vital_id"), ("clinical_note", "note_id"), ("medicine", "medicine_id"),
        ("prescription", "prescription_id"), ("prescription_item", "prescription_item_id"),
        ("lab_test_catalog", "lab_test_id"), ("lab_order", "lab_order_id"), ("insurance_policy", "policy_id"),
        ("bill", "bill_id"), ("bill_item", "bill_item_id"), ("payment", "payment_id"), ("service_queue", "queue_id"),
        ("app_user", "user_id")]}

    def fk(table, col, parent, nullable=True):
        for r in T[table]:
            v = r[col]
            if v is None:
                if not nullable:
                    errs.append(f"{table}.{col} NULL")
            elif v not in ids[parent]:
                errs.append(f"FK {table}.{col}={v} -> {parent}")

    fk("department", "head_doctor_id", "doctor")
    fk("doctor", "department_id", "department", False)
    fk("nurse", "department_id", "department", False)
    fk("room_bed", "department_id", "department", False)
    fk("staff_schedule", "doctor_id", "doctor", False)
    for c, par in [("patient_id", "patient"), ("doctor_id", "doctor")]:
        fk("appointment", c, par, False)
    fk("admission", "patient_id", "patient", False); fk("admission", "room_bed_id", "room_bed", False)
    fk("admission", "admitting_doctor_id", "doctor", False)
    for t in ("diagnosis", "clinical_note"):
        fk(t, "patient_id", "patient", False); fk(t, "doctor_id", "doctor", False)
        fk(t, "appointment_id", "appointment"); fk(t, "admission_id", "admission")
    ids["disease"] = {r["disease_code"] for r in T["disease"]}
    fk("diagnosis", "disease_code", "disease", False)
    fk("diagnosis_symptom", "diagnosis_id", "diagnosis", False); fk("diagnosis_symptom", "symptom_id", "symptom", False)
    fk("vital_sign", "patient_id", "patient", False); fk("vital_sign", "appointment_id", "appointment")
    fk("vital_sign", "admission_id", "admission")
    fk("prescription", "patient_id", "patient", False); fk("prescription", "doctor_id", "doctor", False)
    fk("prescription", "appointment_id", "appointment")
    fk("prescription_item", "prescription_id", "prescription", False); fk("prescription_item", "medicine_id", "medicine", False)
    fk("lab_order", "patient_id", "patient", False); fk("lab_order", "doctor_id", "doctor", False)
    fk("lab_order", "lab_test_id", "lab_test_catalog", False)
    fk("insurance_policy", "patient_id", "patient", False)
    fk("bill", "patient_id", "patient", False); fk("bill", "appointment_id", "appointment"); fk("bill", "admission_id", "admission")
    fk("bill_item", "bill_id", "bill", False); fk("payment", "bill_id", "bill", False)
    fk("service_queue", "patient_id", "patient", False); fk("service_queue", "doctor_id", "doctor")
    fk("service_queue", "department_id", "department")
    fk("app_user", "linked_doctor_id", "doctor"); fk("app_user", "linked_nurse_id", "nurse")

    def uniq(table, cols, skip_null=True):
        seen = set()
        for r in T[table]:
            k = tuple(str(r[c]) if isinstance(r[c], Raw) else r[c] for c in cols)
            if skip_null and any(x is None for x in k):
                continue
            if k in seen:
                errs.append(f"UNIQUE {table}{cols} {k}")
            seen.add(k)

    uniq("department", ["department_name"]); uniq("doctor", ["license_no"]); uniq("doctor", ["email"])
    uniq("nurse", ["license_no"]); uniq("nurse", ["email"]); uniq("patient", ["email"])
    uniq("room_bed", ["room_no", "bed_no"]); uniq("staff_schedule", ["doctor_id", "schedule_date", "start_time"])
    uniq("appointment", ["doctor_id", "appt_date", "appt_time"]); uniq("appointment", ["patient_id", "appt_date", "appt_time"])
    uniq("symptom", ["symptom_name"]); uniq("medicine", ["medicine_code"]); uniq("prescription_item", ["prescription_id", "medicine_id"])
    uniq("lab_test_catalog", ["test_code"]); uniq("insurance_policy", ["patient_id"]); uniq("insurance_policy", ["policy_no"])
    uniq("service_queue", ["queue_type", "queue_date", "queue_number"]); uniq("app_user", ["username"])
    uniq("diagnosis_symptom", ["diagnosis_id", "symptom_id"])

    # CHECK constraints
    for r in T["diagnosis"]:
        if (r["appointment_id"] is None) == (r["admission_id"] is None):
            errs.append("chk_diag_one_encounter")
    for r in T["vital_sign"]:
        if not (25 <= r["temperature_c"] <= 45 and 20 <= r["pulse_rate"] <= 250 and 50 <= r["systolic_bp"] <= 260
                and 30 <= r["diastolic_bp"] <= 180 and 0 <= r["spo2_percent"] <= 100):
            errs.append(f"vital range {r}")
    for r in T["admission"]:
        if r["discharge_date"] is not None and r["discharge_date"].key < r["admit_date"].key:
            errs.append("chk_discharge_after")
    for r in T["lab_order"]:
        if r["result_date"] is not None and r["result_date"].key != "TODAY" and r["order_date"].key != "TODAY" \
                and r["result_date"].key < r["order_date"].key:
            errs.append("chk_result_after_order")
        if r["result_value"] and len(r["result_value"]) > 200:
            errs.append("result len")
    for r in T["prescription_item"]:
        if len(r["dosage"]) > 50 or r["quantity"] <= 0 or r["duration_days"] <= 0:
            errs.append(f"presc item {r}")
    for r in T["payment"]:
        if r["amount_paid"] <= 0:
            errs.append("payment amount")
    for r in T["staff_schedule"]:
        if not r["end_time"] > r["start_time"]:
            errs.append("schedule times")
    lens = {("patient", "address"): 200, ("patient", "city"): 60, ("disease", "disease_name"): 150, ("appointment", "reason"): 200,
            ("admission", "admission_reason"): 200, ("bill_item", "item_description"): 150,
            ("doctor", "qualification"): 120, ("doctor", "specialization"): 80, ("medicine", "medicine_name"): 120,
            ("lab_test_catalog", "normal_range"): 50, ("insurance_policy", "policy_no"): 30,
            ("doctor", "license_no"): 30, ("nurse", "license_no"): 30, ("patient", "phone"): 15}
    for (t, c), n in lens.items():
        for r in T[t]:
            if r[c] is not None and len(str(r[c])) > n:
                errs.append(f"{t}.{c} too long: {r[c]}")
    # bill status consistent with payments (what trg_bill_status_update computes)
    tot = defaultdict(float); paid = defaultdict(float)
    for r in T["bill_item"]:
        tot[r["bill_id"]] += r["amount"]
    for r in T["payment"]:
        paid[r["bill_id"]] += r["amount_paid"]
    for r in T["bill"]:
        b = r["bill_id"]
        exp = "PAID" if paid[b] >= tot[b] - 0.01 and paid[b] > 0 else ("PARTIALLY_PAID" if paid[b] > 0 else "UNPAID")
        if exp != r["status"]:
            errs.append(f"bill status {b} {r['status']} vs {exp}")
    # bed status vs current admissions
    occ = {r["room_bed_id"] for r in T["admission"] if r["status"] == "ADMITTED"}
    for r in T["room_bed"]:
        if (r["status"] == "OCCUPIED") != (r["room_bed_id"] in occ):
            errs.append("bed status")
    if errs:
        raise SystemExit("VALIDATION FAILED:\n  " + "\n  ".join(errs[:40]))


# ==========================================================================
# 15. Write SQL
# ==========================================================================
ORDER = ["department", "doctor", "nurse", "patient", "room_bed", "staff_schedule", "appointment", "admission",
         "symptom", "disease", "diagnosis", "diagnosis_symptom", "vital_sign", "clinical_note", "medicine", "prescription",
         "prescription_item", "lab_test_catalog", "lab_order", "insurance_policy", "bill", "bill_item", "payment",
         "service_queue", "app_user"]
SEQUENCES = [("seq_department_id", "department", "department_id"), ("seq_doctor_id", "doctor", "doctor_id"),
             ("seq_nurse_id", "nurse", "nurse_id"), ("seq_patient_id", "patient", "patient_id"),
             ("seq_room_bed_id", "room_bed", "room_bed_id"), ("seq_schedule_id", "staff_schedule", "schedule_id"),
             ("seq_appointment_id", "appointment", "appointment_id"), ("seq_admission_id", "admission", "admission_id"),
             ("seq_symptom_id", "symptom", "symptom_id"), ("seq_diagnosis_id", "diagnosis", "diagnosis_id"),
             ("seq_vital_id", "vital_sign", "vital_id"), ("seq_note_id", "clinical_note", "note_id"),
             ("seq_medicine_id", "medicine", "medicine_id"), ("seq_prescription_id", "prescription", "prescription_id"),
             ("seq_presc_item_id", "prescription_item", "prescription_item_id"),
             ("seq_labtest_id", "lab_test_catalog", "lab_test_id"), ("seq_laborder_id", "lab_order", "lab_order_id"),
             ("seq_policy_id", "insurance_policy", "policy_id"), ("seq_bill_id", "bill", "bill_id"),
             ("seq_bill_item_id", "bill_item", "bill_item_id"), ("seq_payment_id", "payment", "payment_id"),
             ("seq_queue_id", "service_queue", "queue_id"), ("seq_user_id", "app_user", "user_id")]


def write_sql(path):
    T = db.tables
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = f.write
        w("-- =====================================================================\n")
        w("-- 04_sample_data.sql\n")
        w("-- MediCore HCMS - complete, realistic seed data for EVERY table.\n")
        w("-- GENERATED by database/generate_seed_data.py (seed=%d) - do not hand-edit;\n" % SEED)
        w("-- change the generator and re-run it instead.\n")
        w("--\n")
        w("-- * Dates are relative to TRUNC(SYSDATE,'IW') (Monday of the install week)\n")
        w("--   so history is always in the past and upcoming visits always in the future.\n")
        w("-- * Explicit primary keys are inserted; the block at the end moves every\n")
        w("--   sequence past MAX(id) so new rows from the app never collide.\n")
        w("-- * Bill statuses / bed statuses are already consistent with what the\n")
        w("--   triggers in 10_triggers.sql and 14_bill_status_trigger.sql compute.\n")
        w("--\n-- Row counts:\n")
        for t in ORDER:
            w(f"--   {t:<20} {len(T[t]):>6}\n")
        w(f"--   {'TOTAL':<20} {sum(len(T[t]) for t in ORDER):>6}\n")
        w("-- =====================================================================\n")
        w("SET DEFINE OFF\n")
        w("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD';\n\n")
        for t in ORDER:
            rows = T[t]
            if not rows:
                continue
            cols = db.columns[t]
            if t == "department":
                cols = [c for c in cols if c != "head_doctor_id"]
            w(f"-- ---------------------------------------------------------------\n-- {t.upper()} ({len(rows)} rows)\n"
              f"-- ---------------------------------------------------------------\n")
            for r in rows:
                vals = ", ".join(sql_str(r[c]) for c in cols)
                w(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({vals});\n")
            if t == "doctor":
                w("\n-- department heads (circular FK department <-> doctor, so set after doctors exist)\n")
                for dep in T["department"]:
                    w(f"UPDATE department SET head_doctor_id = {dep['head_doctor_id']} WHERE department_id = {dep['department_id']};\n")
            w("COMMIT;\n\n")
        w("-- ---------------------------------------------------------------\n")
        w("-- Move every sequence past the highest explicit id we inserted\n")
        w("-- ---------------------------------------------------------------\n")
        w("DECLARE\n    v_max NUMBER;\n    v_val NUMBER;\n")
        w("    PROCEDURE sync(p_seq VARCHAR2, p_tab VARCHAR2, p_col VARCHAR2) IS\n    BEGIN\n")
        w("        EXECUTE IMMEDIATE 'SELECT NVL(MAX(' || p_col || '),0) FROM ' || p_tab INTO v_max;\n")
        w("        LOOP\n            EXECUTE IMMEDIATE 'SELECT ' || p_seq || '.NEXTVAL FROM dual' INTO v_val;\n")
        w("            EXIT WHEN v_val >= v_max;\n        END LOOP;\n    END;\nBEGIN\n")
        for s, t, c in SEQUENCES:
            w(f"    sync('{s}', '{t}', '{c}');\n")
        w("END;\n/\n\nCOMMIT;\n")


def summary():
    T = db.tables
    hist = [a for a in appointments]
    ns = sum(1 for a in hist if a["status"] == "NO_SHOW")
    cp = sum(1 for a in hist if a["status"] == "COMPLETED")
    cx = sum(1 for a in hist if a["status"] == "CANCELLED")
    print(f"historical appointments: {len(hist)} (completed {cp}, no-show {ns}, cancelled {cx}); "
          f"no-show rate among resolved = {ns / (ns + cp):.1%}")
    print(f"today: {len(today_appts)}, upcoming: {len(upcoming)}")
    for t in ORDER:
        print(f"  {t:<20} {len(T[t])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "04_sample_data.sql"))
    ap.add_argument("--dump", default=None, help="pickle the generated tables (for offline ML tests)")
    args = ap.parse_args()
    validate()
    write_sql(args.out)
    summary()
    print(f"wrote {args.out}")
    if args.dump:
        def plain(v):
            return v.key if isinstance(v, Raw) else v
        dump = {t: [{c: plain(v) for c, v in r.items()} for r in rows] for t, rows in db.tables.items()}
        with open(args.dump, "wb") as fh:
            pickle.dump(dump, fh)
        print(f"dumped tables to {args.dump}")
