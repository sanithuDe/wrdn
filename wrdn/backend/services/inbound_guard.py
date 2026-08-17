"""
Shared inbound scan helpers for HR, chat, and policy uploads.
"""

from __future__ import annotations

from typing import Any

from wrdn.backend.services.payload_analyzer import (
    analyze_pdf_white_text_bytes,
    analyze_text_payload,
    inbound_scan_result,
)
from wrdn.backend.services.yara_scanner import scan_file_bytes


# HR demo CVs include Mallory-style injection phrases on purpose.
# Treat those YARA phrase hits as warnings so the old
# outbound ALLOW/BLOCK/BYPASS demo still runs.
HR_WARNING_ONLY_RULES = {
    "Wrdn_Injection_Phrases",
    "Wrdn_Long_Base64_Blob",
}


def scan_uploaded_file(
    content: bytes,
    filename: str,
    extracted_text: str = "",
    *,
    relax_demo_injection_rules: bool = False,
) -> dict[str, Any]:
    yara = scan_file_bytes(content, filename=filename)
    payload = (
        analyze_text_payload(extracted_text, source=filename)
        if extracted_text
        else {
            "ok": True,
            "blocked": False,
            "risk_score": 0,
            "findings": [],
            "hard_injection": False,
            "demo_injection_only": False,
            "layer": "Payload Analyzer",
            "reason": "No extracted text yet.",
        }
    )

    white = {
        "ok": True,
        "blocked": False,
        "risk_score": 0,
        "findings": [],
        "layer": "PDF Hidden-Text Heuristic",
        "reason": "Not a PDF or no heuristic run.",
    }
    if (filename or "").lower().endswith(".pdf") or content.lstrip()[
        :4
    ] == b"%PDF":
        white = analyze_pdf_white_text_bytes(content)
        # White PDF + data-harvest text in extract => hard block
        if white.get("findings") and payload.get("hard_injection"):
            white = dict(white)
            white["blocked"] = True
            white["ok"] = False
            white["risk_score"] = 100
            white["findings"] = list(white.get("findings") or []) + [
                "White-text PDF combined with employee "
                "contact/salary harvest instruction."
            ]
            white["reason"] = "; ".join(white["findings"])

    if relax_demo_injection_rules:
        kept_matches = []
        for match in yara.get("matches") or []:
            if match.get("rule") in HR_WARNING_ONLY_RULES:
                continue
            kept_matches.append(match)
        if len(kept_matches) != len(yara.get("matches") or []):
            yara = dict(yara)
            yara["matches"] = kept_matches
            yara["findings"] = [
                f"{hit['rule']}: {hit['description']}"
                for hit in kept_matches
            ]
            high = any(
                hit.get("severity") == "high" for hit in kept_matches
            )
            yara["blocked"] = high
            yara["ok"] = not high
            yara["risk_score"] = (
                100 if high else (55 if kept_matches else 0)
            )
            yara["reason"] = (
                "; ".join(yara["findings"])
                if yara["findings"]
                else "Demo injection phrases noted; file scan not blocked."
            )
        # Only relax Mallory-style demo markers — never relax
        # hard CV white-text / salary-harvest injections.
        if (
            payload.get("blocked")
            and payload.get("demo_injection_only")
            and not payload.get("hard_injection")
        ):
            payload = dict(payload)
            payload["blocked"] = False
            payload["ok"] = True
            payload["risk_score"] = min(
                int(payload.get("risk_score") or 0),
                80,
            )
            extra = (
                "Demo ledger-injection markers recorded as warning "
                "so the outbound shield demo can still run."
            )
            findings = list(payload.get("findings") or [])
            findings.append(extra)
            payload["findings"] = findings
            payload["reason"] = (
                f"{payload.get('reason', '')} {extra}"
            ).strip()

    merged = inbound_scan_result(yara, payload, white)
    merged["yara"] = yara
    merged["payload"] = payload
    merged["white_text"] = white
    merged["detection_log"] = build_detection_log(
        payload=payload,
        yara=yara,
        white_text=white,
        inbound_blocked=bool(merged["blocked"]),
    )
    return merged


def _layer_entry(
    step: int,
    name: str,
    *,
    detected: bool,
    skipped: bool = False,
    risk_score: int = 0,
    detail: str = "",
) -> dict[str, Any]:
    if skipped:
        status = "SKIPPED"
    elif detected:
        status = "DETECTED"
    else:
        status = "CLEAN"
    return {
        "step": step,
        "name": name,
        "status": status,
        "detected": detected,
        "skipped": skipped,
        "risk_score": int(risk_score),
        "detail": detail,
    }


