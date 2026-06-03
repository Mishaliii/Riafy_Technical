import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from database import get_db, init_db
from schemas import (
    CategoryEnum,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
    FilterParams,
    format_inr,
)
from services import (
    svc_create_expense,
    svc_delete_expense,
    svc_export_csv,
    svc_get_dashboard_data,
    svc_get_expense,
    svc_get_expenses,
    svc_get_monthly_summary,
    svc_get_recycled_expenses,
    svc_permanent_delete_expense,
    svc_recycle_retention_days,
    svc_restore_expense,
    svc_update_expense,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Smart Personal Finance Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["format_inr"] = format_inr


def chart_breakdown(summary: dict) -> dict[str, float]:
    return {key: float(value) for key, value in summary["breakdown"].items()}


def chart_daily(summary: dict) -> dict[str, float]:
    return {str(day): float(value) for day, value in summary["daily_totals"].items()}


def to_expense_out(expense) -> ExpenseOut:
    return ExpenseOut.model_validate(expense)


def to_expense_out_list(expenses) -> list[ExpenseOut]:
    return [to_expense_out(expense) for expense in expenses]


def count_active_filters(filters: FilterParams) -> int:
    count = 0
    for value in filters.model_dump().values():
        if value is not None and value != "":
            count += 1
    return count


def parse_optional_year(year: Optional[str]) -> Optional[int]:
    if year is None or str(year).strip() == "":
        return None
    return int(year)


def build_filters(
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
) -> FilterParams:
    parsed_amount_min = None
    parsed_amount_max = None
    if amount_min not in (None, ""):
        parsed_amount_min = Decimal(amount_min)
    if amount_max not in (None, ""):
        parsed_amount_max = Decimal(amount_max)

    parsed_category = None
    if category:
        parsed_category = CategoryEnum(category)

    return FilterParams(
        category=parsed_category,
        date_from=date_from,
        date_to=date_to,
        amount_min=parsed_amount_min,
        amount_max=parsed_amount_max,
        title_search=title_search or None,
        month=month or None,
        year=parse_optional_year(year),
    )


def dashboard_filter_params(
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
) -> FilterParams:
    return build_filters(
        category=category,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        title_search=title_search,
        month=month or date.today().strftime("%Y-%m"),
        year=year,
    )


def parse_form_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = error["loc"][0] if error["loc"] else "form"
        message = error["msg"]
        if field == "amount" and "greater than" in message.lower():
            errors[field] = "Amount must be greater than ₹0"
        elif field == "title" and "empty" in message.lower():
            errors[field] = "Title cannot be empty"
        elif field == "note" and "500" in message:
            errors[field] = "Note cannot exceed 500 characters"
        else:
            errors[field] = message
    return errors


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    today = date.today()
    filters = FilterParams(month=today.strftime("%Y-%m"))
    data = svc_get_dashboard_data(db, filters)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "active_page": "dashboard",
            "stats": data["stats"],
            "analytics": data["analytics"],
            "insights": data["insights"],
            "current_month": today.strftime("%Y-%m"),
            "current_month_label": today.strftime("%B %Y"),
            "categories": [c.value for c in CategoryEnum],
            "today": today.isoformat(),
            "recent_expenses": to_expense_out_list(data["stats"]["recent"]),
        },
    )


@app.get("/expenses", response_class=HTMLResponse)
def expenses_page(request: Request, db: Session = Depends(get_db)):
    filters = FilterParams()
    expense_rows = to_expense_out_list(svc_get_expenses(db, filters))
    return templates.TemplateResponse(
        "expenses.html",
        {
            "request": request,
            "active_page": "expenses",
            "expenses": expense_rows,
            "filters": filters,
            "active_count": 0,
            "categories": [c.value for c in CategoryEnum],
            "today": date.today().isoformat(),
        },
    )


@app.get("/htmx/expenses/list", response_class=HTMLResponse)
def htmx_expense_list(
    request: Request,
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
):
    filters = build_filters(
        category=category,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        title_search=title_search,
        month=month,
        year=year,
    )
    expenses = to_expense_out_list(svc_get_expenses(db, filters))
    return templates.TemplateResponse(
        "partials/expense_list.html",
        {
            "request": request,
            "expenses": expenses,
            "active_count": count_active_filters(filters),
        },
    )


@app.get("/htmx/expenses/form", response_class=HTMLResponse)
def htmx_expense_form(request: Request):
    return templates.TemplateResponse(
        "partials/expense_form.html",
        {
            "request": request,
            "categories": [c.value for c in CategoryEnum],
            "today": date.today().isoformat(),
            "errors": {},
            "values": None,
        },
    )


@app.get("/htmx/expenses/{expense_id}/edit", response_class=HTMLResponse)
def htmx_expense_edit(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = svc_get_expense(db, expense_id)
    if expense is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "partials/edit_form.html",
        {
            "request": request,
            "expense": expense,
            "categories": [c.value for c in CategoryEnum],
        },
    )


@app.get("/htmx/expenses/{expense_id}/view", response_class=HTMLResponse)
def htmx_expense_view(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = svc_get_expense(db, expense_id)
    if expense is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "partials/expense_row.html",
        {"request": request, "expense": to_expense_out(expense)},
    )


