from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Address, StatusType
from schemas.reference import StatusTypeOut
from utils.cache import cache_get, cache_set
from utils.db import get_db

router = APIRouter(tags=["Reference"])


@router.get("/towns", response_model=list[str])
async def list_towns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """List unique towns that have stations, sorted."""
    cache_key = f"towns:{limit}:{offset}"
    if (cached := await cache_get(cache_key)) is not None:
        return cached

    stmt = (
        select(Address.town)
        .where(Address.town.is_not(None), Address.town != "")
        .distinct()
        .order_by(Address.town)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    towns = [row[0] for row in result.all()]
    await cache_set(cache_key, towns)
    return towns


@router.get("/status-types", response_model=list[StatusTypeOut])
async def list_status_types(db: AsyncSession = Depends(get_db)) -> list[StatusTypeOut]:
    """List all possible statuses."""
    if (cached := await cache_get("status-types")) is not None:
        return cached

    result = await db.execute(select(StatusType).order_by(StatusType.id))
    status_types = [StatusTypeOut.model_validate(s).model_dump() for s in result.scalars().all()]
    await cache_set("status-types", status_types)
    return status_types
