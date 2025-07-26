import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start"""
    keyboard = [[InlineKeyboardButton("Узнать подробнее", callback_data='learn_more')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """ДОБРО ПОЖАЛОВАТЬ 
В MARKETSKILLS 🥳

Ты уже в шаге от вступление в наше сообщество. Жми ниже 🚀"""
    
    photo_path = "content/photo1.jpg"
    
    with open(photo_path, 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=welcome_text,
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет помощь при команде /help"""
    help_text = """
Доступные команды:
/start - Запустить бота
/help - Показать эту справку
/series - Отправить серию сообщений
"""
    await update.message.reply_text(help_text)

async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет описание услуг при команде /services"""
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
    """Отправляет серию сообщений"""
    messages = [
        "Сообщение 1 из серии",
        "Сообщение 2 из серии", 
        "Сообщение 3 из серии",
        "Это последнее сообщение серии!"
    ]
    
    for i, message in enumerate(messages, 1):
        await update.message.reply_text(f"{i}. {message}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'learn_more':
        keyboard = [[InlineKeyboardButton("ДАЛЕЕ", callback_data='next_step')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        oferta_text = """Нажимая "Далее" вы соглашаетесь с условиями публичной [ОФФЕРТЫ](https://telegra.ph/Dogovor-vozmezdnogo-okazaniya-uslug--Oferta-07-26) 📄"""
        
        await query.message.reply_text(
            text=oferta_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
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
        
        with open(photo_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=tariff_text,
                reply_markup=reply_markup
            )

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Эхо функция для обработки текстовых сообщений"""
    await update.message.reply_text(f"Вы написали: {update.message.text}")

def main() -> None:
    """Запуск бота"""
    if not TOKEN:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("service", services_command))
    application.add_handler(CommandHandler("series", send_message_series))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()