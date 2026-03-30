"""
frontend/components/global_dashboard.py
────────────────────────────────────────
Advisor-level KPI dashboard shown after login before a client is selected.
"""
import streamlit as st
import pandas as pd
from typing import Any, List

from frontend.api_client import APIClientError, get_global_audit_trail, get_proposal_counts, list_clients

_ACTION_COLORS = {
    "analysis_viewed": "🔵",
    "profile_edit": "🟡",
    "proposal_generated": "🟢",
    "proposal_approved": "✅",
    "report_issued": "🟠",
    "meeting_note_created": "📝",
}


def render_global_dashboard(token: str) -> None:
    advisor_name = st.session_state.get("advisor_name", "Advisor")
    advisor_role = st.session_state.get("advisor_role", "advisor")

    header_col, logout_col = st.columns([5, 1])
    with header_col:
        st.markdown(f"### Welcome, {advisor_name}")
        st.caption(f"Role: `{advisor_role}` | Your advisory workspace")
    with logout_col:
        if st.button("Logout", key="global_dash_logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Load data
    try:
        clients = list_clients(token)
    except APIClientError as exc:
        st.error(f"Could not load clients: {exc}")
        clients = []

    try:
        recent_activity = get_global_audit_trail(token, limit=10)
    except APIClientError:
        recent_activity = []

    try:
        proposal_counts = get_proposal_counts(token)
    except APIClientError:
        proposal_counts = {}

    # ── KPI Row ───────────────────────────────────────────────────────────────
    total_clients = len(clients)
    pending_profiles = sum(1 for c in clients if not c.get("risk_class"))
    total_proposals = sum(proposal_counts.values())
    clients_with_proposals = sum(1 for c in clients if str(c.get("id")) in proposal_counts)

    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Clients", total_clients)
    kpi2.metric("Awaiting Risk Profile", pending_profiles)
    kpi3.metric("Profiled Clients", total_clients - pending_profiles)
    kpi4.metric("Total Proposals", total_proposals)
    kpi5.metric("Clients with Proposals", clients_with_proposals)

    st.markdown("---")

    # ── Two-column layout ─────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("**Clients Awaiting Risk Profile**")
        pending = [c for c in clients if not c.get("risk_class")]
        if not pending:
            st.success("All clients have a risk profile.")
        else:
            pending_df = pd.DataFrame([
                {
                    "Name": c.get("name", "—"),
                    "Age": c.get("age", "—"),
                    "City": c.get("city") or "—",
                    "Source": c.get("source_channel") or "—",
                    "Created": (c.get("created_at") or "")[:10],
                }
                for c in pending
            ])
            st.dataframe(pending_df, use_container_width=True, hide_index=True)

    with right_col:
        st.markdown("**Recent Activity**")
        if not recent_activity:
            st.info("No recent activity.")
        else:
            for entry in recent_activity:
                action = entry.get("action", "event")
                icon = _ACTION_COLORS.get(action, "⚪")
                ts = (entry.get("timestamp") or "")[:16].replace("T", " ")
                notes = entry.get("notes") or ""
                st.markdown(f"{icon} `{ts}` — **{action.replace('_', ' ').title()}**")
                if notes:
                    st.caption(f"  {notes}")

    # ── All Clients Table ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**All Clients**")
    if not clients:
        st.info("No clients found. Create the first client using the New Client button.")
        return

    for client in clients:
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1, 1, 1])
            with col1:
                st.markdown(f"**{client.get('name', 'Unnamed')}**")
                st.caption(f"Age {client.get('age', '-')} | {client.get('city') or '-'} | {client.get('source_channel') or '-'}")
            with col2:
                st.metric("Risk Class", client.get("risk_class") or "—")
            with col3:
                score = client.get("risk_score")
                st.metric("Score", f"{float(score):.1f}" if score is not None else "—")
            with col4:
                p_count = proposal_counts.get(str(client.get("id")), 0)
                st.metric("Proposals", p_count)
            with col5:
                if st.button("Open", key=f"gdash_open_{client['id']}", use_container_width=True):
                    st.session_state["selected_client_id"] = client["id"]
                    st.session_state["loaded_client_id"] = None
                    st.rerun()
