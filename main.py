import os
import uuid
import logging
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram import WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, JobQueue
)

from yookassa import Configuration, Payment

# ==== наши модули (отдельные файлы) ====
from db import get_session
from services.subscriptions import (
    get_or_create_user,
    create_pending_payment,
)
# Если webhook делаешь в отдельном сервисе, там же будут:
#   mark_payment_succeeded, activate_or_extend_subscription

# ================== БАЗОВАЯ НАСТРОЙКА ==================
load_dotenv()

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ЮKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
RETURN_URL = os.getenv("RETURN_URL", "https://t.me/YourBotName")

# Видео файлы
VIDEO_PATH = "content/doc_2025-08-15_19-37-12.mp4"  # квадратное видео

# Настраиваем SDK ЮKassa
Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


# ================== ХЕНДЛЕРЫ БОТА ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    # Автоматически сохраняем или обновляем данные пользователя
    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_id=update.message.from_user.id,
            username=update.message.from_user.username,
            first_name=update.message.from_user.first_name
        )
        await session.commit()

    # Сначала отправляем видео кружочек
    try:
        with open(VIDEO_PATH, "rb") as f:
            await context.bot.send_video_note(
                chat_id=update.message.chat.id,
                video_note=f
            )
        # Добавляем небольшую задержку перед отправкой следующего сообщения
        import asyncio
        await asyncio.sleep(1)
    except Exception as e:
        logger.warning(f"Не удалось отправить видео кружочек: {e}")

    # Затем отправляем приветственное сообщение с кнопкой
    welcome_text = """Посмотри кружок и нажимай на кнопку снизу, чтобы узнать подробнее о MarketSkills: 👇🏻"""
    
    # Создаем кнопку "Смотреть видео"
    video_keyboard = [[InlineKeyboardButton("Смотреть видео 📹", callback_data='watch_video')]]
    video_reply_markup = InlineKeyboardMarkup(video_keyboard)

    await update.message.reply_text(welcome_text, reply_markup=video_reply_markup)

    # Таймер отключен - сообщение о комьюнити будет отправляться только при нажатии кнопки
    # chat_id = update.message.chat.id
    # if context.job_queue:
    #     context.job_queue.run_once(send_community_message, 10, chat_id=chat_id, name=f"auto_msg_{chat_id}")


async def send_community_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с описанием комьюнити"""
    job = context.job
    chat_id = job.chat_id
    
    # Отменяем таймер, если он еще не сработал (пользователь нажал кнопку)
    current_jobs = context.job_queue.get_jobs_by_name(f"auto_msg_{chat_id}")
    for job_to_cancel in current_jobs:
        if job_to_cancel != job:  # не отменяем текущий job
            job_to_cancel.schedule_removal()
    
    community_text = """<b>Открываю тебе доступ в закрытое комьюнити, но знай что...</b> 

Здесь, люди зарабатывают онлайн, позабыв о "работы ради работы" 

📦 Здесь заходят в маркетплейсы с 0
даже без товаров — и вот почему:

💥 Каждые 2 недели — разборы направлений, кейсы с реальными результатами и эфиры 

🫂 Чат с поддержкой: можешь задать вопрос по проекту, сделке, карточке или запуску — подскажут, как сделать лучше.

📚 Пошаговые уроки: как стать менеджером маркетплейсов и всё 
это без "курсов за 100к".

🤝 Ты не просто подписчик — ты часть команды. Здесь находят клиентов, запускают свои первые проекты 

А ещё — тут по-настоящему тёплая движуха. Вместе шутим про поставщиков, скидываем факапы, обсуждаем маркетплейсные тренды и помогаем друг другу не сгореть.

