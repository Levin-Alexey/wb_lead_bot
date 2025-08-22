# models.py
from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Text, Numeric, ForeignKey, Enum, JSON, TIMESTAMP
import enum
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

class Base(DeclarativeBase):
    pass

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"

class SubscriptionStatus(str, enum.Enum):
    active = "active"
    canceled = "canceled"
    expired = "expired"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    notification_24h_sent: Mapped[bool] = mapped_column(default=False)
    notification_48h_sent: Mapped[bool] = mapped_column(default=False)

    payments: Mapped[list["Payment"]] = relationship(back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")

class Tariff(Base):
    __tablename__ = "tariffs"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_months: Mapped[int]
    price_rub: Mapped[float] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tariff_code: Mapped[str] = mapped_column(ForeignKey("tariffs.code"))
    amount_rub: Mapped[float] = mapped_column(Numeric(12, 2))
    provider: Mapped[str] = mapped_column(String, default="yookassa")
    provider_payment_id: Mapped[str | None] = mapped_column(String, unique=False)
    status: Mapped[PaymentStatus] = mapped_column(
        PGEnum(PaymentStatus, name="payment_status", create_type=False),
        default=PaymentStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    # ВАЖНО: атрибут назван НЕ "metadata". Колонка в БД всё ещё называется "metadata".
    provider_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)

    user: Mapped["User"] = relationship(back_populates="payments")
    events: Mapped[list["PaymentEvent"]] = relationship(back_populates="payment")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tariff_code: Mapped[str] = mapped_column(ForeignKey("tariffs.code"))
    start_at: Mapped[datetime]
    end_at: Mapped[datetime]
    status: Mapped[SubscriptionStatus] = mapped_column(
        PGEnum(SubscriptionStatus, name="subscription_status", create_type=False),
        default=SubscriptionStatus.active,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    payments_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    payment: Mapped["Payment"] = relationship(back_populates="events")
