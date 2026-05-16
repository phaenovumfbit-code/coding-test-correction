import streamlit as st


def init_session_state():
    defaults = {
        "step": 1,
        "assignment_pdf_bytes": None,
        "assignment_context": "",
        "assignment_title": "Aufgabenblatt",
        "tasks": [],
        "tasks_confirmed": False,
        "students": [],
        "feedback": {},
        "analysis_done": False,
        "analysis_running": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to_step(n: int):
    st.session_state["step"] = n


def reset_all():
    keys = list(st.session_state.keys())
    for key in keys:
        del st.session_state[key]
    init_session_state()
