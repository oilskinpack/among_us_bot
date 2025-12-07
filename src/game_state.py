from typing import Dict, Optional
from src.model.game import GameSession

# {chat_id: GameSession}
active_games: Dict[int, GameSession] = {}

def get_game(chat_id: int) -> Optional[GameSession]:
    return active_games.get(chat_id)

def create_game(chat_id: int) -> GameSession:
    game = GameSession(chat_id=chat_id)
    active_games[chat_id] = game
    return game

def end_game(chat_id: int):
    if chat_id in active_games:
        del active_games[chat_id]