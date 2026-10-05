from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.models import Operator
from schemas.operator import OperatorOut
from utils.db import get_db

router = APIRouter(prefix="/operators", tags=["Operators"])


@router.get("", response_model=list[OperatorOut])
async def list_operators(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List charging operators."""
    result = await db.execute(select(Operator).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{operator_id}", response_model=OperatorOut)
async def get_operator(operator_id: int, db: AsyncSession = Depends(get_db)):
    """Get an operator by ID."""
    operator = await db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    return operator
