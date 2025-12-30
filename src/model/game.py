# src/model/game.py (обновленная версия с несколькими импостерами)

import random
import asyncio
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from src.tasks import ALL_TASKS

@dataclass
class Player:
    user_id: int
    username: str
    full_name: str
    role: str = "crewmate"

@dataclass
class GameSession:
    chat_id: int
    status: str = "lobby"
    players: List[Player] = field(default_factory=list)
    pending_players: Dict[int, dict] = field(default_factory=dict)
    
    # ИЗМЕНЕНИЕ 1: Заменяем ID одного импостера на список ID
    imposter_ids: List[int] = field(default_factory=list)
    # НОВОЕ ПОЛЕ: Сохраняем исходный состав импостеров для финального сообщения
    original_imposter_ids: List[int] = field(default_factory=list)
    # НОВОЕ ПОЛЕ: Список игроков, которых выгнали голосованием
    voted_out_player_ids: List[int] = field(default_factory=list)
    
    tasks_completed: int = 0
    TASKS_TO_WIN: int = 2
    
    imposter_task_skips_left: int = 2
    imposter_tasks_history: List[str] = field(default_factory=list)
    
    votes_total: int = 0
    votes_used: int = 0
    
    vote_timer_task: Optional[asyncio.Task] = None
    is_voting_active: bool = False
    
    current_votes: Dict[int, int] = field(default_factory=dict)
    players_voted: List[int] = field(default_factory=list)

    available_tasks: List[str] = field(default_factory=lambda: random.sample(ALL_TASKS, len(ALL_TASKS)))
    current_imposter_task: Optional[str] = None

    def get_player(self, user_id: int) -> Optional[Player]:
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    def start_game(self):
        self.status = "in_progress"
        
        # Сначала определяем количество импостеров
        num_players = len(self.players)
        num_imposters = 2 if num_players >= 6 else 1

        # --- ИЗМЕНЕНИЕ: Динамически устанавливаем количество заданий для победы ---
        if num_imposters == 1:
            self.TASKS_TO_WIN = 2
        else: # num_imposters == 2
            self.TASKS_TO_WIN = 3
        
        num_crewmates = num_players - num_imposters
        
        # ИЗМЕНЕНИЕ: Новая гибридная формула
        if num_imposters == 1:
            self.votes_total = num_crewmates - 1
        else: # num_imposters == 2
            self.votes_total = num_crewmates
        
        imposter_players = random.sample(self.players, num_imposters)
        
        for player in imposter_players:
            player.role = "imposter"
            self.imposter_ids.append(player.user_id)
        
        self.original_imposter_ids = self.imposter_ids.copy()
        
    def assign_imposter_task(self) -> Optional[str]:
        if not self.available_tasks:
            self.current_imposter_task = None
            return None
        self.current_imposter_task = self.available_tasks.pop(0)
        # self.imposter_tasks_history.append(self.current_imposter_task)
        return self.current_imposter_task

    def complete_task(self):
        self.tasks_completed += 1
        
    def reset_vote_state(self):
        self.current_votes.clear()
        self.players_voted.clear()