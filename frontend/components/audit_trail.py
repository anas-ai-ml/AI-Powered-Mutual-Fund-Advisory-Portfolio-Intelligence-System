"""
frontend/components/audit_trail.py
───────────────────────────────────
Reusable audit trail component with filtering and color-coded timeline.
"""
import streamlit as st
from datetime import date
from typing import Any, List, Optional

from frontend.api_client import APIClientError, get_client_audit_trail

_ACTION_COLORS = {
    "analysis_viewed": ("#1e40af", "🔵"),
    "profile_edit": ("#92400e", "🟡"),
    "proposal_generated": ("#065f46", "🟢"),
    "proposal_approved": ("#14532d", "✅"),
    "report_issued": ("#7c2d12", "🟠"),
    "meeting_note_created": ("#4c1d95", "📝"),
    "report_issue": ("#7c2d12", "🟠"),
}


def render_audit_trail_screen(token: str, client_id: int) -> None:
    st.subheader("Audit Trail")
    st.caption("Complete chronological history of all profile edits, proposals, and report issuances for this client.")

    try:
        audit_entries = get_client_audit_trail(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not audit_entries:
        st.info("No audit events recorded for this client yet.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    filter_col1, filter_col2 = st.columns([2, 2])
    all_actions = sorted(set(e.get("action", "") for e in audit_entries))
    with filter_col1:
        action_filter = st.multiselect(
            "Filter by Action",
            options=all_actions,
            default=[],
            key=f"audit_action_filter_{client_id}",
        )
    with filter_col2:
        date_range = st.date_input(
            "Filter by Date Range",
            value=[],
            key=f"audit_date_filter_{client_id}",
        )

    filtered = audit_entries
    if action_filter:
        filtered = [e for e in filtered if e.get("action") in action_filter]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = [
            e for e in filtered
            if e.get("timestamp") and start_date <= date.fromisoformat(e["timestamp"][:10]) <= end_date
        ]

    st.caption(f"Showing {len(filtered)} of {len(audit_entries)} entries")

    # ── Timeline ──────────────────────────────────────────────────────────────
    for entry in reversed(filtered):
        action = entry.get("action", "event")
        color, icon = _ACTION_COLORS.get(action, ("#374151", "⚪"))
        ts = (entry.get("timestamp") or "")[:16].replace("T", " ")

        with st.container(border=True):
            time_col, content_col = st.columns([1, 4])
            with time_col:
                st.markdown(f"<span style='color:{color}; font-weight:600'>{icon} {action.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
                st.caption(ts)
                st.caption(f"Advisor #{entry.get('advisor_id', '—')}")
            with content_col:
                if entry.get("notes"):
                    st.markdown(entry["notes"])
                before = entry.get("before_value")
                after = entry.get("after_value")
                if before is not None or after is not None:
                    b_col, a_col = st.columns(2)
                    with b_col:
                        st.markdown("**Before**")
                        st.json(before or {}, expanded=False)
                    with a_col:
                        st.markdown("**After**")
                        st.json(after or {}, expanded=False)
