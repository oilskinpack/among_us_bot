# src/handlers.py (исправленная версия)

import logging
import re
from collections import Counter
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from configs.env_config import Config
import src.game_state as state
from src.model.game import Player, GameSession
from src.keyboards import (
    create_lobby_keyboard,
    create_admin_approval_keyboard,
    create_imposter_task_keyboard,
    create_vote_keyboard
)
from aiogram.exceptions import TelegramBadRequest
import asyncio
from aiogram.filters import CommandObject
import src.task_manager as tm

# --- НОВАЯ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
def escape_markdown(text: str) -> str:
    """Экранирует специальные символы Markdown V1."""
    # Экранируем _, *, `, [
    return re.sub(r'([_*`\[])', r'\\\1', text)

# --- ИНИЦИАЛИЗАЦИЯ РОУТЕРОВ ---
admin_router = Router()
admin_router.message.filter(F.from_user.id == Config.ADMIN_USER_ID)
admin_router.callback_query.filter(F.from_user.id == Config.ADMIN_USER_ID)

player_router = Router()


# ---------------------------------------------------------------------
# --- АДМИНСКИЙ БЛОК: УПРАВЛЕНИЕ ИГРОЙ ---
# ---------------------------------------------------------------------

@admin_router.message(Command("new_game"))
async def new_game_handler(message: Message):
    if message.chat.type == "private":
        await message.answer("Эту команду можно использовать только в групповом чате")
        return
    # ... (остальной код функции без изменений)
    chat_id = message.chat.id
    if state.get_game(chat_id):
        await message.answer("Игра в этом чате уже идет. Завершите ее командой /stop_game перед началом новой")
        return
    game = state.create_game(chat_id)
    logging.info(f"New game created in chat {chat_id}")
    await message.answer(
        "Начинаем новую игру! Кто хочет испытать свою интуицию?\n"
        "Нажмите кнопку ниже, чтобы подать заявку на участие.",
        reply_markup=create_lobby_keyboard()
    )


@admin_router.message(Command("start_game"))
async def start_game_handler(message: Message, bot: Bot):
    chat_id = message.chat.id
    game = state.get_game(chat_id)
    if not game or game.status != "lobby":
        await message.answer("Нет активного лобби для старта игры. Создайте его командой /new_game.")
        return
    
    if len(game.players) < 1:
        await message.answer(f"Недостаточно игроков для начала. Нужно минимум 1, сейчас {len(game.players)}.")
        return
        
    game.start_game()
    game.assign_imposter_task()
    
    num_imposters = len(game.imposter_ids)
    # ИСПРАВЛЕНИЕ: Используем imposter_ids вместо imposter_id
    logging.info(f"Game started in chat {chat_id}. Imposters ({num_imposters}): {game.imposter_ids}")
    
    await message.answer(
        f"Игра началась! Среди вас **{num_imposters}** импостера(-ов).\n"
        f"У вас есть {game.votes_total} попыток на голосование. Удачи!"
    )

    for player in game.players:
        try:
            if player.role == "imposter":
                teammates = [p.full_name for p in game.players if p.user_id in game.imposter_ids and p.user_id != player.user_id]
                teammates_text = f"\nВаши напарники: **{', '.join(teammates)}**." if teammates else ""
                
                await bot.send_message(
                    player.user_id,
                    f"🤫 Ты — Импостер! Твоя цель — выполнить {game.TASKS_TO_WIN} задания вместе с командой.{teammates_text}\n\n"
                    f"Ваше общее задание: **{escape_markdown(game.current_imposter_task)}**\n\n"
                    f"У тебя есть {game.imposter_task_skips_left} возможность сменить задание.",
                    reply_markup=create_imposter_task_keyboard(can_skip=True)
                )
            else:
                await bot.send_message(
                    player.user_id,
                    f"👥 Ты — член экипажа. Ваша цель — вычислить **{num_imposters}** импостера(-ов).\n"
                    f"У вас есть {game.votes_total} попыток на голосование. Используйте их с умом!"
                )
        except Exception as e:
            logging.error(f"Failed to send message to user {player.user_id}: {e}")
            await message.answer(f"⚠️ Не удалось отправить сообщение игроку {escape_markdown(player.full_name)}. Убедитесь, что он запустил бота в ЛС")

