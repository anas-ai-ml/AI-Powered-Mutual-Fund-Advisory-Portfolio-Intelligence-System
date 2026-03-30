"""
frontend/components/review_report.py
─────────────────────────────────────
Periodic portfolio review report: generates a PDF comparing the client's
current portfolio snapshot against the last issued proposal, with advisor
commentary and activity history.
"""
import streamlit as st
from typing import Any, Dict

from frontend.api_client import APIClientError, _request


def _generate_review_report(token: str, client_id: int, notes: str) -> Dict[str, Any]:
    return _request(
        "POST",
        f"/clients/{client_id}/review-report",
        token=token,
        payload={"notes": notes},
    )


def render_review_report(token: str, client_id: int, client_record: Dict[str, Any]) -> None:
    st.subheader("Periodic Review Report")
    st.caption(
        "Generate a structured review PDF comparing the client's current holdings "
        "against the last issued proposal, enriched with activity history and advisor notes."
    )

    client_name = client_record.get("name", "—")
    risk_class = client_record.get("risk_class") or "—"

    # Client header
    col1, col2, col3 = st.columns(3)
    col1.metric("Client", client_name)
    col2.metric("Risk Profile", risk_class)
    col3.metric("Client ID", client_id)

    st.markdown("---")

    # Advisor notes input
    st.markdown("#### Advisor Review Notes")
    st.caption("Summarise key observations, changes in client circumstances, or updated recommendations.")
    notes = st.text_area(
        "Review Commentary",
        height=160,
        key=f"review_notes_{client_id}",
        placeholder=(
            "e.g. Client's income has increased. Recommend reviewing equity allocation upward. "
            "Market conditions remain volatile — STP deployment may be preferable for fresh investments."
        ),
    )

    st.markdown("---")

    # What this report includes
    with st.expander("What will be included in this report?"):
        st.markdown("""
- **Current Portfolio Snapshot** — equity, debt, gold, cash values
- **Last Issued Proposal Reference** — version, date, original rationale
- **Advisor Review Notes** — commentary entered above
- **Recent Activity Timeline** — last 10 advisory interactions
- **Advisor Contact Details** — name, firm, email, phone
- **Regulatory Disclaimer**
        """)

    generate_col, _ = st.columns([1, 2])
    with generate_col:
        if st.button("Generate Review Report PDF", key=f"gen_review_{client_id}", use_container_width=True, type="primary"):
            with st.spinner("Generating review report..."):
                try:
                    result = _generate_review_report(token, client_id, notes.strip())
                    pdf_path = result.get("pdf_path")
                    st.success(f"Review report generated for {result.get('client_name')} — {result.get('review_date')}")

                    if pdf_path:
                        try:
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    "⬇️ Download Review Report PDF",
                                    data=f.read(),
                                    file_name=pdf_path.split("/")[-1],
                                    mime="application/pdf",
                                    key=f"dl_review_{client_id}",
                                )
                        except Exception:
                            st.info(f"PDF saved on server at: `{pdf_path}`")
                    else:
                        st.warning("PDF generation encountered an issue. Record saved — check server logs.")
                except APIClientError as exc:
                    st.error(f"Failed to generate review report: {exc}")
