import streamlit as st

from modules.ai_analyzer import analyze_all_students, extract_tasks_from_assignment
from modules.file_handler import infer_student_name, process_student_upload
from modules.report_generator import (
    bundle_all_as_zip,
    create_summary_report,
    generate_all_reports,
)
from modules.session_state import go_to_step, init_session_state, reset_all

st.set_page_config(
    page_title="KI-Aufgabenkorrektur",
    page_icon="📝",
    layout="wide",
)

init_session_state()


def render_progress_bar():
    steps = ["Aufgabenblatt", "Schüler-Uploads", "KI-Analyse", "Review", "Export"]
    current = st.session_state["step"]
    cols = st.columns(len(steps))
    for i, (col, name) in enumerate(zip(cols, steps), start=1):
        with col:
            if i < current:
                st.markdown(f"✅ **{name}**")
            elif i == current:
                st.markdown(f"🔵 **{name}**")
            else:
                st.markdown(f"⬜ {name}")
    st.divider()


def render_step1():
    st.header("Schritt 1: Aufgabenblatt hochladen")
    st.markdown(
        "Laden Sie das Aufgabenblatt als PDF hoch. Die KI extrahiert automatisch alle Aufgaben und Punktwerte."
    )

    title_input = st.text_input(
        "Titel des Aufgabenblatts",
        value=st.session_state["assignment_title"],
        placeholder="z.B. Python Grundlagen Test",
    )
    st.session_state["assignment_title"] = title_input

    uploaded = st.file_uploader("Aufgabenblatt als PDF", type=["pdf"], key="assignment_upload")

    if uploaded and not st.session_state["tasks_confirmed"]:
        if st.button("Aufgaben extrahieren", type="primary"):
            with st.spinner("KI analysiert das Aufgabenblatt..."):
                try:
                    pdf_bytes = uploaded.read()
                    tasks, context = extract_tasks_from_assignment(pdf_bytes)
                    st.session_state["assignment_pdf_bytes"] = pdf_bytes
                    st.session_state["tasks"] = tasks
                    st.session_state["assignment_context"] = context
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler bei der Extraktion: {e}")

    if st.session_state["tasks"] and not st.session_state["tasks_confirmed"]:
        st.subheader("Extrahierte Aufgaben (bearbeitbar)")
        st.caption("Sie können die Aufgabenbeschreibungen und Punktwerte anpassen, bevor Sie fortfahren.")

        edited = st.data_editor(
            st.session_state["tasks"],
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "task_id": st.column_config.TextColumn("Aufgaben-ID", width="small"),
                "description": st.column_config.TextColumn("Beschreibung", width="large"),
                "max_points": st.column_config.NumberColumn("Max. Punkte", min_value=0, max_value=100, width="small"),
            },
            key="tasks_editor",
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Aufgaben bestätigen", type="primary"):
                if not edited:
                    st.error("Mindestens eine Aufgabe muss vorhanden sein.")
                else:
                    st.session_state["tasks"] = edited
                    st.session_state["tasks_confirmed"] = True
                    go_to_step(2)
                    st.rerun()

    elif st.session_state["tasks_confirmed"]:
        st.success(f"{len(st.session_state['tasks'])} Aufgaben wurden bestätigt.")
        if st.button("Weiter zu Schritt 2", type="primary"):
            go_to_step(2)
            st.rerun()


def render_step2():
    st.header("Schritt 2: Schülerarbeiten hochladen")
    st.markdown(
        "Laden Sie die Abgaben aller Schüler hoch. Unterstützte Formate: **PDF**, **Code-Dateien** (.py, .java, ...), **ZIP-Archive**."
    )

    uploaded_files = st.file_uploader(
        "Schülerarbeiten (mehrere Dateien möglich)",
        type=["pdf", "py", "java", "js", "ts", "jsx", "tsx", "zip", "cpp", "c", "h",
              "cs", "go", "rs", "rb", "php", "kt", "txt", "md", "html", "css", "sql"],
        accept_multiple_files=True,
        key="student_uploads",
    )

    if uploaded_files:
        students_raw = []
        for uf in uploaded_files:
            name = infer_student_name(uf.name)
            files = process_student_upload(uf)
            students_raw.append({"raw_name": name, "original_filename": uf.name, "files": files})

        st.subheader("Erkannte Schüler (Namen anpassbar)")
        student_list = []
        for idx, s in enumerate(students_raw):
            col1, col2 = st.columns([2, 3])
            with col1:
                name = st.text_input(
                    f"Name für '{s['original_filename']}'",
                    value=s["raw_name"],
                    key=f"student_name_{idx}",
                )
            with col2:
                file_summary = ", ".join(
                    f["filename"] for f in s["files"][:3]
                )
                if len(s["files"]) > 3:
                    file_summary += f" (+{len(s['files']) - 3} weitere)"
                st.caption(f"Dateien: {file_summary or '(keine lesbaren Dateien)'}")
            student_list.append({"name": name, "files": s["files"]})

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Weiter zur KI-Analyse", type="primary"):
                if not student_list:
                    st.error("Bitte mindestens eine Schülerarbeit hochladen.")
                else:
                    st.session_state["students"] = student_list
                    st.session_state["analysis_done"] = False
                    go_to_step(3)
                    st.rerun()
        with col2:
            if st.button("← Zurück"):
                go_to_step(1)
                st.rerun()


def render_step3():
    st.header("Schritt 3: KI-Analyse")
    tasks = st.session_state["tasks"]
    students = st.session_state["students"]
    assignment_context = st.session_state["assignment_context"]

    st.info(
        f"**{len(students)} Schüler** werden gegen **{len(tasks)} Aufgaben** bewertet.\n\n"
        "Die Analyse läuft sequenziell. Bitte warten Sie, bis alle Schüler verarbeitet wurden."
    )

    if st.session_state["analysis_done"]:
        st.success("Analyse abgeschlossen!")
        if st.button("Weiter zum Review", type="primary"):
            go_to_step(4)
            st.rerun()
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        start = st.button("Analyse starten", type="primary", disabled=st.session_state["analysis_running"])
    with col2:
        if st.button("← Zurück"):
            go_to_step(2)
            st.rerun()

    if start:
        st.session_state["analysis_running"] = True
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        feedback_result = {}

        def on_progress(student_name, current, total):
            progress_bar.progress(current / total)
            status_text.text(f"Analysiere: {student_name} ({current}/{total})")

        try:
            feedback_result = analyze_all_students(
                tasks=tasks,
                students=students,
                assignment_context=assignment_context,
                progress_callback=on_progress,
            )
            st.session_state["feedback"] = feedback_result
            st.session_state["analysis_done"] = True
            st.session_state["analysis_running"] = False
            progress_bar.progress(1.0)
            status_text.text("Analyse abgeschlossen!")
            st.rerun()
        except Exception as e:
            st.session_state["analysis_running"] = False
            st.error(f"Fehler während der Analyse: {e}")


def render_step4():
    st.header("Schritt 4: Feedback überprüfen und bearbeiten")
    tasks = st.session_state["tasks"]
    feedback = st.session_state["feedback"]
    students = [s["name"] for s in st.session_state["students"]]

    col_nav, col_info = st.columns([2, 3])
    with col_nav:
        selected_student = st.selectbox("Schüler auswählen", students)
    with col_info:
        if selected_student in feedback and "__error__" not in feedback[selected_student]:
            student_fb = feedback[selected_student]
            total = sum(v.get("suggested_points", 0) for v in student_fb.values())
            total_max = sum(t["max_points"] for t in tasks)
            st.metric("Gesamtpunkte", f"{total} / {total_max}")

    st.divider()

    if selected_student not in feedback:
        st.warning("Für diesen Schüler liegt noch kein Feedback vor.")
        return

    student_fb = feedback[selected_student]

    if "__error__" in student_fb:
        st.error(f"KI-Analyse fehlgeschlagen: {student_fb['__error__']}")
        if st.button("Erneut analysieren"):
            with st.spinner("Analysiere..."):
                try:
                    from modules.ai_analyzer import analyze_student_submission
                    student_data = next(s for s in st.session_state["students"] if s["name"] == selected_student)
                    new_fb = analyze_student_submission(
                        student_name=selected_student,
                        tasks=tasks,
                        student_files=student_data["files"],
                        assignment_context=st.session_state["assignment_context"],
                    )
                    st.session_state["feedback"][selected_student] = new_fb
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler: {e}")
        return

    for task in tasks:
        task_id = task["task_id"]
        task_fb = student_fb.get(task_id, {})
        max_p = task["max_points"]
        current_pts = task_fb.get("suggested_points", 0)
        current_text = task_fb.get("feedback_text", "")

        with st.expander(f"{task_id} — {task.get('description', '')[:80]}", expanded=True):
            col1, col2 = st.columns([1, 4])
            with col1:
                new_pts = st.number_input(
                    f"Punkte (max {max_p})",
                    min_value=0,
                    max_value=max_p,
                    value=int(current_pts),
                    key=f"pts_{selected_student}_{task_id}",
                )
            with col2:
                new_text = st.text_area(
                    "Feedback",
                    value=current_text,
                    height=100,
                    key=f"fb_{selected_student}_{task_id}",
                )

            # Persist edits immediately to session state
            if new_pts != current_pts or new_text != current_text:
                st.session_state["feedback"][selected_student][task_id]["suggested_points"] = new_pts
                st.session_state["feedback"][selected_student][task_id]["feedback_text"] = new_text

    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Weiter zum Export", type="primary"):
            go_to_step(5)
            st.rerun()
    with col2:
        if st.button("← Zurück zur Analyse"):
            go_to_step(3)
            st.rerun()


def render_step5():
    st.header("Schritt 5: PDF-Export")
    tasks = st.session_state["tasks"]
    feedback = st.session_state["feedback"]
    assignment_title = st.session_state["assignment_title"]

    # Summary table
    st.subheader("Notenübersicht")
    summary_data = []
    for student_name, student_fb in feedback.items():
        if "__error__" in student_fb:
            summary_data.append({"Schüler/in": student_name, "Gesamt": "Fehler"})
        else:
            total = sum(v.get("suggested_points", 0) for v in student_fb.values())
            total_max = sum(t["max_points"] for t in tasks)
            row = {"Schüler/in": student_name}
            for task in tasks:
                tid = task["task_id"]
                pts = student_fb.get(tid, {}).get("suggested_points", 0)
                row[tid] = f"{pts}/{task['max_points']}"
            row["Gesamt"] = f"{total}/{total_max}"
            summary_data.append(row)

    st.dataframe(summary_data, use_container_width=True)
    st.divider()

    # Generate reports
    with st.spinner("Berichte werden erstellt..."):
        reports = generate_all_reports(feedback, tasks, assignment_title)
        summary_pdf = create_summary_report(feedback, tasks, assignment_title)
        all_zip = bundle_all_as_zip(reports)

    st.subheader("Downloads")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📦 Alle Berichte als ZIP",
            data=all_zip,
            file_name=f"feedback_alle_schueler.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="📊 Klassenübersicht PDF",
            data=summary_pdf,
            file_name=f"klassenuebersicht.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.subheader("Individuelle Berichte")
    cols = st.columns(3)
    for i, (student_name, pdf_bytes) in enumerate(reports.items()):
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in student_name)
        with cols[i % 3]:
            st.download_button(
                label=f"📄 {student_name}",
                data=pdf_bytes,
                file_name=f"{safe_name}_feedback.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_{student_name}",
            )

    st.divider()
    if st.button("🔄 Neue Korrektur starten", type="secondary"):
        reset_all()
        st.rerun()


# --- Main routing ---
render_progress_bar()

step = st.session_state["step"]
if step == 1:
    render_step1()
elif step == 2:
    render_step2()
elif step == 3:
    render_step3()
elif step == 4:
    render_step4()
elif step == 5:
    render_step5()