@admin_router.message(Command("stop_game"))
async def stop_game_handler(message: Message):
    state.end_game(message.chat.id)
    await message.answer("Игра принудительно завершена")


@admin_router.message(Command("player_list"))
async def player_list_handler(message: Message, bot: Bot):
    game = state.get_game(message.chat.id)
    if not game:
        await message.answer("В этом чате нет активной игры", reply_to_message_id=message.message_id)
        return
    
    # ИЗМЕНЕНИЕ: Экранируем имена игроков
    player_lines = [f"- ID: {p.user_id}, Имя: {escape_markdown(p.full_name)}" for p in game.players]
    player_text = "\n".join(player_lines) if player_lines else "В лобби пока пусто"
    
    try:
        # ИЗМЕНЕНИЕ: Экранируем название чата
        await bot.send_message(Config.ADMIN_USER_ID, f"Список игроков в чате {escape_markdown(message.chat.title)}:\n{player_text}")
        if message.chat.type != "private":
            await message.delete()
    except Exception as e:
        logging.error(f"Failed to send player list to admin: {e}")
        await message.answer("Не могу отправить вам личное сообщение. Пожалуйста, начните диалог с ботом")


@admin_router.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_callback(query: CallbackQuery, bot: Bot):
    # ... (код функции до отправки сообщения в группу без изменений)
    target_user_id = int(query.data.split("_")[2])
    game_to_update = None
    for chat_id, game in state.active_games.items():
        if target_user_id in game.pending_players:
            game_to_update = game
            break
    if not game_to_update:
        await query.message.edit_text("Не удалось найти игру для этого игрока. Возможно, она была отменена")
        return

    user_data = game_to_update.pending_players.pop(target_user_id)
    new_player = Player(user_id=target_user_id, **user_data)
    game_to_update.players.append(new_player)
    # ИЗМЕНЕНИЕ: Экранируем имя одобренного пользователя
    await query.message.edit_text(f"Вы одобрили заявку от {escape_markdown(user_data['full_name'])}.")
    # ИЗМЕНЕНИЕ: Экранируем имена всех игроков в списке
    player_names = [escape_markdown(p.full_name) for p in game_to_update.players]
    try:
        await bot.send_message(game_to_update.chat_id, f"✅ {escape_markdown(new_player.full_name)} присоединяется к игре!\n**Текущий список игроков ({len(player_names)}):** {', '.join(player_names)}")
    except Exception as e:
        logging.warning(f"Could not update lobby message in {game_to_update.chat_id}: {e}")


@admin_router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_callback(query: CallbackQuery):
    # ... (код до изменения текста без изменений)
    target_user_id = int(query.data.split("_")[2])
    for game in state.active_games.values():
        if target_user_id in game.pending_players:
            user_data = game.pending_players.pop(target_user_id)
            # ИЗМЕНЕНИЕ: Экранируем имя отклоненного пользователя
            await query.message.edit_text(f"Вы отклонили заявку от {escape_markdown(user_data['full_name'])}.")
            return
    await query.message.edit_text("Не удалось найти этого игрока в заявках")



    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры для изменения")
        return
    
    game.tasks_completed += 1
    await message.answer(
        f"✅ Команда администратора: счет заданий импостера увеличен\n"
        f"Текущий счет: {game.tasks_completed}/{game.TASKS_TO_WIN}"
    )
# --- АВАРИЙНЫЕ АДМИНСКИЕ КОМАНДЫ ---

@admin_router.message(Command("add_task_score"))
async def add_task_score_handler(message: Message):
    """Увеличивает счет выполненных заданий импостера на 1."""
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры для изменения")
        return
    
    game.tasks_completed += 1
    await message.answer(
        f"✅ Команда администратора: счет заданий импостеров увеличен\n"
        f"Текущий счет: {game.tasks_completed}/{game.TASKS_TO_WIN}"
    )

