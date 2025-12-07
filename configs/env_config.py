import os
from dotenv import load_dotenv

class Config:
    """Конфигурация приложения через переменные окружения"""
    load_dotenv()
    
    # Токен бота
    TG_TOKEN = os.getenv("TG_TOKEN", "")
    
    # ID администратора игры (преобразуем в число)
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))