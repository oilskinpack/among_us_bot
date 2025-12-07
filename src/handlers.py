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
    create_vote_keyboard,
)

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
        await message.answer("Эту команду можно использовать только в групповом чате.")
        return
    # ... (остальной код функции без изменений)
    chat_id = message.chat.id
    if state.get_game(chat_id):
        await message.answer("Игра в этом чате уже идет. Завершите ее командой /stop_game перед началом новой.")
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
    # ... (код функции до рассылки без изменений)

    min_players = 2
    chat_id = message.chat.id
    game = state.get_game(chat_id)
    if not game or game.status != "lobby":
        await message.answer("Нет активного лобби для старта игры. Создайте его командой /new_game.")
        return
    if len(game.players) < min_players:
        await message.answer(f"Недостаточно игроков для начала. Нужно минимум {min_players}, сейчас {len(game.players)}.")
        return
    game.start_game()
    game.assign_imposter_task()
    logging.info(f"Game started in chat {chat_id}. Imposter: {game.imposter_id}")
    await message.answer(
        f"Игра началась! Импостер уже среди вас.\n"
        f"У вас есть {game.votes_total} попыток на голосование. Удачи!"
    )
    for player in game.players:
        try:
            # ... (код рассылки ролей без изменений)
            if player.role == "imposter":
                await bot.send_message(
                    player.user_id,
                    f"🤫 Ты — Импостер! Твоя цель — набрать 3 очка.\n\n"
                    f"Твое первое задание: **{escape_markdown(game.current_imposter_task)}**\n\n"
                    f"У тебя есть {game.imposter_task_skips_left} возможность сменить задание.",
                    reply_markup=create_imposter_task_keyboard(can_skip=True)
                )
            else:
                await bot.send_message(
                    player.user_id,
                    "👥 Ты — член экипажа. Ваша цель — вычислить импостера.\n"
                    f"У вас есть {game.votes_total} попыток на голосование. Каждая ошибка приближает импостера к победе!"
                )
        except Exception as e:
            logging.error(f"Failed to send message to user {player.user_id}: {e}")
            # ИЗМЕНЕНИЕ: Экранируем имя игрока в сообщении об ошибке
            await message.answer(f"⚠️ Не удалось отправить сообщение игроку {escape_markdown(player.full_name)}. Убедитесь, что он запустил бота в ЛС.")


@admin_router.message(Command("stop_game"))
async def stop_game_handler(message: Message):
    state.end_game(message.chat.id)
    await message.answer("Игра принудительно завершена.")


@admin_router.message(Command("player_list"))
async def player_list_handler(message: Message, bot: Bot):
    game = state.get_game(message.chat.id)
    if not game:
        await message.answer("В этом чате нет активной игры.", reply_to_message_id=message.message_id)
        return
    
    # ИЗМЕНЕНИЕ: Экранируем имена игроков
    player_lines = [f"- ID: {p.user_id}, Имя: {escape_markdown(p.full_name)}" for p in game.players]
    player_text = "\n".join(player_lines) if player_lines else "В лобби пока пусто."
    
    try:
        # ИЗМЕНЕНИЕ: Экранируем название чата
        await bot.send_message(Config.ADMIN_USER_ID, f"Список игроков в чате {escape_markdown(message.chat.title)}:\n{player_text}")
        if message.chat.type != "private":
            await message.delete()
    except Exception as e:
        logging.error(f"Failed to send player list to admin: {e}")
        await message.answer("Не могу отправить вам личное сообщение. Пожалуйста, начните диалог с ботом.")


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
        await query.message.edit_text("Не удалось найти игру для этого игрока. Возможно, она была отменена.")
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
    await query.message.edit_text("Не удалось найти этого игрока в заявках.")

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
    game = next((g for g in state.active_games.values() if g.imposter_id == user_id and g.status == "in_progress"), None)

    if not game:
        await query.answer("Это действие сейчас недоступно.", show_alert=True)
        return

    if query.data == "task_done":
        game.complete_task()
        await query.message.edit_text(f"✅ Задание принято. Ваш счет: {game.imposter_score}/3")

        if game.imposter_score >= 3:
            imposter = game.get_player(game.imposter_id)
            await bot.send_message(game.chat_id, f"🏆 **Победа Импостера!**\nОн набрал 3 очка. Коварным импостером был {escape_markdown(imposter.full_name)}!")
            state.end_game(game.chat_id)
            return

        await bot.send_message(game.chat_id, f"✅ Задание выполнено! Счет импостера: {game.imposter_score}/3. Будьте начеку!")
        
        new_task = game.assign_imposter_task()
        if new_task:
            await query.message.answer(f"Ваше следующее задание: **{escape_markdown(new_task)}**", reply_markup=create_imposter_task_keyboard(can_skip=False))
        else:
            await query.message.answer("Задания закончились!")

    elif query.data == "task_skip":
        if game.imposter_task_skips_left <= 0:
            await query.answer("Вы уже использовали свою попытку смены задания.", show_alert=True)
            return
        
        game.imposter_task_skips_left -= 1
        new_task = game.assign_imposter_task()
        
        # --- ВОТ ИСПРАВЛЕНИЕ ---
        # Было: if new_text:
        # Стало: if new_task:
        if new_task:
            await query.message.edit_text(
                f"Задание сменено. Ваше новое задание: **{escape_markdown(new_task)}**",
                reply_markup=create_imposter_task_keyboard(can_skip=False)
            )
        else:
            await query.message.edit_text("Не удалось сменить, так как задания закончились.")