@admin_router.message(Command("remove_task_score"))
async def remove_task_score_handler(message: Message):
    """Уменьшает счет выполненных заданий импостера на 1."""
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры для изменения")
        return
    
    if game.tasks_completed > 0:
        game.tasks_completed -= 1
    
    await message.answer(
        f"✅ Команда администратора: счет заданий импостеров уменьшен\n"
        f"Текущий счет: {game.tasks_completed}/{game.TASKS_TO_WIN}"
    )

@admin_router.message(Command("add_vote"))
async def add_vote_handler(message: Message):
    """Добавляет 1 попытку для голосования."""
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры для изменения")
        return
        
    game.votes_total += 1
    await message.answer(
        f"✅ Команда администратора: количество попыток голосования увеличено\n"
        f"Текущее количество: {game.votes_total}"
    )

@admin_router.message(Command("remove_vote"))
async def remove_vote_handler(message: Message):
    """Убирает 1 попытку для голосования."""
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры для изменения")
        return
    
    if game.votes_total > 0:
        game.votes_total -= 1
        
    await message.answer(
        f"✅ Команда администратора: количество попыток голосования уменьшено\n"
        f"Текущее количество: {game.votes_total}"
    )

@admin_router.message(Command("resend_task"))
async def resend_task_handler(message: Message, bot: Bot):
    """Принудительно отправляет новое задание импостерам."""
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress":
        await message.answer("Нет активной игры.")
        return
        
    # ИСПРАВЛЕНИЕ: Используем imposter_ids вместо imposter_id
    if not game.imposter_ids:
        await message.answer("Ошибка: в игре еще не назначены импостеры.")
        return
        
    new_task = game.assign_imposter_task()
    if new_task:
        for imposter_id in game.imposter_ids:
            try:
                await bot.send_message(
                    imposter_id,
                    f"⚙️ **(Команда администратора)**\nВам выдано новое общее задание:\n"
                    f"**{escape_markdown(new_task)}**",
                    reply_markup=create_imposter_task_keyboard(can_skip=game.imposter_task_skips_left > 0)
                )
            except Exception as e:
                logging.error(f"Admin command /resend_task failed to send PM to {imposter_id}: {e}")
        
        await message.answer("✅ Команда администратора: импостерам отправлено новое задание.")
    else:
        await message.answer("Не удалось выдать новое задание (возможно, они закончились).")

# --- УПРАВЛЕНИЕ ЗАДАНИЯМИ ---

@admin_router.message(Command("tasks"))
async def view_production_tasks(message: Message, bot: Bot):
    if message.chat.type != "private":
        try:
            await message.delete()
        except TelegramBadRequest:
            logging.warning("Не удалось удалить сообщение, недостаточно прав в чате.")
        
        # Отправляем временное сообщение в чат с подсказкой
        confirm_msg = await message.answer("Команда доступна только для админа")
        await asyncio.sleep(5)
        await confirm_msg.delete()
        return

    # Если команда в ЛС, отправляем список
    tasks = tm.get_production_tasks()
    text = "📝 **Чистовые задания (в игре):**\n\n"
    if not tasks:
        text += "Список пуст."
    else:
        task_lines = [f"{i}. {escape_markdown(task)}" for i, task in enumerate(tasks, 1)]
        text += "\n".join(task_lines)
    
    await message.answer(text)


@admin_router.message(Command("backlog"))
async def view_backlog_tasks(message: Message, bot: Bot):
    if message.chat.type != "private":
        try:
            await message.delete()
        except TelegramBadRequest:
            logging.warning("Не удалось удалить сообщение, недостаточно прав в чате.")
            
        confirm_msg = await message.answer("Команда доступна только для админа")
        await asyncio.sleep(5)
        await confirm_msg.delete()
        return

    # Если команда в ЛС, отправляем список
    tasks = tm.get_backlog_tasks()
    text = "📋 **Черновики заданий (бэклог):**\n\n"
    if not tasks:
        text += "Список пуст."
    else:
        task_lines = [f"{i}. {escape_markdown(task)}" for i, task in enumerate(tasks, 1)]
        text += "\n".join(task_lines)

    await message.answer(text)

