import io
import json
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from wrdn.config import MAX_REQUIREMENT_FILE_SIZE_BYTES


MAX_EXTRACTED_CHARACTERS = 50_000
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".json",
}


def extract_requirement_text(
    filename: str,
    content: bytes,
) -> dict:
    """
    Safely extract readable text from a requirement file.
    """

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Only PDF, DOCX, TXT and JSON files are allowed."
        )

    if not content:
        raise ValueError(
            "The requirement file is empty."
        )

    if len(content) > MAX_REQUIREMENT_FILE_SIZE_BYTES:
        raise ValueError(
            "The requirement file exceeds the configured size limit."
        )

    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(content))

        extracted_text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    elif extension == ".docx":
        document = Document(io.BytesIO(content))

        extracted_text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    elif extension == ".json":
        parsed_content = json.loads(
            content.decode("utf-8")
        )

        extracted_text = json.dumps(
            parsed_content,
            ensure_ascii=False,
            indent=2,
        )

    else:
        extracted_text = content.decode("utf-8")

    extracted_text = extracted_text.strip()

    if not extracted_text:
        raise ValueError(
            "No readable requirement text was found."
        )

    return {
        "filename": filename,
        "file_type": extension.removeprefix("."),
        "extracted_text": (
            extracted_text[
                :MAX_EXTRACTED_CHARACTERS
            ]
        ),
    }