@player_router.message(Command("vote"))
async def vote_command_handler(message: Message, bot: Bot):
    # ... (код функции до рассылки клавиатур без изменений)
    if message.chat.type == "private": return
    game = state.get_game(message.chat.id)
    if not game or game.status != "in_progress": return
    if game.players_voted:
        await message.answer("Голосование уже идет!", reply_to_message_id=message.message_id)
        return
    if game.votes_used >= game.votes_total:
        await message.answer("Попытки голосования закончились!", reply_to_message_id=message.message_id)
        return
    game.votes_used += 1
    # ИЗМЕНЕНИЕ: Экранируем имя инициатора голосования
    await message.answer(
        f"📢 {escape_markdown(message.from_user.full_name)} созывает экстренное совещание!\n"
        f"Использована попытка голосования {game.votes_used} из {game.votes_total}.\n"
        "Проголосуйте в личном чате с ботом. Результаты будут объявлены, когда проголосуют все."
    )
    for player in game.players:
        try:
            await bot.send_message(player.user_id, "Кого вы подозреваете?", reply_markup=create_vote_keyboard(game, voter_id=player.user_id))
        except Exception as e:
            logging.error(f"Failed to send vote keyboard to {player.user_id}: {e}")
            # ИЗМЕНЕНИЕ: Экранируем имя игрока в сообщении об ошибке
            await message.answer(f"⚠️ Не удалось отправить клавиатуру для голосования игроку {escape_markdown(player.full_name)}.")


@player_router.callback_query(F.data.startswith("vote_"), F.message.chat.type == "private")
async def process_vote_callback(query: CallbackQuery, bot: Bot):
    # ... (этот хендлер не выводит пользовательские данные, оставляем без изменений)
    voter_id = query.from_user.id
    game = next((g for g in state.active_games.values() if g.get_player(voter_id) and g.status == "in_progress"), None)
    if not game:
        await query.answer("Вы не участвуете в активной игре.", show_alert=True)
        return
    if voter_id in game.players_voted:
        await query.answer("Вы уже проголосовали.", show_alert=True)
        return
    accused_id = int(query.data.split("_")[1])
    game.players_voted.append(voter_id)
    game.current_votes[accused_id] = game.current_votes.get(accused_id, 0) + 1
    await query.message.edit_text("Ваш голос принят.")
    if len(game.players_voted) == len(game.players):
        await process_vote_results(game, bot)


async def process_vote_results(game: GameSession, bot: Bot):
    # ... (код функции до вывода результатов без изменений)
    if not game.current_votes:
        await bot.send_message(game.chat_id, "Голосование завершилось, но никто не проголосовал. Попытка потрачена впустую.")
        game.reset_vote_state()
        return
    max_votes = max(game.current_votes.values())
    most_voted_ids = [uid for uid, votes in game.current_votes.items() if votes == max_votes]
    results_text = "📊 **Результаты голосования:**\n"
    for player_id, votes in Counter(game.current_votes).most_common():
        player = game.get_player(player_id)
        # ИЗМЕНЕНИЕ: Экранируем имя игрока в результатах
        results_text += f"- {escape_markdown(player.full_name)}: {votes} голос(а)\n"
    await bot.send_message(game.chat_id, results_text)
    
    # ... (код далее с экранированием имен)
    if len(most_voted_ids) > 1:
        await bot.send_message(game.chat_id, "⚠️ Голоса разделились! Никто не был назван. **Это считается неудачным голосованием.**")
        game.failed_vote()
    else:
        accused_id = most_voted_ids[0]
        accused_player = game.get_player(accused_id)
        if accused_id == game.imposter_id:
            await bot.send_message(
                game.chat_id,
                f"✅ Вы были правы! {escape_markdown(accused_player.full_name)} действительно был импостером!\n\n"
                f"🏆 **Победа Экипажа!** Поздравляем!"
            )
            state.end_game(game.chat_id)
            return
        else:
            await bot.send_message(
                game.chat_id,
                f"❌ Ошибка! {escape_markdown(accused_player.full_name)} не был импостером. **Это было неудачное голосование.**"
            )
            game.failed_vote()
    await bot.send_message(game.chat_id, f"Счет импостера теперь: {game.imposter_score}/3.")
    if game.imposter_score >= 3:
        imposter = game.get_player(game.imposter_id)
        await bot.send_message(game.chat_id, f"🏆 **Победа Импостера!**\nОн набрал 3 очка. Коварным импостером был {escape_markdown(imposter.full_name)}!")
        state.end_game(game.chat_id)
    else:
        game.reset_vote_state()