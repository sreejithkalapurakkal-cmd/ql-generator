from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.icp import ICPConfig
from app.schemas.icp import ICPConfigCreate, ICPConfigUpdate, ICPConfigResponse, ICPGenerateRequest, ICPGenerateResponse
from app.services.icp_import_service import generate_icp_template, parse_icp_excel
from app.services.icp_generation_service import generate_icp_config_async

router = APIRouter(prefix="/icp", tags=["ICP Configuration"])


@router.get("/template/download")
async def download_icp_template():
    buffer = generate_icp_template()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=icp_template.xlsx"},
    )


@router.post("/import/parse")
async def parse_icp_upload(file: UploadFile = File(...)):
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
async def generate_icp(request: ICPGenerateRequest):
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


@router.post("", response_model=ICPConfigResponse)
async def create_icp(request: ICPConfigCreate, db: AsyncSession = Depends(get_db)):
    icp = ICPConfig(
        name=request.name,
        description=request.description,
        config_json=request.config,
    )
    db.add(icp)
    await db.commit()
    await db.refresh(icp)
    return ICPConfigResponse(
        id=icp.id,
        name=icp.name,
        description=icp.description,
        config=icp.config_json,
        created_at=icp.created_at,
        updated_at=icp.updated_at,
        is_active=icp.is_active,
    )


@router.get("", response_model=List[ICPConfigResponse])
async def list_icps(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ICPConfig).where(ICPConfig.is_active == True).order_by(ICPConfig.created_at.desc())
    )
    icps = result.scalars().all()
    return [
        ICPConfigResponse(
            id=icp.id,
            name=icp.name,
            description=icp.description,
            config=icp.config_json,
            created_at=icp.created_at,
            updated_at=icp.updated_at,
            is_active=icp.is_active,
        )
        for icp in icps
    ]


@router.get("/{icp_id}", response_model=ICPConfigResponse)
async def get_icp(icp_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")
    return ICPConfigResponse(
        id=icp.id,
        name=icp.name,
        description=icp.description,
        config=icp.config_json,
        created_at=icp.created_at,
        updated_at=icp.updated_at,
        is_active=icp.is_active,
    )


@router.put("/{icp_id}", response_model=ICPConfigResponse)
async def update_icp(icp_id: UUID, request: ICPConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")

    if request.name is not None:
        icp.name = request.name
    if request.description is not None:
        icp.description = request.description
    if request.config is not None:
        icp.config_json = request.config

    await db.commit()
    await db.refresh(icp)
    return ICPConfigResponse(
        id=icp.id,
        name=icp.name,
        description=icp.description,
        config=icp.config_json,
        created_at=icp.created_at,
        updated_at=icp.updated_at,
        is_active=icp.is_active,
    )


@router.delete("/{icp_id}")
async def delete_icp(icp_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ICPConfig).where(ICPConfig.id == icp_id))
    icp = result.scalar_one_or_none()
    if not icp:
        raise HTTPException(status_code=404, detail="ICP configuration not found")
    icp.is_active = False
    await db.commit()
    return {"message": "ICP configuration deleted"}