И всё это — за 1490₽ в месяц.
Когда, если не сейчас. Вступай!"""

    photo_path = "content/photo3.jpg"

    try:
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=community_text,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.warning(f"Не удалось отправить фото комьюнити: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=community_text,
            parse_mode=ParseMode.HTML
        )

    # Запуск таймера на 3 секунды для отправки кнопки подключения к комьюнити
    import asyncio
    await asyncio.sleep(3)
    
    # Отправляем текст и кнопку подключения к комьюнити
    connect_keyboard = [[InlineKeyboardButton("💥 Подключиться 💥", callback_data='connect_community')]]
    connect_reply_markup = InlineKeyboardMarkup(connect_keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="🔥🔥🔥 ПОДКЛЮЧИТЬСЯ К КОМЬЮНИТИ 🔥🔥🔥",
        reply_markup=connect_reply_markup
    )


async def send_community_message_direct(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Прямая отправка сообщения с описанием комьюнити (при нажатии кнопки)"""
    community_text = """<b>Открываю тебе доступ в закрытое комьюнити, но знай что...</b> 

Здесь, люди зарабатывают онлайн, позабыв о "работы ради работы" 

📦 Здесь заходят в маркетплейсы с 0
даже без товаров — и вот почему:

💥 Каждые 2 недели — разборы направлений, кейсы с реальными результатами и эфиры 

🫂 Чат с поддержкой: можешь задать вопрос по проекту, сделке, карточке или запуску — подскажут, как сделать лучше.

📚 Пошаговые уроки: как стать менеджером маркетплейсов и всё 
это без "курсов за 100к".

🤝 Ты не просто подписчик — ты часть команды. Здесь находят клиентов, запускают свои первые проекты 

А ещё — тут по-настоящему тёплая движуха. Вместе шутим про поставщиков, скидываем факапы, обсуждаем маркетплейсные тренды и помогаем друг другу не сгореть.

И всё это — за 1490₽ в месяц.
Когда, если не сейчас. Вступай!"""

    photo_path = "content/photo3.jpg"
    
    # Создаем кнопку подключения к комьюнити
    connect_keyboard = [[InlineKeyboardButton("💥 Подключиться 💥", callback_data='connect_community')]]
    connect_reply_markup = InlineKeyboardMarkup(connect_keyboard)

    try:
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=community_text,
                parse_mode=ParseMode.HTML,
                reply_markup=connect_reply_markup
            )
    except Exception as e:
        logger.warning(f"Не удалось отправить фото комьюнити: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=community_text,
            parse_mode=ParseMode.HTML,
            reply_markup=connect_reply_markup
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Доступные команды:
/start - Запустить бота
/help - Показать эту справку
/series - Отправить серию сообщений
"""
    await update.message.reply_text(help_text)


async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    services_text = """Описание услуги: 

Мы создали целое сообщество, подписочный проект, который позволяет людям обучиться и работать в сфере маркетплейсов и товарного бизнеса 

За подписку в 1490₽
Человек получает:

- Уроки по тому, как стать менеджером маркетплейсов
- Как работать с Китаем
- Как делать инфографику
- Как открыть свой бизнес на WB
- Помощь кураторов
- Эфиры и новости
- Полезные гайды
- Поддержку от единомышленников"""
    await update.message.reply_text(services_text)


async def send_message_series(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    messages = [
        "Сообщение 1 из серии",
        "Сообщение 2 из серии",
        "Сообщение 3 из серии",
        "Это последнее сообщение серии!"
    ]
    for i, message in enumerate(messages, 1):
        await update.message.reply_text(f"{i}. {message}")


# --------- ЮKassa: создание платежа ---------
def yk_create_payment_and_get_url(chat_id: int, payment_db_id: int, tariff_code: str, amount_rub: str, description: str):
    """
    Создаёт платёж в ЮKassa и возвращает (provider_payment_id, confirmation_url).
    amount_rub: строка с двумя знаками, например '1490.00'
    """
    idempotence_key = str(uuid.uuid4())
    metadata = {
        "chat_id": chat_id,
        "tariff": tariff_code,
        "payment_db_id": payment_db_id
    }
    payment = Payment.create({
        "amount": {"value": amount_rub, "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": RETURN_URL},
        "capture": True,
        "description": description,
        "metadata": metadata,
        # при необходимости оф. чек:
        "receipt": {
            "customer": {"email": "client@example.com"},
            "items": [{
                "description": description,
                "quantity": "1.00",
                "amount": {"value": amount_rub, "currency": "RUB"},
                "vat_code": 1,
                "payment_subject": "service",
                "payment_mode": "full_payment"
            }]
        }
    }, idempotence_key)
    return payment.id, payment.confirmation.confirmation_url


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == 'all_good_continue':
        # Обработчик для кнопки "Все супер, дальше🚀"
        # Отправляем сообщение о комьюнити
        await send_community_message_direct(query.message.chat.id, context)

    elif query.data == 'watch_video':
        # Обработчик для кнопки "Смотреть видео 📹"
        # Отправляем картинку с двумя кнопками
        button_keyboard = [
            [InlineKeyboardButton("Смотреть инструкцию 👀", web_app=WebAppInfo(url="https://rutube.ru/video/private/749e29cb5ef61090468cf42120ad016b/?p=Q8BIQDKmwYGd2m9-lm9yKQ"))],
            [InlineKeyboardButton("Все супер, дальше🚀", callback_data='all_good_continue')]
        ]
        button_reply_markup = InlineKeyboardMarkup(button_keyboard)

        button_photo_path = "content/3810.JPG"

        try:
            with open(button_photo_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    reply_markup=button_reply_markup
                )
        except Exception as e:
            logger.warning(f"Не удалось отправить фото с кнопками: {e}")
            await query.message.reply_text("Выберите действие:", reply_markup=button_reply_markup)

    elif query.data == 'connect_community':
        # Обработчик для кнопки "💥Подключиться к комьюнити"
        tariff_text = """Выбирай подходящий тариф! 👌🏻

Помесячный - 1490₽/мес. 
Стабильный - 3990₽/ 3 мес. 

По всем вопросам: оплаты или просто так, пишите сюда :)
@spoddershka"""
        
        photo_path = "content/photo2.jpg"
        
        # Создаем кнопку "Выбрать тариф"
        choose_tariff_keyboard = [[InlineKeyboardButton("🤝 Выбрать тариф 🤝", callback_data='choose_tariff_step')]]
        choose_tariff_reply_markup = InlineKeyboardMarkup(choose_tariff_keyboard)

        try:
            with open(photo_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=tariff_text,
                    reply_markup=choose_tariff_reply_markup
                )
        except Exception as e:
            logger.warning(f"Не удалось отправить фото с тарифами: {e}")
            await query.message.reply_text(tariff_text, reply_markup=choose_tariff_reply_markup)

    elif query.data == 'choose_tariff_step':
        # Обработчик для кнопки "🤝Выбрать тариф"
        oferta_url = "https://docs.yandex.ru/docs/view?url=ya-disk-public%3A%2F%2FZkx7HkIuQDpkVUiXOfvHBOO%2FQPNC9%2Fxb%2BiOzOS22ub%2FpW7TeWe4Yk3b3NEtMKypTq%2FJ6bpmRyOJonT3VoXnDag%3D%3D"
        
        oferta_text = f"""<b>Ты уже в шаге от нас!</b> 🥹
