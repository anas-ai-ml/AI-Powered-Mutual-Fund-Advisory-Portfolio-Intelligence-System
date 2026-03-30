"""
frontend/components/proposal_builder.py
────────────────────────────────────────
Proposal builder: section editing, preview, approval, and report issuance.
"""
import streamlit as st
import pandas as pd
from typing import Any, Dict, List

from frontend.api_client import (
    APIClientError,
    approve_proposal,
    create_proposal_draft,
    issue_proposal_report,
    list_issued_reports,
    list_proposals,
)

_STATUS_COLORS = {
    "draft": "🔵",
    "reviewed": "🟡",
    "overridden": "🟠",
    "approved": "🟢",
    "issued": "✅",
}

_DEFAULT_SIP_ROWS = [
    {"Monthly SIP (₹)": 5000, "Horizon (Yrs)": 10, "Return (%)": 10, "Projected Corpus (₹)": 0},
    {"Monthly SIP (₹)": 10000, "Horizon (Yrs)": 15, "Return (%)": 12, "Projected Corpus (₹)": 0},
    {"Monthly SIP (₹)": 20000, "Horizon (Yrs)": 20, "Return (%)": 14, "Projected Corpus (₹)": 0},
]

_DEFAULT_BENCHMARK_ROWS = [
    {"Period": "1 Year", "Scheme (%)": 0.0, "Benchmark (%)": 0.0, "Category Avg (%)": 0.0},
    {"Period": "3 Years", "Scheme (%)": 0.0, "Benchmark (%)": 0.0, "Category Avg (%)": 0.0},
    {"Period": "5 Years", "Scheme (%)": 0.0, "Benchmark (%)": 0.0, "Category Avg (%)": 0.0},
    {"Period": "Since Inception", "Scheme (%)": 0.0, "Benchmark (%)": 0.0, "Category Avg (%)": 0.0},
]


def _compute_corpus(sip: float, years: int, rate_pct: float) -> float:
    """Future value of SIP using standard FV formula."""
    r = rate_pct / 100.0 / 12.0
    n = years * 12
    if r == 0:
        return sip * n
    return sip * (((1 + r) ** n - 1) / r) * (1 + r)


