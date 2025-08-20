# webhook.py

from dotenv import load_dotenv

load_dotenv()  # Загружаем .env файл

import os
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import aiofiles

from db import get_session
from subscriptions import (
    mark_payment_succeeded,
    activate_or_extend_subscription,
)
from models import Payment as PaymentDB, PaymentStatus  # только для типов/отладочных выборок
from services.notification_service import (
    get_24h_notification_text,
    get_24h_notification_keyboard,
    get_48h_notification_text,
    get_48h_notification_keyboard
)

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

    async with get_session() as session:
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
            text = """Оплата прошла успешно!

Добро пожаловать в МаркетСкиллс. Закреп этого бота чтобы не потерять, здесь будут лучшие предложения для участие в клубе. Подключайся👇🏻"""

            keyboard = [[InlineKeyboardButton("Подключиться", url="https://t.me/c/2436392617/78")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Используем абсолютный путь к файлу
            photo_path = Path(__file__).parent / "content" / "photo4.jpg"

            try:
                # Проверяем существование файла
                if not photo_path.exists():
                    log.error(f"Файл не найден: {photo_path}")
                    raise FileNotFoundError(f"Photo file not found: {photo_path}")
                
                # Асинхронное чтение файла
                async with aiofiles.open(photo_path, 'rb') as photo:
                    photo_data = await photo.read()
                    await bot.send_photo(
                        chat_id=int(chat_id),
                        photo=photo_data,
                        caption=text,
                        reply_markup=reply_markup
                    )
                log.info(f"Успешно отправлено фото пользователю {chat_id}")
            except FileNotFoundError as e:
                log.error(f"Файл не найден: {e}")
                await bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    reply_markup=reply_markup
                )
                log.info(f"Отправлено текстовое сообщение пользователю {chat_id} (без фото)")
            except Exception as e:
                log.error(f"Ошибка при отправке фото пользователю {chat_id}: {e}")
                await bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    reply_markup=reply_markup
                )
                log.info(f"Отправлено текстовое сообщение пользователю {chat_id} (fallback)")
        except Exception as e:
            log.exception(f"Критическая ошибка при отправке уведомления пользователю {chat_id}: {e}")

    return {"status": "ok"}

@app.post("/n8n/notification")
async def n8n_notification_webhook(request: Request):
    """
    Endpoint для получения уведомлений от N8N о необходимости отправки 24ч/48ч сообщений
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Получаем данные из N8N
    delay_hours = data.get("delay_hours")
    payment_id = data.get("payment_id")
    chat_id = data.get("chat_id")
    user_id = data.get("user_id")

    log.info(
        f"[N8N] notification delay_hours={delay_hours} payment_id={payment_id} "
        f"chat_id={chat_id} user_id={user_id}"
    )

    if not all([delay_hours, payment_id, chat_id]):
        log.error("Missing required fields in N8N notification")
        raise HTTPException(status_code=400, detail="Missing required fields")

    # Проверяем статус платежа перед отправкой уведомления
    async with get_session() as session:
        try:
            payment = await session.get(PaymentDB, payment_id)
            
            # Если платеж не найден или уже оплачен, не отправляем уведомление
            if not payment or payment.status == PaymentStatus.succeeded:
                log.info(f"Payment {payment_id} not found or already paid, skipping notification")
                return {"status": "skipped", "reason": "payment_not_found_or_paid"}
                
        except Exception as e:
            log.error(f"Error checking payment status: {e}")
            raise HTTPException(status_code=500, detail="database_error")

    # Отправляем соответствующее уведомление
    try:
        if delay_hours == 24:
            # 24-часовое уведомление
            text = get_24h_notification_text()
            keyboard = get_24h_notification_keyboard()
            
            await bot.send_message(
                chat_id=int(chat_id),
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            
            log.info(f"Sent 24h notification to user {chat_id}")
            
        elif delay_hours == 48:
            # 48-часовое уведомление
            text = get_48h_notification_text()
            keyboard = get_48h_notification_keyboard()
            
            await bot.send_message(
                chat_id=int(chat_id),
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            
            log.info(f"Sent 48h notification to user {chat_id}")
            
        else:
            log.warning(f"Unknown delay_hours value: {delay_hours}")
            return {"status": "error", "reason": "unknown_delay_hours"}
            
    except Exception as e:
        log.exception(f"Failed to send notification to user {chat_id}: {e}")
        raise HTTPException(status_code=500, detail="telegram_send_error")

    return {"status": "ok", "notification_type": f"{delay_hours}h"}
