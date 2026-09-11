from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Address, StatusType
from schemas.reference import StatusTypeOut
from utils.db import get_db

router = APIRouter(tags=["Reference"])


@router.get("/towns", response_model=list[str])
async def list_towns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Get the list of towns that have stations, with no duplicates, sorted A to Z."""
    stmt = (
        select(Address.town)
        .where(Address.town.is_not(None), Address.town != "")
        .distinct()
        .order_by(Address.town)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


@router.get("/status-types", response_model=list[StatusTypeOut])
async def list_status_types(db: AsyncSession = Depends(get_db)) -> list[StatusTypeOut]:
    """Get the full list of possible statuses, so a filter dropdown can be built from it."""
    result = await db.execute(select(StatusType).order_by(StatusType.id))
    return result.scalars().all()
