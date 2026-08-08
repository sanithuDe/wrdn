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

from wrdn.backend.services.hr_candidate_service import (
    get_sample_cvs,
    process_candidate_cv,
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


@router.get("/sample-cvs")
def sample_cvs() -> dict:
    """Return safe and attack CV samples for the demo."""

    return get_sample_cvs()


@router.post("/extract-cv")
async def extract_cv(
    file: UploadFile = File(...),
) -> dict:
    """
    Extract readable text from an uploaded CV
    (PDF, DOCX, or TXT).
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

    try:
        return process_candidate_cv(
            cv_text=payload.cv_text,
            client_id=payload.client_id,
            target_role=payload.target_role,
        )
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
) -> dict:
    """
    Upload a CV file and run the full HR pipeline.
    """

    filename = file.filename or "cv.txt"
    content = await file.read()

    try:
        extracted = extract_requirement_text(
            filename=filename,
            content=content,
        )
        result = process_candidate_cv(
            cv_text=extracted["extracted_text"],
            client_id=client_id,
            target_role=target_role
            or "Software Engineer",
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
    return result
