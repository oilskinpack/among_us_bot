import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes,CallbackQueryHandler
from configs.env_config import Config
import sys
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,Update,KeyboardButton, ReplyKeyboardMarkup
from telegram.error import BadRequest
import asyncio


LOG_SEPARATOR = "\t|\t"
print('Модель загружена')


# Отключаем логирование HTTP-запросов
logging.getLogger("httpx").setLevel(logging.WARNING)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='datetime : %(asctime)s\t|\t%(message)s',
    handlers=[
        #logging.FileHandler('bot_interactions.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # Дублирование в консоль (опционально)
    ]
    )

logger = logging.getLogger(__name__)

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""

    user_id = update.effective_user.id

    welcome_text = ("Приветственный текст🧐")
    await update.message.reply_text(welcome_text)


def log_activity(update: Update, message_type: str, text: str,sender: str,specific_message_id: int = None):
    """
    Формирует и записывает стандартизированный лог активности пользователя.

    :param update: Объект Update от python-telegram-bot.
    :param message_type: Строка, описывающая тип события (e.g., "question", "feedback_like").
    :param text: Основной текст, связанный с событием (вопрос, ответ, callback_data).
    """
    user = update.effective_user
    chat = update.effective_chat
    
    # Безопасно получаем message_id, так как в callback_query он находится в другом месте
    message_id = "N/A"
    if specific_message_id is not None:
        message_id = specific_message_id
    elif update.effective_message:
        message_id = update.effective_message.message_id
    
    msg_sender = "N/A"
    if sender == 'user':
        msg_sender = sender
    elif sender == 'bot':
        msg_sender = sender

    # Экранируем спецсимволы в тексте
    # sanitized_text = text.replace('\n', '\\n').replace('\t', '\\t')

    # Собираем части лога в список
    log_parts = [
        f"chat_id : {chat.id if chat else 'N/A'}",
        f"user_id : {user.id if user else 'N/A'}",
        f"message_id : {message_id}",
        f"user_name : {user.first_name if user else 'N/A'}",
        f"user_surname : {user.last_name or ''}", # or '' чтобы не выводить None
        f"sender : {msg_sender}",
        f"message_type : {message_type}",
        f"text : {text}"
    ]

    # Соединяем части с помощью разделителя и отправляем в лог
    log_message = LOG_SEPARATOR.join(log_parts)
    logger.info(log_message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
        async def keep_typing_task():
            """Выводит сообщение печатает... в статусе бота
            """
            while True:
                await update.message.chat.send_action(action="typing")
                await asyncio.sleep(5)

        try:
            #Запускаем typing...
            typing_task = asyncio.create_task(keep_typing_task())
            text = "Сообщение"
            # Отправляем ответ пользователю
            await update.message.reply_text(text,parse_mode="Markdown"
                                            # ,reply_markup=reply_markup
                                            )
            return
            
        except Exception as e:
            # logging.error(f"Error processing message: {e}")
            fail_answer = "Произошла какая то ошибка🧐"
            # log_activity(update=update,message_type='answer',sender='bot',text=fail_answer)
            # log_activity(update=update,message_type='exception',sender='bot',text=e)
            await update.message.reply_text(fail_answer,parse_mode="Markdown")
            return
        #Для закрытия задачки по тайпингу
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                #Ожидаемое помещение
                pass


# Главная функция
def main():
    
    # Создаем приложение бота
    application = Application.builder().token(Config.TG_TOKEN).build()
    #application = Application.builder().token(Config.TG_TOKEN_STAGE).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()