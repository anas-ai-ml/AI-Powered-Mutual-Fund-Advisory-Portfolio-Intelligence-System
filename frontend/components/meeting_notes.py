"""
frontend/components/meeting_notes.py
─────────────────────────────────────
Meeting notes capture, AI extraction, and apply-to-profile screen.
"""
import streamlit as st
from typing import Any

from frontend.api_client import (
    APIClientError,
    apply_meeting_note_to_profile,
    create_meeting_note,
    extract_meeting_notes_ai,
    list_meeting_notes,
)

_CONFIDENCE_COLORS = {
    "high": "🟢",
    "medium": "🟡",
    "low": "🔴",
    "not_found": "⚪",
}


def _render_confidence_badge(level: str) -> str:
    return f"{_CONFIDENCE_COLORS.get(level, '⚪')} {level.replace('_', ' ').title()}"


def render_meeting_notes(token: str, client_id: int) -> None:
    st.subheader("Meeting Notes & Transcript Capture")
    st.caption("Paste meeting notes or a transcript. The system extracts structured advisory inputs and lets you apply them directly to the client profile.")

    # ── Input Panel ───────────────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("**Transcript / Notes Input**")
        transcript = st.text_area(
            "Paste meeting notes or transcript here",
            height=280,
            placeholder="e.g. 'Client is 35 years old, earning ₹1.5L monthly, wants to invest ₹20,000 SIP for 20 years for retirement. Mentions interest in Flexi Cap fund. Risk appetite seems moderate.'",
            key=f"meeting_transcript_{client_id}",
        )
        extract_col, clear_col = st.columns(2)
        with extract_col:
            extract_clicked = st.button("Extract with AI", key=f"extract_btn_{client_id}", use_container_width=True)
        with clear_col:
            if st.button("Clear", key=f"clear_btn_{client_id}", use_container_width=True):
                st.session_state.pop(f"meeting_extraction_{client_id}", None)
                st.rerun()

        if extract_clicked and transcript.strip():
            try:
                with st.spinner("Extracting structured data..."):
                    result = extract_meeting_notes_ai(token, transcript.strip())
                st.session_state[f"meeting_extraction_{client_id}"] = result
                st.session_state[f"meeting_transcript_text_{client_id}"] = transcript.strip()
            except APIClientError as exc:
                st.error(f"Extraction failed: {exc}")

    with right_col:
        extraction = st.session_state.get(f"meeting_extraction_{client_id}")
        if extraction:
            st.markdown("**Extracted Advisory Data**")
            extractions = extraction.get("extractions", {})
            confidence_flags = extraction.get("confidence_flags", {})
            ai_summary = extraction.get("ai_summary", "")

            if ai_summary:
                st.info(ai_summary)

            # Show extracted fields as a table
            rows = []
            field_labels = {
                "age": "Age",
                "monthly_income": "Monthly Income (₹)",
                "monthly_sip_amount": "Monthly SIP Target (₹)",
                "horizon_years": "Horizon (Years)",
                "occupation": "Occupation",
                "city": "City",
                "risk_cues": "Risk Cues",
                "current_holdings": "Current Holdings",
                "product_interest": "Product Interest",
            }
            for field, label in field_labels.items():
                value = extractions.get(field)
                confidence = confidence_flags.get(field, "not_found")
                if value is not None:
                    display_value = ", ".join(value) if isinstance(value, list) else str(value)
                    rows.append({
                        "Field": label,
                        "Extracted Value": display_value,
                        "Confidence": _render_confidence_badge(confidence),
                    })

            if rows:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.warning("No structured fields could be extracted. Try adding more details to the transcript.")

    # ── Save and Apply Actions ────────────────────────────────────────────────
    if st.session_state.get(f"meeting_extraction_{client_id}"):
        st.markdown("---")
        save_col, apply_col = st.columns(2)
        extraction = st.session_state[f"meeting_extraction_{client_id}"]
        transcript_text = st.session_state.get(f"meeting_transcript_text_{client_id}", "")

        with save_col:
            if st.button("Save as Meeting Note", key=f"save_note_{client_id}", use_container_width=True):
                try:
                    saved = create_meeting_note(
                        token,
                        client_id,
                        {
                            "raw_transcript": transcript_text,
                            "ai_summary": extraction.get("ai_summary"),
                            "structured_extractions": extraction.get("extractions"),
                            "confidence_flags": extraction.get("confidence_flags"),
                        },
                    )
                    st.session_state[f"saved_note_id_{client_id}"] = saved.get("id")
                    st.success("Meeting note saved.")
                    st.rerun()
                except APIClientError as exc:
                    st.error(f"Failed to save: {exc}")

        with apply_col:
            saved_note_id = st.session_state.get(f"saved_note_id_{client_id}")
            apply_disabled = saved_note_id is None
            if st.button(
                "Apply to Profile",
                key=f"apply_note_{client_id}",
                use_container_width=True,
                disabled=apply_disabled,
            ):
                try:
                    apply_meeting_note_to_profile(token, saved_note_id)
                    st.success("Profile updated from meeting note. Reload the Analysis Workspace to see changes.")
                    st.session_state.pop(f"meeting_extraction_{client_id}", None)
                    st.session_state.pop(f"saved_note_id_{client_id}", None)
                except APIClientError as exc:
                    st.error(f"Failed to apply: {exc}")

    # ── Previous Meeting Notes ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Previous Meeting Notes**")
    try:
        notes = list_meeting_notes(token, client_id)
    except APIClientError as exc:
        st.error(f"Could not load notes: {exc}")
        return

    if not notes:
        st.info("No meeting notes recorded yet.")
        return

    for note in notes:
        applied_badge = "✅ Applied to Profile" if note.get("applied_to_profile") else "⏳ Not Applied"
        label = f"{note.get('created_at', '')[:16]} — {applied_badge}"
        with st.expander(label):
            st.markdown(f"**AI Summary:** {note.get('ai_summary') or 'No summary generated.'}")
            if note.get("structured_extractions"):
                st.markdown("**Extracted Fields:**")
                st.json(note["structured_extractions"])
            with st.expander("View Raw Transcript"):
                st.text(note.get("raw_transcript", ""))