def _render_edit_tab(token: str, client_id: int, client_record: Dict[str, Any]) -> None:
    st.markdown("#### Client Snapshot (Read-Only)")
    snap_col1, snap_col2, snap_col3 = st.columns(3)
    with snap_col1:
        st.metric("Name", client_record.get("name", "—"))
        st.metric("Age", client_record.get("age", "—"))
    with snap_col2:
        risk_class = (client_record.get("analysis") or {}).get("risk_questionnaire", {}) or {}
        st.metric("Risk Class", (risk_class.get("risk_class") if risk_class else None) or client_record.get("risk_class") or "—")
        st.metric("Risk Score", (risk_class.get("score") if risk_class else None) or "—")
    with snap_col3:
        st.metric("City", client_record.get("city") or "—")
        st.metric("Contact", client_record.get("contact") or "—")

    st.markdown("---")
    st.markdown("#### Category Rationale (WHY – Flexi Cap / Category)")
    category_name = st.text_input(
        "Fund Category Name",
        value=st.session_state.get(f"pb_cat_name_{client_id}", "Flexi Cap Fund"),
        key=f"pb_cat_name_{client_id}",
        placeholder="e.g. Flexi Cap Fund",
    )
    rationale_text = st.text_area(
        "Why this category? (Advisor rationale)",
        value=st.session_state.get(f"pb_rationale_{client_id}", ""),
        height=150,
        key=f"pb_rationale_{client_id}",
        placeholder="e.g. Given the client's 15-year horizon and moderate risk appetite, a Flexi Cap fund offers dynamic allocation across market caps, balancing growth and stability...",
    )

    st.markdown("---")
    st.markdown("#### SIP Illustration Table")
    st.caption("Edit the rows. Projected Corpus is computed automatically on save.")
    sip_df = pd.DataFrame(
        st.session_state.get(f"pb_sip_rows_{client_id}", _DEFAULT_SIP_ROWS)
    )
    edited_sip = st.data_editor(
        sip_df,
        num_rows="dynamic",
        key=f"pb_sip_editor_{client_id}",
        use_container_width=True,
        column_config={
            "Monthly SIP (₹)": st.column_config.NumberColumn("Monthly SIP (₹)", min_value=100, step=500),
            "Horizon (Yrs)": st.column_config.NumberColumn("Horizon (Yrs)", min_value=1, max_value=40, step=1),
            "Return (%)": st.column_config.NumberColumn("Assumed Return (%)", min_value=1, max_value=30, step=0.5),
            "Projected Corpus (₹)": st.column_config.NumberColumn("Projected Corpus (₹)", disabled=True),
        },
    )

    st.markdown("---")
    st.markdown("#### Benchmark Comparison Table")
    bench_df = pd.DataFrame(
        st.session_state.get(f"pb_bench_rows_{client_id}", _DEFAULT_BENCHMARK_ROWS)
    )
    edited_bench = st.data_editor(
        bench_df,
        num_rows="dynamic",
        key=f"pb_bench_editor_{client_id}",
        use_container_width=True,
    )

    st.markdown("---")
    override_reason = st.text_area(
        "Advisor Notes / Override Reason (optional)",
        value=st.session_state.get(f"pb_override_{client_id}", ""),
        height=80,
        key=f"pb_override_{client_id}",
    )

    if st.button("Save Proposal Draft", key=f"pb_save_{client_id}", use_container_width=True):
        # Compute corpus values
        sip_rows = []
        for _, row in edited_sip.iterrows():
            sip = float(row.get("Monthly SIP (₹)", 0) or 0)
            years = int(row.get("Horizon (Yrs)", 10) or 10)
            rate = float(row.get("Return (%)", 12) or 12)
            corpus = _compute_corpus(sip, years, rate)
            sip_rows.append({
                "monthly_sip": sip,
                "horizon_years": years,
                "assumed_return_pct": rate,
                "projected_corpus": round(corpus, 2),
            })

        bench_rows = [
            {
                "period": str(row.get("Period", "")),
                "scheme_pct": float(row.get("Scheme (%)", 0) or 0),
                "benchmark_pct": float(row.get("Benchmark (%)", 0) or 0),
                "category_avg_pct": float(row.get("Category Avg (%)", 0) or 0),
            }
            for _, row in edited_bench.iterrows()
        ]

        system_draft = {
            "client_snapshot": {
                "name": client_record.get("name"),
                "age": client_record.get("age"),
                "risk_class": client_record.get("risk_class"),
            },
            "fund_category": category_name,
        }

        try:
            saved = create_proposal_draft(
                token,
                client_id,
                {
                    "system_draft": system_draft,
                    "category_rationale": rationale_text,
                    "sip_assumptions": {"rows": sip_rows},
                    "benchmark_data": bench_rows,
                    "override_reason": override_reason.strip() or None,
                    "status": "draft",
                },
            )
            st.session_state[f"pb_sip_rows_{client_id}"] = [
                {
                    "Monthly SIP (₹)": r["monthly_sip"],
                    "Horizon (Yrs)": r["horizon_years"],
                    "Return (%)": r["assumed_return_pct"],
                    "Projected Corpus (₹)": r["projected_corpus"],
                }
                for r in sip_rows
            ]
            st.session_state[f"pb_bench_rows_{client_id}"] = [
                {
                    "Period": r["period"],
                    "Scheme (%)": r["scheme_pct"],
                    "Benchmark (%)": r["benchmark_pct"],
                    "Category Avg (%)": r["category_avg_pct"],
                }
                for r in bench_rows
            ]
            st.success(f"Proposal v{saved.get('version_number', '?')} saved (status: {saved.get('status')}).")
            st.rerun()
        except APIClientError as exc:
            st.error(f"Failed to save proposal: {exc}")


