from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
SOURCE = (
    ROOT.parent
    / "demo-requirements"
    / "Test Case 02"
    / "SAM EDDH (Extra Words ).pdf"
)
OUTPUT = ROOT / "03_suspicious_pdf_javascript.pdf"


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    writer = PdfWriter()
    writer.append(PdfReader(str(SOURCE)))
    writer.add_js("app.alert('WRDN demo embedded file');")
    writer.add_attachment(
        "SAM_EDDH_embedded.pdf",
        SOURCE.read_bytes(),
    )

    with OUTPUT.open("wb") as handle:
        writer.write(handle)

    data = OUTPUT.read_bytes()
    print(f"Wrote {OUTPUT.name} ({len(data)} bytes)")
    print("JavaScript:", b"/JavaScript" in data or b"/JS" in data)
    print("EmbeddedFile:", b"/EmbeddedFile" in data)
    print("OpenAction:", b"/OpenAction" in data)


if __name__ == "__main__":
    main()
