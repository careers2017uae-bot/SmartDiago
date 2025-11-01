# app.py
"""
SmartDiago — IntelliDoctor
Streamlit app that uses Grok (x.ai) chat API to provide an AI-assisted medical triage and reporting tool.

Set your API key as:
- Streamlit secrets: GROQ_API_KEY
  or
- Environment variable: GROQ_API_KEY

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os
import io
import json
import base64
from datetime import datetime
from typing import List, Dict

import streamlit as st
import requests
from fpdf import FPDF

# ---------- Config ----------
st.set_page_config(page_title="SmartDiago — IntelliDoctor", layout="wide")
st.title("🩺 SmartDiago — IntelliDoctor (AI Medical Assistant)")
st.markdown(
    "**Prototype / Educational Use Only.** This application is NOT a replacement for medical care. "
    "Always consult a licensed clinician for diagnosis or treatment decisions."
)

API_URL = "https://api.x.ai/v1/chat/completions"
# Prefer Streamlit secrets, fallback to environment variable
API_KEY = st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else os.getenv("GROQ_API_KEY")

DEFAULT_MODEL = "grok-beta"  # change if your account supports another Grok model

# ---------- Helpers ----------
def show_api_warning():
    st.error("GROQ_API_KEY not found. Set GROQ_API_KEY in Streamlit Secrets or as an environment variable.")
    st.stop()

def call_grok_chat(messages: List[Dict], model: str = DEFAULT_MODEL, temperature: float = 0.0, max_tokens: int = 1024):
    """
    Chat wrapper for Grok / x.ai endpoint.
    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    Returns text or raises Exception with details.
    """
    if not API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY. See README / app instructions.")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        # include server body for debugging
        raise RuntimeError(f"API error {resp.status_code}: {resp.text}")
    data = resp.json()
    # expected shape: {"choices":[{"message":{"role":"assistant","content":"..."}}], ...}
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        # fallback
        return json.dumps(data, indent=2)

def make_pdf_report(patient: Dict, timeline: List[Dict], uploaded_files: List[Dict]) -> bytes:
    """
    Simple PDF generator using fpdf. timeline: list of {"title":..., "content":...}
    uploaded_files: list of {"name":..., "type": "image"|"pdf", "bytes": ...}
    """
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "SmartDiago — Patient Report", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)

    # Patient info
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Patient Information:", ln=True)
    pdf.set_font("Arial", size=11)
    for k, v in patient.items():
        pdf.multi_cell(0, 6, f"{k}: {v}")
    pdf.ln(3)

    # Timeline sections
    for entry in timeline:
        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(0, 7, entry.get("title", ""))
        pdf.set_font("Arial", size=11)
        pdf.multi_cell(0, 6, entry.get("content", ""))
        pdf.ln(2)

    if uploaded_files:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Uploaded Files:", ln=True)
        pdf.set_font("Arial", size=11)
        for f in uploaded_files:
            pdf.multi_cell(0, 6, f"- {f['name']} ({f['type']})")

    return pdf.output(dest="S").encode("latin1")

def bytes_download_link(b: bytes, filename: str, label: str):
    b64 = base64.b64encode(b).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">{label}</a>'
    return href

# ---------- Session State Initialization ----------
if "patient" not in st.session_state:
    st.session_state.patient = {
        "Name": "",
        "Age": 30,
        "Gender": "Male",
        "Location": "",
        "Past History": ""
    }
if "symptoms_text" not in st.session_state:
    st.session_state.symptoms_text = ""
if "initial_diag" not in st.session_state:
    st.session_state.initial_diag = ""
if "doctor_notes" not in st.session_state:
    st.session_state.doctor_notes = ""
if "test_recs" not in st.session_state:
    st.session_state.test_recs = ""
if "uploaded_results" not in st.session_state:
    st.session_state.uploaded_results = []  # dicts with name, bytes, type
if "final_diag" not in st.session_state:
    st.session_state.final_diag = ""
if "final_prescription" not in st.session_state:
    st.session_state.final_prescription = ""
if "followup" not in st.session_state:
    st.session_state.followup = ""
if "timeline" not in st.session_state:
    st.session_state.timeline = []

# ---------- Show API status ----------
if not API_KEY:
    show_api_warning()

# ---------- Layout ----------
left, right = st.columns([1, 1.4])

with left:
    st.header("Patient Profile")
    name = st.text_input("Full name", value=st.session_state.patient.get("Name", ""))
    age = st.number_input("Age", min_value=0, max_value=130, value=int(st.session_state.patient.get("Age", 30)))
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=0 if st.session_state.patient.get("Gender","Male")=="Male" else 1)
    location = st.text_input("Location / City", value=st.session_state.patient.get("Location",""))
    past_history = st.text_area("Past medical history (brief)", value=st.session_state.patient.get("Past History",""), height=80)

    col_a, col_b = st.columns(2)
    with col_a:
        calories = st.number_input("Daily calories intake (approx)", min_value=0, value=int(st.session_state.patient.get("Calories", 2000)))
        steps = st.number_input("Average steps/day", min_value=0, value=int(st.session_state.patient.get("Steps", 5000)))
    with col_b:
        sleep_hours = st.number_input("Avg sleep (hrs)", min_value=0.0, max_value=24.0, value=float(st.session_state.patient.get("Sleep", 7.0)))
        heart_rate = st.number_input("Resting heart rate (bpm)", min_value=30, max_value=200, value=int(st.session_state.patient.get("HeartRate", 72)))

    if st.button("Save profile"):
        st.session_state.patient.update({
            "Name": name, "Age": age, "Gender": gender, "Location": location, "Past History": past_history,
            "Calories": calories, "Steps": steps, "Sleep": sleep_hours, "HeartRate": heart_rate
        })
        st.success("Patient profile saved.")

    st.markdown("---")
    st.header("1) Symptoms (Upload or Paste)")
    uploaded_symptoms = st.file_uploader("Upload symptom text file (.txt/.md)", type=["txt","md"])
    if uploaded_symptoms:
        try:
            st.session_state.symptoms_text = uploaded_symptoms.read().decode("utf-8")
            st.success("Symptoms loaded from file.")
        except Exception:
            st.error("Could not read file; please paste symptoms below.")

    manual_symptoms = st.text_area("Or paste/type symptoms here (include duration, severity):", value=st.session_state.symptoms_text, height=180)
    st.session_state.symptoms_text = manual_symptoms

    if st.button("2) Get initial diagnostic (AI)"):
        st.info("Calling Grok for initial diagnostic...")
        sys_msg = "You are IntelliDoctor, a concise and responsible medical assistant. Always emphasize uncertainty, red flags, and advise to consult a clinician."
        prompt = (
            f"Patient profile: {json.dumps(st.session_state.patient)}\n\n"
            f"Symptoms:\n{st.session_state.symptoms_text}\n\n"
            "Task:\n1) Provide top 3 differential diagnoses with brief confidence %.\n"
            "2) List red flags needing urgent care.\n3) Suggest initial home management and urgency.\n4) Recommend initial tests to narrow diagnosis.\n"
            "Respond in numbered sections, concise."
        )
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ]
        try:
            out = call_grok_chat(messages, temperature=0.0, max_tokens=800)
            st.session_state.initial_diag = out
            st.success("Initial diagnostic generated.")
        except Exception as e:
            st.error(f"Error calling Grok API: {e}")

    if st.session_state.initial_diag:
        st.subheader("Initial Diagnostic (AI)")
        st.info(st.session_state.initial_diag)

    st.markdown("---")
    st.header("3) Doctor Input / Notes")
    doc_notes = st.text_area("Doctor notes / evaluation (edit AI output or add findings):", value=st.session_state.doctor_notes, height=140)
    st.session_state.doctor_notes = doc_notes
    if st.button("Save doctor notes"):
        st.success("Doctor notes saved.")

    st.markdown("---")
    st.header("4) Tests & Radiology (AI-assisted)")
    if st.button("Generate test & radiology recommendations"):
        if not st.session_state.symptoms_text and not st.session_state.initial_diag:
            st.warning("Please provide symptoms and run initial diagnostic first.")
        else:
            try:
                sys_msg = "You are a helpful clinician-assistant recommending appropriate lab and imaging tests."
                prompt = (
                    f"Patient profile: {json.dumps(st.session_state.patient)}\n\n"
                    f"Symptoms: {st.session_state.symptoms_text}\n\nDoctor notes: {st.session_state.doctor_notes}\n\n"
                    "Task: Provide a prioritized list of lab tests and imaging (including specific radiology views/protocols if relevant). For each test include purpose, what positive/negative results would indicate, and urgency (routine/urgent/emergency). Keep concise."
                )
                messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
                tr = call_grok_chat(messages, temperature=0.0, max_tokens=700)
                st.session_state.test_recs = tr
                st.success("Test & radiology recommendations generated.")
            except Exception as e:
                st.error(f"Error calling Grok API: {e}")

    if st.session_state.test_recs:
        st.subheader("Recommended Tests & Radiology")
        st.code(st.session_state.test_recs)

    st.markdown("---")
    st.header("5) Upload test results (images / pdf)")
    uploaded_files = st.file_uploader("Upload images (png/jpg) or PDFs (multiple allowed)", accept_multiple_files=True, type=["png","jpg","jpeg","pdf"])
    if uploaded_files:
        added = 0
        for f in uploaded_files:
            try:
                content = f.read()
                ftype = "pdf" if f.type == "application/pdf" or f.name.lower().endswith(".pdf") else "image"
                st.session_state.uploaded_results.append({"name": f.name, "bytes": content, "type": ftype})
                added += 1
            except Exception:
                st.warning(f"Could not read file {f.name}")
        if added:
            st.success(f"Added {added} file(s).")

    if st.session_state.uploaded_results:
        st.write("Uploaded results:")
        for idx, item in enumerate(st.session_state.uploaded_results):
            st.write(f"{idx+1}. {item['name']} ({item['type']})")
            if item["type"] == "image":
                st.image(item["bytes"], width=220)

with right:
    st.header("Compact Dashboard / Workflow")
    st.markdown("Use the buttons below to add items to the final report timeline and step through the process.")

    if st.button("Add: Initial AI diagnostic"):
        st.session_state.timeline.append({"title": "Initial AI Diagnostic", "content": st.session_state.initial_diag or "N/A"})
        st.success("Added initial diagnostic to timeline.")
    if st.button("Add: Doctor notes"):
        st.session_state.timeline.append({"title": "Doctor Notes", "content": st.session_state.doctor_notes or "N/A"})
        st.success("Added doctor notes to timeline.")
    if st.button("Add: Tests & Radiology"):
        st.session_state.timeline.append({"title": "Test & Radiology Recommendations", "content": st.session_state.test_recs or "N/A"})
        st.success("Added tests & radiology to timeline.")
    if st.button("Add: Uploaded Results summary"):
        uploads_summary = "\n".join([f"{u['name']} ({u['type']})" for u in st.session_state.uploaded_results]) or "None"
        st.session_state.timeline.append({"title": "Uploaded Results", "content": uploads_summary})
        st.success("Added uploaded results to timeline.")

    st.markdown("---")
    st.header("6) Final Diagnostic & Prescription (AI-assisted)")
    if st.button("Generate final diagnostic (AI)"):
        try:
            sys_msg = "You are IntelliDoctor: create a careful final diagnosis with conservative prescription suggestions. Always include uncertainty and when to refer."
            prompt = (
                f"Patient profile: {json.dumps(st.session_state.patient)}\n"
                f"Symptoms: {st.session_state.symptoms_text}\n"
                f"Initial AI diagnostic: {st.session_state.initial_diag}\n"
                f"Doctor notes: {st.session_state.doctor_notes}\n"
                f"Tests: {st.session_state.test_recs}\n"
                f"Uploaded files: {', '.join([u['name'] for u in st.session_state.uploaded_results])}\n\n"
                "Task: Provide 1) final concise diagnosis with reasoning and confidence, 2) suggested prescription (drug names, dose, duration) with alternatives and allergy/interaction cautions, 3) recommendations for referrals."
            )
            messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
            out = call_grok_chat(messages, temperature=0.0, max_tokens=900)
            st.session_state.final_diag = out
            st.success("Final diagnostic generated.")
        except Exception as e:
            st.error(f"Error calling Grok API: {e}")

    if st.session_state.final_diag:
        st.subheader("AI Final Diagnostic / Draft Prescription")
        st.info(st.session_state.final_diag)

    st.markdown("Doctor review & finalize prescription:")
    final_pres = st.text_area("Final prescription / clinician confirmation:", value=st.session_state.final_prescription or "", height=140)
    st.session_state.final_prescription = final_pres
    if st.button("Save final prescription to timeline"):
        st.session_state.timeline.append({"title": "Final Diagnostic & Prescription", "content": st.session_state.final_prescription or st.session_state.final_diag})
        st.success("Saved final prescription to timeline.")

    st.markdown("---")
    st.header("9) Generate Patient Report (PDF)")
    if st.button("Generate & preview report (PDF)"):
        if not st.session_state.timeline:
            # auto-build timeline
            st.session_state.timeline = [
                {"title": "Initial AI Diagnostic", "content": st.session_state.initial_diag},
                {"title": "Doctor Notes", "content": st.session_state.doctor_notes},
                {"title": "Tests & Radiology", "content": st.session_state.test_recs},
                {"title": "Final Diagnostic & Prescription", "content": st.session_state.final_prescription or st.session_state.final_diag}
            ]
        patient_info = st.session_state.patient.copy()
        pdf_bytes = make_pdf_report(patient_info, st.session_state.timeline, st.session_state.uploaded_results)
        st.session_state.last_report = pdf_bytes
        st.success("PDF report generated. Use the download button below.")

    if "last_report" in st.session_state:
        st.markdown(bytes_download_link(st.session_state.last_report, f"{st.session_state.patient.get('Name','patient')}_SmartDiago_Report.pdf", "📥 Download PDF report"), unsafe_allow_html=True)
        st.download_button("Download report", data=st.session_state.last_report, file_name=f"{st.session_state.patient.get('Name','patient')}_SmartDiago_Report.pdf", mime="application/pdf")

    st.markdown("---")
    st.header("10) Follow-up Recommendations")
    if st.button("Generate follow-up plan (AI)"):
        try:
            sys_msg = "You are a clinician assistant: propose follow-up scheduling, monitoring parameters, red flags and remote-monitoring suggestions."
            prompt = (
                f"Patient: {json.dumps(st.session_state.patient)}\n"
                f"Final diagnosis: {st.session_state.final_prescription or st.session_state.final_diag}\n"
                "Task: provide timelines for follow-up, monitoring metrics, red flags for early review, and lifestyle advice. Keep concise."
            )
            messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
            out = call_grok_chat(messages, temperature=0.0, max_tokens=500)
            st.session_state.followup = out
            st.success("Follow-up plan generated.")
        except Exception as e:
            st.error(f"Error calling Grok API: {e}")

    if st.session_state.followup:
        st.subheader("Follow-up Recommendations")
        st.info(st.session_state.followup)

# ---------- Timeline preview ----------
st.markdown("---")
st.header("Report Timeline Preview")
if st.session_state.timeline:
    for i, item in enumerate(st.session_state.timeline, start=1):
        st.write(f"**{i}. {item.get('title','Untitled')}**")
        st.write(item.get("content",""))
else:
    st.write("Timeline empty — use dashboard buttons to add items.")

# ---------- Footer / Debug ----------
st.markdown("---")
st.write("**Notes:** Configure `GROQ_API_KEY` in Streamlit secrets or as an environment variable. This app uses the Grok / x.ai chat endpoint.")
st.write("**Disclaimer:** For demonstration only. Not a replacement for professional medical advice.")
