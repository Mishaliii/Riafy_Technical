import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from models import RECYCLE_RETENTION_DAYS, Expense
from schemas import CategoryEnum, ExpenseCreate, ExpenseUpdate, FilterParams

ALL_CATEGORIES = [c.value for c in CategoryEnum]


def _active_only(stmt):
    return stmt.where(Expense.deleted_at.is_(None))


def _apply_filters(stmt, filters: FilterParams):
    date_from = filters.date_from
    date_to = filters.date_to
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    amount_min = filters.amount_min
    amount_max = filters.amount_max
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        amount_min, amount_max = amount_max, amount_min

    if filters.category is not None:
        stmt = stmt.where(Expense.category == filters.category.value)

    if date_from is not None:
        stmt = stmt.where(Expense.date >= date_from)

    if date_to is not None:
        stmt = stmt.where(Expense.date <= date_to)

    if amount_min is not None:
        stmt = stmt.where(Expense.amount >= amount_min)

    if amount_max is not None:
        stmt = stmt.where(Expense.amount <= amount_max)

    if filters.title_search:
        term = filters.title_search.strip().lower()
        if term:
            stmt = stmt.where(
                or_(
                    func.lower(Expense.title).like(f"%{term}%"),
                    func.lower(func.coalesce(Expense.note, "")).like(f"%{term}%"),
                )
            )

    if filters.month:
        year_part, month_part = filters.month.split("-")
        stmt = stmt.where(
            and_(
                extract("year", Expense.date) == int(year_part),
                extract("month", Expense.date) == int(month_part),
            )
        )

    if filters.year is not None:
        stmt = stmt.where(extract("year", Expense.date) == filters.year)

    return stmt


