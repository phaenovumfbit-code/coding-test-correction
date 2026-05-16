import json
import os
from typing import Callable, Optional

import anthropic
from dotenv import load_dotenv

from modules.pdf_handler import extract_text_from_pdf, is_scanned_pdf, pdf_to_images_base64

load_dotenv()

MODEL = "claude-sonnet-4-6"

TASK_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "description": {"type": "string"},
                    "max_points": {"type": "integer"},
                },
                "required": ["task_id", "description", "max_points"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tasks"],
    "additionalProperties": False,
}

GRADING_SCHEMA = {
    "type": "object",
    "properties": {
        "student_grades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "feedback_text": {"type": "string"},
                    "suggested_points": {"type": "integer"},
                    "max_points": {"type": "integer"},
                },
                "required": ["task_id", "feedback_text", "suggested_points", "max_points"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["student_grades"],
    "additionalProperties": False,
}

GRADING_SYSTEM_PROMPT = """Du bist ein erfahrener Programmierleherer, der Schülerarbeiten bewertet.
Analysiere die Schülerabgabe sorgfältig anhand der gestellten Aufgaben und ihrer Punktwerte.

Deine Bewertung soll:
- Konkret und spezifisch sein (referenziere bestimmte Teile der Schülerarbeit)
- Konstruktives Feedback geben, das dem Schüler hilft sich zu verbessern
- Fair und konsistent sein
- Deutsch als Sprache verwenden

Für jede Aufgabe gibst du:
- Eine Feedback-Text (2-5 Sätze, spezifisch zur Schülerarbeit)
- Eine ganzzahlige Punktzahl zwischen 0 und max_points (inklusive)
"""


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY ist nicht gesetzt. Bitte .env Datei erstellen.")
    return anthropic.Anthropic(api_key=api_key)


def extract_tasks_from_assignment(
    pdf_bytes: bytes,
) -> tuple[list[dict], str]:
    client = get_client()
    text = extract_text_from_pdf(pdf_bytes)

    if is_scanned_pdf(text):
        images = pdf_to_images_base64(pdf_bytes)
        content = []
        for img in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["base64"],
                },
            })
        content.append({
            "type": "text",
            "text": "Extrahiere alle Aufgaben und ihre Punktwerte aus diesen Aufgabenblatt-Seiten.",
        })
        assignment_context = "(gescanntes PDF — Inhalt über Vision verarbeitet)"
    else:
        content = [
            {
                "type": "text",
                "text": f"Extrahiere alle Aufgaben und ihre Punktwerte aus diesem Aufgabenblatt:\n\n{text}",
            }
        ]
        assignment_context = text

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=(
            "Du bist ein Experte für die Analyse von Aufgabenblättern im Schulbereich. "
            "Extrahiere alle Aufgaben/Fragen und ihre Punktwerte aus dem Dokument. "
            "Falls Punktwerte nicht explizit angegeben sind, schätze sinnvolle Werte basierend auf der Aufgabenkomplexität. "
            "Aufgaben-IDs sollen kurze Bezeichner sein wie 'Aufgabe 1', 'A1', 'Teilaufgabe 2a' etc."
        ),
        messages=[{"role": "user", "content": content}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": TASK_EXTRACTION_SCHEMA,
            }
        },
    )

    result = json.loads(response.content[0].text)
    return result["tasks"], assignment_context


def analyze_student_submission(
    student_name: str,
    tasks: list[dict],
    student_files: list[dict],
    assignment_context: str,
    sample_solution_files: list[dict] = [],
) -> dict:
    client = get_client()

    solution_text = ""
    if sample_solution_files:
        parts = []
        for f in sample_solution_files:
            if f["content_type"] == "text":
                parts.append(f"--- {f['filename']} ---\n{f['content']}")
        if parts:
            solution_text = "\n\n".join(parts)

    cached_text = (
        f"AUFGABEN MIT PUNKTWERTEN:\n{json.dumps(tasks, ensure_ascii=False, indent=2)}\n\n"
        f"AUFGABENBESCHREIBUNG (Kontext):\n{assignment_context[:3000]}"
    )
    if solution_text:
        cached_text += f"\n\nMUSTERLÖSUNG (Referenz für die Bewertung):\n{solution_text[:3000]}"

    system = [
        {
            "type": "text",
            "text": GRADING_SYSTEM_PROMPT,
        },
        {
            "type": "text",
            "text": cached_text,
            "cache_control": {"type": "ephemeral"},
        },
    ]

    content = [
        {
            "type": "text",
            "text": f"Schüler/Schülerin: **{student_name}**\n\nHier ist die Abgabe des Schülers:",
        }
    ]

    for file_info in student_files:
        if file_info["content_type"] == "text":
            content.append({
                "type": "text",
                "text": f"\n--- Datei: {file_info['filename']} ---\n{file_info['content']}",
            })
        elif file_info["content_type"] == "images":
            content.append({
                "type": "text",
                "text": f"\n--- Gescannte Seiten aus: {file_info['filename']} ---\n(Handschriftliche Abgabe, bitte Handschrift sorgfältig lesen)",
            })
            for img in file_info["content"]:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["base64"],
                    },
                })

    content.append({
        "type": "text",
        "text": (
            "\nBewerte diese Schülerarbeit für jede Aufgabe einzeln. "
            "Stelle sicher, dass du für JEDE der oben genannten Aufgaben ein Feedback gibst. "
            "Die suggested_points dürfen max_points nicht überschreiten."
        ),
    })

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": GRADING_SCHEMA,
            }
        },
    )

    result = json.loads(response.content[0].text)
    feedback = {}
    for grade in result["student_grades"]:
        task_id = grade["task_id"]
        feedback[task_id] = {
            "feedback_text": grade["feedback_text"],
            "suggested_points": min(grade["suggested_points"], grade["max_points"]),
            "max_points": grade["max_points"],
        }

    # Ensure all tasks have feedback (fill missing ones)
    for task in tasks:
        if task["task_id"] not in feedback:
            feedback[task["task_id"]] = {
                "feedback_text": "Keine Abgabe für diese Aufgabe gefunden.",
                "suggested_points": 0,
                "max_points": task["max_points"],
            }

    return feedback


def analyze_all_students(
    tasks: list[dict],
    students: list[dict],
    assignment_context: str,
    progress_callback: Optional[Callable] = None,
    sample_solution_files: list[dict] = [],
) -> dict:
    all_feedback = {}
    total = len(students)

    for i, student in enumerate(students):
        student_name = student["name"]
        try:
            feedback = analyze_student_submission(
                student_name=student_name,
                tasks=tasks,
                student_files=student["files"],
                assignment_context=assignment_context,
                sample_solution_files=sample_solution_files,
            )
            all_feedback[student_name] = feedback
        except Exception as e:
            all_feedback[student_name] = {"__error__": str(e)}

        if progress_callback:
            progress_callback(student_name, i + 1, total)

    return all_feedback