Перед тем как тебя перенаправит на оплату, нажимая на кнопку: <b>"Далее"</b> ты соглашаешься с <a href="{oferta_url}">Публичной офферты</a>"""

        dalee_keyboard = [[InlineKeyboardButton("Далее", callback_data='proceed_to_payment')]]
        dalee_reply_markup = InlineKeyboardMarkup(dalee_keyboard)

        await query.message.reply_text(
            text=oferta_text,
            parse_mode=ParseMode.HTML,
            reply_markup=dalee_reply_markup,
            disable_web_page_preview=True
        )

    elif query.data == 'proceed_to_payment':
        # Обработчик для кнопки "Далее"
        payment_keyboard = [
            [InlineKeyboardButton("Оплата картой РФ 🇷🇺", callback_data='payment_rf_card')],
            [InlineKeyboardButton("Оплата не РФ 🌍", callback_data='payment_foreign_card')]
        ]
        payment_reply_markup = InlineKeyboardMarkup(payment_keyboard)

        await query.message.reply_text(
            text="<b>Выберите способ оплаты</b> 💳:",
            parse_mode=ParseMode.HTML,
            reply_markup=payment_reply_markup
        )

    elif query.data == 'payment_foreign_card':
        # Обработчик для кнопки "Оплата картой иностранного банка"
        foreign_payment_keyboard = [[InlineKeyboardButton("💳 Перейти к оплате", url="https://t.me/tribute/app?startapp=ep_8xY0SyWiII0m5WAIvnXUKtqnazJqBXJjWYaks9qLwjy6iK7m80")]]
        foreign_payment_reply_markup = InlineKeyboardMarkup(foreign_payment_keyboard)

        await query.message.reply_text(
            text="Для оплаты картой иностранного банка нажмите кнопку ниже:",
            reply_markup=foreign_payment_reply_markup
        )

    elif query.data == 'payment_rf_card':
        # Обработчик для кнопки "Оплата картой РФ" - показываем выбор тарифов
        tariff_keyboard = [
            [InlineKeyboardButton("Тариф Помесячный — 1490₽/мес.", callback_data='tariff_monthly')],
            [InlineKeyboardButton("Тариф Стабильный — 3990₽ / 3 мес.", callback_data='tariff_stable')],
        ]
        await query.message.reply_text(
            "Выберите тариф 👇",
            reply_markup=InlineKeyboardMarkup(tariff_keyboard),
        )

    elif query.data == 'learn_more':
        oferta_url = (
            "https://docs.yandex.ru/docs/view?url=ya-disk-public%3A%2F%2FZkx7HkIuQDpkVUiXOfvHBOO%2FQPNC9%2Fxb%2BiOzOS22ub%2FpW7TeWe4Yk3b3NEtMKypTq%2FJ6bpmRyOJonT3VoXnDag%3D%3D"
            "&name=%D0%9E%D1%84%D1%84%D0%B5%D1%80%D1%82%D0%B0%20MarketSkills%20(2).docx&nosw=1"
        )

        keyboard = [
            [InlineKeyboardButton("Посмотреть оферту 📄", url=oferta_url)],
            [InlineKeyboardButton("ДАЛЕЕ", callback_data='next_step')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        oferta_text = (
            'Нажимая "Далее" вы соглашаетесь с условиями публичной '
            f'<a href="{oferta_url}">ОФФЕРТЫ</a> 📄'
            '\nинн: 051701385730 ИП Газиев Шамиль Газиевич'
        )

        await query.message.reply_text(
            text=oferta_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    elif query.data == 'next_step':
        keyboard = [[InlineKeyboardButton("Выбрать тариф 🚀", callback_data='choose_tariff')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        tariff_text = """Выбирай подходящий тариф! 👌🏻

