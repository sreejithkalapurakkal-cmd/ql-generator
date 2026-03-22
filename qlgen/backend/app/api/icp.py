from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.icp import ICPConfig
from app.models.user import User
from app.schemas.icp import ICPConfigCreate, ICPConfigUpdate, ICPConfigResponse, ICPGenerateRequest, ICPGenerateResponse
from app.services.icp_import_service import generate_icp_template, parse_icp_excel
from app.services.icp_generation_service import generate_icp_config_async, extract_text_from_file
from app.auth.dependencies import get_current_user, get_user_from_token_param
from app.auth.authorization import is_admin, ownership_filter, check_resource_access, check_edit_permission, check_delete_permission
from app.services.audit_service import log_audit

router = APIRouter(prefix="/icp", tags=["ICP Configuration"])


def _build_icp_response(icp: ICPConfig, user: User) -> ICPConfigResponse:
    """Build an ICPConfigResponse, including user attribution for admins."""
    resp = ICPConfigResponse(
        id=icp.id,
        name=icp.name,
        description=icp.description,
        config=icp.config_json,
        created_at=icp.created_at,
        updated_at=icp.updated_at,
        is_active=icp.is_active,
    )
    if is_admin(user) and icp.user:
        resp.user_name = icp.user.name
        resp.user_email = icp.user.email
    return resp


@router.get("/template/download")
async def download_icp_template(_user: User = Depends(get_user_from_token_param)):
    buffer = generate_icp_template()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=icp_template.xlsx"},
    )


@router.post("/import/parse")
async def parse_icp_upload(file: UploadFile = File(...), _user: User = Depends(get_current_user)):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    contents = await file.read()
    buffer = BytesIO(contents)
    try:
        results = parse_icp_excel(buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")
    return results


@router.post("/generate", response_model=ICPGenerateResponse)
async def generate_icp(request: ICPGenerateRequest, _user: User = Depends(get_current_user)):
    if not request.description or len(request.description.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 20 characters long",
        )
    try:
        result = await generate_icp_config_async(request.description.strip())
        return ICPGenerateResponse(
            name=result.get("name", "AI Generated ICP"),
            description=result.get("description"),
            config=result["config"],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("/generate-from-file", response_model=ICPGenerateResponse)
async def generate_icp_from_file(
    file: UploadFile = File(...),
    description: str = Form(""),
    _user: User = Depends(get_current_user),
):
    """Generate ICP config from an uploaded file (PDF, DOCX, XLSX, TXT, CSV) and optional description."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    contents = await file.read()
    try:
        file_text = extract_text_from_file(contents, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file_text and not description.strip():
        raise HTTPException(status_code=400, detail="File contains no text and no description provided")

    try:
        result = await generate_icp_config_async(description.strip(), file_text=file_text)
        return ICPGenerateResponse(
            name=result.get("name", "AI Generated ICP"),
            description=result.get("description"),
            config=result["config"],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse AI response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@router.post("", response_model=ICPConfigResponse)
async def create_icp(request: ICPConfigCreate, http_request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    icp = ICPConfig(
        name=request.name,
        description=request.description,
        config_json=request.config,
        user_id=user.id,
    )
    db.add(icp)
    await db.flush()
    await log_audit(db, user.id, "create", "icp", icp.id, {"name": icp.name}, ip_address=http_request.client.host if http_request.client else None)
    await db.commit()
    await db.refresh(icp)
    return _build_icp_response(icp, user)


@router.get("", response_model=List[ICPConfigResponse])
async def list_icps(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    query = select(ICPConfig).where(ICPConfig.is_active == True)
    if not is_admin(user):
        query = query.where(ICPConfig.user_id == user.id)
    query = query.order_by(ICPConfig.created_at.desc())
    result = await db.execute(query)
    icps = result.scalars().all()
    return [_build_icp_response(icp, user) for icp in icps]


@router.get("/{icp_id}", response_model=ICPConfigResponse)
async def get_icp(icp_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")
    check_resource_access(icp.user_id, user)
    return _build_icp_response(icp, user)


@router.put("/{icp_id}", response_model=ICPConfigResponse)
async def update_icp(icp_id: UUID, request: ICPConfigUpdate, http_request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")
    check_edit_permission(icp.user_id, user)

    changed_fields = []
    if request.name is not None:
        icp.name = request.name
        changed_fields.append("name")
    if request.description is not None:
        icp.description = request.description
        changed_fields.append("description")
    if request.config is not None:
        icp.config_json = request.config
        changed_fields.append("config")

    await log_audit(db, user.id, "update", "icp", icp.id, {"changed_fields": changed_fields}, ip_address=http_request.client.host if http_request.client else None)
    await db.commit()
    await db.refresh(icp)
    return _build_icp_response(icp, user)


@router.delete("/{icp_id}")
async def delete_icp(icp_id: UUID, http_request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")
    check_delete_permission(icp.user_id, user)
    icp.is_active = False
    await log_audit(db, user.id, "delete", "icp", icp.id, {"name": icp.name}, ip_address=http_request.client.host if http_request.client else None)
    await db.commit()
    return {"message": "ICP configuration deleted"}
