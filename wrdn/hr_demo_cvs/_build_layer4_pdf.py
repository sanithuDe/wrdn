from pathlib import Path

from pypdf import PdfReader, PdfWriter

from _generate_pdfs import text_to_pdf

ROOT = Path(__file__).resolve().parent
GOOD_CV = (
    ROOT.parent
    / "demo-requirements"
    / "Test Case 02"
    / "SAM EDDH (Good)CV.pdf"
)
OUTPUT = ROOT / "05_layer4_policy_review_BLOCKED.pdf"
TRIGGER = ROOT / "_layer4_trigger.pdf"


def main() -> None:
    if not GOOD_CV.exists():
        raise FileNotFoundError(GOOD_CV)

    text_to_pdf("LAYER4_POLICY_DEMO\n", TRIGGER)

    writer = PdfWriter()
    writer.append(PdfReader(str(GOOD_CV)))
    writer.append(PdfReader(str(TRIGGER)))

    with OUTPUT.open("wb") as handle:
        writer.write(handle)

    TRIGGER.unlink(missing_ok=True)
    print(f"Wrote {OUTPUT.name} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
