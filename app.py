# app.py
import os
import io
import json
import base64
import tempfile
from datetime import datetime
from typing import List

import streamlit as st
import requests
from fpdf import FPDF  # for PDF generation

# ---------- Configuration ----------
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"  # chat style endpoint, compatible with Grok
DEFAULT_MODEL = "grok-3-mini"  # change to grok-4 if you have access (costs vary). See docs for model options. :contentReference[oaicite:2]{index=2}

if XAI_API_KEY is None:
    st.warning("XAI_API_KEY not found in environment. Set XAI_API_KEY to your x.ai (Grok) API key to use the AI features.")

st.set_page_config(page_title="SmartDiago - IntelliDoctor", layout="wide", initial_sidebar_state="expanded")

# ---------- Utilities ----------
def call_grok(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.0, max_tokens: int = 1000):
    """
    Small wrapper to call the Grok (x.ai) chat/completions endpoint.
    The endpoint and payload mirror common chat endpoints.
    """
    if not XAI_API_KEY:
        return "Missing API key. Set XAI_API_KEY in environment to call Grok."

    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise, professional medical-assistant helping triage symptoms, recommending tests, and drafting prescriptions. Always include uncertainty and advise to consult a doctor."},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        resp = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # try common fields
        if "choices" in data and len(data["choices"]) > 0:
            # assume standard chat/completion response shape
            text = data["choices"][0].get("message", {}).get("content") or data["choices"][0].get("text")
            return text.strip()
        # fallback: return JSON
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error calling Grok API: {str(e)}"

