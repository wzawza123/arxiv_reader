from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Subscription, SubscriptionKind
from ..schemas import SubscriptionIn, SubscriptionOut

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionOut])
def list_subs(db: Session = Depends(get_db)):
    return db.execute(select(Subscription).order_by(Subscription.id)).scalars().all()


@router.post("", response_model=SubscriptionOut)
def create_sub(payload: SubscriptionIn, db: Session = Depends(get_db)):
    sub = Subscription(
        kind=SubscriptionKind(payload.kind),
        value=payload.value.strip(),
        enabled=payload.enabled,
    )
    db.add(sub)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "subscription already exists")
    db.refresh(sub)
    return sub


@router.patch("/{sub_id}", response_model=SubscriptionOut)
@router.post("/{sub_id}/update", response_model=SubscriptionOut)
def update_sub(sub_id: int, payload: SubscriptionIn, db: Session = Depends(get_db)):
    sub = db.get(Subscription, sub_id)
    if sub is None:
        raise HTTPException(404)
    sub.kind = SubscriptionKind(payload.kind)
    sub.value = payload.value.strip()
    sub.enabled = payload.enabled
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{sub_id}")
@router.post("/{sub_id}/delete")
def delete_sub(sub_id: int, db: Session = Depends(get_db)):
    sub = db.get(Subscription, sub_id)
    if sub is None:
        raise HTTPException(404)
    db.delete(sub)
    db.commit()
    return {"ok": True}
