"""The 11-question sample set from data/sample_questions.md, with grading
criteria hand-derived from actually reading every source document (STW PDFs
+ local protocol) -- not guessed. expected_state is what a correct system
must return; expect_doc_codes are the citation(s) that MUST appear when
ANSWERED/PARTIAL; expect_text_contains are substrings that must appear
verbatim in the answer (proving retrieve-and-quote, not paraphrase)."""
from __future__ import annotations

SAMPLE_QUESTIONS = [
    {
        "id": "Q1", "question": "What is the first-line antibiotic, dose basis, and duration for acute otitis media in a child?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-PED-01"],
        "expect_text_contains": ["Amoxicillin 40 mg/kg/day"],
    },
    {
        "id": "Q2", "question": "A 6-year-old with non-severe community pneumonia: what is the amoxicillin dose exactly as the workflow states it?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-PED-02"],
        "expect_text_contains": ["Amoxicillin 40 mg/kg/day"],
    },
    {
        "id": "Q3", "question": "What is the first-line initial drug therapy for newly diagnosed adult hypertension?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-GP-02"],
        "expect_text_contains": ["Amlodipine 5 mg"],
        "expect_version": "2025.2",  # the CURRENT edition -- must not answer from the archived 2021.1 edition
    },
    {
        "id": "Q4", "question": "Which analgesic class must be avoided in suspected dengue, and why?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-GP-04"],
        "expect_text_contains": ["NSAIDs", "bleeding"],
    },
    {
        "id": "Q5", "question": "What are the ORS volumes after each loose stool for a child aged 2-10 years, and what zinc course accompanies it?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-PED-03"],
        "expect_text_contains": ["100–200 ml", "Zinc 20 mg"],
    },
    {
        "id": "Q6", "question": "Which red flags in acute low back pain mandate imaging or referral?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-ORT-01"],
        "expect_text_contains": ["Saddle anaesthesia"],
    },
    {
        "id": "Q7", "question": "Which urinary antibiotic is avoided at 36+ weeks of pregnancy, and what is the stated alternative?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-GYN-02"],
        "expect_text_contains": ["Nitrofurantoin", "Cefixime"],
    },
    {
        "id": "Q8", "question": "At what HbA1c threshold at diagnosis does the workflow add a second agent to metformin, and which agent?",
        "expected_state": "ANSWERED", "expect_doc_codes": ["STW-GP-03"],
        "expect_text_contains": ["8.5%", "Glimepiride"],
    },
    {
        "id": "Q9", "question": "What is the first-line prophylactic drug for migraine in adults?",
        "expected_state": "ABSTAINED",
        "note": "No STW or local protocol in this corpus addresses migraine.",
    },
    {
        "id": "Q10", "question": "What is the standard drug regimen for newly diagnosed pulmonary tuberculosis?",
        "expected_state": "ABSTAINED",
        "note": "No STW or local protocol in this corpus addresses tuberculosis.",
    },
    {
        "id": "Q11", "question": "Per the clinic's own protocol, when are empirical antibiotics started in adult acute undifferentiated fever, and does the national workflow pack say the same?",
        "expected_state": "PARTIAL", "expect_doc_codes": ["SOP-CLIN-014"],
        "expect_text_contains": ["48 hours", "Azithromycin"],
        "expect_missing_source_type": "national_stw",
    },
]
