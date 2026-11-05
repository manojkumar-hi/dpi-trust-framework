"""Local-only HR prototype tools backed by synthetic in-memory sample data."""

from __future__ import annotations

from datetime import date, timedelta
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.agent_templates.base import AgentTemplate, AgentTemplateTool


class LeaveBalanceInput(BaseModel):
    employee_id: str = Field(default="EMP-1001", min_length=1, max_length=32)


class LeaveStatusInput(BaseModel):
    request_id: str = Field(default="LR-2026-001", min_length=1, max_length=40)


class SubmitLeaveInput(BaseModel):
    employee_id: str = Field(default="EMP-1001", min_length=1, max_length=32)
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=240)


class EmployeeProfileInput(BaseModel):
    employee_id: str = Field(default="EMP-1001", min_length=1, max_length=32)


class TrainingPlanInput(BaseModel):
    department: str = Field(default="Customer Support", min_length=2, max_length=80)
    training_topic: str = Field(default="Service quality and compliance", min_length=3, max_length=120)


# These records are deliberately synthetic and live only in this process.
_EMPLOYEES = {
    "EMP-1001": {
        "employee_id": "EMP-1001",
        "name": "Alex Morgan (sample)",
        "department": "People Operations",
        "title": "HR Coordinator",
        "work_email": "alex.morgan@example.test",
        "employment_status": "active",
    },
    "EMP-1002": {
        "employee_id": "EMP-1002",
        "name": "Sam Lee (sample)",
        "department": "Engineering",
        "title": "Software Engineer",
        "work_email": "sam.lee@example.test",
        "employment_status": "active",
    },
}
_LEAVE_BALANCES = {"EMP-1001": {"annual": 12, "sick": 6}, "EMP-1002": {"annual": 8, "sick": 5}}
_LEAVE_REQUESTS = {
    "LR-2026-001": {
        "request_id": "LR-2026-001",
        "employee_id": "EMP-1001",
        "status": "APPROVED",
        "start_date": "2026-02-09",
        "end_date": "2026-02-10",
        "reason": "Sample personal leave",
    }
}
_leave_lock = Lock()


async def read_policies() -> dict:
    return {
        "prototype": True,
        "source": "synthetic local sample",
        "policies": [
            {"id": "POL-01", "title": "Annual leave", "summary": "Sample allowance is 20 days per year."},
            {"id": "POL-02", "title": "Sick leave", "summary": "Sample allowance is 10 days per year."},
            {"id": "POL-03", "title": "Request notice", "summary": "Sample requests should be submitted in advance."},
        ],
    }


async def calculate_leave_balance(employee_id: str = "EMP-1001") -> dict:
    request = LeaveBalanceInput(employee_id=employee_id)
    employee = _EMPLOYEES.get(request.employee_id)
    if employee is None:
        return {"prototype": True, "error": "No sample employee matches that ID."}
    balance = _LEAVE_BALANCES[request.employee_id]
    return {"prototype": True, "employee_id": request.employee_id, "annual_days_remaining": balance["annual"], "sick_days_remaining": balance["sick"]}


async def view_holiday_calendar(year: int | None = None) -> dict:
    calendar_year = year or date.today().year
    if calendar_year < 2000 or calendar_year > 2100:
        raise ValueError("Year must be between 2000 and 2100.")
    return {
        "prototype": True,
        "year": calendar_year,
        "holidays": [
            {"date": f"{calendar_year}-01-01", "name": "New Year's Day (sample)"},
            {"date": f"{calendar_year}-05-01", "name": "Community Day (sample)"},
            {"date": f"{calendar_year}-12-25", "name": "Winter Holiday (sample)"},
        ],
    }


async def check_leave_status(request_id: str = "LR-2026-001") -> dict:
    request = LeaveStatusInput(request_id=request_id)
    with _leave_lock:
        record = _LEAVE_REQUESTS.get(request.request_id)
        if record is None:
            return {"prototype": True, "error": "No sample leave request matches that ID."}
        return {"prototype": True, **record}


