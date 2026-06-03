from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
SQLALCHEMY_DATABASE_URL = f"sqlite:///{(BASE_DIR / 'expenses.db').as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_sample_data(db: Session) -> None:
    from models import Expense

    existing = db.execute(select(Expense).limit(1)).scalar_one_or_none()
    if existing is not None:
        return

    today = date.today()
    month_current = today.replace(day=1)
    month_prev = (month_current - timedelta(days=1)).replace(day=1)
    month_prev2 = (month_prev - timedelta(days=1)).replace(day=1)

    def d(year: int, month: int, day: int) -> date:
        return date(year, month, day)

    samples = [
        ("Zomato lunch order", Decimal("349.00"), "Food", month_current, d(today.year, today.month, min(5, today.day)), "Office lunch order"),
        ("Swiggy dinner", Decimal("520.00"), "Food", month_current, d(today.year, today.month, min(8, today.day)), "Friday night order"),
        ("Grocery run - DMart", Decimal("2340.50"), "Food", month_current, d(today.year, today.month, min(12, today.day)), "Monthly staples"),
        ("Metro card recharge", Decimal("500.00"), "Transport", month_current, d(today.year, today.month, min(3, today.day)), None),
        ("Uber to airport", Decimal("899.00"), "Transport", month_current, d(today.year, today.month, min(15, today.day)), "Early morning flight"),
        ("Ola ride home", Decimal("245.00"), "Transport", month_current, d(today.year, today.month, min(18, today.day)), None),
        ("Amazon order - books", Decimal("1299.00"), "Shopping", month_current, d(today.year, today.month, min(10, today.day)), None),
        ("Flipkart electronics", Decimal("4999.00"), "Shopping", month_current, d(today.year, today.month, min(20, today.day)), "Wireless earbuds"),
        ("myntra clothes", Decimal("1899.00"), "Shopping", month_prev, d(month_prev.year, month_prev.month, 14), None),
        ("Electricity bill - BESCOM", Decimal("2150.00"), "Bills", month_prev, d(month_prev.year, month_prev.month, 5), "Two-month bill"),
        ("Airtel broadband", Decimal("999.00"), "Bills", month_prev, d(month_prev.year, month_prev.month, 8), None),
        ("Jio recharge", Decimal("299.00"), "Bills", month_prev, d(month_prev.year, month_prev.month, 22), None),
        ("Netflix subscription", Decimal("649.00"), "Entertainment", month_prev, d(month_prev.year, month_prev.month, 1), None),
        ("BookMyShow movie", Decimal("450.00"), "Entertainment", month_prev, d(month_prev.year, month_prev.month, 16), "Weekend show"),
        ("Spotify premium", Decimal("119.00"), "Entertainment", month_prev2, d(month_prev2.year, month_prev2.month, 12), None),
        ("Apollo pharmacy", Decimal("380.00"), "Health", month_prev2, d(month_prev2.year, month_prev2.month, 6), None),
        ("Doctor consultation", Decimal("800.00"), "Health", month_prev2, d(month_prev2.year, month_prev2.month, 18), "Follow-up visit"),
        ("Gym membership", Decimal("1500.00"), "Health", month_prev2, d(month_prev2.year, month_prev2.month, 1), "Quarterly plan"),
        ("Udemy Python course", Decimal("499.00"), "Education", month_prev2, d(month_prev2.year, month_prev2.month, 9), None),
        ("Coursera subscription", Decimal("3999.00"), "Education", month_prev2, d(month_prev2.year, month_prev2.month, 25), "Annual plan"),
        ("Coffee at Starbucks", Decimal("320.00"), "Other", month_current, d(today.year, today.month, min(2, today.day)), None),
        ("Lunch at office canteen", Decimal("120.00"), "Food", month_prev, d(month_prev.year, month_prev.month, 11), None),
        ("Petrol - HP pump", Decimal("2500.00"), "Transport", month_prev, d(month_prev.year, month_prev.month, 19), "Full tank"),
        ("Rapido bike ride", Decimal("85.00"), "Other", month_prev2, d(month_prev2.year, month_prev2.month, 28), None),
        ("Reliance Fresh groceries", Decimal("756.00"), "Food", month_prev2, d(month_prev2.year, month_prev2.month, 15), "Vegetables and fruits"),
    ]

    now = datetime.utcnow()
    for title, amount, category, _month_anchor, expense_date, note in samples:
        expense = Expense(
            title=title,
            amount=amount,
            category=category,
            date=expense_date,
            note=note,
            created_at=now,
            updated_at=now,
        )
        db.add(expense)
    db.commit()


def migrate_db() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "expenses" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("expenses")}
    if "deleted_at" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE expenses ADD COLUMN deleted_at DATETIME"))


def init_db() -> None:
    from crud import purge_expired_recycle

    Base.metadata.create_all(bind=engine)
    migrate_db()
    db = SessionLocal()
    try:
        seed_sample_data(db)
        purge_expired_recycle(db)
    finally:
        db.close()
