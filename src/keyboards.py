from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.model.game import GameSession

def create_lobby_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Подать заявку", callback_data="apply_to_join"))
    return builder.as_markup()

def create_admin_approval_keyboard(user_id: int, username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{user_id}")
    )
    return builder.as_markup()

def create_imposter_task_keyboard(can_skip: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Задание выполнено", callback_data="task_done"))
    if can_skip:
        builder.add(InlineKeyboardButton(text="♻️ Сменить задание", callback_data="task_skip"))
    return builder.as_markup()

def create_vote_keyboard(game: GameSession, voter_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # ИЗМЕНЕНИЕ: Получаем список только тех игроков, кто еще в игре
    active_players = [p for p in game.players if p.user_id not in game.voted_out_player_ids]
    
    for player in active_players:
        if player.user_id != voter_id: # Нельзя голосовать за себя
            builder.add(InlineKeyboardButton(
                text=player.full_name,
                callback_data=f"vote_{player.user_id}"
            ))
    builder.adjust(2)
    return builder.as_markup()

