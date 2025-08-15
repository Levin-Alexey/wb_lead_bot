# webhook.py
import os
import logging
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from telegram import Bot
from telegram.constants import ParseMode

from db import get_session
from subscriptions import (
    mark_payment_succeeded,
    activate_or_extend_subscription,
)
from models import Payment as PaymentDB  # только для типов/отладочных выборок

# ------------------ Config & logging ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env is required")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("yookassa-webhook")

bot = Bot(token=BOT_TOKEN)
app = FastAPI(title="YooKassa Webhook")

# ------------------ Helpers ------------------
def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    # показываем в UTC; при желании добавь tz/локаль
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ------------------ Routes ------------------
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    """
    Ожидает JSON от ЮKassa с событиями:
    - payment.succeeded (минимум)
    Документация ЮKassa: см. объект события и поле object.metadata
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = data.get("event")
    obj = data.get("object") or {}
    provider_payment_id = obj.get("id")

    # metadata, который мы передавали при создании платежа
    md = obj.get("metadata") or {}
    payment_db_id = md.get("payment_db_id")
    chat_id = md.get("chat_id")
    tariff = md.get("tariff")

    log.info(
        f"[YK] event={event} provider_payment_id={provider_payment_id} "
        f"payment_db_id={payment_db_id} chat_id={chat_id} tariff={tariff}"
    )

    # Обрабатываем только успешную оплату
    if event != "payment.succeeded":
        return {"status": "ignored"}

    if payment_db_id is None:
        # Без нашего внутреннего ID не знаем, какой платеж апдейтить
        log.error("Missing metadata.payment_db_id in webhook payload")
        raise HTTPException(status_code=400, detail="Missing payment_db_id")

    async for session in get_session():
        try:
            # 1) Обновляем запись платежа: succeeded + paid_at + provider_payment_id + сырой payload
            payment: PaymentDB = await mark_payment_succeeded(
                session=session,
                payment_db_id=int(payment_db_id),
                provider_payment_id=provider_payment_id or "",
                payload=obj,
            )

            # 2) Активируем/продлеваем подписку пользователю по тарифу из платежа
            sub = await activate_or_extend_subscription(
                session=session,
                user_id=payment.user_id,
                tariff_code=payment.tariff_code,
            )

            await session.commit()
            log.info(
                f"Payment {payment.id} marked as succeeded; "
                f"subscription end_at={fmt_dt(sub.end_at)} user_id={payment.user_id}"
            )
        except Exception as e:
            log.exception("Failed to handle payment.succeeded")
            await session.rollback()
            raise HTTPException(status_code=500, detail="processing_error") from e

    # 3) Уведомляем пользователя в Telegram (если chat_id передали в metadata)
    if chat_id:
        try:
            text = "🎉 Оплата прошла успешно! "
            if tariff == "monthly":
                text += "Активирован тариф *Помесячный* (1 мес.)."
            elif tariff == "stable":
                text += "Активирован тариф *Стабильный* (3 мес.)."
            else:
                text += "Подписка активирована."
            text += f"\nПодписка действует до: *{fmt_dt(sub.end_at)}*."

            await bot.send_message(
                chat_id=int(chat_id),
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            log.exception("Failed to send Telegram notification")

    return {"status": "ok"}
