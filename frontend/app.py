from pathlib import Path
from datetime import datetime
import os
import sys

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from frontend.api_client import (
    APIClientError,
    API_BASE_URL,
    create_client_audit_log,
    get_advisor_profile,
    get_client_audit_trail,
    create_client_record,
    get_client_record,
    get_current_advisor,
    list_clients,
    login_advisor,
    register_advisor,
    update_advisor_profile,
    update_client_record,
)
from frontend.components.audit_trail import render_audit_trail_screen as render_audit_trail
from frontend.components.client_portal import render_client_portal
from frontend.components.dashboard import render_dashboard
from frontend.components.global_dashboard import render_global_dashboard
from frontend.components.input_form import render_input_form
from frontend.components.meeting_notes import render_meeting_notes
from frontend.components.portfolio_snapshot import render_portfolio_snapshot
from frontend.components.proposal_builder import render_proposal_builder
from frontend.components.review_report import render_review_report

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

st.markdown(
    """
Advisor login is the entry point. After authentication, select or create a client record, then load the existing dashboard on top of that client’s saved data.
"""
)


def _clear_login_state() -> None:
    for key in (
        "advisor_token",
        "advisor_id",
        "advisor_name",
        "advisor_email",
        "advisor_role",
        "selected_client_id",
        "selected_client_record",
        "client_data",
        "loaded_client_id",
        "show_new_client_form",
    ):
        st.session_state.pop(key, None)


def _clear_selected_client() -> None:
    for key in ("selected_client_id", "selected_client_record", "client_data", "loaded_client_id"):
        st.session_state.pop(key, None)


def _build_client_profile(client_record: dict) -> dict:
    profile = dict(client_record.get("profile_data") or {})
    for field in ("name", "age", "contact", "pan_placeholder", "city", "source_channel"):
        value = client_record.get(field)
        if value is not None and field not in profile:
            profile[field] = value
    return profile


def _render_login_screen() -> None:
    st.subheader("Advisor Login")
    st.caption(f"Connecting to backend API at `{API_BASE_URL}`.")
    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        if st.session_state.get("register_success_message"):
            st.success(st.session_state.pop("register_success_message"))
        with st.form("advisor_login_form", clear_on_submit=False):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", width="stretch")

        if submitted:
            try:
                auth_response = login_advisor(email=email, password=password)
            except APIClientError as exc:
                st.error(str(exc))
            else:
                advisor = auth_response.get("advisor", {})
                st.session_state["advisor_token"] = auth_response["access_token"]
                st.session_state["advisor_id"] = advisor.get("id")
                st.session_state["advisor_name"] = advisor.get("name", "Advisor")
                st.session_state["advisor_email"] = advisor.get("email")
                st.session_state["advisor_role"] = advisor.get("role", "advisor")
                st.success("Login successful.")
                st.rerun()

    with register_tab:
        with st.form("advisor_register_form", clear_on_submit=False):
            full_name = st.text_input("Full Name")
            register_email = st.text_input("Email")
            register_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            role = st.selectbox("Role", ["advisor", "admin"], index=0)
            register_submitted = st.form_submit_button("Register", width="stretch")

        if register_submitted:
            if not full_name.strip() or not register_email.strip() or not register_password or not confirm_password:
                st.error("All fields are required.")
            elif len(register_password) < 8:
                st.error("Password must be at least 8 characters long.")
            elif register_password != confirm_password:
                st.error("Passwords do not match.")
            elif "@" not in register_email or "." not in register_email.split("@")[-1]:
                st.error("Enter a valid email address.")
            else:
                try:
                    register_advisor(
                        email=register_email,
                        password=register_password,
                        name=full_name,
                        role=role,
                    )
                except APIClientError as exc:
                    message = str(exc)
                    if "already exists" in message.lower():
                        st.error("An account with this email already exists.")
                    else:
                        st.error(message)
                else:
                    st.session_state["register_success_message"] = "Account created. Please login."
                    st.rerun()


