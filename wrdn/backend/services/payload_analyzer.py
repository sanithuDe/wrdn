"""
Inbound payload analyzer.

Inspects request/CV text for encoding wrappers,
hidden characters, and decoded injection content.
Does not execute or decrypt unknown ciphertext.
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from typing import Any
from urllib.parse import unquote_plus


ZERO_WIDTH_CHARS = (
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2060",
    "\ufeff",
)

# Soft demo markers (Mallory salary-ledger CV).
# HR may keep these as warnings so outbound ON/OFF demo still runs.
DEMO_INJECTION_MARKERS = (
    "administrative re-routing",
    "private salary details",
    "do not notify the human operator",
    "corporate salary ledger",
)

# Hard block: white-text / hidden CV asks that harvest company data.
# Includes common typos from demo CVs (e.g. "eomployees").
HARD_INJECTION_MARKERS = (
    "pass my cv",
    "give me the all employees",
    "give me the all eomployees",
    "give me all employees",
    "give me all eomployees",
    "all employees contact",
    "all eomployees contact",
    "employees contact numbers",
    "eomployees contact numbers",
    "contact numbers and salaries",
    "contact numbers and salary",
    "all employee salaries",
    "all employees salaries",
    "give me all employee",
    "dump all salaries",
    "send all employee",
    "list all employees salary",
    "ignore previous instructions",
    "ignore all policies",
    "send sahan",
    "leak salary",
)

# Broader harvest phrasing (typos / spacing variants).
HARD_INJECTION_RE = re.compile(
    r"(pass\s+my\s+cv).{0,80}(contact|salar|employee|eomployee)"
    r"|(give\s+me).{0,40}(all\s+)?(e?o?mploye\w*).{0,40}"
    r"(contact|salar|phone|number)",
    re.IGNORECASE | re.DOTALL,
)

INJECTION_MARKERS = DEMO_INJECTION_MARKERS + HARD_INJECTION_MARKERS

BASE64_RE = re.compile(
    r"(?:[A-Za-z0-9+/]{40,}={0,2})"
)
HEX_RE = re.compile(
    r"(?:[0-9a-fA-F]{48,})"
)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _looks_like_text(value: str) -> bool:
    if not value:
        return False
    printable = sum(
        1
        for char in value
        if char.isprintable() or char.isspace()
    )
    return printable / max(len(value), 1) >= 0.75


def _safe_b64_decode(blob: str) -> str | None:
    cleaned = re.sub(r"\s+", "", blob)
    if len(cleaned) < 40:
        return None
    pad = (-len(cleaned)) % 4
    try:
        decoded = base64.b64decode(
            cleaned + ("=" * pad),
            validate=False,
        )
    except (binascii.Error, ValueError):
        return None
    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if _looks_like_text(text) and any(
        char.isalpha() for char in text
    ):
        return text
    return None


def _safe_hex_decode(blob: str) -> str | None:
    cleaned = re.sub(r"\s+", "", blob)
    if len(cleaned) < 48 or len(cleaned) % 2:
        return None
    try:
        decoded = bytes.fromhex(cleaned)
        text = decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if _looks_like_text(text) and any(
        char.isalpha() for char in text
    ):
        return text
    return None


def _collect_decoded_views(text: str) -> list[str]:
    views = [text]
    if "%" in text:
        views.append(unquote_plus(text))

    for match in BASE64_RE.findall(text):
        decoded = _safe_b64_decode(match)
        if decoded:
            views.append(decoded)

    for match in HEX_RE.findall(text):
        decoded = _safe_hex_decode(match)
        if decoded:
            views.append(decoded)

    return _unique(views)


def analyze_text_payload(
    text: str,
    source: str = "request",
) -> dict[str, Any]:
    """
    Analyze inbound text. Returns risk findings.
    blocked=True means do not call Gemini.
    """

    original = text or ""
    findings: list[str] = []
    risk = 0

    zero_width = sum(original.count(char) for char in ZERO_WIDTH_CHARS)
    if zero_width:
        findings.append(
            f"Hidden/zero-width characters detected ({zero_width})."
        )
        risk = max(risk, 70)

    normalized = unicodedata.normalize("NFKC", original)
    stripped = normalized
    for char in ZERO_WIDTH_CHARS:
        stripped = stripped.replace(char, "")

    views = _collect_decoded_views(stripped)
    decoded_views = [view for view in views if view != original]
    if decoded_views:
        findings.append(
            "Encoded or wrapped content was safely decoded once."
        )
        risk = max(risk, 50)

    lowered_views = "\n".join(views).lower()
    hard_hits = [
        marker
        for marker in HARD_INJECTION_MARKERS
        if marker in lowered_views
    ]
    if HARD_INJECTION_RE.search(lowered_views):
        hard_hits.append("cv data-harvest instruction")
        hard_hits = _unique(hard_hits)
    demo_hits = [
        marker
        for marker in DEMO_INJECTION_MARKERS
        if marker in lowered_views
    ]
    hit_markers = hard_hits + demo_hits
    if hit_markers:
        findings.append(
            "Decoded/normalized payload contains injection markers: "
            + ", ".join(hit_markers[:4])
        )
        risk = max(risk, 100)

    # White-text / invisible CV tricks often sit at the end of resumes.
    if hard_hits and (
        "cv" in lowered_views
        or "resume" in lowered_views
        or "flight attendant" in lowered_views
        or "software engineer" in lowered_views
        or source.lower().endswith((".pdf", ".docx", ".txt"))
    ):
        findings.append(
            "Hidden CV instruction asks for employee contacts/salaries "
            "(common white-text prompt injection)."
        )
        risk = max(risk, 100)

    if BASE64_RE.search(original) and not hit_markers:
        findings.append("Long Base64-like blob in payload.")
        risk = max(risk, 40)

    blocked = risk >= 90
    return {
        "ok": not blocked,
        "blocked": blocked,
        "risk_score": risk,
        "findings": findings,
        "hard_injection": bool(hard_hits),
        "demo_injection_only": bool(demo_hits) and not hard_hits,
        "layer": "Payload Analyzer",
        "source": source,
        "decoded_preview": (
            decoded_views[0][:240] if decoded_views else ""
        ),
        "reason": (
            "; ".join(findings)
            if findings
            else "Inbound text payload looks normal."
        ),
    }


def analyze_pdf_white_text_bytes(
    content: bytes,
) -> dict[str, Any]:
    """
    Lightweight PDF heuristic for white-fill text tricks.
    Not full steganography — flags likely hidden white text.
    """

    findings: list[str] = []
    risk = 0
    sample = content[:2_000_000].lower()

    white_ops = (
        b"1 1 1 rg",
        b"1.0 1.0 1.0 rg",
        b"1 g\n",
        b"1.0 g",
    )
    has_white = any(op in sample for op in white_ops)
    has_text_op = b"tj" in sample or b"t*" in sample

    if has_white and has_text_op:
        findings.append(
            "PDF uses white/near-white fill with text operators "
            "(possible hidden white-text injection)."
        )
        risk = max(risk, 85)

    blocked = risk >= 90
    return {
        "ok": not blocked,
        "blocked": blocked,
        "risk_score": risk,
        "findings": findings,
        "layer": "PDF Hidden-Text Heuristic",
        "reason": (
            "; ".join(findings)
            if findings
            else "No white-text PDF heuristic hit."
        ),
    }


def inbound_scan_result(
    *scans: dict[str, Any],
) -> dict[str, Any]:
    """Merge YARA + payload scans into one inbound result."""

    findings: list[str] = []
    layers: list[str] = []
    risk = 0
    blocked = False
    for scan in scans:
        if not scan:
            continue
        findings.extend(scan.get("findings") or [])
        if scan.get("layer"):
            layers.append(str(scan["layer"]))
        risk = max(risk, int(scan.get("risk_score") or 0))
        blocked = blocked or bool(scan.get("blocked"))

    findings = _unique(findings)
    return {
        "ok": not blocked,
        "blocked": blocked,
        "risk_score": risk,
        "findings": findings,
        "layers": _unique(layers),
        "layer": " + ".join(_unique(layers)) or "Inbound Scan",
        "reason": (
            "; ".join(findings)
            if findings
            else "Inbound scan passed."
        ),
    }
