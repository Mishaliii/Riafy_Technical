import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, extract, select
from sqlalchemy.orm import Session

from models import Expense


def generate_insights(db: Session, year: int, month: int) -> list[str]:
    insights: list[str] = []

    def month_filter():
        return and_(
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )

    def prev_month_filter():
        if month == 1:
            py, pm = year - 1, 12
        else:
            py, pm = year, month - 1
        return and_(
            extract("year", Expense.date) == py,
            extract("month", Expense.date) == pm,
        )

    month_expenses = list(
        db.execute(select(Expense).where(month_filter(), Expense.deleted_at.is_(None))).scalars().all()
    )

    total = sum((Decimal(str(e.amount)) for e in month_expenses), Decimal("0"))
    count = len(month_expenses)

    if count == 0:
        insights.append("No expenses recorded for this month yet.")
        insights.append("Start adding expenses to see your spending insights.")
        return insights

    cat_totals: dict[str, Decimal] = {}
    for expense in month_expenses:
        amount = Decimal(str(expense.amount))
        cat_totals[expense.category] = cat_totals.get(expense.category, Decimal("0")) + amount

    if cat_totals:
        top_cat = max(cat_totals, key=cat_totals.get)
        pct = round((cat_totals[top_cat] / total) * 100) if total > 0 else 0
        insights.append(
            f"{top_cat} accounts for {pct}% of your spending this month "
            f"(₹{cat_totals[top_cat]:,.0f})."
        )

    if month_expenses:
        highest = max(month_expenses, key=lambda e: e.amount)
        insights.append(
            f"Your highest expense was ₹{Decimal(str(highest.amount)):,.0f} "
            f"for '{highest.title}'."
        )

    prev_expenses = list(
        db.execute(select(Expense).where(prev_month_filter(), Expense.deleted_at.is_(None)))
        .scalars()
        .all()
    )
    prev_total = sum((Decimal(str(e.amount)) for e in prev_expenses), Decimal("0"))
    if prev_total > 0:
        change_pct = ((total - prev_total) / prev_total) * 100
        direction = "more" if change_pct > 0 else "less"
        insights.append(
            f"You spent {abs(round(change_pct))}% {direction} than last month "
            f"(₹{prev_total:,.0f} → ₹{total:,.0f})."
        )

    days_in_month = calendar.monthrange(year, month)[1]
    daily_avg = total / days_in_month
    insights.append(f"You're averaging ₹{daily_avg:,.0f} per day this month.")

    day_totals: dict[int, Decimal] = {}
    for expense in month_expenses:
        day = expense.date.day
        amount = Decimal(str(expense.amount))
        day_totals[day] = day_totals.get(day, Decimal("0")) + amount

    if day_totals:
        best_day = max(day_totals, key=day_totals.get)
        insights.append(
            f"Your highest spending day was the {best_day}th "
            f"with ₹{day_totals[best_day]:,.0f} spent."
        )

    if count > 0:
        per_week = round(count / 4.3, 1)
        insights.append(
            f"You've recorded {count} transactions this month "
            f"— about {per_week} per week."
        )

    if month_expenses:
        last_date = max(e.date for e in month_expenses)
        days_ago = (date.today() - last_date).days
        if days_ago >= 3:
            insights.append(f"You haven't logged an expense in {days_ago} days.")

    notable = {"Bills", "Health", "Food"}
    for cat in notable:
        if cat not in cat_totals or cat_totals[cat] == 0:
            insights.append(f"No {cat} expenses recorded this month.")
            break

    return insights[:8]