def create_expense(db: Session, data: ExpenseCreate) -> Expense:
    now = datetime.utcnow()
    expense = Expense(
        title=data.title,
        amount=data.amount,
        category=data.category.value,
        date=data.date,
        note=data.note,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def get_expense(db: Session, expense_id: int) -> Expense | None:
    stmt = _active_only(select(Expense)).where(Expense.id == expense_id)
    return db.execute(stmt).scalar_one_or_none()


def get_expense_including_deleted(db: Session, expense_id: int) -> Expense | None:
    return db.get(Expense, expense_id)


def get_expenses(db: Session, filters: FilterParams) -> list[Expense]:
    stmt = _active_only(select(Expense))
    stmt = _apply_filters(stmt, filters)
    stmt = stmt.order_by(Expense.date.desc(), Expense.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def update_expense(db: Session, expense_id: int, data: ExpenseUpdate) -> Expense | None:
    expense = get_expense(db, expense_id)
    if expense is None:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "category" in update_data and update_data["category"] is not None:
        update_data["category"] = update_data["category"].value

    for field, value in update_data.items():
        setattr(expense, field, value)

    expense.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, expense_id: int) -> bool:
    expense = get_expense(db, expense_id)
    if expense is None:
        return False
    expense.deleted_at = datetime.utcnow()
    expense.updated_at = datetime.utcnow()
    db.commit()
    return True


def restore_expense(db: Session, expense_id: int) -> bool:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is None:
        return False
    expense.deleted_at = None
    expense.updated_at = datetime.utcnow()
    db.commit()
    return True


def permanent_delete_expense(db: Session, expense_id: int) -> bool:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is None:
        return False
    db.delete(expense)
    db.commit()
    return True


def purge_expired_recycle(db: Session) -> int:
    cutoff = datetime.utcnow() - timedelta(days=RECYCLE_RETENTION_DAYS)
    expired = list(
        db.execute(select(Expense).where(Expense.deleted_at.isnot(None), Expense.deleted_at < cutoff))
        .scalars()
        .all()
    )
    for expense in expired:
        db.delete(expense)
    if expired:
        db.commit()
    return len(expired)


def get_recycled_expenses(db: Session) -> list[Expense]:
    cutoff = datetime.utcnow() - timedelta(days=RECYCLE_RETENTION_DAYS)
    stmt = (
        select(Expense)
        .where(Expense.deleted_at.isnot(None), Expense.deleted_at >= cutoff)
        .order_by(Expense.deleted_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def _anchor_month(filters: FilterParams) -> tuple[int, int]:
    if filters.month:
        year_part, month_part = filters.month.split("-")
        return int(year_part), int(month_part)
    if filters.date_to:
        return filters.date_to.year, filters.date_to.month
    if filters.date_from:
        return filters.date_from.year, filters.date_from.month
    today = date.today()
    return today.year, today.month


def get_dashboard_stats(db: Session, filters: FilterParams | None = None) -> dict:
    filters = filters or FilterParams()
    anchor_year, anchor_month = _anchor_month(filters)
    expenses = get_expenses(db, filters)
    amounts = [Decimal(str(e.amount)) for e in expenses]

    total_all_time = sum(amounts, Decimal("0"))
    count = len(expenses)
    average = total_all_time / count if count else Decimal("0")
    highest = max(amounts) if amounts else Decimal("0")

    month_expenses = [
        e
        for e in expenses
        if e.date.year == anchor_year and e.date.month == anchor_month
    ]
    month_amounts = [Decimal(str(e.amount)) for e in month_expenses]
    total_this_month = sum(month_amounts, Decimal("0"))

    cat_totals: dict[str, Decimal] = {}
    for expense in month_expenses or expenses:
        cat_totals[expense.category] = cat_totals.get(expense.category, Decimal("0")) + Decimal(
            str(expense.amount)
        )
    top_category = max(cat_totals, key=cat_totals.get) if cat_totals else "N/A"

    recent = sorted(expenses, key=lambda e: (e.date, e.created_at), reverse=True)[:5]
    month_name = date(anchor_year, anchor_month, 1).strftime("%B")

    return {
        "total_all_time": total_all_time,
        "total_this_month": total_this_month,
        "count": count,
        "average": average,
        "highest": highest,
        "top_category": top_category,
        "recent": recent,
        "month_name": month_name,
        "month_label": date(anchor_year, anchor_month, 1).strftime("%B %Y"),
    }


def get_monthly_summary(db: Session, year: int, month: int, filters: FilterParams | None = None) -> dict:
    filters = filters or FilterParams()
    month_filters = FilterParams(
        category=filters.category,
        amount_min=filters.amount_min,
        amount_max=filters.amount_max,
        title_search=filters.title_search,
        month=f"{year:04d}-{month:02d}",
    )
    month_expenses = get_expenses(db, month_filters)
    amounts = [Decimal(str(e.amount)) for e in month_expenses]
    total = sum(amounts, Decimal("0"))
    count = len(month_expenses)
    average = total / count if count else Decimal("0")
    highest = max(amounts) if amounts else Decimal("0")

    breakdown = {cat: Decimal("0.00") for cat in ALL_CATEGORIES}
    for expense in month_expenses:
        breakdown[expense.category] += Decimal(str(expense.amount))

    last_day = calendar.monthrange(year, month)[1]
    daily_totals = {day: Decimal("0") for day in range(1, last_day + 1)}
    for expense in month_expenses:
        daily_totals[expense.date.day] += Decimal(str(expense.amount))

    highest_day = 1
    highest_day_amount = Decimal("0")
    for day, amount in daily_totals.items():
        if amount > highest_day_amount:
            highest_day_amount = amount
            highest_day = day

    return {
        "total": total,
        "count": int(count),
        "average": average,
        "highest": highest,
        "breakdown": breakdown,
        "daily_totals": daily_totals,
        "highest_day": highest_day,
        "highest_day_amount": highest_day_amount,
    }


def get_dashboard_analytics(db: Session, filters: FilterParams | None = None) -> dict:
    filters = filters or FilterParams()
    anchor_year, anchor_month = _anchor_month(filters)
    anchor = date(anchor_year, anchor_month, 1)

    monthly_labels = []
    monthly_values = []
    for offset in range(5, -1, -1):
        month_index = anchor.month - offset
        year = anchor.year
        while month_index < 1:
            month_index += 12
            year -= 1
        while month_index > 12:
            month_index -= 12
            year += 1
        month_filters = FilterParams(
            category=filters.category,
            date_from=filters.date_from,
            date_to=filters.date_to,
            amount_min=filters.amount_min,
            amount_max=filters.amount_max,
            title_search=filters.title_search,
            month=f"{year:04d}-{month_index:02d}",
        )
        month_rows = get_expenses(db, month_filters)
        total = sum(float(e.amount) for e in month_rows)
        monthly_labels.append(date(year, month_index, 1).strftime("%b %Y"))
        monthly_values.append(total)

    current_total = Decimal(str(monthly_values[-1] if monthly_values else 0))
    previous_total = Decimal(str(monthly_values[-2] if len(monthly_values) > 1 else 0))
    if previous_total > 0:
        change_pct = float(((current_total - previous_total) / previous_total) * 100)
    else:
        change_pct = 0.0 if current_total == 0 else 100.0

    summary = get_monthly_summary(db, anchor_year, anchor_month, filters)

    expenses = get_expenses(db, filters)
    breakdown = {cat: 0.0 for cat in ALL_CATEGORIES}
    for expense in expenses:
        breakdown[expense.category] += float(expense.amount)

    return {
        "breakdown": breakdown,
        "daily_totals": {str(k): float(v) for k, v in summary["daily_totals"].items()},
        "monthly_labels": monthly_labels,
        "monthly_values": monthly_values,
        "current_month_total": float(current_total),
        "previous_month_total": float(previous_total),
        "change_pct": round(change_pct, 1),
        "change_direction": "up" if change_pct > 0 else "down" if change_pct < 0 else "flat",
        "month_label": date(anchor_year, anchor_month, 1).strftime("%B %Y"),
    }


def get_expenses_for_export(db: Session, filters: FilterParams) -> list[Expense]:
    return get_expenses(db, filters)
