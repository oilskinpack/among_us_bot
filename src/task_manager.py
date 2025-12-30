# src/task_manager.py (обновленная версия)

import os
from src.tasks import ALL_TASKS, BACKLOG_TASKS

# Теперь у нас только один файл для всех заданий
TASKS_FILE_PATH = "src/tasks.py"

def _read_both_task_lists():
    """Безопасно читает ОБА списка заданий из одного файла."""
    try:
        with open(TASKS_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            local_scope = {}
            exec(content, {}, local_scope)
            prod_tasks = local_scope.get("ALL_TASKS", [])
            backlog_tasks = local_scope.get("BACKLOG_TASKS", [])
            return prod_tasks, backlog_tasks
    except FileNotFoundError:
        return [], []

def _write_both_task_lists(prod_tasks, backlog_tasks):
    """Безопасно записывает ОБА списка заданий в один файл."""
    with open(TASKS_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("# src/tasks.py\n\n")
        
        # Записываем ALL_TASKS
        f.write("ALL_TASKS = [\n")
        for task in prod_tasks:
            formatted_task = task.replace('"', '\\"')
            if '\n' in formatted_task:
                f.write(f'    """{formatted_task}""",\n')
            else:
                f.write(f'    "{formatted_task}",\n')
        f.write("]\n\n")
        
        # Записываем BACKLOG_TASKS
        f.write("BACKLOG_TASKS = [\n")
        for task in backlog_tasks:
            formatted_task = task.replace('"', '\\"')
            if '\n' in formatted_task:
                f.write(f'    """{formatted_task}""",\n')
            else:
                f.write(f'    "{formatted_task}",\n')
        f.write("]\n")

def get_production_tasks():
    prod_tasks, _ = _read_both_task_lists()
    return prod_tasks

def get_backlog_tasks():
    _, backlog_tasks = _read_both_task_lists()
    return backlog_tasks

def add_task_to_backlog(task_text: str):
    prod_tasks, backlog_tasks = _read_both_task_lists()
    backlog_tasks.append(task_text)
    _write_both_task_lists(prod_tasks, backlog_tasks)

def move_task(source_list: str, task_index: int):
    prod_tasks, backlog_tasks = _read_both_task_lists()

    if source_list == 'backlog':
        if 0 <= task_index < len(backlog_tasks):
            task_to_move = backlog_tasks.pop(task_index)
            prod_tasks.append(task_to_move)
    elif source_list == 'prod':
        if 0 <= task_index < len(prod_tasks):
            task_to_move = prod_tasks.pop(task_index)
            backlog_tasks.append(task_to_move)
    
    _write_both_task_lists(prod_tasks, backlog_tasks)

def delete_task(source_list: str, task_index: int):
    prod_tasks, backlog_tasks = _read_both_task_lists()
    
    if source_list == 'backlog':
        if 0 <= task_index < len(backlog_tasks):
            backlog_tasks.pop(task_index)
    elif source_list == 'prod':
        if 0 <= task_index < len(prod_tasks):
            prod_tasks.pop(task_index)
            
    _write_both_task_lists(prod_tasks, backlog_tasks)