def make_pdf_report(patient_info: dict, timeline: List[dict], output_files: List[dict]):
    """
    Create a simple PDF report using FPDF.
    timeline: list of items with {"title":..., "content":...}
    output_files: list of {"name":..., "bytes":...} to attach as images (if image) or list as attachments.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, "SmartDiago - Patient Report", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)

    # Patient info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Patient Information:", ln=True)
    pdf.set_font("Arial", size=11)
    for k, v in patient_info.items():
        pdf.cell(0, 6, f"{k}: {v}", ln=True)
    pdf.ln(4)

    # Timeline / sections
    for entry in timeline:
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 7, entry.get("title", ""))
        pdf.set_font("Arial", size=11)
        # ensure long text wraps
        pdf.multi_cell(0, 6, entry.get("content", ""))
        pdf.ln(3)

    # Mention uploaded files
    if output_files:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Uploaded Files (attached or saved separately):", ln=True)
        pdf.set_font("Arial", size=11)
        for f in output_files:
            pdf.cell(0, 6, f"- {f.get('name')}", ln=True)

    # return bytes
    buf = pdf.output(dest="S").encode("latin1")
    return buf

def file_download_link(file_bytes: bytes, filename: str, label: str = "Download"):
    b64 = base64.b64encode(file_bytes).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# ---------- Session State Initialize ----------
if "patient" not in st.session_state:
    st.session_state.patient = {}
if "symptoms" not in st.session_state:
    st.session_state.symptoms = ""
if "initial_diag" not in st.session_state:
    st.session_state.initial_diag = ""
if "doctor_notes" not in st.session_state:
    st.session_state.doctor_notes = ""
if "test_recs" not in st.session_state:
    st.session_state.test_recs = ""
if "uploaded_results" not in st.session_state:
    st.session_state.uploaded_results = []  # list of dicts {"name":..., "bytes":..., "type": "image"/"pdf"}
if "final_diag" not in st.session_state:
    st.session_state.final_diag = ""
if "final_prescription" not in st.session_state:
    st.session_state.final_prescription = ""
if "followup" not in st.session_state:
    st.session_state.followup = ""

# ---------- Layout ----------
st.title("SmartDiago — IntelliDoctor (AI Medical Assistant)")
st.markdown("**Prototype / Educational Use Only.** Not a substitute for professional medical care. Always consult a licensed clinician.")

# Sidebar: patient metadata / navigation
with st.sidebar:
    st.header("Patient Profile")
    name = st.text_input("Full name", value=st.session_state.patient.get("Name",""))
    age = st.number_input("Age", min_value=0, max_value=130, value=int(st.session_state.patient.get("Age", 30)))
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=0 if st.session_state.patient.get("Gender","Male")=="Male" else 1)
    location = st.text_input("Location / City", value=st.session_state.patient.get("Location",""))
    past_records = st.text_area("Past medical history (brief)", value=st.session_state.patient.get("Past History",""), height=80)
    calories = st.number_input("Daily calories intake (approx)", min_value=0, value=int(st.session_state.patient.get("Calories",2000)))
    steps = st.number_input("Average steps/day", min_value=0, value=int(st.session_state.patient.get("Steps",5000)))
    sleep_hours = st.number_input("Average sleep (hrs)", min_value=0.0, max_value=24.0, value=float(st.session_state.patient.get("Sleep",7.0)))
    heart_rate = st.number_input("Resting heart rate (bpm)", min_value=30, max_value=200, value=int(st.session_state.patient.get("HeartRate",72)))

    if st.button("Save patient profile"):
        st.session_state.patient = {
            "Name": name,
            "Age": age,
            "Gender": gender,
            "Location": location,
            "Past History": past_records,
            "Calories": calories,
            "Steps": steps,
            "Sleep": sleep_hours,
            "HeartRate": heart_rate
        }
        st.success("Patient profile saved.")

# Main columns: left input / right dashboard
col1, col2 = st.columns([1, 1.4])

with col1:
    st.subheader("1. Upload / Enter Symptoms")
    uploaded_txt = st.file_uploader("Upload symptom description (txt or md) or paste below", type=["txt","md"])
    if uploaded_txt:
        try:
            txt = uploaded_txt.read().decode("utf-8")
            st.session_state.symptoms = txt
            st.success("Symptoms loaded from file.")
        except Exception:
            st.error("Could not read uploaded file; paste symptoms in the box below instead.")

    manual_symptoms = st.text_area("Or type/paste symptoms here (include duration, severity, red flags):", value=st.session_state.symptoms, height=200)
    st.session_state.symptoms = manual_symptoms

    if st.button("Get initial AI diagnostic"):
        with st.spinner("Analyzing symptoms with IntelliDoctor..."):
            prompt = f"""Patient data:
Name: {st.session_state.patient.get('Name','Unknown')}
Age: {st.session_state.patient.get('Age','?')}
Gender: {st.session_state.patient.get('Gender','?')}
Location: {st.session_state.patient.get('Location','?')}
Vitals/Activity: steps/day={st.session_state.patient.get('Steps','?')}, sleep={st.session_state.patient.get('Sleep','?')}, heart_rate={st.session_state.patient.get('HeartRate','?')}, calories={st.session_state.patient.get('Calories','?')}
Past history: {st.session_state.patient.get('Past History','None')}

Symptoms:
{st.session_state.symptoms}

Task:
1) Provide an initial differential diagnosis listing top 3 possible conditions with brief probability / confidence.
2) Suggest immediate red-flag signs requiring urgent care.
3) Recommend appropriate tests (lab/imaging) for narrowing diagnosis.
4) Provide short advice for initial home management and whether to seek emergency care.
Respond concisely in numbered sections."""
            out = call_grok(prompt, model=DEFAULT_MODEL, temperature=0.0, max_tokens=600)
            st.session_state.initial_diag = out
            st.success("Initial AI diagnostic generated.")

    if st.session_state.initial_diag:
        st.subheader("Initial Diagnostic (AI)")
        st.info(st.session_state.initial_diag)

    st.markdown("---")
    st.subheader("3. Doctor / Clinician Input")
    doc_input = st.text_area("Doctor notes / evaluation (edit AI or add findings):", value=st.session_state.doctor_notes, height=150)
    st.session_state.doctor_notes = doc_input
    if st.button("Save doctor notes"):
        st.success("Doctor notes saved.")

    st.markdown("---")
    st.subheader("4. Tests & Radiology Recommendations")
    if st.button("Generate test recommendations (AI)"):
        prompt = f"""Based on:
Patient age: {st.session_state.patient.get('Age')}, gender: {st.session_state.patient.get('Gender')}, past history: {st.session_state.patient.get('Past History')}.
Symptoms: {st.session_state.symptoms}
Doctor notes: {st.session_state.doctor_notes}

Task: Provide a prioritized list of lab tests, imaging, and specific radiology views/protocols if needed. For each test include: purpose, what results would indicate, and urgency (routine/urgent/emergency). Keep brief."""
        tr = call_grok(prompt, model=DEFAULT_MODEL, temperature=0.0, max_tokens=600)
        st.session_state.test_recs = tr
    if st.session_state.test_recs:
        st.success("Test recommendations ready.")
        st.code(st.session_state.test_recs)

    st.markdown("---")
    st.subheader("5. Upload test results (images or PDF)")
    files = st.file_uploader("Upload images (jpg/png) or PDFs of reports (can upload multiple)", accept_multiple_files=True, type=["png","jpg","jpeg","pdf"])
    if files:
        added = 0
        for f in files:
            content = f.read()
            typ = "pdf" if f.type == "application/pdf" or f.name.lower().endswith(".pdf") else "image"
            st.session_state.uploaded_results.append({"name": f.name, "bytes": content, "type": typ})
            added += 1
        st.success(f"Added {added} files to uploaded results.")

    if st.session_state.uploaded_results:
        st.write("Uploaded results:")
        for idx, item in enumerate(st.session_state.uploaded_results):
            st.write(f"{idx+1}. {item['name']} ({item['type']})")
            if item['type'] == "image":
                st.image(item['bytes'], width=200)

with col2:
    st.subheader("Compact Dashboard / Workflow")
    st.markdown("Use the buttons below to step through the diagnostic workflow. Each action appends to the timeline used in the final report.")

    # Timeline stored in session
    if "timeline" not in st.session_state:
        st.session_state.timeline = []

    if st.button("Add Initial AI diagnostic to report"):
        st.session_state.timeline.append({"title": "Initial AI Diagnostic", "content": st.session_state.initial_diag or "No AI diagnostic available."})
        st.success("Added initial diagnostic to timeline.")

    if st.button("Add Doctor notes to report"):
        st.session_state.timeline.append({"title": "Doctor Notes", "content": st.session_state.doctor_notes or "No doctor notes."})
        st.success("Added doctor notes to timeline.")

    if st.button("Add Test Recommendations to report"):
        st.session_state.timeline.append({"title": "Test & Radiology Recommendations", "content": st.session_state.test_recs or "No test recommendations."})
        st.success("Added test recommendations to timeline.")

    if st.button("Add Uploaded Results summary to report"):
        textblocks = []
        for item in st.session_state.uploaded_results:
            textblocks.append(f"{item['name']} ({item['type']})")
        st.session_state.timeline.append({"title": "Uploaded Test Results", "content": "\n".join(textblocks) if textblocks else "None"})
        st.success("Added uploads to timeline.")

    st.markdown("---")
    st.subheader("6. Final Diagnostic & Prescription")
    if st.button("Generate final diagnostic (AI)"):
        prompt = f"""Using all provided information below, produce:
1) A concise final diagnosis with reasoning and confidence.
2) A suggested prescription (drugs, dose, duration) where applicable, with alternatives and allergy/interaction warnings.
3) A short follow-up and monitoring plan.