Помесячный - 1490₽/мес. 
Стабильный - 3990₽/ 3 мес. 

По всем вопросам: оплаты или просто так, пишите сюда :)
@spoddershka"""
        photo_path = "content/photo2.jpg"

        try:
            with open(photo_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=tariff_text,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logging.warning(f"Не удалось отправить фото: {e}")
            await query.message.reply_text(tariff_text, reply_markup=reply_markup)

    # ---------- ДОБАВЛЕННЫЕ ОБРАБОТЧИКИ КНОПОК ТАРИФОВ ----------
    elif query.data == 'choose_tariff':
        tariff_keyboard = [
            [InlineKeyboardButton("Тариф Помесячный — 1490₽/мес.", callback_data='tariff_monthly')],
            [InlineKeyboardButton("Тариф Стабильный — 3990₽ / 3 мес.", callback_data='tariff_stable')],
            [InlineKeyboardButton("↩️ Назад", callback_data='next_step')],
        ]
        await query.message.reply_text(
            "Выберите тариф 👇",
            reply_markup=InlineKeyboardMarkup(tariff_keyboard),
        )

    elif query.data in ('tariff_monthly', 'tariff_stable'):
        tariff_code = 'monthly' if query.data == 'tariff_monthly' else 'stable'

        # 1) фиксируем намерение оплаты в БД (pending)
        async with get_session() as session:
            user = await get_or_create_user(
                session,
                tg_id=query.from_user.id,
                username=query.from_user.username,
                first_name=query.from_user.first_name
            )
            payment = await create_pending_payment(session, user.id, tariff_code=tariff_code)
            await session.commit()  # чтобы получить payment.id

        # 2) создаём платёж в ЮKassa и сохраняем provider_payment_id
        try:
            amount_str = f"{float(payment.amount_rub):.2f}"
            description = (
                "Подписка MARKETSKILLS — Помесячный (1 мес.)"
                if tariff_code == "monthly"
                else "Подписка MARKETSKILLS — Стабильный (3 мес.)"
            )
            provider_payment_id, url = yk_create_payment_and_get_url(
                chat_id=query.from_user.id,
                payment_db_id=payment.id,
                tariff_code=tariff_code,
                amount_rub=amount_str,
                description=description,
            )
            # сохраняем provider_payment_id
            async with get_session() as session:
                # лёгкое обновление — заново подгружать объект не обязательно,
                # но для простоты можно так:
                from sqlalchemy import select
                from models import Payment as PaymentModel
                p = await session.get(PaymentModel, payment.id)
                if p:
                    p.provider_payment_id = provider_payment_id
                    await session.commit()

            title = "*Тариф Помесячный* — 1490₽/мес." if tariff_code == "monthly" \
                else "*Тариф Стабильный* — 3990₽ / 3 мес."
            await query.message.reply_text(
                f"✅ Вы выбрали {title}\n"
                f"Заявка на оплату №{payment.id} создана.\n"
                "Нажмите кнопку ниже, чтобы перейти к оплате:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить в ЮKassa", url=url)]])
            )
        except Exception:
            logger.exception("Ошибка создания платежа в ЮKassa")
            await query.message.reply_text("❌ Не удалось создать платёж. Попробуйте позже.")
    # ------------------------------------------------------------


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Вы написали: {update.message.text}")


def main() -> None:
    """Запуск бота (без вебхуков ЮKassa — они в отдельном сервисе)"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return

    # Создаем приложение с Job Queue
    job_queue = JobQueue()
    application = Application.builder().token(BOT_TOKEN).job_queue(job_queue).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("service", services_command))
    application.add_handler(CommandHandler("series", send_message_series))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
