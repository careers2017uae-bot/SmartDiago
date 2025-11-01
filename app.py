import streamlit as st
import requests
import base64
from fpdf import FPDF

# ✅ Title and Description
st.set_page_config(page_title="SmartDiago - AI Medical Assistant", layout="wide")
st.title("🩺 SmartDiago - AI Medical Assistant")
st.write("""
**IntelliDoctor** is your AI-powered personal medical assistant.
It helps analyze symptoms, suggest diagnostics, recommend tests, and generate reports.
""")

# ✅ GROK (x.ai) API Config
API_URL = "https://api.x.ai/v1/chat/completions"
API_KEY = st.secrets.get("GROQ_API_KEY") or "YOUR_GROQ_API_KEY"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def call_grok(prompt):
    """Send prompt to Grok API and return response text"""
    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": "You are IntelliDoctor, an AI medical assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code != 200:
        st.error(f"Error calling Grok API: {response.status_code} - {response.text}")
        return None
    data = response.json()
    return data["choices"][0]["message"]["content"]

# ✅ Step 1: Upload Symptoms
symptoms = st.text_area("🧍‍♀️ Enter or Upload Patient Symptoms:", height=120)
if symptoms:
    if st.button("Analyze Symptoms"):
        with st.spinner("Analyzing symptoms..."):
            diagnostic = call_grok(f"Analyze the following symptoms and give an initial diagnosis:\n{symptoms}")
            if diagnostic:
                st.subheader("🩻 Initial Diagnostic Result")
                st.write(diagnostic)
                st.session_state["initial_diagnostic"] = diagnostic

# ✅ Step 2: Doctor's Input
doctor_input = st.text_area("👨‍⚕️ Doctor’s Notes / Comments (optional):", height=100)

# ✅ Step 3: Test & Radiology Recommendations
if st.button("Recommend Tests & Radiology"):
    if "initial_diagnostic" in st.session_state:
        with st.spinner("Preparing recommendations..."):
            recommendations = call_grok(
                f"Based on this diagnosis: {st.session_state['initial_diagnostic']}, "
                f"recommend relevant medical tests and radiology scans."
            )
            st.subheader("🧪 Recommended Tests & Radiology")
            st.write(recommendations)
            st.session_state["tests"] = recommendations
    else:
        st.warning("Please analyze symptoms first.")

# ✅ Step 4: Upload Results (Images / PDFs)
uploaded_files = st.file_uploader("📁 Upload Test Results (Image or PDF)", accept_multiple_files=True)

if uploaded_files:
    st.success(f"{len(uploaded_files)} files uploaded successfully.")

# ✅ Step 5: Final Diagnosis
if st.button("Generate Final Diagnosis"):
    all_data = f"""
    Symptoms: {symptoms}
    Doctor Input: {doctor_input}
    Tests: {st.session_state.get('tests', '')}
    Uploaded files: {[f.name for f in uploaded_files] if uploaded_files else 'None'}
    """
    with st.spinner("Generating final diagnosis..."):
        final_diag = call_grok(f"Using the following information, provide a comprehensive final diagnosis:\n{all_data}")
        if final_diag:
            st.subheader("🏥 Final Diagnosis")
            st.write(final_diag)
            st.session_state["final_diag"] = final_diag

# ✅ Step 6: Prescription
if st.button("Generate Prescription"):
    if "final_diag" in st.session_state:
        with st.spinner("Generating prescription..."):
            prescription = call_grok(f"Generate a complete medical prescription for:\n{st.session_state['final_diag']}")
            st.subheader("💊 Prescription")
            st.write(prescription)
            st.session_state["prescription"] = prescription

# ✅ Step 7: Generate PDF Report
if st.button("📄 Generate Patient Report (PDF)"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, "SmartDiago - AI Medical Report", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, f"""
Symptoms:
{symptoms}

Doctor's Input:
{doctor_input}

Tests & Radiology:
{st.session_state.get('tests', '')}

Final Diagnosis:
{st.session_state.get('final_diag', '')}

Prescription:
{st.session_state.get('prescription', '')}
    """)
    pdf.output("SmartDiago_Report.pdf")
    with open("SmartDiago_Report.pdf", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="SmartDiago_Report.pdf">📥 Download Report</a>'
        st.markdown(href, unsafe_allow_html=True)

# ✅ Step 8: Follow-up Recommendation
if st.button("🩹 Follow-up Recommendations"):
    if "final_diag" in st.session_state:
        with st.spinner("Analyzing follow-up steps..."):
            followup = call_grok(f"Suggest follow-up care plan for: {st.session_state['final_diag']}")
            st.subheader("📅 Follow-up Recommendations")
            st.write(followup)
