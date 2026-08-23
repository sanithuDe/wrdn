"""
HR Candidate Processor API routes.
"""

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field

from wrdn.backend.database import get_protection_enabled
from wrdn.backend.services.hr_candidate_service import (
    get_sample_cvs,
    list_hr_history,
    process_candidate_cv,
)
from wrdn.backend.services.inbound_guard import (
    blocked_hr_response,
    build_detection_log,
    maybe_bypass_inbound_for_protection,
    scan_uploaded_file,
)
from wrdn.backend.services.requirement_parser import (
    extract_requirement_text,
)


router = APIRouter(
    prefix="/api/hr",
    tags=["HR Candidate Processor"],
)


class ProcessCvRequest(BaseModel):
    cv_text: str = Field(
        ...,
        min_length=1,
        description="Full candidate CV / resume text",
    )
    client_id: str = Field(
        default="default",
        description="Tenant client id for policy + protection",
    )
    target_role: str = Field(
        default="Software Engineer",
        description="Role the candidate is applying for",
    )
    username: str = Field(
        default="",
        description="Signed-in user who ran the pipeline",
    )


@router.get("/sample-cvs")
def sample_cvs() -> dict:
    """Return safe and attack CV samples for the demo."""

    return get_sample_cvs()


@router.get("/history")
def hr_history(
    client_id: str = "default",
    username: str = "",
    role: str = "EMPLOYEE",
    limit: int = 40,
) -> dict:
    """
    Recent HR candidate runs (inbound blocks + outbound
    ALLOWED / BLOCKED / BYPASSED) for the Live Registry /
    HR page history panel.
    """

    try:
        items = list_hr_history(
            client_id=client_id,
            username=username,
            role=role,
            limit=max(1, min(int(limit or 40), 100)),
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load HR history: {error}",
        ) from error

    return {
        "client_id": (client_id or "default").strip(),
        "count": len(items),
        "items": items,
    }


@router.post("/extract-cv")
async def extract_cv(
    file: UploadFile = File(...),
) -> dict:
    """
    Extract readable text from an uploaded CV
    (PDF, DOCX, or TXT).

    Does not enforce inbound blocks — protection gating
    happens on process-cv / process-cv-upload.
    """

    filename = file.filename or "cv.txt"
    content = await file.read()

    try:
        extracted = extract_requirement_text(
            filename=filename,
            content=content,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error).replace(
                "requirement",
                "CV",
            ),
        ) from error

    return {
        "filename": extracted["filename"],
        "file_type": extracted["file_type"],
        "cv_text": extracted["extracted_text"],
        "character_count": len(
            extracted["extracted_text"]
        ),
    }


@router.post("/process-cv")
def process_cv(payload: ProcessCvRequest) -> dict:
    """
    Run CV → Agent 1 → Agent 2 → WRDN outbound email shield.
    """

    client_id = (payload.client_id or "default").strip()
    role = payload.target_role or "Software Engineer"
    protection_enabled = get_protection_enabled(client_id)

    inbound = maybe_bypass_inbound_for_protection(
        scan_uploaded_file(
            payload.cv_text.encode("utf-8", errors="ignore"),
            filename="pasted-cv.txt",
            extracted_text=payload.cv_text,
            relax_demo_injection_rules=True,
        ),
        protection_enabled=protection_enabled,
    )
    if inbound["blocked"]:
        return blocked_hr_response(
            inbound,
            client_id=client_id,
            target_role=role,
            protection_enabled=protection_enabled,
            username=payload.username,
            filename="pasted-cv.txt",
        )

    try:
        result = process_candidate_cv(
            cv_text=payload.cv_text,
            client_id=client_id,
            target_role=role,
            username=payload.username,
        )
        result["inbound_scan"] = inbound
        result["detection_log"] = build_detection_log(
            payload=inbound.get("payload") or {},
            yara=inbound.get("yara") or {},
            white_text=inbound.get("white_text") or {},
            leak={
                "leaked": bool(
                    result.get("shield", {}).get(
                        "leak_detected"
                    )
                ),
                "risk_score": int(
                    result.get("shield", {}).get(
                        "risk_score"
                    )
                    or 0
                ),
                "reason": result.get("shield", {}).get(
                    "reason"
                ),
            },
            policy_check=result.get("policy_check"),
            inbound_blocked=False,
        )
        return result
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "HR candidate processing failed: "
                f"{error}"
            ),
        ) from error


@router.post("/process-cv-upload")
async def process_cv_upload(
    file: UploadFile = File(...),
    client_id: str = Form(default="default"),
    target_role: str = Form(
        default="Software Engineer",
    ),
    username: str = Form(default=""),
) -> dict:
    """
    Upload a CV file and run the full HR pipeline.
    """

    filename = file.filename or "cv.txt"
    content = await file.read()
    role = target_role or "Software Engineer"
    protection_enabled = get_protection_enabled(
        (client_id or "default").strip()
    )

    try:
        extracted = extract_requirement_text(
            filename=filename,
            content=content,
        )
        inbound = maybe_bypass_inbound_for_protection(
            scan_uploaded_file(
                content,
                filename,
                extracted_text=extracted["extracted_text"],
                relax_demo_injection_rules=True,
            ),
            protection_enabled=protection_enabled,
        )
        if inbound["blocked"]:
            return blocked_hr_response(
                inbound,
                client_id=client_id or "default",
                target_role=role,
                protection_enabled=protection_enabled,
                username=username,
                filename=filename,
            )

        result = process_candidate_cv(
            cv_text=extracted["extracted_text"],
            client_id=client_id,
            target_role=role,
            username=username,
            file_bytes=content,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error).replace(
                "requirement",
                "CV",
            ),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "HR candidate processing failed: "
                f"{error}"
            ),
        ) from error

    result["uploaded_file"] = {
        "filename": extracted["filename"],
        "file_type": extracted["file_type"],
        "character_count": len(
            extracted["extracted_text"]
        ),
    }
    result["inbound_scan"] = inbound
    result["detection_log"] = build_detection_log(
        payload=inbound.get("payload") or {},
        yara=inbound.get("yara") or {},
        white_text=inbound.get("white_text") or {},
        leak={
            "leaked": bool(
                result.get("shield", {}).get("leak_detected")
            ),
            "risk_score": int(
                result.get("shield", {}).get("risk_score") or 0
            ),
            "reason": result.get("shield", {}).get("reason"),
        },
        policy_check=result.get("policy_check"),
        inbound_blocked=False,
    )
    return result
