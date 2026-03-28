from typing import Any, Dict, Optional

import streamlit as st


def render_client_workspace(store) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    st.subheader("Advisor Workspace")
    advisor_id = st.text_input(
        "Advisor ID",
        value=st.session_state.get("advisor_id", "advisor_demo"),
        help="Used to scope the client list to the logged-in advisor.",
    ).strip()
    st.session_state["advisor_id"] = advisor_id

    if not advisor_id:
        st.info("Enter an advisor ID to load clients.")
        return None, None

    clients = store.list_clients(advisor_id)

    list_col, create_col = st.columns([1.3, 1])
    selected_client_id = None

    with list_col:
        st.markdown("### Client List")
        if not clients:
            st.info("No clients found for this advisor. Create one to begin.")
        else:
            options = {
                f"{client['name']} | {client.get('contact') or 'No contact'} | Age {client.get('age') or '-'}": client[
                    "client_id"
                ]
                for client in clients
            }
            chosen_label = st.radio(
                "Select a client",
                list(options.keys()),
                label_visibility="collapsed",
            )
            selected_client_id = options.get(chosen_label)
            if st.button("Open Client", width="stretch"):
                st.session_state["selected_client_id"] = selected_client_id
                st.rerun()

    with create_col:
        st.markdown("### Create Client")
        with st.form("create_client_form", clear_on_submit=True):
            name = st.text_input("Client Name")
            age = st.number_input("Age", min_value=18, max_value=100, value=30)
            contact = st.text_input("Contact")
            pan_placeholder = st.text_input("PAN Placeholder", value="ABCDE1234F")
            source_channel = st.selectbox(
                "Source Channel",
                ["Referral", "Website", "Walk-in", "Campaign", "Other"],
            )
            created = st.form_submit_button("Create Client", width="stretch")

        if created:
            if not name.strip():
                st.error("Client name is required.")
            else:
                record = store.create_client(
                    advisor_id=advisor_id,
                    name=name.strip(),
                    age=int(age),
                    contact=contact.strip(),
                    pan_placeholder=pan_placeholder.strip(),
                    source_channel=source_channel,
                )
                st.session_state["selected_client_id"] = record.get("client_id")
                st.rerun()

    return advisor_id, next((c for c in clients if c.get("client_id") == selected_client_id), None)
