"""
Генератор Moodle GIFT файлов с категориями
"""

from typing import List, Dict, Any


def _is_category_switch_line(line: str) -> bool:
    """Проверяет, является ли строка переключателем категории из исходного файла (её не нужно выводить)."""
    s = line.strip()
    if not s:
        return False
    # Строки $CATEGORY: создают лишние категории в Moodle
    if s.startswith('$CATEGORY:'):
        return True
    # // question: 0  name: Switch category to ... — служебные комментарии смены категории
    if s.startswith('// question:') and 'Switch category to' in s:
        return True
    return False


def _filter_question_raw_lines(raw_text: str) -> List[str]:
    """
    Удаляет из raw_text вопроса строки переключения категорий ($CATEGORY, Switch category to).
    Иначе при импорте в Moodle создаются лишние вложенные категории с длинными/битыми именами.
    """
    if not raw_text:
        return []
    out = []
    for line in raw_text.split('\n'):
        if _is_category_switch_line(line):
            continue
        out.append(line)
    return out


def generate_moodle_file(
    base_category: str,
    categorized_questions: Dict[str, List[Dict[str, Any]]]
) -> str:
    """
    Генерирует Moodle GIFT файл с категориями
    
    Параметры:
    - base_category: базовая категория (например, "Персонал предприятия")
    - categorized_questions: словарь {категория: [вопросы]}
    
    Возвращает:
    - содержимое файла в формате GIFT
    """
    lines = []
    
    # Базовая категория
    lines.append(f"// question: 0  name: Switch category to $course$/top/{base_category}")
    lines.append(f"$CATEGORY: $course$/top/{base_category}")
    lines.append("")
    lines.append("")
    
    # Проходим по категориям в порядке
    category_order = [
        '1.1 Легкие/Открытые',
        '1.2 Легкие/Закрытые',
        '2.1 Средние+Сложные/Открытые',
        '2.2 Средние+Сложные/Закрытые',
        '3 На переделку'
    ]
    
    for category_name in category_order:
        if category_name not in categorized_questions:
            continue
        
        questions = categorized_questions[category_name]
        if not questions:
            continue
        
        # Добавляем категорию
        category_path = f"{base_category}/{category_name}"
        lines.append(f"// question: 0  name: Switch category to $course$/top/{category_path}")
        lines.append(f"$CATEGORY: $course$/top/{category_path}")
        lines.append("")
        lines.append("")
        
        # Добавляем вопросы (без строк $CATEGORY и Switch category to из исходного файла)
        for q in questions:
            moodle_q = q['moodle_question']
            raw_text = moodle_q.get('raw_text', '')
            if not raw_text:
                continue
            raw_lines = _filter_question_raw_lines(raw_text)
            if not raw_lines:
                continue
            for raw_line in raw_lines:
                lines.append(raw_line)
            lines.append("")
            lines.append("")
    
    return '\n'.join(lines)
