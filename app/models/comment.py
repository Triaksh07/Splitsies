from sqlalchemy import Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ExpenseComment(Base):
    __tablename__ = "expense_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(Integer, ForeignKey("expenses.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    expense = relationship("Expense", back_populates="comments")
    user = relationship("User")