def _render_preview_tab(token: str, client_id: int) -> None:
    try:
        proposals = list_proposals(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not proposals:
        st.info("No proposals yet. Create one in the Edit Sections tab.")
        return

    selected_version = st.selectbox(
        "Select Proposal Version",
        options=range(len(proposals)),
        format_func=lambda i: f"v{proposals[i].get('version_number', i+1)} — {proposals[i].get('status', 'draft').title()} — {proposals[i].get('created_at', '')[:10]}",
        key=f"pb_version_select_{client_id}",
    )
    proposal = proposals[selected_version]
    status = proposal.get("status", "draft")
    status_icon = _STATUS_COLORS.get(status, "⚪")

    with st.container(border=True):
        st.markdown(f"### Proposal v{proposal.get('version_number', '?')}  &nbsp; {status_icon} {status.title()}")
        snap = (proposal.get("system_draft") or {}).get("client_snapshot", {})
        if snap:
            col1, col2, col3 = st.columns(3)
            col1.metric("Client", snap.get("name", "—"))
            col2.metric("Age", snap.get("age", "—"))
            col3.metric("Risk Class", snap.get("risk_class", "—"))

    if proposal.get("category_rationale"):
        with st.container(border=True):
            cat_name = (proposal.get("system_draft") or {}).get("fund_category", "Fund Category")
            st.markdown(f"#### WHY – {cat_name.upper()}")
            st.markdown(proposal["category_rationale"])

    sip_data = (proposal.get("sip_assumptions") or {}).get("rows", [])
    if sip_data:
        with st.container(border=True):
            st.markdown("#### SIP Illustration")
            sip_display = [
                {
                    "Monthly SIP (₹)": f"₹{r.get('monthly_sip', 0):,.0f}",
                    "Horizon": f"{r.get('horizon_years', 0)} yrs",
                    "Assumed Return": f"{r.get('assumed_return_pct', 0)}%",
                    "Projected Corpus": f"₹{r.get('projected_corpus', 0):,.0f}",
                }
                for r in sip_data
            ]
            st.dataframe(pd.DataFrame(sip_display), use_container_width=True, hide_index=True)
            st.caption("Past performance is not a guarantee of future returns. Projections are indicative only.")

    bench_data = proposal.get("benchmark_data") or []
    if bench_data:
        with st.container(border=True):
            st.markdown("#### Benchmark Comparison")
            bench_display = [
                {
                    "Period": r.get("period", ""),
                    "Scheme (%)": f"{r.get('scheme_pct', 0):.1f}%",
                    "Benchmark (%)": f"{r.get('benchmark_pct', 0):.1f}%",
                    "Category Avg (%)": f"{r.get('category_avg_pct', 0):.1f}%",
                }
                for r in bench_data
            ]
            st.dataframe(pd.DataFrame(bench_display), use_container_width=True, hide_index=True)


def _render_issue_tab(token: str, client_id: int) -> None:
    try:
        proposals = list_proposals(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not proposals:
        st.info("No proposals yet.")
        return

    actionable = [p for p in proposals if p.get("status") in ("draft", "reviewed", "overridden", "approved")]
    issued_proposals = [p for p in proposals if p.get("status") == "issued"]

    if actionable:
        proposal = actionable[0]
        status = proposal.get("status", "draft")
        st.markdown(f"**Latest Actionable Proposal:** v{proposal.get('version_number', '?')} — {_STATUS_COLORS.get(status, '')} {status.title()}")

        action_col1, action_col2 = st.columns(2)
        with action_col1:
            if status in ("draft", "reviewed", "overridden"):
                if st.button("✅ Approve Proposal", key=f"approve_{client_id}_{proposal['id']}", use_container_width=True):
                    try:
                        approve_proposal(token, client_id, proposal["id"])
                        st.success("Proposal approved.")
                        st.rerun()
                    except APIClientError as exc:
                        st.error(str(exc))

        with action_col2:
            if status == "approved":
                report_type = st.selectbox(
                    "Report Type",
                    ["proposal_deck", "vinsan_proposal"],
                    format_func=lambda x: "Standard Proposal Deck" if x == "proposal_deck" else "Vinsan Presentation Deck",
                    key=f"report_type_{client_id}",
                )
                if st.button("📄 Issue Report / Generate PDF", key=f"issue_{client_id}_{proposal['id']}", use_container_width=True):
                    try:
                        with st.spinner("Generating PDF..."):
                            issued = issue_proposal_report(token, client_id, proposal["id"], {"report_type": report_type})
                        st.success(f"Report issued. PDF: `{issued.get('pdf_path', 'N/A')}`")
                        if issued.get("pdf_path"):
                            try:
                                with open(issued["pdf_path"], "rb") as f:
                                    st.download_button(
                                        "⬇️ Download PDF",
                                        data=f.read(),
                                        file_name=issued["pdf_path"].split("/")[-1],
                                        mime="application/pdf",
                                    )
                            except Exception:
                                st.info("PDF generated on server. Check the reports/ directory.")
                        st.rerun()
                    except APIClientError as exc:
                        st.error(str(exc))

    st.markdown("---")
    st.markdown("#### Issued Reports History")
    try:
        issued_reports = list_issued_reports(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not issued_reports:
        st.info("No reports issued yet.")
        return

    for report in issued_reports:
        with st.container(border=True):
            r_col1, r_col2, r_col3 = st.columns([2, 1, 1])
            with r_col1:
                st.markdown(f"**v{report.get('version_number', '?')}** — {report.get('report_type', '').replace('_', ' ').title()}")
                st.caption(f"Issued: {report.get('issue_date', '')[:16]} | By advisor #{report.get('issued_by')}")
            with r_col2:
                pdf_path = report.get("pdf_path")
                if pdf_path:
                    try:
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "⬇️ PDF",
                                data=f.read(),
                                file_name=pdf_path.split("/")[-1],
                                mime="application/pdf",
                                key=f"dl_{report['id']}",
                            )
                    except Exception:
                        st.caption(f"`{pdf_path}`")


def _render_compare_tab(token: str, client_id: int) -> None:
    """Side-by-side view of system-generated draft vs advisor-finalised version."""
    try:
        proposals = list_proposals(token, client_id)
    except APIClientError as exc:
        st.error(str(exc))
        return

    if not proposals:
        st.info("No proposals yet. Create one in the Edit Sections tab.")
        return

    selected_version = st.selectbox(
        "Select Proposal Version",
        options=range(len(proposals)),
        format_func=lambda i: f"v{proposals[i].get('version_number', i+1)} — {proposals[i].get('status', 'draft').title()} — {proposals[i].get('created_at', '')[:10]}",
        key=f"pb_compare_version_{client_id}",
    )
    proposal = proposals[selected_version]

    system_draft = proposal.get("system_draft") or {}
    advisor_final = proposal.get("advisor_final") or {}
    override_reason = proposal.get("override_reason") or ""

    col_sys, col_adv = st.columns(2)

    with col_sys:
        st.markdown("##### System Generated")
        st.caption("Auto-computed recommendation before advisor review.")
        if system_draft:
            with st.container(border=True):
                snap = system_draft.get("client_snapshot", {})
                if snap:
                    st.markdown(f"**Client:** {snap.get('name', '—')}  |  **Age:** {snap.get('age', '—')}  |  **Risk:** {snap.get('risk_class', '—')}")
                fund_cat = system_draft.get("fund_category", "—")
                st.markdown(f"**Fund Category:** `{fund_cat}`")
                if system_draft.get("allocation"):
                    st.markdown("**Allocation:**")
                    for k, v in system_draft["allocation"].items():
                        st.markdown(f"- {k.title()}: `{v}`")
                with st.expander("Full system_draft JSON"):
                    st.json(system_draft)
        else:
            st.info("No system draft available.")

    with col_adv:
        st.markdown("##### Advisor Final")
        st.caption("Values after advisor review and any overrides.")
        if advisor_final:
            with st.container(border=True):
                snap = advisor_final.get("client_snapshot", {})
                if snap:
                    st.markdown(f"**Client:** {snap.get('name', '—')}  |  **Age:** {snap.get('age', '—')}  |  **Risk:** {snap.get('risk_class', '—')}")
                fund_cat = advisor_final.get("fund_category") or system_draft.get("fund_category", "—")
                st.markdown(f"**Fund Category:** `{fund_cat}`")
                if advisor_final.get("allocation"):
                    st.markdown("**Allocation:**")
                    for k, v in advisor_final["allocation"].items():
                        sys_v = (system_draft.get("allocation") or {}).get(k)
                        diff = ""
                        if sys_v is not None:
                            try:
                                delta = float(v) - float(sys_v)
                                diff = f"  ({'▲' if delta > 0 else '▼'}{abs(delta):.1f}%)"
                            except (TypeError, ValueError):
                                pass
                        st.markdown(f"- {k.title()}: `{v}`{diff}")
                with st.expander("Full advisor_final JSON"):
                    st.json(advisor_final)
        else:
            st.info("No advisor override recorded. System draft is the active proposal.")
            with st.container(border=True):
                st.caption("System draft (used as-is):")
                st.json(system_draft)

    if override_reason:
        st.markdown("---")
        st.markdown("**Override Reason / Notes:**")
        st.info(override_reason)

    # Diff summary
    st.markdown("---")
    st.markdown("##### Change Summary")
    if not advisor_final:
        st.success("No changes from system recommendation — proposal issued as generated.")
    else:
        changed_keys = []
        for k in set(list(system_draft.keys()) + list(advisor_final.keys())):
            if system_draft.get(k) != advisor_final.get(k):
                changed_keys.append(k)
        if changed_keys:
            st.warning(f"{len(changed_keys)} field(s) differ between system and advisor versions: `{'`, `'.join(changed_keys)}`")
        else:
            st.success("System draft and advisor final are identical.")


def render_proposal_builder(token: str, client_id: int, client_record: Dict[str, Any]) -> None:
    st.subheader("Proposal Builder")
    st.caption("Build, preview, approve, and issue client proposals with SIP illustrations, benchmark comparison, and rationale.")

    edit_tab, compare_tab, preview_tab, issue_tab = st.tabs(["Edit Sections", "Compare Versions", "Preview", "Approval & Issue"])

    with edit_tab:
        _render_edit_tab(token, client_id, client_record)

    with compare_tab:
        _render_compare_tab(token, client_id)

    with preview_tab:
        _render_preview_tab(token, client_id)

    with issue_tab:
        _render_issue_tab(token, client_id)
