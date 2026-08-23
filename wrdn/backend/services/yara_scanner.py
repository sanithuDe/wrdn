"""
Local YARA file scanner with a Python fallback.

Uses yara-python when installed. Otherwise applies the
same demo rules with simple byte searches so Docker and
Windows still work without the native YARA library.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

RULES_PATH = (
    Path(__file__).resolve().parents[1]
    / "security_rules"
    / "wrdn_files.yar"
)

FALLBACK_RULES: list[dict[str, Any]] = [
    {
        "name": "Wrdn_Pdf_JavaScript",
        "severity": "high",
        "need_pdf": True,
        "needles": (b"/javascript", b"/js"),
        "description": "PDF contains JavaScript action",
    },
    {
        "name": "Wrdn_Pdf_Launch_Or_Embedded",
        "severity": "high",
        "need_pdf": True,
        "needles": (b"/launch", b"/embeddedfile", b"/openaction"),
        "description": "PDF launch or embedded file",
    },
    {
        "name": "Wrdn_Office_Macro",
        "severity": "high",
        "need_pdf": False,
        "needles": (b"vba", b"macrosheet", b"oleobject"),
        "description": "Office macro indicators",
    },
    {
        "name": "Wrdn_Injection_Phrases",
        "severity": "high",
        "need_pdf": False,
        "needles": (
            b"administrative re-routing",
            b"private salary details",
            b"do not notify the human operator",
            b"corporate salary ledger",
        ),
        "description": "Prompt-injection phrases in file bytes",
    },
    {
        "name": "Wrdn_Cv_Data_Harvest",
        "severity": "high",
        "need_pdf": False,
        "needles": (
            b"pass my cv",
            b"contact numbers and salaries",
            b"contact numbers and salary",
            b"all employees contact",
            b"all eomployees contact",
            b"give me the all employees",
            b"give me the all eomployees",
            b"dump all salaries",
        ),
        "description": "Hidden CV asks for employee contacts or salaries",
    },
]


def _is_pdf(content: bytes) -> bool:
    return content.lstrip().startswith(b"%PDF")


def _fallback_scan(
    content: bytes,
    filename: str = "",
) -> list[dict[str, str]]:
    lowered = content.lower()
    name = (filename or "").lower()
    is_pdf = _is_pdf(content) or name.endswith(".pdf")
    hits: list[dict[str, str]] = []

    for rule in FALLBACK_RULES:
        if rule["need_pdf"] and not is_pdf:
            continue
        if any(needle in lowered for needle in rule["needles"]):
            hits.append(
                {
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "description": rule["description"],
                }
            )

    # Medium: long base64-like ASCII run
    import re

    if re.search(rb"[A-Za-z0-9+/]{120,}={0,2}", content):
        hits.append(
            {
                "rule": "Wrdn_Long_Base64_Blob",
                "severity": "medium",
                "description": "Long Base64-like blob in file",
            }
        )

    return hits


def _yara_scan(content: bytes) -> list[dict[str, str]] | None:
    if not RULES_PATH.exists():
        return None
    try:
        import yara  # type: ignore
    except Exception:
        return None

    try:
        rules = yara.compile(filepath=str(RULES_PATH))
        matches = rules.match(data=content)
    except Exception as error:
        logger.warning("YARA compile/match failed: %s", error)
        return None

    hits: list[dict[str, str]] = []
    for match in matches:
        meta = match.meta or {}
        hits.append(
            {
                "rule": match.rule,
                "severity": str(meta.get("severity") or "medium"),
                "description": str(
                    meta.get("description") or match.rule
                ),
            }
        )
    return hits


def scan_file_bytes(
    content: bytes,
    filename: str = "upload.bin",
) -> dict[str, Any]:
    """
    Scan uploaded file bytes. High-severity hits block.
    """

    engine = "fallback"
    hits = _yara_scan(content)
    if hits is None:
        hits = _fallback_scan(content, filename=filename)
    else:
        engine = "yara"

    findings = [
        f"{hit['rule']}: {hit['description']}"
        for hit in hits
    ]
    high = any(hit["severity"] == "high" for hit in hits)
    medium_only = bool(hits) and not high
    risk = 100 if high else (55 if medium_only else 0)
    blocked = high

    return {
        "ok": not blocked,
        "blocked": blocked,
        "risk_score": risk,
        "findings": findings,
        "matches": hits,
        "engine": engine,
        "filename": filename,
        "layer": "YARA File Scan",
        "reason": (
            "; ".join(findings)
            if findings
            else "No YARA/file-rule hits."
        ),
    }
