from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Operator
from schemas.operator import OperatorOut
from utils.cache import cache_get, cache_set
from utils.db import get_db

router = APIRouter(prefix="/operators", tags=["Operators"])


@router.get("", response_model=list[OperatorOut])
async def list_operators(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List charging operators."""
    cache_key = f"operators:{skip}:{limit}"
    if (cached := await cache_get(cache_key)) is not None:
        return cached

    result = await db.execute(select(Operator).offset(skip).limit(limit))
    operators = [OperatorOut.model_validate(o).model_dump() for o in result.scalars().all()]
    await cache_set(cache_key, operators)
    return operators


@router.get("/{operator_id}", response_model=OperatorOut)
async def get_operator(operator_id: int, db: AsyncSession = Depends(get_db)):
    """Get an operator by ID."""
    operator = await db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    return operator