Patient profile: {json.dumps(st.session_state.patient)}
Symptoms: {st.session_state.symptoms}
Initial AI diagnostic: {st.session_state.initial_diag}
Doctor notes: {st.session_state.doctor_notes}
Tests & their results (if uploaded): {', '.join([u['name'] for u in st.session_state.uploaded_results])}

Be conservative: include uncertainty and recommend specialist referral if appropriate."""
        out = call_grok(prompt, model=DEFAULT_MODEL, temperature=0.0, max_tokens=800)
        st.session_state.final_diag = out
    if st.session_state.final_diag:
        st.subheader("AI Final Diagnostic & Prescription (draft)")
        st.info(st.session_state.final_diag)

    st.markdown("Doctor review / finalize prescription:")
    final_doc_input = st.text_area("Final doctor edits / confirmed prescription:", value=st.session_state.final_prescription or "", height=140)
    st.session_state.final_prescription = final_doc_input

    if st.button("Save final prescription & add to report"):
        st.session_state.timeline.append({"title": "Final Diagnostic & Prescription", "content": st.session_state.final_prescription or st.session_state.final_diag})
        st.success("Saved final prescription into timeline.")

    st.markdown("---")
    st.subheader("9. Generate Patient Report (PDF)")
    if st.button("Generate & Show Report (PDF)"):
        patient_info = st.session_state.patient.copy()
        # build timeline if empty
        if not st.session_state.timeline:
            st.session_state.timeline = [
                {"title":"Initial AI Diagnostic", "content": st.session_state.initial_diag},
                {"title":"Doctor Notes", "content": st.session_state.doctor_notes},
                {"title":"Tests & Recommendations", "content": st.session_state.test_recs},
                {"title":"Final Diagnostic & Prescription", "content": st.session_state.final_prescription or st.session_state.final_diag}
            ]
        pdf_bytes = make_pdf_report(patient_info, st.session_state.timeline, st.session_state.uploaded_results)
        st.session_state.latest_report = pdf_bytes
        st.success("PDF report generated. Use the download link below.")

    if "latest_report" in st.session_state:
        st.markdown(file_download_link(st.session_state.latest_report, f"{st.session_state.patient.get('Name','patient')}_SmartDiago_Report.pdf", "Download patient PDF report"), unsafe_allow_html=True)
        st.write("---")
        st.download_button("Download report (file)", data=st.session_state.latest_report, file_name=f"{st.session_state.patient.get('Name','patient')}_SmartDiago_Report.pdf", mime="application/pdf")

    st.markdown("---")
    st.subheader("10. Follow-up Recommendations")
    if st.button("Generate follow-up plan (AI)"):
        prompt = f"""Create a follow-up and monitoring plan for the patient based on:
Patient: {json.dumps(st.session_state.patient)}
Final diagnosis/prescription: {st.session_state.final_prescription or st.session_state.final_diag}
Include timelines (when to follow-up), red flags for earlier review, lifestyle advice, and suggested remote monitoring (what to track and thresholds). Keep it concise."""
        out = call_grok(prompt, model=DEFAULT_MODEL, temperature=0.0, max_tokens=400)
        st.session_state.followup = out
    if st.session_state.followup:
        st.info(st.session_state.followup)

# bottom: quick timeline view
st.markdown("---")
st.subheader("Workflow Timeline Preview")
if st.session_state.timeline:
    for i, t in enumerate(st.session_state.timeline):
        st.write(f"**{i+1}. {t.get('title','Untitled')}**")
        st.write(t.get("content",""))
else:
    st.write("No timeline entries yet. Use the action buttons to append items to the patient report timeline.")

# Footer: small API info / disclaimers
st.markdown("---")
#st.markdown("**Notes:** This demo uses xAI / Grok API for AI-generated text. Configure `XAI_API_KEY` as an environment variable before running. See x.ai docs for models and pricing. :contentReference[oaicite:3]{index=3}")
st.markdown("**Disclaimer:** This software is only for demonstration. Do not rely on it for medical decision-making; always consult a licensed clinician.")
