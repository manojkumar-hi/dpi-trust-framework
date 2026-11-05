"""Local-only Finance prototype tools backed by synthetic in-memory sample data."""

from __future__ import annotations

from decimal import Decimal
from threading import Lock

from pydantic import BaseModel, Field

from app.services.agent_templates.base import AgentTemplate, AgentTemplateTool


class BudgetInput(BaseModel):
    cost_center: str = Field(default="CC-100", min_length=1, max_length=32)


class InvoiceInput(BaseModel):
    invoice_id: str = Field(default="INV-2026-001", min_length=1, max_length=40)


class PaymentInput(BaseModel):
    invoice_id: str = Field(default="INV-2026-001", min_length=1, max_length=40)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)


_BUDGETS = {
    "CC-100": {
        "cost_center": "CC-100",
        "name": "People Operations (sample)",
        "fiscal_year": 2026,
        "allocated": "250000.00",
        "committed": "148500.00",
        "remaining": "101500.00",
        "currency": "USD",
    },
    "CC-200": {
        "cost_center": "CC-200",
        "name": "Engineering (sample)",
        "fiscal_year": 2026,
        "allocated": "600000.00",
        "committed": "412000.00",
        "remaining": "188000.00",
        "currency": "USD",
    },
}
_INVOICES = {
    "INV-2026-001": {
        "invoice_id": "INV-2026-001",
        "supplier": "Northwind Office Supplies (sample)",
        "cost_center": "CC-100",
        "amount": "1250.00",
        "currency": "USD",
        "status": "PENDING_REVIEW",
    }
}
_PAYMENT_PREPARATIONS: list[dict] = []
_finance_lock = Lock()


async def read_budget(cost_center: str = "CC-100") -> dict:
    request = BudgetInput(cost_center=cost_center)
    budget = _BUDGETS.get(request.cost_center)
    if budget is None:
        return {"prototype": True, "error": "No sample budget matches that cost center."}
    return {"prototype": True, "budget": budget}


async def review_invoice(invoice_id: str = "INV-2026-001") -> dict:
    request = InvoiceInput(invoice_id=invoice_id)
    invoice = _INVOICES.get(request.invoice_id)
    if invoice is None:
        return {"prototype": True, "error": "No sample invoice matches that ID."}
    amount = Decimal(invoice["amount"])
    return {
        "prototype": True,
        "invoice": invoice,
        "review": {
            "within_sample_tolerance": amount <= Decimal("5000.00"),
            "requires_human_approval": True,
            "signals": ["Supplier and amount are synthetic sample values."],
        },
    }


async def prepare_payment(
    invoice_id: str = "INV-2026-001",
    amount: Decimal = Decimal("1250.00"),
    currency: str = "USD",
) -> dict:
    request = PaymentInput(invoice_id=invoice_id, amount=amount, currency=currency.upper())
    invoice = _INVOICES.get(request.invoice_id)
    if invoice is None:
        return {"prototype": True, "error": "No sample invoice matches that ID."}
    if request.currency != invoice["currency"] or request.amount != Decimal(invoice["amount"]):
        return {"prototype": True, "error": "Payment amount and currency must match the sample invoice."}

    preparation = {
        "invoice_id": request.invoice_id,
        "amount": f"{request.amount:.2f}",
        "currency": request.currency,
        "status": "PREPARED_FOR_REVIEW (sample only)",
    }
    with _finance_lock:
        _PAYMENT_PREPARATIONS.append(preparation)
    return {
        "prototype": True,
        "payment": preparation,
        "notice": "Prepared in this backend process only; no payment was submitted.",
    }


finance_agent_template = AgentTemplate(
    template_id="finance_agent",
    template_version="1.0.0",
    display_name="Finance Agent",
    description="Local prototype for budget, invoice review, and payment preparation workflows.",
    system_prompt="You are a helpful finance assistant. Clearly identify all returned information as synthetic prototype data and never imply that a payment was submitted.",
    tools=[
        AgentTemplateTool(name="read_budget", description="Read a synthetic budget summary", capability_code="finance.read_budget", func=read_budget),
        AgentTemplateTool(name="review_invoice", description="Review a synthetic invoice", capability_code="finance.review_invoice", func=review_invoice),
        AgentTemplateTool(name="prepare_payment", description="Prepare a synthetic payment for human review", capability_code="finance.prepare_payment", func=prepare_payment),
    ],
)
