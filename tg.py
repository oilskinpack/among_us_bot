import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
# 1. ДОБАВЛЯЕМ ИМПОРТ ДЛЯ КОМАНД
from aiogram.types import BotCommand, BotCommandScopeDefault

from configs.env_config import Config
from src.handlers import admin_router, player_router

# 2. СОЗДАЕМ АСИНХРОННУЮ ФУНКЦИЮ ДЛЯ УСТАНОВКИ КОМАНД
async def set_commands(bot: Bot):
    """
    Создает и устанавливает список команд, которые будут видны в меню.
    """
    commands = [
        BotCommand(
            command="new_game",
            description="🚀 Создать новое лобби для игры"
        ),
        BotCommand(
            command="start_game",
            description="▶️ Начать игру (когда все собрались)"
        ),
        BotCommand(
            command="vote",
            description="📢 Начать голосование"
        ),
        BotCommand(
            command="player_list",
            description="📋 Показать список игроков (только для админа)"
        ),
        BotCommand(
            command="stop_game",
            description="❌ Принудительно завершить игру"
        )
    ]
    # Устанавливаем команды для всех пользователей по умолчанию
    await bot.set_my_commands(commands, BotCommandScopeDefault())


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    bot = Bot(
        token=Config.TG_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    
    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(player_router)
    
    # 3. ВЫЗЫВАЕМ ФУНКЦИЮ УСТАНОВКИ КОМАНД ПЕРЕД ЗАПУСКОМ
    await set_commands(bot)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())