@admin_router.message(Command("add_task"))
async def add_task_command(message: Message, command: CommandObject):
    if message.chat.type != "private":
        await message.answer("Команда доступна только для админа")
        return

    task_text = command.args
    if not task_text:
        await message.answer("Пожалуйста, укажите текст задания после команды.\nПример: `/add_task Спеть песню`")
        return
    
    tm.add_task_to_backlog(task_text)
    await message.answer(f"✅ Задание \"{task_text}\" добавлено в черновики.")


@admin_router.message(Command("move_to_prod"))
async def move_to_prod_handler(message: Message, command: CommandObject):
    if message.chat.type != "private":
        await message.answer("Команда доступна только для админа")
        return
    try:
        task_index = int(command.args) - 1
        tm.move_task('backlog', task_index)
        await message.answer(f"✅ Задание #{task_index + 1} из черновика перемещено в игру.")
    except (TypeError, ValueError):
        await message.answer("Пожалуйста, укажите номер задания.\nПример: `/move_to_prod 3`")

@admin_router.message(Command("move_to_backlog"))
async def move_to_backlog_handler(message: Message, command: CommandObject):
    if message.chat.type != "private":
        await message.answer("Команда доступна только для админа")
        return
    try:
        task_index = int(command.args) - 1
        tm.move_task('prod', task_index)
        await message.answer(f"✅ Задание #{task_index + 1} из игры перемещено в черновик.")
    except (TypeError, ValueError):
        await message.answer("Пожалуйста, укажите номер задания.\nПример: `/move_to_backlog 5`")

@admin_router.message(Command("delete_prod"))
async def delete_prod_handler(message: Message, command: CommandObject):
    if message.chat.type != "private":
        await message.answer("Команда доступна только для админа")
        return
    try:
        task_index = int(command.args) - 1
        tm.delete_task('prod', task_index)
        await message.answer(f"❌ Задание #{task_index + 1} из игрового списка удалено.")
    except (TypeError, ValueError):
        await message.answer("Пожалуйста, укажите номер задания.\nПример: `/delete_prod 2`")

@admin_router.message(Command("delete_backlog"))
async def delete_backlog_handler(message: Message, command: CommandObject):
    if message.chat.type != "private":
        await message.answer("Команда доступна только для админа")
        return
    try:
        task_index = int(command.args) - 1
        tm.delete_task('backlog', task_index)
        await message.answer(f"❌ Задание #{task_index + 1} из черновика удалено.")
    except (TypeError, ValueError):
        await message.answer("Пожалуйста, укажите номер задания.\nПример: `/delete_backlog 1`")


# ---------------------------------------------------------------------
# --- ОБЩИЙ ИГРОВОЙ БЛОК: ДЕЙСТВИЯ ИГРОКОВ ---
# ---------------------------------------------------------------------

@player_router.callback_query(F.data == "apply_to_join")
async def apply_to_join_callback(query: CallbackQuery, bot: Bot):
    # ... (код до отправки админу без изменений)
    chat_id = query.message.chat.id
    user = query.from_user
    game = state.get_game(chat_id)
    if not game or game.status != "lobby":
        await query.answer("Набор в игру уже закрыт.", show_alert=True)
        return
    if game.get_player(user.id) or user.id in game.pending_players:
        await query.answer("Вы уже в списке или ваша заявка на рассмотрении.", show_alert=True)
        return
    game.pending_players[user.id] = {"username": user.username, "full_name": user.full_name}
    
    try:
        # ИЗМЕНЕНИЕ: Экранируем все пользовательские данные
        user_full_name = escape_markdown(user.full_name)
        username = escape_markdown(user.username or "")
        chat_title = escape_markdown(query.message.chat.title)
        
        await bot.send_message(
            Config.ADMIN_USER_ID,
            f"Пользователь {user_full_name} (@{username}) хочет присоединиться к игре в чате '{chat_title}'.",
            reply_markup=create_admin_approval_keyboard(user.id, user.username)
        )
        await query.answer("Ваша заявка отправлена администратору.", show_alert=False)
    except Exception as e:
        logging.error(f"Failed to send approval request to admin: {e}")
        await query.answer("Не удалось связаться с админом. Попросите его проверить ЛС с ботом.", show_alert=True)


