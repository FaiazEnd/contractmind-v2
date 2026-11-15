"""Obligation extraction schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ObligationItem(BaseModel):
    clause_reference: str
    obligation_type: str
    obligor: str
    recipient: str
    description: str
    due_date_or_trigger: str
    recurrence: str = "One-time"
    penalty_for_breach: str = "Material breach / contractual remedies"
