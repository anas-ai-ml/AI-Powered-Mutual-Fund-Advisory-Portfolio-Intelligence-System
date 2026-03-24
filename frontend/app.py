import streamlit as st
import sys
import os

# Add root directory to sys.path to allow backend imports if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.components.input_form import render_input_form
from frontend.components.dashboard import render_dashboard

st.set_page_config(page_title="Institutional Financial Engine", layout="wide")

# Minimal Institutional Custom CSS
st.markdown(
    """
<style>
    /* Premium Elegant Dark Theme */
    .stApp {
        background-color: #0B0F19 !important;
        color: #E2E8F0 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Elegant Cards & Containers */
    div[data-testid="stForm"], .stSelectbox > div > div, .stNumberInput > div > div {
        background-color: #111827 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
        transition: border-color 0.2s ease;
    }
    div[data-testid="stForm"]:hover, .stSelectbox > div > div:hover, .stNumberInput > div > div:hover {
        border-color: #374151 !important;
    }
    
    /* Sleek Typography */
    h1, h2, h3, h4 {
        color: #F8FAFC !important;
        font-weight: 300 !important;
        letter-spacing: -0.01em;
        border-bottom: 1px solid #1E293B;
        padding-bottom: 0.75rem;
    }
    p, label, span, div {
        color: #94A3B8;
    }
    
    /* High-End Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        color: #F8FAFC !important;
        font-weight: 400;
        letter-spacing: -0.02em;
        font-family: 'Helvetica Neue', 'Inter', sans-serif;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 500;
    }
    
    /* Premium Button (Muted Slate) */
    div.stButton > button:first-child {
        background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%) !important;
        color: #E2E8F0 !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        padding: 10px 20px;
        font-weight: 500;
        letter-spacing: 0.03em;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
        transition: all 0.2s ease;
    }
    div.stButton > button:first-child:hover {
        border-color: #475569 !important;
        color: #FFFFFF !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("AI-Powered Portfolio Intelligence Engine")

st.markdown("""
Welcome to the intelligent terminal. Define your profile on the left to activate the **Financial Quantum Engine** on the right.
""")

if "client_data" not in st.session_state:
    st.session_state.client_data = None

col1, col2 = st.columns([1, 2.5])

with col1:
    st.header("Client Profile")
    render_input_form()

with col2:
    st.header("Intelligence Dashboard")
    if st.session_state.client_data:
        render_dashboard(st.session_state.client_data)
    else:
        st.info("Please fill the Client Profile form to generate your financial plan.")

st.markdown("---")
with open(os.path.join(os.path.dirname(__file__), "..", "DISCLAIMER.txt"), "r") as f:
    disclaimer = f.read()
st.caption(f"**Disclaimer:** {disclaimer}")
