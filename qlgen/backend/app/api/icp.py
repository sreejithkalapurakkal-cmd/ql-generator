from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.models.icp import ICPConfig
from app.schemas.icp import ICPConfigCreate, ICPConfigUpdate, ICPConfigResponse

router = APIRouter(prefix="/icp", tags=["ICP Configuration"])


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
