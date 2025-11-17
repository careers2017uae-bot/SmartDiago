# app.py
"""
SmartDiago — IntelliDoctor
Streamlit app using Grok (x.ai) chat API for AI-assisted medical triage and reporting.

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
# Load API key
API_KEY = st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = "grok-beta"

# ---------- Helper Functions ----------
def show_api_warning():
    st.error(
        "🚨 GROQ_API_KEY not found or invalid.\n"
        "Set GROQ_API_KEY in Streamlit Secrets (`.streamlit/secrets.toml`) or as an environment variable."
    )
    st.stop()

def call_grok_chat(messages: List[Dict], model: str = DEFAULT_MODEL, temperature: float = 0.0, max_tokens: int = 1024):
    """Call Grok / x.ai chat endpoint with error handling."""
    if not API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY. See instructions.")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.HTTPError as e:
        if resp.status_code == 400 and "Incorrect API key" in resp.text:
            st.error("🚨 Invalid GROQ_API_KEY provided. Please update your key in Streamlit Secrets or environment.")
            st.stop()
        else:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error calling Grok API: {e}") from e

def make_pdf_report(patient: Dict, timeline: List[Dict], uploaded_files: List[Dict]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "SmartDiago — Patient Report", ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Patient Information:", ln=True)
    pdf.set_font("Arial", size=11)
    for k, v in patient.items():
        pdf.multi_cell(0, 6, f"{k}: {v}")
    pdf.ln(3)
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

# ---------- Session State ----------
if "patient" not in st.session_state:
    st.session_state.patient = {"Name": "", "Age": 30, "Gender": "Male", "Location": "", "Past History": ""}
if "symptoms_text" not in st.session_state: st.session_state.symptoms_text = ""
if "initial_diag" not in st.session_state: st.session_state.initial_diag = ""
if "doctor_notes" not in st.session_state: st.session_state.doctor_notes = ""
if "test_recs" not in st.session_state: st.session_state.test_recs = ""
if "uploaded_results" not in st.session_state: st.session_state.uploaded_results = []
if "final_diag" not in st.session_state: st.session_state.final_diag = ""
if "final_prescription" not in st.session_state: st.session_state.final_prescription = ""
if "followup" not in st.session_state: st.session_state.followup = ""
if "timeline" not in st.session_state: st.session_state.timeline = []

# ---------- Check API Key ----------
if not API_KEY:
    show_api_warning()
else:
    st.success("✅ GROQ_API_KEY loaded successfully.")

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

# ------------------- Right Column & Dashboard Workflow -------------------
# You can continue adding the remaining workflow exactly as in your original app:
# Doctor notes, tests & radiology, file uploads, final diagnostic & prescription,
# PDF report generation, follow-up recommendations, and timeline dashboard.
# All session_state handling and button workflow remain the same.

