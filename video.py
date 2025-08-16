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

# Какая переменная будет в .env
ENV_KEY = "VIDEO_FILE_ID_1"  # поменяй на VIDEO_FILE_ID_2, если для второго видео

async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    if video:
        file_id = video.file_id
        logger.info(f"Получен file_id: {file_id}")

        # Сохраняем в .env
        set_key(".env", ENV_KEY, file_id)

        await update.message.reply_text(
            f"Сохранил {ENV_KEY} в .env:\n{file_id}"
        )
    else:
        await update.message.reply_text("Отправь именно видео.")

def main():
    token = os.getenv("BOT_TOKEN").strip().strip('"')
    if not token:
        logger.error("BOT_TOKEN не найден в .env")
        return

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.VIDEO, get_file_id))

    logger.info("Бот для получения file_id запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