@app.get("/htmx/dashboard/cards", response_class=HTMLResponse)
def htmx_dashboard_cards(
    request: Request,
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
):
    filters = dashboard_filter_params(
        category, date_from, date_to, amount_min, amount_max, title_search, month, year
    )
    stats = svc_get_dashboard_data(db, filters)["stats"]
    return templates.TemplateResponse(
        "partials/dashboard_cards.html",
        {"request": request, "stats": stats},
    )


@app.get("/htmx/dashboard/charts", response_class=HTMLResponse)
def htmx_dashboard_charts(
    request: Request,
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
):
    filters = dashboard_filter_params(
        category, date_from, date_to, amount_min, amount_max, title_search, month, year
    )
    data = svc_get_dashboard_data(db, filters)
    return templates.TemplateResponse(
        "partials/dashboard_charts.html",
        {"request": request, "analytics": data["analytics"]},
    )


@app.get("/htmx/summary", response_class=HTMLResponse)
def htmx_summary(
    request: Request,
    month: str = Query(default_factory=lambda: date.today().strftime("%Y-%m")),
    db: Session = Depends(get_db),
):
    data = svc_get_monthly_summary(db, month)
    return templates.TemplateResponse(
        "partials/summary.html",
        {"request": request, **data},
    )


@app.post("/api/expenses")
async def api_create_expense(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    amount: str = Form(...),
    category: str = Form(...),
    date_value: str = Form(alias="date"),
    note: Optional[str] = Form(None),
):
    try:
        data = ExpenseCreate(
            title=title,
            amount=Decimal(amount),
            category=CategoryEnum(category),
            date=date.fromisoformat(date_value),
            note=note or None,
        )
    except (ValidationError, ValueError, InvalidOperation) as exc:
        errors: dict[str, str] = {}
        values = {
            "title": title,
            "amount": amount,
            "category": category,
            "date": date_value,
            "note": note or "",
        }
        if isinstance(exc, ValidationError):
            errors = parse_form_errors(exc)
        elif isinstance(exc, InvalidOperation):
            errors["amount"] = "Amount must be greater than ₹0"
        else:
            errors["form"] = str(exc)
        return templates.TemplateResponse(
            "partials/expense_form.html",
            {
                "request": request,
                "categories": [c.value for c in CategoryEnum],
                "today": date.today().isoformat(),
                "errors": errors,
                "values": values,
            },
            status_code=422,
        )

    svc_create_expense(db, data)
    response = Response(status_code=204)
    response.headers["HX-Trigger"] = json.dumps(
        {
            "closeModal": True,
            "refreshDashboard": True,
            "refreshExpenseList": True,
            "showToast": "Expense added successfully!",
        }
    )
    return response


@app.put("/api/expenses/{expense_id}")
async def api_update_expense(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db),
    title: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    date_value: Optional[str] = Form(None, alias="date"),
    note: Optional[str] = Form(None),
):
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if amount is not None:
        payload["amount"] = Decimal(amount)
    if category is not None:
        payload["category"] = CategoryEnum(category)
    if date_value is not None:
        payload["date"] = date.fromisoformat(date_value)
    if note is not None:
        payload["note"] = note or None

    try:
        data = ExpenseUpdate(**payload)
    except (ValidationError, ValueError, InvalidOperation) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = svc_update_expense(db, expense_id, data)
    if result is None:
        raise HTTPException(status_code=404)

    response = templates.TemplateResponse(
        "partials/expense_row.html",
        {"request": request, "expense": to_expense_out(result)},
    )
    response.headers["HX-Trigger"] = json.dumps(
        {
            "refreshDashboard": True,
            "refreshExpenseList": True,
            "showToast": "Expense updated!",
        }
    )
    return response


@app.delete("/api/expenses/{expense_id}")
def api_delete_expense(expense_id: int, db: Session = Depends(get_db)):
    result = svc_delete_expense(db, expense_id)
    if not result:
        raise HTTPException(status_code=404)
    response = Response(status_code=200, content="")
    response.headers["HX-Trigger"] = json.dumps(
        {
            "refreshDashboard": True,
            "refreshExpenseList": True,
            "showToast": "Expense moved to recycle bin.",
        }
    )
    return response


@app.get("/recycle", response_class=HTMLResponse)
def recycle_page(request: Request, db: Session = Depends(get_db)):
    recycled = to_expense_out_list(svc_get_recycled_expenses(db))
    return templates.TemplateResponse(
        "recycle.html",
        {
            "request": request,
            "active_page": "recycle",
            "expenses": recycled,
            "retention_days": svc_recycle_retention_days(),
        },
    )


@app.post("/api/expenses/{expense_id}/restore")
def api_restore_expense(expense_id: int, db: Session = Depends(get_db)):
    if not svc_restore_expense(db, expense_id):
        raise HTTPException(status_code=404)
    response = Response(status_code=200, content="")
    response.headers["HX-Trigger"] = json.dumps(
        {
            "refreshDashboard": True,
            "refreshExpenseList": True,
            "showToast": "Expense restored successfully.",
        }
    )
    return response


@app.delete("/api/expenses/{expense_id}/permanent")
def api_permanent_delete(expense_id: int, db: Session = Depends(get_db)):
    if not svc_permanent_delete_expense(db, expense_id):
        raise HTTPException(status_code=404)
    response = Response(status_code=200, content="")
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": "Expense permanently deleted."}
    )
    return response


@app.get("/api/expenses/export")
def api_export_expenses(
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    title_search: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
):
    filters = build_filters(
        category=category,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        title_search=title_search,
        month=month,
        year=year,
    )
    csv_content, filename = svc_export_csv(db, filters)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )
