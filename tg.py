# tg.py (финальная, исправленная версия)

import asyncio
import logging
import traceback
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, Update, ErrorEvent

from configs.env_config import Config
from src.handlers import admin_router, player_router

# Вспомогательная функция для HTML-экранирования
def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def errors_handler(event: ErrorEvent, bot: Bot):
    """
    Ловит все ошибки из хендлеров, логирует их и сообщает админу.
    """
    update = event.update
    exception = event.exception
    
    error_text = f"❗️ Произошла ошибка в боте!\n\n"
    error_text += f"Тип апдейта: {update.event_type}\n"
    
    tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    # --- ИЗМЕНЕНИЕ: Логика усечения длинного сообщения ---
    MAX_TRACEBACK_LEN = 4000 # Оставляем запас до лимита в 4096
    if len(tb_str) > MAX_TRACEBACK_LEN:
        tb_str = f"... (Traceback урезан) ...\n{tb_str[-MAX_TRACEBACK_LEN:]}"
        
    error_text += f"\nTraceback:\n<code>{escape_html(tb_str)}</code>"

    logging.error(f"Caught exception: {exception}\n{tb_str}")

    try:
        await bot.send_message(
            Config.ADMIN_USER_ID,
            error_text,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение об ошибке админу: {e}")

    if update.message:
        try:
            await update.message.answer("Произошла непредвиденная ошибка. Администратор уже уведомлен.")
        except Exception:
            pass
    
    return True

async def set_commands(bot: Bot):
    """
    Создает и устанавливает список команд, которые будут видны в меню.
    """
    # Команды, которые видят ВСЕ пользователи
    user_commands = [
        BotCommand(command="vote", description="📢 Начать голосование"),
        BotCommand(command="new_game", description="🚀 Создать новое лобби [АДМИН]"),
        BotCommand(command="start_game", description="▶️ Начать игру [АДМИН]"),
        BotCommand(command="stop_game", description="❌ Завершить игру [АДМИН]"),
        BotCommand(command="player_list", description="👤 Список игроков (в ЛС)"),
        BotCommand(command="add_task_score", description="⚙️ +1 балл импостерам"),
        BotCommand(command="remove_task_score", description="⚙️ -1 балл импостерам"),
        BotCommand(command="add_vote", description="⚙️ +1 попытка голосования"),
        BotCommand(command="remove_vote", description="⚙️ -1 попытка голосования"),
        BotCommand(command="resend_task", description="⚙️ Переотправить задание"),
    ]
    
    # Полный список команд, который видит ТОЛЬКО администратор
    admin_commands = [
        # --- Игровые команды ---
        
        # --- Команды управления заданиями ---
        BotCommand(command="tasks", description="📝 Показать задания в игре"),
        BotCommand(command="backlog", description="📋 Показать черновики"),
        BotCommand(command="add_task", description="➕ Добавить задание в черновик"),
        BotCommand(command="move_to_prod", description="⬆️ Из черновика в игру"),
        BotCommand(command="move_to_backlog", description="⬇️ Из игры в черновик"),
        BotCommand(command="delete_prod", description="🗑️ Удалить из игры"),
        BotCommand(command="delete_backlog", description="🗑️ Удалить из черновика")
        
    ]

    # 2. Устанавливаем команды для всех пользователей по умолчанию
    # Они увидят только команду /vote
    await bot.set_my_commands(user_commands, BotCommandScopeDefault())
    
    # 3. Устанавливаем расширенный набор команд персонально для администратора
    # Эти команды будут видны только вам в вашем личном чате с ботом
    await bot.set_my_commands(admin_commands, BotCommandScopeChat(chat_id=Config.ADMIN_USER_ID))


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    bot = Bot(
        token=Config.TG_TOKEN, # Убедитесь, что здесь правильное имя переменной
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    dp = Dispatcher()
    
    dp.errors.register(errors_handler)
    
    dp.include_router(admin_router)
    dp.include_router(player_router)
    
    await set_commands(bot)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())