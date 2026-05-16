import base64
import io

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text)
        doc.close()
        return "\n\n".join(pages_text)
    except Exception:
        return ""


def pdf_to_images_base64(pdf_bytes: bytes, dpi: int = 150, max_pages: int = 10) -> list[dict]:
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = min(len(doc), max_pages)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for page_num in range(page_count):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
            images.append({
                "page_num": page_num + 1,
                "base64": b64,
                "media_type": "image/png",
            })
        doc.close()
    except Exception:
        pass
    return images


def is_scanned_pdf(text: str, threshold: int = 100) -> bool:
    return len(text.strip()) < threshold
