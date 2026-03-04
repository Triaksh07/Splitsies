from sqlalchemy import Integer, String, DateTime, Date, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from decimal import Decimal


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    split_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    group = relationship("Group", back_populates="expenses")
    paid_by_participant = relationship("Participant", back_populates="paid_expenses")
    splits = relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")
comments = relationship("ExpenseComment", back_populates="expense",
                        cascade="all, delete-orphan", order_by="app.models.comment.ExpenseComment.created_at")

class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(Integer, ForeignKey("expenses.id"), nullable=False)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    amount_owed_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    expense = relationship("Expense", back_populates="splits")
    participant = relationship("Participant", back_populates="expense_splits")
    guest_collection = relationship("GuestCollection", back_populates="expense_split", uselist=False)


class GuestCollection(Base):
    __tablename__ = "guest_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_split_id: Mapped[int] = mapped_column(Integer, ForeignKey("expense_splits.id"), nullable=False)
    collected_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    collected_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    expense_split = relationship("ExpenseSplit", back_populates="guest_collection")