def _render_new_client_form(token: str) -> None:
    with st.form("new_client_form", clear_on_submit=True):
        st.markdown("### New Client")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name")
            age = st.number_input("Age", min_value=18, max_value=100, value=30)
            contact = st.text_input("Contact")
        with col2:
            pan_placeholder = st.text_input("PAN Placeholder")
            city = st.text_input("City")
            source_channel = st.text_input("Source Channel")
        submitted = st.form_submit_button("Create Client", width="stretch")

    if not submitted:
        return

    if not name.strip():
        st.error("Client name is required.")
        return

    try:
        created = create_client_record(
            token,
            {
                "name": name.strip(),
                "age": int(age),
                "contact": contact.strip() or None,
                "pan_placeholder": pan_placeholder.strip() or None,
                "city": city.strip() or None,
                "source_channel": source_channel.strip() or None,
            },
        )
    except APIClientError as exc:
        st.error(str(exc))
        return

    st.session_state["show_new_client_form"] = False
    st.session_state["selected_client_id"] = created["id"]
    st.session_state["loaded_client_id"] = None
    st.success("Client created.")
    st.rerun()


def _render_client_selector(token: str) -> None:
    advisor_role = st.session_state.get("advisor_role", "advisor")
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.subheader("Client List")
        st.caption(
            (
                f"Signed in as `{st.session_state.get('advisor_name', 'Advisor')}` (`{advisor_role}`). "
                "Admin can view every client record."
            )
            if advisor_role == "admin"
            else f"Signed in as `{st.session_state.get('advisor_name', 'Advisor')}` (`{advisor_role}`). Advisors see only their own clients."
        )
    with header_col2:
        if st.button("Logout", width="stretch"):
            _clear_login_state()
            st.rerun()

    action_col1, action_col2 = st.columns([1, 4])
    with action_col1:
        if st.button("New Client", width="stretch"):
            st.session_state["show_new_client_form"] = not st.session_state.get("show_new_client_form", False)
    with action_col2:
        st.caption(
            "Admin access is global across clients."
            if advisor_role == "admin"
            else "Each advisor only sees their own clients."
        )

    if st.session_state.get("show_new_client_form"):
        _render_new_client_form(token)

    try:
        clients = list_clients(token)
    except APIClientError as exc:
        st.error(str(exc))
        if "authorization" in str(exc).lower() or "token" in str(exc).lower():
            _clear_login_state()
            st.rerun()
        return

    if not clients:
        st.info("No clients found yet. Create the first client record to begin.")
        return

    for client in clients:
        container = st.container(border=True)
        with container:
            col1, col2, col3, col4 = st.columns([2.5, 1, 1, 1])
            with col1:
                st.markdown(f"**{client.get('name', 'Unnamed Client')}**")
                st.caption(
                    (
                        f"Age {client.get('age', '-')} | Contact: {client.get('contact') or '-'} | Source: {client.get('source_channel') or '-'} | Owner: {client.get('advisor_name') or client.get('advisor_id')}"
                        if advisor_role == "admin"
                        else f"Age {client.get('age', '-')} | Contact: {client.get('contact') or '-'} | Source: {client.get('source_channel') or '-'}"
                    )
                )
            with col2:
                st.metric("Risk Class", client.get("risk_class") or "Not saved")
            with col3:
                risk_score = client.get("risk_score")
                st.metric(
                    "Risk Score",
                    f"{float(risk_score):.1f}/10" if risk_score is not None else "—",
                )
            with col4:
                if st.button("Open", key=f"open_client_{client['id']}", width="stretch"):
                    st.session_state["selected_client_id"] = client["id"]
                    st.session_state["loaded_client_id"] = None
                    st.rerun()


