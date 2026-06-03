from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CategoryEnum(str, Enum):
    Food = "Food"
    Transport = "Transport"
    Shopping = "Shopping"
    Bills = "Bills"
    Entertainment = "Entertainment"
    Health = "Health"
    Education = "Education"
    Other = "Other"


def format_indian_number(value: Decimal | float | int) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    integer_part, _, fractional_part = f"{amount:.2f}".partition(".")
    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        grouped = ",".join(groups + [last_three])
    return f"{sign}{grouped}.{fractional_part}"


def format_inr(value: Decimal | float | int) -> str:
    return f"₹{format_indian_number(value)}"


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=Decimal("0"))
    category: CategoryEnum
    date: DateType = Field(default_factory=DateType.today)
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        quantized = value.quantize(Decimal("0.01"))
        if quantized.as_tuple().exponent < -2:
            raise ValueError("Amount supports up to 2 decimal places")
        if len(str(quantized.to_integral_value()).replace("-", "")) > 10:
            raise ValueError("Amount is too large")
        return quantized

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) > 500:
            raise ValueError("Note cannot exceed 500 characters")
        return stripped or None


class ExpenseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    category: Optional[CategoryEnum] = None
    date: Optional[DateType] = None
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title cannot be empty")
        return stripped

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return None
        quantized = value.quantize(Decimal("0.01"))
        if len(str(quantized.to_integral_value()).replace("-", "")) > 10:
            raise ValueError("Amount is too large")
        return quantized

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) > 500:
            raise ValueError("Note cannot exceed 500 characters")
        return stripped or None


class ExpenseOut(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: str
    date: DateType
    note: Optional[str]
    created_at: datetime
    updated_at: datetime
    date_display: str = ""
    amount_display: str = ""

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_display_fields(self) -> "ExpenseOut":
        self.date_display = self.date.strftime("%d %b %Y")
        self.amount_display = format_inr(self.amount)
        return self


class FilterParams(BaseModel):
    category: Optional[CategoryEnum] = None
    date_from: Optional[DateType] = None
    date_to: Optional[DateType] = None
    amount_min: Optional[Decimal] = Field(None, ge=0)
    amount_max: Optional[Decimal] = Field(None, ge=0)
    title_search: Optional[str] = None
    month: Optional[str] = None
    year: Optional[int] = None
