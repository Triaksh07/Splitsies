from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    group = relationship("Group", back_populates="participants")
    linked_user = relationship("User", back_populates="participants")
    paid_expenses = relationship("Expense", back_populates="paid_by_participant")
    expense_splits = relationship("ExpenseSplit", back_populates="participant")
    settlements_from = relationship("Settlement", foreign_keys="Settlement.from_participant_id", back_populates="from_participant")
    settlements_to = relationship("Settlement", foreign_keys="Settlement.to_participant_id", back_populates="to_participant")