def _render_advisor_settings(token: str) -> None:
    st.subheader("Advisor Settings")
    st.caption("Update your branding details — these appear on all generated PDF reports.")

    try:
        profile = get_advisor_profile(token)
    except APIClientError as exc:
        st.error(f"Could not load profile: {exc}")
        return

    with st.form("advisor_settings_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Display Name", value=profile.get("name") or "")
            firm_name = st.text_input("Firm / Company Name", value=profile.get("firm_name") or "",
                                      placeholder="e.g. Vinsan Financial Services")
        with col2:
            phone = st.text_input("Phone Number", value=profile.get("phone") or "",
                                  placeholder="e.g. +91 98765 43210")
            logo_path = st.text_input("Logo File Path (server path)", value=profile.get("logo_path") or "",
                                      placeholder="e.g. /app/assets/logo.png")

        st.caption(f"Email: `{profile.get('email')}` (cannot be changed) | Role: `{profile.get('role')}`")
        save = st.form_submit_button("Save Settings", use_container_width=True)

    if save:
        try:
            updated = update_advisor_profile(token, {
                "name": name.strip() or None,
                "firm_name": firm_name.strip() or None,
                "phone": phone.strip() or None,
                "logo_path": logo_path.strip() or None,
            })
            st.session_state["advisor_name"] = updated.get("name", st.session_state.get("advisor_name"))
            st.success("Settings saved. Your details will appear on the next generated report.")
        except APIClientError as exc:
            st.error(f"Failed to save: {exc}")

    st.markdown("---")
    st.markdown("**Client Portal Link**")
    st.caption("Share this URL pattern with clients after issuing a proposal:")
    st.code("http://localhost:8501/?view=portal&client_id=<CLIENT_ID>", language="text")