def build_detection_log(
    *,
    payload: dict[str, Any] | None = None,
    yara: dict[str, Any] | None = None,
    white_text: dict[str, Any] | None = None,
    leak: dict[str, Any] | None = None,
    policy_check: dict[str, Any] | None = None,
    inbound_blocked: bool = False,
) -> list[dict[str, Any]]:
    """
    One-by-one layer log for the frontend.
    1 Payload Analyzer
    2 YARA File Scan
    3 Regex / leak detector
    4 Policy risk review
    """

    payload = payload or {}
    yara = yara or {}
    white_text = white_text or {}
    payload_detected = bool(
        payload.get("findings")
        or white_text.get("findings")
        or int(payload.get("risk_score") or 0) > 0
        or int(white_text.get("risk_score") or 0) > 0
        or payload.get("blocked")
        or white_text.get("blocked")
    )
    yara_detected = bool(
        yara.get("findings")
        or yara.get("matches")
        or int(yara.get("risk_score") or 0) > 0
        or yara.get("blocked")
    )

    payload_detail_parts = [
        str(payload.get("reason") or "").strip(),
        str(white_text.get("reason") or "").strip(),
    ]
    payload_detail = "; ".join(
        part
        for part in payload_detail_parts
        if part
        and part
        not in {
            "Inbound text payload looks normal.",
            "No white-text PDF heuristic hit.",
            "Not a PDF or no heuristic run.",
            "No extracted text yet.",
        }
    ) or str(payload.get("reason") or "No payload findings.")

    log = [
        _layer_entry(
            1,
            "Payload Analyzer",
            detected=payload_detected,
            risk_score=max(
                int(payload.get("risk_score") or 0),
                int(white_text.get("risk_score") or 0),
            ),
            detail=payload_detail,
        ),
        _layer_entry(
            2,
            "YARA File Scan",
            detected=yara_detected,
            risk_score=int(yara.get("risk_score") or 0),
            detail=str(
                yara.get("reason") or "No YARA hits."
            ),
        ),
    ]

    later_skipped = inbound_blocked
    leak_detected = bool((leak or {}).get("leaked"))
    policy_not_ok = not bool(
        (policy_check or {}).get("policy_ok", True)
    ) if policy_check is not None else False

    log.append(
        _layer_entry(
            3,
            "Regex / leak detector",
            detected=leak_detected,
            skipped=later_skipped or leak is None,
            risk_score=int((leak or {}).get("risk_score") or 0),
            detail=(
                "Skipped because inbound scan blocked "
                "before Gemini."
                if later_skipped or leak is None
                else str(
                    (leak or {}).get("reason")
                    or "No leak detected."
                )
            ),
        )
    )
    log.append(
        _layer_entry(
            4,
            "Policy risk review",
            detected=policy_not_ok,
            skipped=later_skipped or policy_check is None,
            risk_score=int(
                (policy_check or {}).get("risk_score") or 0
            ),
            detail=(
                "Skipped because inbound scan blocked "
                "before Gemini."
                if later_skipped or policy_check is None
                else str(
                    (policy_check or {}).get("reason")
                    or "Policy check passed."
                )
            ),
        )
    )
    return log


def maybe_bypass_inbound_for_protection(
    scan: dict[str, Any],
    *,
    protection_enabled: bool,
) -> dict[str, Any]:
    """
    When WRDN protection is OFF, never hard-block the HR pipeline.
    Keep scan findings so the detection log still shows what
    would have been caught when protection is ON.
    """

    result = dict(scan or {})
    would_block = bool(result.get("blocked"))
    result["would_block"] = would_block

    if protection_enabled:
        result["enforcement"] = "enforced"
        return result

    result["enforcement"] = "bypassed"
    if would_block:
        result["blocked"] = False
        result["ok"] = True
        note = (
            "Inbound threats detected but not enforced "
            "because WRDN protection is OFF (BYPASSED)."
        )
        findings = list(result.get("findings") or [])
        findings.append(note)
        result["findings"] = findings
        original = str(result.get("reason") or "").strip()
        result["reason"] = (
            f"{note} Findings: {original}"
            if original
            else note
        )
    return result


def blocked_hr_response(
    scan: dict[str, Any],
    *,
    client_id: str,
    target_role: str,
    protection_enabled: bool,
    username: str = "",
    filename: str = "",
) -> dict[str, Any]:
    reason = str(scan.get("reason") or "Inbound scan blocked this file.")
    layer = str(scan.get("layer") or "Inbound Scan")
    risk = int(scan.get("risk_score") or 100)

    from wrdn.backend.services.hr_candidate_service import (
        record_hr_inbound_block,
    )

    record_hr_inbound_block(
        client_id=client_id,
        target_role=target_role,
        reason=reason,
        risk_score=risk,
        layer=f"HR {layer}" if not layer.upper().startswith("HR") else layer,
        username=username,
        filename=filename,
    )

    return {
        "client_id": client_id,
        "protection_enabled": protection_enabled,
        "target_role": target_role,
        "inbound_scan": scan,
        "detection_log": scan.get("detection_log")
        or build_detection_log(
            payload=scan.get("payload") or {},
            yara=scan.get("yara") or {},
            inbound_blocked=True,
        ),
        "agent_1": {
            "name": "Candidate Evaluator",
            "evaluation": {},
        },
        "agent_2": {
            "name": "Outbound Email Writer",
            "email": {
                "to": "",
                "subject": "",
                "body_raw": "",
                "body_final": "",
            },
            "injection_realized": False,
        },
        "shield": {
            "status": "BLOCKED",
            "risk_score": risk,
            "reason": reason,
            "leak_detected": False,
            "leak_findings": [],
            "layer": layer,
        },
        "email_dispatched": False,
        "email_send": {
            "attempted": False,
            "sent": False,
            "status": "not_sent",
            "message": "Not sent because inbound scan blocked the file.",
            "intended_to": "",
            "delivered_to": "",
        },
        "demo_hint": (
            "Inbound YARA/payload scan blocked this upload "
            "before Gemini ran."
        ),
    }
