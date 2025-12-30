# --- ЭТАП 1: СБОРЩИК (BUILDER) ---
# Здесь мы устанавливаем все зависимости, включая сборочные
FROM python:3.12-slim AS builder

# Устанавливаем системные зависимости, необходимые для сборки пакетов
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Poetry
RUN pip install poetry

# Создаем рабочую директорию
WORKDIR /app

# Настраиваем Poetry для установки зависимостей в системный Python
RUN poetry config virtualenvs.create false

# Копируем только файлы зависимостей для кэширования
COPY pyproject.toml poetry.lock* ./

# Устанавливаем зависимости проекта
# --no-dev убирает зависимости для разработки, делая образ меньше
RUN poetry install --no-interaction --no-root --only main


# --- ЭТАП 2: ФИНАЛЬНЫЙ ОБРАЗ (FINAL) ---
# Здесь мы создаем чистый образ для запуска приложения
FROM python:3.12-slim AS final

# Создаем рабочую директорию
WORKDIR /app

# Копируем установленные зависимости из этапа сборщика
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Копируем весь исходный код вашего приложения
COPY . .

# Создаем пользователя без привилегий для безопасности
RUN adduser --disabled-password --gecos '' botuser

# ИСПРАВЛЕНИЕ 2: Рекурсивно меняем владельца всей папки приложения на botuser
# Это нужно сделать до переключения пользователя (USER)
RUN chown -R botuser:botuser /app

# Переключаемся на непривилегированного пользователя
USER botuser

# ИСПРАВЛЕНИЕ 1: Устанавливаем правильную точку входа
CMD ["python", "tg.py"]