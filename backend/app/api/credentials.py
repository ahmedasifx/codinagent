"""Credentials vault — stores a reference (env var / secret-manager key) to a secret,
never the raw value."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.db import db_enabled, get_db
from ..schemas.registry import CredentialIn, CredentialOut

router = APIRouter()


def _require_db():
    if not db_enabled():
        raise HTTPException(503, "Database not configured (DB-less mode)")


@router.get("/credentials")
async def list_credentials(db: Session = Depends(get_db)):
    _require_db()
    from ..models import Credential

    return [
        CredentialOut(id=str(c.id), name=c.name, type=c.type, secret_ref=c.secret_ref)
        for c in db.query(Credential).all()
    ]


@router.post("/credentials", status_code=201)
async def create_credential(payload: CredentialIn, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Credential

    row = Credential(name=payload.name, type=payload.type, secret_ref=payload.secret_ref)
    db.add(row)
    db.commit()
    db.refresh(row)
    return CredentialOut(id=str(row.id), name=row.name, type=row.type, secret_ref=row.secret_ref)


@router.delete("/credentials/{cred_id}", status_code=204)
async def delete_credential(cred_id: str, db: Session = Depends(get_db)):
    _require_db()
    from ..models import Credential

    row = db.get(Credential, uuid.UUID(cred_id))
    if row:
        db.delete(row)
        db.commit()
