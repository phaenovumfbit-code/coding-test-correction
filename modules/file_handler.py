import io
import re
import zipfile
from pathlib import Path

from modules.pdf_handler import extract_text_from_pdf, is_scanned_pdf, pdf_to_images_base64

TEXT_EXTENSIONS = {
    ".py", ".java", ".js", ".ts", ".jsx", ".tsx", ".cpp", ".c", ".h",
    ".cs", ".go", ".rs", ".rb", ".php", ".kt", ".swift", ".r", ".m",
    ".sql", ".html", ".css", ".txt", ".md", ".xml", ".json", ".yaml",
    ".yml", ".sh", ".bash", ".toml", ".ini", ".cfg",
}

SKIP_PATTERNS = {
    "__pycache__", ".git", "node_modules", ".DS_Store",
}

MAX_FILES_PER_ZIP = 50
MAX_TEXT_BYTES = 100_000


def process_student_upload(uploaded_file) -> list[dict]:
    filename = uploaded_file.name
    ext = Path(filename).suffix.lower()
    raw_bytes = uploaded_file.read()

    if ext == ".zip":
        return extract_zip(raw_bytes)
    elif ext == ".pdf":
        return handle_student_pdf(raw_bytes, filename)
    elif ext in TEXT_EXTENSIONS:
        return _read_text_file(filename, raw_bytes)
    else:
        return []


def extract_zip(zip_bytes: bytes) -> list[dict]:
    results = []
    total_text = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            processed = 0
            for name in names:
                if processed >= MAX_FILES_PER_ZIP:
                    break
                if any(skip in name for skip in SKIP_PATTERNS):
                    continue
                if name.endswith("/"):
                    continue
                ext = Path(name).suffix.lower()
                try:
                    file_bytes = zf.read(name)
                except Exception:
                    continue

                if ext == ".pdf":
                    items = handle_student_pdf(file_bytes, name)
                    results.extend(items)
                    processed += 1
                elif ext in TEXT_EXTENSIONS:
                    if total_text >= MAX_TEXT_BYTES:
                        continue
                    items = _read_text_file(name, file_bytes)
                    for item in items:
                        total_text += len(item.get("content", ""))
                    results.extend(items)
                    processed += 1
    except zipfile.BadZipFile:
        pass
    return results


def handle_student_pdf(pdf_bytes: bytes, filename: str) -> list[dict]:
    text = extract_text_from_pdf(pdf_bytes)
    if not is_scanned_pdf(text):
        return [{"filename": filename, "content": text, "content_type": "text"}]
    images = pdf_to_images_base64(pdf_bytes)
    if images:
        return [{"filename": filename, "content": images, "content_type": "images"}]
    return [{"filename": filename, "content": "(PDF konnte nicht gelesen werden)", "content_type": "text"}]


def _read_text_file(filename: str, raw_bytes: bytes) -> list[dict]:
    try:
        content = raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return []
    return [{"filename": filename, "content": content, "content_type": "text"}]


def infer_student_name(filename: str) -> str:
    stem = Path(filename).stem
    # Remove common suffixes like homework1, submission, abgabe, aufgabe
    stem = re.sub(r"[-_](homework|submission|abgabe|aufgabe|task|aufg|hw)\d*$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\d+$", "", stem).strip("_- ")
    # Replace separators with space
    name = re.sub(r"[-_]+", " ", stem).strip()
    return name if name else Path(filename).stem
