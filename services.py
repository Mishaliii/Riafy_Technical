import csv
import io
from datetime import date
from decimal import Decimal

from crud import (
    create_expense,
    delete_expense,
    get_dashboard_analytics,
    get_dashboard_stats,
    get_expense,
    get_expenses,
    get_expenses_for_export,
    get_monthly_summary,
    get_recycled_expenses,
    permanent_delete_expense,
    purge_expired_recycle,
    restore_expense,
    update_expense,
)
from insights import generate_insights
from models import Expense, RECYCLE_RETENTION_DAYS
from schemas import ExpenseCreate, ExpenseUpdate, FilterParams


def svc_create_expense(db, data: ExpenseCreate) -> Expense:
    return create_expense(db, data)


def svc_get_expense(db, expense_id: int) -> Expense | None:
    return get_expense(db, expense_id)


def svc_get_expenses(db, filters: FilterParams) -> list[Expense]:
    return get_expenses(db, filters)


def svc_update_expense(db, expense_id: int, data: ExpenseUpdate) -> Expense | None:
    return update_expense(db, expense_id, data)


def svc_delete_expense(db, expense_id: int) -> bool:
    return delete_expense(db, expense_id)


def svc_restore_expense(db, expense_id: int) -> bool:
    return restore_expense(db, expense_id)


def svc_permanent_delete_expense(db, expense_id: int) -> bool:
    return permanent_delete_expense(db, expense_id)


def svc_get_recycled_expenses(db) -> list[Expense]:
    purge_expired_recycle(db)
    return get_recycled_expenses(db)


def svc_get_dashboard_data(db, filters: FilterParams | None = None) -> dict:
    filters = filters or FilterParams()
    today = date.today()
    anchor_year, anchor_month = (
        int(filters.month[:4]),
        int(filters.month[5:7]),
    ) if filters.month else (today.year, today.month)
    stats = get_dashboard_stats(db, filters)
    summary = get_monthly_summary(db, anchor_year, anchor_month, filters)
    analytics = get_dashboard_analytics(db, filters)
    insights = generate_insights(db, anchor_year, anchor_month)
    return {
        "stats": stats,
        "summary": summary,
        "analytics": analytics,
        "insights": insights,
    }


def svc_get_monthly_summary(db, month_str: str, filters: FilterParams | None = None) -> dict:
    filters = filters or FilterParams()
    year, month = int(month_str[:4]), int(month_str[5:7])
    summary = get_monthly_summary(db, year, month, filters)
    insights = generate_insights(db, year, month)
    return {
        "summary": summary,
        "insights": insights,
        "month_label": date(year, month, 1).strftime("%B %Y"),
        "summary_month": month_str,
    }


def svc_export_csv(db, filters: FilterParams) -> tuple[str, str]:
    expenses = get_expenses_for_export(db, filters)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Title", "Category", "Amount (₹)", "Note"])
    for expense in expenses:
        writer.writerow(
            [
                expense.date.strftime("%d %b %Y"),
                expense.title,
                expense.category,
                f"{Decimal(str(expense.amount)):.2f}",
                expense.note or "",
            ]
        )
    filename = f"expenses_{date.today().strftime('%Y%m%d')}.csv"
    return output.getvalue(), filename


def svc_recycle_retention_days() -> int:
    return RECYCLE_RETENTION_DAYS
