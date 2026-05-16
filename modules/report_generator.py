import io
import zipfile
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

COLOR_BLUE = colors.HexColor("#1e3a5f")
COLOR_LIGHT_BLUE = colors.HexColor("#e8f0fe")
COLOR_GRAY = colors.HexColor("#f5f5f5")
COLOR_GREEN = colors.HexColor("#2d7a2d")
COLOR_YELLOW = colors.HexColor("#b8860b")
COLOR_RED = colors.HexColor("#c0392b")
COLOR_WHITE = colors.white
COLOR_DARK = colors.HexColor("#2c2c2c")


def _make_styles():
    styles = getSampleStyleSheet()
    custom = {
        "Title": ParagraphStyle(
            "Title",
            parent=styles["Normal"],
            fontSize=18,
            textColor=COLOR_BLUE,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=12,
            textColor=COLOR_DARK,
            spaceAfter=2,
            fontName="Helvetica",
        ),
        "TaskHeader": ParagraphStyle(
            "TaskHeader",
            parent=styles["Normal"],
            fontSize=11,
            textColor=COLOR_BLUE,
            spaceBefore=8,
            spaceAfter=2,
            fontName="Helvetica-Bold",
        ),
        "TaskDesc": ParagraphStyle(
            "TaskDesc",
            parent=styles["Normal"],
            fontSize=9,
            textColor=COLOR_DARK,
            spaceAfter=4,
            fontName="Helvetica-Oblique",
        ),
        "Feedback": ParagraphStyle(
            "Feedback",
            parent=styles["Normal"],
            fontSize=10,
            textColor=COLOR_DARK,
            spaceAfter=4,
            leading=14,
            fontName="Helvetica",
        ),
        "Footer": ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.gray,
            fontName="Helvetica-Oblique",
        ),
    }
    return custom


def _points_color(points: int, max_points: int) -> colors.Color:
    if max_points == 0:
        return COLOR_GRAY
    ratio = points / max_points
    if ratio >= 0.75:
        return COLOR_GREEN
    elif ratio >= 0.4:
        return COLOR_YELLOW
    return COLOR_RED


def generate_student_report(
    student_name: str,
    tasks: list[dict],
    feedback: dict,
    assignment_title: str = "Aufgabenblatt",
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )
    styles = _make_styles()
    story = []

    # Header
    story.append(Paragraph(assignment_title, styles["Title"]))
    story.append(Paragraph(f"Schüler/in: <b>{student_name}</b>", styles["Subtitle"]))

    total_points = sum(
        fb.get("suggested_points", 0)
        for fb in feedback.values()
        if not isinstance(fb, dict) or "__error__" not in fb
    )
    total_max = sum(t["max_points"] for t in tasks)
    story.append(
        Paragraph(
            f"Gesamtpunktzahl: <b>{total_points} / {total_max}</b>  |  Datum: {date.today().strftime('%d.%m.%Y')}",
            styles["Subtitle"],
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR_BLUE))
    story.append(Spacer(1, 0.4 * cm))

    if "__error__" in feedback:
        story.append(Paragraph(f"Fehler bei der KI-Analyse: {feedback['__error__']}", styles["Feedback"]))
    else:
        for task in tasks:
            task_id = task["task_id"]
            task_fb = feedback.get(task_id, {})
            fb_text = task_fb.get("feedback_text", "Kein Feedback verfügbar.")
            points = task_fb.get("suggested_points", 0)
            max_p = task["max_points"]
            pt_color = _points_color(points, max_p)

            # Task header row with points badge
            header_data = [
                [
                    Paragraph(f"{task_id}", styles["TaskHeader"]),
                    Paragraph(
                        f'<font color="#{pt_color.hexval()[2:]}"><b>{points} / {max_p} Pkt.</b></font>',
                        ParagraphStyle(
                            "pts",
                            parent=styles["TaskHeader"],
                            alignment=2,
                            textColor=pt_color,
                        ),
                    ),
                ]
            ]
            header_table = Table(header_data, colWidths=["75%", "25%"])
            header_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BLUE),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_LIGHT_BLUE]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            story.append(header_table)

            if task.get("description"):
                story.append(Paragraph(task["description"], styles["TaskDesc"]))

            story.append(Paragraph(fb_text, styles["Feedback"]))
            story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(
        Paragraph(
            "Erstellt mit KI-gestütztem Bewertungssystem | Feedback zur Überprüfung durch Lehrkraft",
            styles["Footer"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def generate_all_reports(
    students_feedback: dict,
    tasks: list[dict],
    assignment_title: str = "Aufgabenblatt",
) -> dict:
    reports = {}
    for student_name, feedback in students_feedback.items():
        reports[student_name] = generate_student_report(
            student_name=student_name,
            tasks=tasks,
            feedback=feedback,
            assignment_title=assignment_title,
        )
    return reports


def create_summary_report(
    students_feedback: dict,
    tasks: list[dict],
    assignment_title: str = "Aufgabenblatt",
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = _make_styles()
    story = []

    story.append(Paragraph(f"Klassenübersicht — {assignment_title}", styles["Title"]))
    story.append(Paragraph(f"Datum: {date.today().strftime('%d.%m.%Y')}", styles["Subtitle"]))
    story.append(Spacer(1, 0.4 * cm))

    # Build table
    task_ids = [t["task_id"] for t in tasks]
    task_max = {t["task_id"]: t["max_points"] for t in tasks}
    total_max = sum(t["max_points"] for t in tasks)

    header_row = ["Schüler/in"] + task_ids + ["Gesamt"]
    max_row = ["(Max)"] + [str(task_max[tid]) for tid in task_ids] + [str(total_max)]

    data = [header_row, max_row]
    totals_per_task = {tid: 0 for tid in task_ids}
    student_count = 0

    for student_name, feedback in students_feedback.items():
        if "__error__" in feedback:
            row = [student_name] + ["—"] * len(task_ids) + ["Fehler"]
        else:
            row_points = []
            student_total = 0
            for tid in task_ids:
                pts = feedback.get(tid, {}).get("suggested_points", 0)
                row_points.append(str(pts))
                student_total += pts
                totals_per_task[tid] += pts
            row = [student_name] + row_points + [str(student_total)]
            student_count += 1
        data.append(row)

    if student_count > 0:
        avg_row = ["Ø Durchschnitt"]
        for tid in task_ids:
            avg = totals_per_task[tid] / student_count
            avg_row.append(f"{avg:.1f}")
        class_total_avg = sum(totals_per_task.values()) / student_count
        avg_row.append(f"{class_total_avg:.1f}")
        data.append(avg_row)

    col_widths = [4 * cm] + [max(2 * cm, 14 / max(len(task_ids), 1) * cm)] * len(task_ids) + [2.5 * cm]

    table = Table(data, colWidths=col_widths, repeatRows=2)
    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, 1), COLOR_GRAY),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Oblique"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 2), (-1, -2), [COLOR_WHITE, COLOR_GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])
    if student_count > 0:
        avg_row_idx = len(data) - 1
        table_style.add("BACKGROUND", (0, avg_row_idx), (-1, avg_row_idx), COLOR_LIGHT_BLUE)
        table_style.add("FONTNAME", (0, avg_row_idx), (-1, avg_row_idx), "Helvetica-Bold")

    table.setStyle(table_style)
    story.append(table)

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Erstellt mit KI-gestütztem Bewertungssystem | Feedback zur Überprüfung durch Lehrkraft",
            styles["Footer"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def bundle_all_as_zip(reports: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for student_name, pdf_bytes in reports.items():
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in student_name)
            zf.writestr(f"{safe_name}_feedback.pdf", pdf_bytes)
    return buffer.getvalue()
