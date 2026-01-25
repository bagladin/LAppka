"""
Парсер для Moodle GIFT файлов
"""

import re
from typing import List, Dict, Any, Tuple


def parse_moodle_file(file_content: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Парсит Moodle GIFT файл и извлекает вопросы
    
    Параметры:
    - file_content: содержимое файла
    
    Возвращает:
    - кортеж (базовая категория, список вопросов)
    """
    lines = file_content.split('\n')
    questions = []
    base_category = None
    current_category = None
    current_question = None
    question_text = []
    next_question_id = None
    next_question_name = None
    comment_lines = []  # Сохраняем строки комментариев для raw_text
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        original_line = lines[i]  # Сохраняем оригинальную строку с форматированием
        
        # Определяем базовую категорию
        if line.startswith('$CATEGORY:'):
            category_path = line.replace('$CATEGORY:', '').strip()
            if base_category is None:
                # Извлекаем базовую категорию (последняя часть пути)
                parts = category_path.split('/')
                base_category = parts[-1] if parts else category_path
            current_category = category_path
            comment_lines.append(original_line)
        
        # Комментарий с ID вопроса
        elif line.startswith('// question:'):
            # Извлекаем ID вопроса из комментария
            match = re.search(r'question:\s*(\d+)', line)
            question_id = match.group(1) if match else None
            
            # Извлекаем название из комментария
            name_match = re.search(r'name:\s*(.+)', line)
            question_name_from_comment = name_match.group(1).strip() if name_match else None
            
            # Сохраняем ID и название для следующего вопроса
            next_question_id = question_id
            next_question_name = question_name_from_comment
            comment_lines.append(original_line)
        
        # Начало вопроса
        elif line.startswith('::') and '::' in line[2:]:
            # Сохраняем предыдущий вопрос, если есть
            if current_question:
                current_question['text'] = '\n'.join(question_text)
                questions.append(current_question)
            
            # Извлекаем название вопроса
            match = re.match(r'::(.+?)::', line)
            if match:
                question_name = match.group(1)
                # Формируем raw_text с комментариями
                raw_text_parts = comment_lines + [original_line]
                comment_lines = []  # Очищаем после использования
                
                current_question = {
                    'id': next_question_id,
                    'name': question_name,
                    'name_from_comment': next_question_name,
                    'category': current_category,
                    'text': '',
                    'type': None,
                    'raw_text': '\n'.join(raw_text_parts)
                }
                question_text = [original_line]
                # Сбрасываем временные переменные
                next_question_id = None
                next_question_name = None
        
        # Продолжение вопроса
        elif current_question:
            question_text.append(original_line)
            current_question['raw_text'] += '\n' + original_line
            
            # Определяем тип вопроса по содержимому
            if current_question['type'] is None:
                current_question['type'] = detect_question_type(line)
        
        # Пустые строки между комментариями и вопросами - сохраняем в comment_lines
        elif not line:
            if comment_lines:
                comment_lines.append(original_line)
        
        i += 1
    
    # Сохраняем последний вопрос
    if current_question:
        current_question['text'] = '\n'.join(question_text)
        questions.append(current_question)
    
    return base_category or "Вопросы", questions


def detect_question_type(line: str) -> str:
    """
    Определяет тип вопроса по синтаксису GIFT
    
    Параметры:
    - line: строка с вопросом
    
    Возвращает:
    - тип вопроса в формате системы
    """
    line_lower = line.lower()
    
    # Числовой ответ
    if re.search(r'\{#.*?\}', line):
        return 'Числовой ответ'
    
    # Короткий ответ (текстовый ввод)
    if re.search(r'\{%.*?%', line) or re.search(r'\{#.*?:', line):
        return 'Короткий ответ'
    
    # Верно/Неверно
    if '{TRUE}' in line or '{FALSE}' in line:
        return 'Верно/Неверно'
    
    # На соответствие
    if '->' in line or re.search(r'\{.*?=.*?->', line):
        return 'На соответствие'
    
    # Множественный выбор (по умолчанию)
    if '{' in line and ('=' in line or '~' in line):
        return 'Множественный выбор'
    
    # Выбор пропущенных слов
    if re.search(r'\{.*?=.*?=.*?\}', line):
        return 'Выбор пропущенных слов'
    
    return 'Множественный выбор'  # По умолчанию


def is_open_question_type(question_type: str) -> bool:
    """
    Определяет, является ли вопрос открытым
    
    Открытые вопросы:
    - Числовой ответ
    - Короткий ответ
    
    Параметры:
    - question_type: тип вопроса
    
    Возвращает:
    - True, если вопрос открытый
    """
    return question_type in ['Числовой ответ', 'Короткий ответ']
