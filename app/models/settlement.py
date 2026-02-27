from sqlalchemy import Integer, String, DateTime, Date, Numeric, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from decimal import Decimal


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    from_participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    to_participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    amount_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    amount_original: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    group = relationship("Group", back_populates="settlements")
    from_participant = relationship("Participant", foreign_keys=[from_participant_id], back_populates="settlements_from")
    to_participant = relationship("Participant", foreign_keys=[to_participant_id], back_populates="settlements_to")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(16, 6), nullable=False)
    fetched_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("from_currency", "to_currency", name="uq_currency_pair"),)