async def submit_leave_request(
    employee_id: str,
    start_date: date,
    end_date: date,
    reason: str,
) -> dict:
    request = SubmitLeaveInput(employee_id=employee_id, start_date=start_date, end_date=end_date, reason=reason)
    if request.employee_id not in _EMPLOYEES:
        return {"prototype": True, "error": "No sample employee matches that ID."}
    if request.start_date < date.today():
        raise ValueError("Start date must be today or later.")
    if request.end_date < request.start_date:
        raise ValueError("End date must be on or after the start date.")

    business_days = sum(
        1 for offset in range((request.end_date - request.start_date).days + 1)
        if (request.start_date + timedelta(days=offset)).weekday() < 5
    )
    request_id = f"LR-LOCAL-{uuid4().hex[:8].upper()}"
    record = {
        "request_id": request_id,
        "employee_id": request.employee_id,
        "status": "SUBMITTED (sample only)",
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "business_days": business_days,
        "reason": request.reason,
    }
    with _leave_lock:
        _LEAVE_REQUESTS[request_id] = record
    return {"prototype": True, **record, "notice": "Stored in this backend process only; no HR system was contacted."}


async def view_employee_profile(employee_id: str = "EMP-1001") -> dict:
    request = EmployeeProfileInput(employee_id=employee_id)
    employee = _EMPLOYEES.get(request.employee_id)
    if employee is None:
        return {"prototype": True, "error": "No sample employee matches that ID."}
    return {"prototype": True, "profile": employee}


async def plan_training_program(
    department: str = "Customer Support",
    training_topic: str = "Service quality and compliance",
    budget: dict | None = None,
) -> dict:
    request = TrainingPlanInput(department=department, training_topic=training_topic)
    budget = budget or {}
    remaining = budget.get("remaining", "unknown")
    currency = budget.get("currency", "USD")
    return {
        "prototype": True,
        "workflow": "workforce_training_program",
        "department": request.department,
        "training_topic": request.training_topic,
        "budget_summary": {
            "cost_center": budget.get("cost_center", "CC-100"),
            "remaining": remaining,
            "currency": currency,
        },
        "training_plan": {
            "audience": f"{request.department} team",
            "modules": [
                "Policy and process refresher",
                "Scenario-based practice",
                "Knowledge check and manager follow-up",
            ],
            "delivery": "Two half-day sessions with a two-week follow-up",
            "budget_fit": f"Plan scoped against the Finance budget with {remaining} {currency} remaining.",
        },
        "notice": "HR combined its planning work with an automatically verified Finance budget lookup.",
    }


hr_agent_template = AgentTemplate(
    template_id="hr_agent",
    template_version="1.0.0",
    display_name="HR Agent",
    description="Local prototype for common HR questions and sample leave workflows.",
    system_prompt="You are a helpful HR assistant. Clearly identify all returned information as synthetic prototype data.",
    tools=[
        AgentTemplateTool(name="read_hr_policies", description="Read sample HR policy summaries", capability_code="hr.read_policies", func=read_policies),
        AgentTemplateTool(name="calculate_leave_balance", description="Calculate sample leave balances", capability_code="hr.calculate_leave_balance", func=calculate_leave_balance),
        AgentTemplateTool(name="view_holiday_calendar", description="View the sample holiday calendar", capability_code="hr.view_holiday_calendar", func=view_holiday_calendar),
        AgentTemplateTool(name="check_leave_status", description="Check a sample leave request", capability_code="hr.check_leave_status", func=check_leave_status),
        AgentTemplateTool(name="submit_leave_request", description="Submit a local sample leave request", capability_code="hr.submit_leave_request", func=submit_leave_request),
        AgentTemplateTool(name="view_employee_profile", description="View a synthetic sample employee profile", capability_code="hr.view_employee_profile", func=view_employee_profile),
        AgentTemplateTool(name="plan_training_program", description="Plan a synthetic workforce training program using an internal Finance budget check", capability_code="hr.plan_training_program", func=plan_training_program),
    ],
)
