# services/subscriptions.py
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Tariff, Payment, PaymentStatus, Subscription, SubscriptionStatus

async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, first_name: str | None) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == tg_id))
    if user:
        return user
    user = User(telegram_id=tg_id, username=username, first_name=first_name)
    session.add(user)
    await session.flush()
    return user

async def create_pending_payment(session: AsyncSession, user_id: int, tariff_code: str) -> Payment:
    tariff = await session.get(Tariff, tariff_code)
    if not tariff:
        raise ValueError("Unknown tariff")
    p = Payment(
        user_id=user_id,
        tariff_code=tariff.code,
        amount_rub=tariff.price_rub,
        status=PaymentStatus.pending,
        provider_metadata={},  # <-- было metadata={}
    )
    session.add(p)
    await session.flush()  # получим p.id
    return p

async def mark_payment_succeeded(session: AsyncSession, payment_db_id: int, provider_payment_id: str, payload: dict) -> Payment:
    p = await session.get(Payment, payment_db_id)
    if not p:
        raise ValueError("Payment not found")
    p.status = PaymentStatus.succeeded
    p.paid_at = datetime.now(timezone.utc)
    p.provider_payment_id = provider_payment_id
    p.provider_metadata = payload  # <-- было p.metadata = payload
    await session.flush()
    return p

async def activate_or_extend_subscription(session: AsyncSession, user_id: int, tariff_code: str) -> Subscription:
    tariff = await session.get(Tariff, tariff_code)
    if not tariff:
        raise ValueError("Unknown tariff")

    # Определяем период подписки согласно тарифу
    if tariff_code == "monthly":
        months_to_add = 1
    elif tariff_code == "stable":
        months_to_add = 3
    else:
        # fallback на значение из БД если тариф неизвестный
        months_to_add = tariff.duration_months

    now = datetime.now(timezone.utc)
    # ищем активную подписку
    sub = await session.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == SubscriptionStatus.active)
        .order_by(Subscription.end_at.desc())
        .limit(1)
    )

    if sub and sub.end_at > now:
        # продлеваем
        new_end = sub.end_at + relativedelta(months=months_to_add)
        sub.end_at = new_end
        await session.flush()
        return sub

    # создаём новую
    new_sub = Subscription(
        user_id=user_id,
        tariff_code=tariff.code,
        start_at=now,
        end_at=now + relativedelta(months=months_to_add),
        status=SubscriptionStatus.active
    )
    session.add(new_sub)
    await session.flush()
    return new_sub
