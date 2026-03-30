"""
frontend/components/client_portal.py
─────────────────────────────────────
Read-only client-facing portal for viewing and downloading issued proposals.

Access pattern:
  ?view=portal&client_id=<id>
  The URL is shared by the advisor after issuing a report.
"""
import streamlit as st
from typing import Any, Dict, List

from frontend.api_client import APIClientError, portal_get_client_reports


_REPORT_TYPE_LABELS = {
    "proposal_deck": "Investment Proposal",
    "vinsan_proposal": "Advisory Presentation",
    "review_report": "Portfolio Review Report",
}


def _type_label(report_type: str) -> str:
    return _REPORT_TYPE_LABELS.get(report_type, report_type.replace("_", " ").title())


def render_client_portal(token: str, report_id: int) -> None:
    """
    Renders the client-facing portal.

    Parameters
    ----------
    token:
        Not used for portal (public endpoint), kept for API signature compatibility.
    report_id:
        Treated as `client_id` for the portal — the advisor shares a link
        containing ?view=portal&client_id=<id>.
    """
    client_id = report_id  # caller passes client_id via the report_id param

    st.markdown("## Your Investment Proposals")
    st.caption("This is a read-only view prepared by your advisor. Please contact your advisor for any questions or modifications.")

    if not client_id:
        st.warning("No client ID provided. Please use the link shared by your advisor.")
        return

    with st.spinner("Loading your proposals..."):
        try:
            data = portal_get_client_reports(client_id)
        except APIClientError as exc:
            st.error(f"Unable to load proposals: {exc}")
            return

    client_name = data.get("client_name", "—")
    reports: List[Dict[str, Any]] = data.get("reports", [])

    st.markdown(f"### Welcome, {client_name}")
    st.markdown("---")

    if not reports:
        st.info("No proposals have been issued yet. Please check back after your advisory meeting.")
        return

    st.markdown(f"**{len(reports)} report(s) available:**")

    for report in reports:
        with st.container(border=True):
            col_info, col_dl = st.columns([3, 1])

            with col_info:
                label = _type_label(report.get("report_type", ""))
                version = report.get("version_number", "?")
                issue_date = (report.get("issue_date") or "")[:10]
                st.markdown(f"**{label}** &nbsp; — &nbsp; Version {version}")
                st.caption(f"Issued: {issue_date}")

            with col_dl:
                pdf_path = report.get("pdf_path")
                if report.get("pdf_available") and pdf_path:
                    try:
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "⬇️ Download PDF",
                                data=f.read(),
                                file_name=pdf_path.split("/")[-1],
                                mime="application/pdf",
                                key=f"portal_dl_{report['id']}",
                                use_container_width=True,
                            )
                    except Exception:
                        st.caption("PDF available — contact advisor for link.")
                else:
                    st.caption("PDF not available")

    st.markdown("---")
    st.caption(
        "This portal is provided for informational purposes only. "
        "The proposals shown are advisory in nature and do not constitute a guarantee of returns. "
        "Please consult your advisor before making any investment decisions."
    )
