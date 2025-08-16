import os
import logging
from dotenv import load_dotenv, set_key
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Загружаем .env
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ключ в .env (оставляем как просили)
ENV_KEY = "VIDEO_FILE_ID_1"

async def get_video_note_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    # Ищем именно кружок (video_note)
    if msg and msg.video_note:
        file_id = msg.video_note.file_id
        logger.info(f"Получен video_note file_id: {file_id}")

        # Сохраняем в .env
        set_key(".env", ENV_KEY, file_id)

        await msg.reply_text(f"Сохранил {ENV_KEY} (video_note) в .env:\n{file_id}")
        return

    # Если прислали обычное видео — подсказываем, что нужен кружок
    if msg and msg.video:
        await msg.reply_text("Это обычное видео. Пожалуйста, пришли **видео-кружок** (video note).")
        return

    await msg.reply_text("Пришли видео-кружок (video note).")

def main():
    token = os.getenv("BOT_TOKEN", "").strip().strip('"')
    if not token:
        logger.error("BOT_TOKEN не найден в .env")
        return

    app = Application.builder().token(token).build()

    # Ловим только кружки
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, get_video_note_id))
    # На всякий случай ловим любые медиасообщения и подсказываем
    app.add_handler(MessageHandler(filters.VIDEO, get_video_note_id))

    logger.info("Бот для получения video_note file_id запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()