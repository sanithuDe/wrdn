"""Generate simple text-based PDF CVs for the HR demo (no extra deps)."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _escape_pdf_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def text_to_pdf(text: str, output_path: Path) -> None:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Keep readable page density for demo uploads.
    max_lines_per_page = 48
    pages: list[list[str]] = []
    for index in range(0, len(lines), max_lines_per_page):
        pages.append(lines[index : index + max_lines_per_page])
    if not pages:
        pages = [[""]]

    objects: list[bytes] = []

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    # Placeholder; filled after page objects exist.
    font_obj = add_object(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )

    page_object_ids: list[int] = []
    for page_lines in pages:
        content_commands = ["BT", "/F1 10 Tf", "50 762 Td", "14 TL"]
        first = True
        for line in page_lines:
            safe = _escape_pdf_text(line[:110])
            if first:
                content_commands.append(f"({safe}) Tj")
                first = False
            else:
                content_commands.append("T*")
                content_commands.append(f"({safe}) Tj")
        content_commands.append("ET")
        stream = "\n".join(content_commands).encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length %d >>\nstream\n%s\nendstream"
            % (len(stream), stream)
        )
        page_id = add_object(
            (
                b"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 %d 0 R >> >> "
                b"/Contents %d 0 R >>"
            )
            % (font_obj, content_id)
        )
        page_object_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    pages_id = add_object(
        (
            f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>"
        ).encode("ascii")
    )

    # Patch Parent references now that pages_id is known.
    for page_id in page_object_ids:
        objects[page_id - 1] = objects[page_id - 1].replace(
            b"/Parent 0 0 R",
            f"/Parent {pages_id} 0 R".encode("ascii"),
        )

    catalog_id = add_object(
        f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    )

    # Build final PDF with correct offsets.
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )

    output_path.write_bytes(out)
    print(f"Wrote {output_path.name} ({output_path.stat().st_size} bytes)")


def main() -> None:
    mapping = {
        "01_safe_david_miller_ALLOWED.txt": "01_safe_david_miller_ALLOWED.pdf",
    }
    for src_name, pdf_name in mapping.items():
        src = ROOT / src_name
        text_to_pdf(src.read_text(encoding="utf-8"), ROOT / pdf_name)


if __name__ == "__main__":
    main()