def _render_audit_trail(token: str, client_id: int) -> None:
    st.subheader("Audit Trail")
    st.caption("Chronological history of profile edits, proposal actions, and report issues for this client.")
    try:
        audit_entries = get_client_audit_trail(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not audit_entries:
        st.info("No audit events recorded for this client yet.")
        return

    for entry in audit_entries:
        container = st.container(border=True)
        with container:
            st.markdown(
                f"**{entry.get('action', 'event').replace('_', ' ').title()}**  \n"
                f"`{entry.get('timestamp', '-')}` • Advisor `{entry.get('advisor_id', '-')}`"
            )
            if entry.get("notes"):
                st.caption(entry["notes"])
            before_value = entry.get("before_value")
            after_value = entry.get("after_value")
            if before_value is not None or after_value is not None:
                before_col, after_col = st.columns(2)
                with before_col:
                    st.markdown("**Before**")
                    st.json(before_value or {})
                with after_col:
                    st.markdown("**After**")
                    st.json(after_value or {})


def _load_selected_client(token: str, client_id: int) -> tuple[dict, dict] | tuple[None, None]:
    if st.session_state.get("loaded_client_id") == client_id:
        return st.session_state.get("selected_client_record"), st.session_state.get("client_data")

    try:
        client_record = get_client_record(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        _clear_selected_client()
        return None, None

    try:
        create_client_audit_log(
            token,
            client_id,
            {
                "action": "analysis_viewed",
                "after_value": {
                    "viewed_at": datetime.now().isoformat(),
                    "viewed_by": st.session_state.get("advisor_name"),
                },
                "notes": "Client analysis workspace opened.",
            },
        )
    except APIClientError:
        pass

    client_profile = _build_client_profile(client_record)
    st.session_state["selected_client_record"] = client_record
    st.session_state["client_data"] = client_profile
    st.session_state["loaded_client_id"] = client_id
    return client_record, client_profile


# ── Client portal: ?view=portal&client_id=X ──────────────────────────────────
_qp = st.query_params
if _qp.get("view") == "portal":
    _portal_client_id = _qp.get("client_id")
    if _portal_client_id:
        render_client_portal(token="", report_id=int(_portal_client_id))
    else:
        st.error("Invalid portal link. No client_id provided.")
    st.stop()

if "advisor_token" not in st.session_state:
    _render_login_screen()
else:
    advisor_token = st.session_state["advisor_token"]

    try:
        advisor_profile = get_current_advisor(advisor_token)
        st.session_state["advisor_id"] = advisor_profile.get("id")
        st.session_state["advisor_name"] = advisor_profile.get("name", st.session_state.get("advisor_name", "Advisor"))
        st.session_state["advisor_email"] = advisor_profile.get("email", st.session_state.get("advisor_email"))
        st.session_state["advisor_role"] = advisor_profile.get("role", st.session_state.get("advisor_role", "advisor"))
    except APIClientError as exc:
        st.error(str(exc))
        _clear_login_state()
        st.rerun()

    if not st.session_state.get("selected_client_id"):
        dash_tab, settings_tab = st.tabs(["Dashboard", "Advisor Settings"])
        with dash_tab:
            render_global_dashboard(advisor_token)
        with settings_tab:
            _render_advisor_settings(advisor_token)
    else:
        selected_client_id = int(st.session_state["selected_client_id"])
        client_record, client_profile = _load_selected_client(advisor_token, selected_client_id)
        if not client_record or not client_profile:
            st.stop()

        action_col1, action_col2, action_col3 = st.columns([1, 4, 1])
        with action_col1:
            if st.button("Back to Clients", width="stretch"):
                _clear_selected_client()
                st.rerun()
        with action_col2:
            st.caption(
                f"User: `{st.session_state.get('advisor_name', '-')}` (`{st.session_state.get('advisor_role', 'advisor')}`) | Client: `{client_record.get('name', '-')}` | "
                f"Contact: `{client_record.get('contact') or '-'}` | City: `{client_record.get('city') or '-'}` | "
                f"Source: `{client_record.get('source_channel') or '-'}` | Owner: `{client_record.get('advisor_name') or client_record.get('advisor_id')}`"
            )
        with action_col3:
            if st.button("Logout", width="stretch"):
                _clear_login_state()
                st.rerun()

        (
            analysis_tab,
            meeting_tab,
            snapshot_tab,
            proposal_tab,
            review_tab,
            audit_tab,
        ) = st.tabs([
            "Analysis Workspace",
            "Meeting Notes",
            "Portfolio Snapshot",
            "Proposal Builder",
            "Review Report",
            "Audit Trail",
        ])

        with analysis_tab:
            col1, col2 = st.columns([1, 2.5])

            with col1:
                st.header("Client Profile")
                updated_profile = render_input_form(initial_data=client_profile)
                if updated_profile:
                    try:
                        updated_client = update_client_record(
                            advisor_token,
                            selected_client_id,
                            {
                                "age": int(updated_profile["age"]),
                                "occupation": updated_profile.get("occupation"),
                                "income_bracket": updated_profile.get("income_bracket"),
                                "investable_surplus": updated_profile.get("effective_monthly_savings"),
                                "profile_data": updated_profile,
                            },
                        )
                    except APIClientError as exc:
                        st.error(str(exc))
                    else:
                        merged_profile = _build_client_profile(updated_client)
                        refreshed_record = dict(client_record)
                        refreshed_record.update(updated_client)
                        refreshed_record["profile_data"] = updated_client.get("profile_data", merged_profile)
                        st.session_state["selected_client_record"] = refreshed_record
                        st.session_state["client_data"] = merged_profile
                        client_record = refreshed_record
                        client_profile = merged_profile
                        st.success("Client profile saved.")

            with col2:
                st.header("Intelligence Dashboard")
                if client_profile.get("monthly_income") is not None:
                    render_dashboard(st.session_state.get("client_data", client_profile))
                else:
                    st.info("Complete and save the client profile to load the dashboard.")

        with meeting_tab:
            render_meeting_notes(advisor_token, selected_client_id)

        with snapshot_tab:
            render_portfolio_snapshot(advisor_token, selected_client_id, client_profile)

        with proposal_tab:
            render_proposal_builder(advisor_token, selected_client_id, client_record)

        with review_tab:
            render_review_report(advisor_token, selected_client_id, client_record)

        with audit_tab:
            render_audit_trail(advisor_token, selected_client_id)

st.markdown("---")
with open(PROJECT_ROOT / "DISCLAIMER.txt", "r") as f:
    disclaimer = f.read()
st.caption(f"**Disclaimer:** {disclaimer}")