@player_router.callback_query(F.data.in_({"task_done", "task_skip"}), F.message.chat.type == "private")
async def imposter_actions_callback(query: CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    # Используем imposter_ids для поиска
    game = next((g for g in state.active_games.values() if user_id in g.imposter_ids and g.status == "in_progress"), None)

    if not game:
        await query.answer("Это действие сейчас неактивно", show_alert=True)
        return

    if query.data == "task_done":
        # Добавляем задание в историю в момент его выполнения
        game.imposter_tasks_history.append(game.current_imposter_task)
        game.complete_task()
        try:
            await query.message.edit_text(f"✅ Задание принято. Выполнено: {game.tasks_completed}/{game.TASKS_TO_WIN}")
        except TelegramBadRequest:
            logging.warning("Failed to edit a stale message for imposter task completion.")
        
        await query.answer("Задание принято!")

        if game.tasks_completed >= game.TASKS_TO_WIN:
            imposter_names = [escape_markdown(p.full_name) for p in game.players if p.user_id in game.original_imposter_ids]
            tasks_summary = format_task_history(game)
            await bot.send_message(
                game.chat_id,
                f"🏆 **Победа Импостеров!**\nОни успешно выполнили все {game.TASKS_TO_WIN} задания\n"
                f"Коварными импостерами были: {', '.join(imposter_names)}!{tasks_summary}"
            )
            state.end_game(game.chat_id)
            return

        await bot.send_message(game.chat_id, f"✅ Задание выполнено! Импостеры выполнили {game.tasks_completed} из {game.TASKS_TO_WIN} заданий. Будьте начеку!")
        
        new_task = game.assign_imposter_task()
        if new_task:
            living_imposters = [p for p in game.players if p.user_id in game.imposter_ids]
            for imposter in living_imposters:
                try:
                    await bot.send_message(
                        imposter.user_id,
                        f"Ваше следующее общее задание: **{escape_markdown(new_task)}**",
                        reply_markup=create_imposter_task_keyboard(can_skip=game.imposter_task_skips_left > 0)
                    )
                except Exception:
                    pass
        else:
            await query.message.answer("Задания закончились!")

    elif query.data == "task_skip":
        if game.imposter_task_skips_left <= 0:
            await query.answer("Вы уже использовали свою попытку смены задания", show_alert=True)
            return
        
        game.imposter_task_skips_left -= 1
        new_task = game.assign_imposter_task()
        
        # Сначала подтверждаем нажатие кнопки
        await query.answer("Задание сменено!")

        if new_task:
            try:
                # Убираем кнопки у того, кто нажал
                await query.message.edit_text("Вы сменили общее задание. Новое задание отправлено всем импостерам")
            except TelegramBadRequest:
                logging.warning("Failed to edit message after task skip.")
            
            # --- ИЗМЕНЕНИЕ: Рассылаем новое задание всем живым импостерам ---
            living_imposters = [p for p in game.players if p.user_id in game.imposter_ids]
            for imposter in living_imposters:
                try:
                    await bot.send_message(
                        imposter.user_id,
                        f"Ваше общее задание было сменено. Новое задание:\n"
                        f"**{escape_markdown(new_task)}**",
                        # Кнопка смены задания больше неактивна
                        reply_markup=create_imposter_task_keyboard(can_skip=False)
                    )
                except Exception:
                    pass # Игнорируем, если не удалось доставить одному из
        else:
            await query.message.edit_text("Не удалось сменить, так как задания закончились")


@player_router.message(Command("vote"))
async def vote_command_handler(message: Message, bot: Bot):
    if message.chat.type == "private": return

    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress": return
    
    # ИЗМЕНЕНИЕ 1: Проверяем, не выбыл ли игрок, который пытается начать голосование
    if message.from_user.id in game.voted_out_player_ids:
        await message.answer("Вы выбыли из игры и не можете начинать голосование.", reply_to_message_id=message.message_id)
        return

    if game.is_voting_active:
        await message.answer("Голосование уже идет!", reply_to_message_id=message.message_id)
        return

    if game.votes_used >= game.votes_total:
        await message.answer("Попытки голосования закончились!", reply_to_message_id=message.message_id)
        return

    game.is_voting_active = True
    game.votes_used += 1
    
    await message.answer(
        f"📢 {escape_markdown(message.from_user.full_name)} созывает экстренное совещание!\n"
        f"Использована попытка голосования {game.votes_used} из {game.votes_total}.\n"
        "**У вас есть 60 секунд, чтобы проголосовать в личном чате с ботом!**"
    )

    game.vote_timer_task = asyncio.create_task(_vote_timer(game, bot))

    # ИЗМЕНЕНИЕ 2: Отправляем приглашение только "живым" игрокам
    active_players = [p for p in game.players if p.user_id not in game.voted_out_player_ids]
    for player in active_players:
        try:
            await bot.send_message(player.user_id, "Кого вы подозреваете?", reply_markup=create_vote_keyboard(game, voter_id=player.user_id))
        except Exception as e:
            logging.error(f"Failed to send vote keyboard to {player.user_id}: {e}")
            await message.answer(f"⚠️ Не удалось отправить клавиатуру для голосования игроку {escape_markdown(player.full_name)}.")


@player_router.callback_query(F.data.startswith("vote_"), F.message.chat.type == "private")
async def process_vote_callback(query: CallbackQuery, bot: Bot):
    # ... (этот хендлер не выводит пользовательские данные, оставляем без изменений)
    voter_id = query.from_user.id
    game = next((g for g in state.active_games.values() if g.get_player(voter_id) and g.status == "in_progress"), None)

    if not game:
        await query.answer("Вы не участвуете в активной игре.", show_alert=True)
        return
    
    if not game.is_voting_active:
        await query.answer("Время для голосования уже вышло.", show_alert=True)
        try:
            # Пытаемся убрать кнопки, чтобы игрок не нажал их снова
            await query.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass # Игнорируем ошибку, если сообщение уже нельзя изменить
        return
        
    if voter_id in game.players_voted:
        await query.answer("Вы уже проголосовали.", show_alert=True)
        return

    accused_id = int(query.data.split("_")[1])
    game.players_voted.append(voter_id)
    game.current_votes[accused_id] = game.current_votes.get(accused_id, 0) + 1

    try:
        await query.message.edit_text("Ваш голос принят")

    except TelegramBadRequest:
        logging.warning("Failed to edit a stale message for vote action.")
        await query.answer("Ваш голос принят")
    if len(game.players_voted) == len(game.players):
        if game.vote_timer_task:
            game.vote_timer_task.cancel()
        game.is_voting_active = False
        await process_vote_results(game, bot)


async def _vote_timer(game: GameSession, bot: Bot):
    """
    Таймер, который ждет 60 секунд и принудительно завершает голосование.
    """
    try:
        await asyncio.sleep(300)
        game.is_voting_active = False
        # Если мы дождались, значит, голосование не завершилось само.
        logging.info(f"Таймер голосования сработал для чата {game.chat_id}")
        await bot.send_message(game.chat_id, "⏰ **Время вышло!** Подводим итоги по имеющимся голосам")
        await process_vote_results(game, bot)
    except asyncio.CancelledError:
        # Это исключение возникнет, когда мы отменим задачу. Это нормальное поведение.
        logging.info(f"Таймер голосования для чата {game.chat_id} был отменен.")
        raise

async def process_vote_results(game: GameSession, bot: Bot):
    if not game.current_votes:
        await bot.send_message(game.chat_id, "Голосование завершилось, но никто не проголосовал. Попытка потрачена впустую.")
    else:
        max_votes = max(game.current_votes.values())
        most_voted_ids = [uid for uid, votes in game.current_votes.items() if votes == max_votes]

        if len(most_voted_ids) > 1:
            await bot.send_message(game.chat_id, "⚠️ Голоса разделились! Никто не был изгнан")
        else:
            accused_id = most_voted_ids[0]
            accused_player = game.get_player(accused_id)

            # --- ИЗМЕНЕНИЕ ЛОГИКИ ---
            if accused_id in game.imposter_ids:
                # Если угадали, то добавляем в список выбывших и удаляем из активных импостеров
                game.voted_out_player_ids.append(accused_id)
                game.imposter_ids.remove(accused_id)
                await bot.send_message(game.chat_id, f"✅ **Один импостер был найден!** Это был {escape_markdown(accused_player.full_name)}.")
            else:
                # Если ошиблись, просто сообщаем об этом. Игрок НЕ выбывает.
                await bot.send_message(game.chat_id, f"❌ Вы ошиблись в выборе импостера! Попытка голосования потрачена")
    
    # --- ПРОВЕРКА УСЛОВИЙ ОКОНЧАНИЯ ИГРЫ ПОСЛЕ ГОЛОСОВАНИЯ ---
    
    # 1. Проверка на победу экипажа (все импостеры найдены)
    if not game.imposter_ids:
        imposter_names = [escape_markdown(p.full_name) for p in game.players if p.user_id in game.original_imposter_ids]
        tasks_summary = format_task_history(game)
        await bot.send_message(
            game.chat_id,
            f"🏆 **Победа Экипажа!**\nВсе импостеры были найдены!\n"
            f"Коварными импостерами были: {', '.join(imposter_names)}!{tasks_summary}"
        )
        state.end_game(game.chat_id)
        return

    # 2. Проверка на победу импостеров (их количество равно или больше мирных)
    living_imposters_count = len(game.imposter_ids)
    # Количество живых игроков теперь всегда равно общему числу игроков минус число выбывших импостеров
    living_players_count = len(game.players) - len(game.voted_out_player_ids)
    living_crew_count = living_players_count - living_imposters_count

    if living_imposters_count >= living_crew_count:
        imposter_names = [escape_markdown(p.full_name) for p in game.players if p.user_id in game.original_imposter_ids]
        tasks_summary = format_task_history(game)
        await bot.send_message(
            game.chat_id,
            f"🏆 **Победа Импостеров!**\nИх осталось слишком много, чтобы сопротивляться.\n"
            f"Коварными импостерами были: {', '.join(imposter_names)}!{tasks_summary}"
        )
        state.end_game(game.chat_id)
        return

    # 3. Проверка на победу импостеров (закончились попытки голосования)
    remaining_votes = game.votes_total - game.votes_used
    if remaining_votes <= 0:
        imposter_names = [escape_markdown(p.full_name) for p in game.players if p.user_id in game.original_imposter_ids]
        tasks_summary = format_task_history(game)
        await bot.send_message(
            game.chat_id,
            "Попытки голосования закончились, а импостеры так и не были найдены!\n\n"
            f"🏆 **Победа Импостеров!**\n"
            f"Коварными импостерами были: {', '.join(imposter_names)}!{tasks_summary}"
        )
        state.end_game(game.chat_id)
        return

    # Если игра не закончилась, сообщаем статус и сбрасываем состояние
    await bot.send_message(game.chat_id, f"В игре осталось **{len(game.imposter_ids)}** импостера(-ов). Осталось попыток для голосования: **{remaining_votes}/{game.votes_total}**")
    game.reset_vote_state()

def format_task_history(game: GameSession) -> str:
    """Форматирует историю ВЫПОЛНЕННЫХ заданий импостера для вывода в чат."""
    if game.tasks_completed == 0:
        return ""
    
    tasks_text = "\n\nЗадания, которые импостер успел выполнить:\n"
    
    completed_tasks = game.imposter_tasks_history[:game.tasks_completed]
    
    tasks_list = [
        f"{i}. {escape_markdown(task)}" 
        for i, task in enumerate(completed_tasks, 1)
    ]
    tasks_text += "\n\n".join(tasks_list)
    return tasks_text

