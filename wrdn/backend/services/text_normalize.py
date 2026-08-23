"""Helpers for PDF text that extracts with spaces between letters."""

from __future__ import annotations

import re


def join_letter_spaced_pdf_text(text: str) -> str:
    """
    Designed CVs (Canva etc.) often extract as
    'S a h a n  J a y a w a r d e n a'. Join those
    letters back into words. Normal resumes are
    left unchanged.
    """

    lines_out: list[str] = []
    for line in (text or "").splitlines():
        tokens = line.split()
        if not tokens:
            lines_out.append(line)
            continue
        singles = sum(
            1 for token in tokens if len(token) == 1
        )
        if singles / len(tokens) < 0.5:
            lines_out.append(line)
            continue
        marked = re.sub(r" {2,}", "\x1f", line)
        marked = marked.replace(" ", "")
        lines_out.append(marked.replace("\x1f", " "))
    return "\n".join(lines_out)
