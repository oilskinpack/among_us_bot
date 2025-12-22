# src/model/game.py (исправленная версия)

import random
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# Загружаем задания один раз при старте
with open('data/tasks.json', 'r', encoding='utf-8') as f:
    ALL_TASKS = json.load(f)

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
    
    imposter_id: Optional[int] = None
    imposter_score: int = 0
    imposter_score_to_win: int = 3
    imposter_task_skips_left: int = 1

    # Поле для истории заданий
    imposter_tasks_history: List[str] = field(default_factory=list)
    
    votes_total: int = 0
    votes_used: int = 0
    
    current_votes: Dict[int, int] = field(default_factory=dict)
    players_voted: List[int] = field(default_factory=list)

    available_tasks: List[str] = field(default_factory=lambda: random.sample(ALL_TASKS, len(ALL_TASKS)))
    current_imposter_task: Optional[str] = None

    # <<< ВОТ ЭТОТ МЕТОД НУЖНО ДОБАВИТЬ
    def get_player(self, user_id: int) -> Optional[Player]:
        """Ищет игрока в списке self.players по его ID."""
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None
    # КОНЕЦ ДОБАВЛЕННОГО БЛОКА

    def start_game(self):
        self.status = "in_progress"
        self.votes_total = len(self.players) - 1
        self.imposter_score_to_win = self.votes_total
        
        imposter_player = random.choice(self.players)
        imposter_player.role = "imposter"
        self.imposter_id = imposter_player.user_id
        
    def assign_imposter_task(self) -> Optional[str]:
        if not self.available_tasks:
            self.current_imposter_task = None
            return None
        
        self.current_imposter_task = self.available_tasks.pop(0)
        #Добавляем задание в историю
        self.imposter_tasks_history.append(self.current_imposter_task)
        return self.current_imposter_task

    def complete_task(self):
        self.imposter_score += 1

    def failed_vote(self):
        self.imposter_score += 1
        
    def reset_vote_state(self):
        self.current_votes.clear()
        self.players_voted.clear()
