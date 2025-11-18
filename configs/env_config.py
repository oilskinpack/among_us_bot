import os
from dotenv import load_dotenv

class Config:
    """Конфигурация приложения через переменные окружения
    """
    load_dotenv()

    #Токен бота
    TG_TOKEN = os.getenv("TG_TOKEN","")
