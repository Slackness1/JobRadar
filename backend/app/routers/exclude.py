from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExcludeRule
from app.schemas import ExcludeRuleOut, ExcludeRuleIn

router = APIRouter(prefix="/api/exclude", tags=["exclude"])


@router.get("", response_model=list[ExcludeRuleOut])
@router.get("/", response_model=list[ExcludeRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(ExcludeRule).order_by(ExcludeRule.category).all()


@router.post("", response_model=ExcludeRuleOut)
@router.post("/", response_model=ExcludeRuleOut)
def add_rule(data: ExcludeRuleIn, db: Session = Depends(get_db)):
    rule = ExcludeRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(ExcludeRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}
