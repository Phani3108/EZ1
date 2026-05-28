"""Finance / inventory / library / visitors endpoints — Phase 13c."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.dependencies import get_current_user, get_school_id
from app.models.ops import (
    Expense, VendorPayment, CapitalProject,
    Asset, AssetMovement,
    LibraryBook, BookLoan, Visitor,
)
from app.models.audit import AuditLog
from eduzim_shared.audit import record_audit_event
# Phase 20a — shared route helpers.
from eduzim_shared.routes import (
    _meta, _err,
)


router = APIRouter(tags=["Ops"])


EXPENSE_CATEGORIES = {
    "utilities", "repairs", "supplies", "salaries_topup",
    "transport", "food", "events", "other",
}
ASSET_CATEGORIES = {
    "furniture", "electronics", "textbook", "lab_equipment",
    "sports", "transport", "other",
}
ASSET_STATUSES = {"in_stock", "assigned", "maintenance", "disposed", "lost"}
ASSET_ACTIONS = {"assigned", "returned", "maintenance", "disposed", "lost", "found"}
CAPITAL_STATUSES = {"planning", "in_progress", "completed", "cancelled"}
VISITOR_TYPES = {"parent", "vendor", "inspector", "guest", "contractor", "other"}



def _actor(current_user: dict) -> uuid.UUID:
    return uuid.UUID(str(current_user["sub"]))



# ─── A-008 — Expenses ─────────────────────────────────────────────


class ExpenseCreate(BaseModel):
    category: str = Field(default="other")
    description: str = Field(..., max_length=500)
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    incurred_on: date
    vendor_name: Optional[str] = Field(default=None, max_length=255)
    attachment_id: Optional[uuid.UUID] = None


def _ser_expense(e: Expense) -> dict:
    return {
        "id": e.id, "category": e.category,
        "description": e.description,
        "amount_cents": e.amount_cents, "currency": e.currency,
        "incurred_on": e.incurred_on.isoformat() if e.incurred_on else None,
        "vendor_name": e.vendor_name,
        "attachment_id": e.attachment_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/expenses")
def list_expenses(
    request: Request,
    category: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Expense).filter(Expense.school_id == str(school_id))
    if category:
        q = q.filter(Expense.category == category)
    if from_date:
        q = q.filter(Expense.incurred_on >= from_date)
    if to_date:
        q = q.filter(Expense.incurred_on <= to_date)
    rows = q.order_by(desc(Expense.incurred_on)).limit(500).all()
    total = sum(r.amount_cents for r in rows)
    return {
        "data": {"items": [_ser_expense(r) for r in rows],
                 "total_cents": total},
        "meta": _meta(request),
    }


@router.post("/expenses")
def create_expense(
    payload: ExpenseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.category not in EXPENSE_CATEGORIES:
        return _err("INVALID_CATEGORY",
                    f"must be in {sorted(EXPENSE_CATEGORIES)}", request)
    actor = _actor(current_user)
    e = Expense(
        school_id=str(school_id),
        category=payload.category,
        description=payload.description,
        amount_cents=payload.amount_cents,
        currency=payload.currency,
        incurred_on=payload.incurred_on,
        vendor_name=payload.vendor_name,
        attachment_id=str(payload.attachment_id) if payload.attachment_id else None,
        recorded_by_user_id=str(actor),
    )
    db.add(e)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="expense.recorded",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "expense", "id": e.id},
        # Amount IS audit story for a money move.
        details={"category": payload.category,
                 "amount_cents": payload.amount_cents,
                 "currency": payload.currency},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_expense(e), "meta": _meta(request)}


# ─── A-008 — Vendor payments ──────────────────────────────────────


class VendorPaymentCreate(BaseModel):
    vendor_name: str = Field(..., max_length=255)
    invoice_reference: Optional[str] = Field(default=None, max_length=120)
    amount_cents: int = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    paid_on: date
    method: str = Field(default="bank_transfer", max_length=32)
    notes: Optional[str] = None


def _ser_vp(v: VendorPayment) -> dict:
    return {
        "id": v.id, "vendor_name": v.vendor_name,
        "invoice_reference": v.invoice_reference,
        "amount_cents": v.amount_cents, "currency": v.currency,
        "paid_on": v.paid_on.isoformat() if v.paid_on else None,
        "method": v.method, "notes": v.notes,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("/vendor-payments")
def list_vendor_payments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(VendorPayment)
        .filter(VendorPayment.school_id == str(school_id))
        .order_by(desc(VendorPayment.paid_on)).limit(500).all()
    )
    return {"data": [_ser_vp(r) for r in rows], "meta": _meta(request)}


@router.post("/vendor-payments")
def create_vendor_payment(
    payload: VendorPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    actor = _actor(current_user)
    v = VendorPayment(
        school_id=str(school_id),
        vendor_name=payload.vendor_name,
        invoice_reference=payload.invoice_reference,
        amount_cents=payload.amount_cents, currency=payload.currency,
        paid_on=payload.paid_on, method=payload.method,
        notes=payload.notes,
        recorded_by_user_id=str(actor),
    )
    db.add(v)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="vendor_payment.recorded",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "vendor_payment", "id": v.id,
                "vendor_name": payload.vendor_name},
        details={"amount_cents": payload.amount_cents,
                 "currency": payload.currency,
                 "method": payload.method},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_vp(v), "meta": _meta(request)}


# ─── A-008 — Capital projects ─────────────────────────────────────


class CapitalProjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    budget_cents: int = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    starts_on: Optional[date] = None
    target_completion: Optional[date] = None


class CapitalProjectUpdate(BaseModel):
    spent_cents: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None
    completed_on: Optional[date] = None


def _ser_cp(c: CapitalProject) -> dict:
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "budget_cents": c.budget_cents, "spent_cents": c.spent_cents,
        "currency": c.currency, "status": c.status,
        "starts_on": c.starts_on.isoformat() if c.starts_on else None,
        "target_completion": (
            c.target_completion.isoformat() if c.target_completion else None
        ),
        "completed_on": c.completed_on.isoformat() if c.completed_on else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/capital-projects")
def list_projects(
    request: Request,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(CapitalProject).filter(
        CapitalProject.school_id == str(school_id),
    )
    if status:
        q = q.filter(CapitalProject.status == status)
    rows = q.order_by(desc(CapitalProject.created_at)).all()
    return {"data": [_ser_cp(r) for r in rows], "meta": _meta(request)}


@router.post("/capital-projects")
def create_project(
    payload: CapitalProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    c = CapitalProject(
        school_id=str(school_id),
        name=payload.name, description=payload.description,
        budget_cents=payload.budget_cents, currency=payload.currency,
        starts_on=payload.starts_on,
        target_completion=payload.target_completion,
        created_by_user_id=str(_actor(current_user)),
    )
    db.add(c)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="capital_project.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "capital_project", "id": c.id,
                "name": payload.name},
        details={"budget_cents": payload.budget_cents,
                 "currency": payload.currency},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_cp(c), "meta": _meta(request)}


@router.put("/capital-projects/{pid}")
def update_project(
    pid: uuid.UUID, payload: CapitalProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    c = (
        db.query(CapitalProject)
        .filter(CapitalProject.id == str(pid),
                CapitalProject.school_id == str(school_id))
        .first()
    )
    if c is None:
        return _err("NOT_FOUND", "Project not found.", request, 404)
    changed = []
    if payload.spent_cents is not None:
        c.spent_cents = payload.spent_cents
        changed.append("spent_cents")
    if payload.status is not None:
        if payload.status not in CAPITAL_STATUSES:
            return _err("INVALID_STATUS",
                        f"must be in {sorted(CAPITAL_STATUSES)}", request)
        c.status = payload.status
        changed.append("status")
    if payload.completed_on is not None:
        c.completed_on = payload.completed_on
        changed.append("completed_on")
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="capital_project.updated",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "capital_project", "id": c.id},
        details={"changed_fields": changed},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_cp(c), "meta": _meta(request)}


# ─── A-009 — Assets ──────────────────────────────────────────────


class AssetCreate(BaseModel):
    asset_tag: str = Field(..., max_length=64)
    category: str = Field(default="other")
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    serial_number: Optional[str] = Field(default=None, max_length=128)
    purchase_date: Optional[date] = None
    purchase_cost_cents: Optional[int] = Field(default=None, ge=0)
    currency: str = Field(default="USD", max_length=3)


class AssetMove(BaseModel):
    action: str = Field(...)
    target_user_id: Optional[uuid.UUID] = None
    target_location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


def _ser_asset(a: Asset) -> dict:
    return {
        "id": a.id, "asset_tag": a.asset_tag, "category": a.category,
        "name": a.name, "description": a.description,
        "serial_number": a.serial_number,
        "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
        "purchase_cost_cents": a.purchase_cost_cents,
        "currency": a.currency, "status": a.status,
        "assigned_to_user_id": a.assigned_to_user_id,
        "assigned_to_location": a.assigned_to_location,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/assets")
def list_assets(
    request: Request,
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Asset).filter(Asset.school_id == str(school_id))
    if category:
        q = q.filter(Asset.category == category)
    if status:
        q = q.filter(Asset.status == status)
    rows = q.order_by(Asset.asset_tag.asc()).all()
    return {"data": [_ser_asset(r) for r in rows], "meta": _meta(request)}


@router.post("/assets")
def create_asset(
    payload: AssetCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.category not in ASSET_CATEGORIES:
        return _err("INVALID_CATEGORY",
                    f"must be in {sorted(ASSET_CATEGORIES)}", request)
    a = Asset(
        school_id=str(school_id),
        asset_tag=payload.asset_tag,
        category=payload.category,
        name=payload.name, description=payload.description,
        serial_number=payload.serial_number,
        purchase_date=payload.purchase_date,
        purchase_cost_cents=payload.purchase_cost_cents,
        currency=payload.currency,
    )
    db.add(a)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="asset.created",
        school_id=school_id, actor_user_id=_actor(current_user),
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "asset", "id": a.id,
                "asset_tag": payload.asset_tag},
        details={"category": payload.category},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_asset(a), "meta": _meta(request)}


@router.post("/assets/{aid}/movements")
def move_asset(
    aid: uuid.UUID, payload: AssetMove,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.action not in ASSET_ACTIONS:
        return _err("INVALID_ACTION",
                    f"must be in {sorted(ASSET_ACTIONS)}", request)
    a = (
        db.query(Asset)
        .filter(Asset.id == str(aid),
                Asset.school_id == str(school_id))
        .first()
    )
    if a is None:
        return _err("NOT_FOUND", "Asset not found.", request, 404)
    actor = _actor(current_user)
    m = AssetMovement(
        school_id=str(school_id), asset_id=a.id,
        action=payload.action,
        actor_user_id=str(actor),
        target_user_id=str(payload.target_user_id) if payload.target_user_id else None,
        target_location=payload.target_location,
        notes=payload.notes,
    )
    db.add(m)
    # Update Asset.status based on action
    if payload.action == "assigned":
        a.status = "assigned"
        a.assigned_to_user_id = str(payload.target_user_id) if payload.target_user_id else None
        a.assigned_to_location = payload.target_location
    elif payload.action == "returned":
        a.status = "in_stock"
        a.assigned_to_user_id = None
        a.assigned_to_location = None
    elif payload.action == "maintenance":
        a.status = "maintenance"
    elif payload.action == "disposed":
        a.status = "disposed"
    elif payload.action == "lost":
        a.status = "lost"
    elif payload.action == "found":
        a.status = "in_stock"
    db.flush()
    record_audit_event(
        db, AuditLog, event_type=f"asset.{payload.action}",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "asset", "id": a.id},
        details={"action": payload.action},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": {"asset": _ser_asset(a), "movement_id": m.id},
            "meta": _meta(request)}


# ─── A-011 — Library ────────────────────────────────────────────


class BookCreate(BaseModel):
    title: str = Field(..., max_length=500)
    author: Optional[str] = Field(default=None, max_length=255)
    isbn: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=64)
    total_copies: int = Field(default=1, ge=1)
    shelf_location: Optional[str] = Field(default=None, max_length=64)


class LoanCreate(BaseModel):
    book_id: uuid.UUID
    borrower_user_id: uuid.UUID
    due_on: date


def _ser_book(b: LibraryBook) -> dict:
    return {
        "id": b.id, "title": b.title, "author": b.author,
        "isbn": b.isbn, "category": b.category,
        "total_copies": b.total_copies,
        "available_copies": b.available_copies,
        "shelf_location": b.shelf_location,
    }


def _ser_loan(l: BookLoan) -> dict:
    overdue = (
        l.returned_at is None and l.due_on < date.today()
    )
    return {
        "id": l.id, "book_id": l.book_id,
        "borrower_user_id": l.borrower_user_id,
        "issued_at": l.issued_at.isoformat() if l.issued_at else None,
        "due_on": l.due_on.isoformat() if l.due_on else None,
        "returned_at": l.returned_at.isoformat() if l.returned_at else None,
        "status": (
            "returned" if l.returned_at else
            ("overdue" if overdue else "active")
        ),
    }


@router.get("/library/books")
def list_books(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    rows = (
        db.query(LibraryBook)
        .filter(LibraryBook.school_id == str(school_id))
        .order_by(LibraryBook.title.asc())
        .limit(500).all()
    )
    return {"data": [_ser_book(r) for r in rows], "meta": _meta(request)}


@router.post("/library/books")
def create_book(
    payload: BookCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    b = LibraryBook(
        school_id=str(school_id),
        title=payload.title, author=payload.author,
        isbn=payload.isbn, category=payload.category,
        total_copies=payload.total_copies,
        available_copies=payload.total_copies,
        shelf_location=payload.shelf_location,
    )
    db.add(b)
    db.flush()
    db.commit()
    return {"data": _ser_book(b), "meta": _meta(request)}


@router.post("/library/loans")
def issue_loan(
    payload: LoanCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    b = (
        db.query(LibraryBook)
        .filter(LibraryBook.id == str(payload.book_id),
                LibraryBook.school_id == str(school_id))
        .first()
    )
    if b is None:
        return _err("NOT_FOUND", "Book not found.", request, 404)
    if b.available_copies <= 0:
        return _err("UNAVAILABLE", "No copies available.", request, 409)
    l = BookLoan(
        school_id=str(school_id), book_id=b.id,
        borrower_user_id=str(payload.borrower_user_id),
        due_on=payload.due_on,
    )
    db.add(l)
    b.available_copies -= 1
    db.flush()
    db.commit()
    return {"data": _ser_loan(l), "meta": _meta(request)}


@router.post("/library/loans/{lid}/return")
def return_loan(
    lid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    l = (
        db.query(BookLoan)
        .filter(BookLoan.id == str(lid),
                BookLoan.school_id == str(school_id))
        .first()
    )
    if l is None or l.returned_at is not None:
        return _err("NOT_FOUND", "Active loan not found.", request, 404)
    l.returned_at = datetime.now(timezone.utc)
    b = (
        db.query(LibraryBook)
        .filter(LibraryBook.id == l.book_id).first()
    )
    if b:
        b.available_copies = min(b.available_copies + 1, b.total_copies)
    db.flush()
    db.commit()
    return {"data": _ser_loan(l), "meta": _meta(request)}


# ─── A-014 — Visitor management ──────────────────────────────────


class VisitorSignIn(BaseModel):
    full_name: str = Field(..., max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    visitor_type: str = Field(default="guest")
    purpose: str = Field(..., max_length=255)
    visiting_user_id: Optional[uuid.UUID] = None
    visitor_badge_number: Optional[str] = Field(default=None, max_length=32)


def _ser_visitor(v: Visitor) -> dict:
    return {
        "id": v.id, "full_name": v.full_name, "phone": v.phone,
        "visitor_type": v.visitor_type, "purpose": v.purpose,
        "visiting_user_id": v.visiting_user_id,
        "visitor_badge_number": v.visitor_badge_number,
        "signed_in_at": v.signed_in_at.isoformat() if v.signed_in_at else None,
        "signed_out_at": v.signed_out_at.isoformat() if v.signed_out_at else None,
    }


@router.get("/visitors")
def list_visitors(
    request: Request,
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    q = db.query(Visitor).filter(Visitor.school_id == str(school_id))
    if active_only:
        q = q.filter(Visitor.signed_out_at.is_(None))
    rows = q.order_by(desc(Visitor.signed_in_at)).limit(500).all()
    return {"data": [_ser_visitor(r) for r in rows], "meta": _meta(request)}


@router.post("/visitors")
def sign_in_visitor(
    payload: VisitorSignIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    if payload.visitor_type not in VISITOR_TYPES:
        return _err("INVALID_TYPE",
                    f"must be in {sorted(VISITOR_TYPES)}", request)
    actor = _actor(current_user)
    v = Visitor(
        school_id=str(school_id),
        full_name=payload.full_name, phone=payload.phone,
        visitor_type=payload.visitor_type, purpose=payload.purpose,
        visiting_user_id=str(payload.visiting_user_id) if payload.visiting_user_id else None,
        visitor_badge_number=payload.visitor_badge_number,
        signed_in_by_user_id=str(actor),
    )
    db.add(v)
    db.flush()
    record_audit_event(
        db, AuditLog, event_type="visitor.signed_in",
        school_id=school_id, actor_user_id=actor,
        actor_role=(current_user.get("roles") or [None])[0],
        target={"resource": "visitor", "id": v.id},
        # Visitor type + visiting user are admin-debuggable. Name +
        # phone are PII so not logged.
        details={"visitor_type": payload.visitor_type,
                 "purpose_length": len(payload.purpose)},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    return {"data": _ser_visitor(v), "meta": _meta(request)}


@router.post("/visitors/{vid}/sign-out")
def sign_out_visitor(
    vid: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    school_id: uuid.UUID = Depends(get_school_id),
):
    v = (
        db.query(Visitor)
        .filter(Visitor.id == str(vid),
                Visitor.school_id == str(school_id))
        .first()
    )
    if v is None or v.signed_out_at is not None:
        return _err("NOT_FOUND", "Active visitor not found.", request, 404)
    v.signed_out_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    return {"data": _ser_visitor(v), "meta": _meta(request)}
