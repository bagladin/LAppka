"""
Логика категоризации вопросов
"""

from typing import List, Dict, Any, Tuple, Set
import re
import numpy as np
from difflib import SequenceMatcher
from modules.categorization.moodle_parser import is_open_question_type


def normalize_metric_value(value: Any) -> str:
    """
    Нормализует значение метрики для сравнения
    
    Параметры:
    - value: значение метрики (может быть строкой или числом)
    
    Возвращает:
    - нормализованную строку для сравнения
    """
    if value is None:
        return ''
    
    # Преобразуем в строку
    str_value = str(value).strip()
    
    # Заменяем запятую на точку для числовых значений
    str_value = str_value.replace(',', '.')
    
    # Удаляем знак процента, если есть
    str_value = str_value.replace('%', '')
    
    # Пытаемся преобразовать в float для нормализации (убираем лишние нули)
    try:
        float_value = float(str_value)
        # Округляем до 2 знаков после запятой для сравнения
        return f"{float_value:.2f}"
    except (ValueError, TypeError):
        # Если не число, возвращаем как есть (в нижнем регистре)
        return str_value.lower()
    
    return str_value


def get_question_signature(question: Dict[str, Any]) -> str:
    """
    Создает "подпись" вопроса на основе всех метрик для поиска дубликатов
    
    Дубликаты определяются по совпадению:
    - Название вопроса (нормализованное)
    - Тип вопроса
    - Попытки
    - Индекс легкости (сложность)
    - Стандартное отклонение
    - Вероятность угадывания
    - Предполагаемый вес
    - Эффективный вес
    - Индекс дискриминации
    - Эффективность дискриминации
    
    Параметры:
    - question: словарь с данными о вопросе
    
    Возвращает:
    - строку-подпись вопроса
    """
    # Нормализуем название вопроса
    title = normalize_text(question.get('title', ''))
    
    # Нормализуем тип вопроса (исключаем "случайный")
    question_type = str(question.get('type', '')).strip()
    if question_type.lower() in ['случайный', 'случайный вопрос', 'random', '']:
        question_type = ''
    
    # Нормализуем все метрики для сравнения
    metrics = [
        question_type,
        normalize_metric_value(question.get('attempts', '')),
        normalize_metric_value(question.get('difficulty', '')),
        normalize_metric_value(question.get('std_dev', '')),
        normalize_metric_value(question.get('guess_prob', '')),
        normalize_metric_value(question.get('weight', '')),
        normalize_metric_value(question.get('effective_weight', '')),
        normalize_metric_value(question.get('discrimination', '')),
        normalize_metric_value(question.get('efficiency', ''))
    ]
    
    # Создаем подпись из названия и метрик
    signature = f"{title}|{'|'.join(metrics)}"
    return signature


def find_and_deduplicate_questions(analyzed_questions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    """
    Находит дубликаты в проанализированных вопросах и возвращает дедуплицированный список
    
    Дубликаты определяются по совпадению всех метрик:
    - Тип вопроса
    - Название вопроса (нормализованное)
    - Попытки
    - Индекс легкости (сложность)
    - Стандартное отклонение
    - Вероятность угадывания
    - Предполагаемый вес
    - Эффективный вес
    - Индекс дискриминации
    - Эффективность дискриминации
    
    Параметры:
    - analyzed_questions: список проанализированных вопросов
    
    Возвращает:
    - кортеж (дедуплицированный список вопросов, словарь {подпись: [список ID дубликатов]})
    """
    # Группируем вопросы по подписи
    signature_groups = {}  # signature -> [questions]
    
    for question in analyzed_questions:
        signature = get_question_signature(question)
        if signature not in signature_groups:
            signature_groups[signature] = []
        signature_groups[signature].append(question)
    
    # Создаем дедуплицированный список (берем первого представителя из каждой группы)
    deduplicated = []
    duplicates_info = {}  # signature -> [list of IDs]
    
    for signature, questions in signature_groups.items():
        # Берем первого представителя
        representative = questions[0].copy()
        # Добавляем duplicate_ids и display_id для отображения в карточках
        all_ids = [q.get('id', '') for q in questions if q.get('id')]
        if len(all_ids) > 1:
            duplicates_info[signature] = all_ids
            rep_id = representative.get('id', '')
            representative['duplicate_ids'] = [i for i in all_ids if i != rep_id]
            representative['display_id'] = rep_id + (' (' + ', '.join(representative['duplicate_ids']) + ')' if representative['duplicate_ids'] else '')
        deduplicated.append(representative)
    
    return deduplicated, duplicates_info


def extract_question_text_from_gift(gift_text: str) -> str:
    """
    Извлекает текст вопроса из GIFT формата
    Текст находится между вторым :: и открывающейся фигурной скобкой {
    
    Параметры:
    - gift_text: полный текст вопроса в формате GIFT
    
    Возвращает:
    - текст вопроса без форматирования
    """
    if not gift_text:
        return ""
    
    # Ищем второе вхождение ::
    parts = gift_text.split('::')
    if len(parts) < 3:
        return ""
    
    # Берем часть после второго ::
    text_after_second_colon = '::'.join(parts[2:])
    
    # Ищем первую открывающуюся фигурную скобку
    brace_pos = text_after_second_colon.find('{')
    if brace_pos == -1:
        # Если нет фигурной скобки, берем весь текст
        return text_after_second_colon.strip()
    
    # Берем текст до фигурной скобки
    question_text = text_after_second_colon[:brace_pos].strip()
    
    return question_text


def clean_html_tags(text: str) -> str:
    """
    Удаляет HTML-разметку из текста и извлекает текстовое содержимое:
    - Обрабатывает экранированные символы (\:, \n, \=)
    - Извлекает текстовое содержимое из HTML-таблиц
    - Удаляет все HTML теги
    - Удаляет [html]...[/html] блоки
    
    Параметры:
    - text: текст с HTML-разметкой
    
    Возвращает:
    - очищенный текст с сохранением содержимого таблиц
    """
    if not text:
        return ""
    
    # Сначала заменяем экранированные символы на обычные
    text = text.replace('\\:', ':')
    text = text.replace('\\;', ';')
    text = text.replace('\\=', '=')
    text = text.replace('\\n', ' ')
    text = text.replace('&nbsp;', ' ')
    
    # Извлекаем содержимое из HTML-таблиц перед удалением тегов
    # Заменяем ячейки таблиц на их текстовое содержимое с разделителями
    # Обрабатываем <td> и <th> - заменяем на их содержимое с пробелом
    text = re.sub(r'<td[^>]*>(.*?)</td>', r' \1 ', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<th[^>]*>(.*?)</th>', r' \1 ', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Обрабатываем <caption> - добавляем его содержимое
    text = re.sub(r'<caption[^>]*>(.*?)</caption>', r' \1 ', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Обрабатываем <br> и <br/> - заменяем на пробел
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    
    # Теперь удаляем все остальные HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    
    # Удаляем [html]...[/html] блоки (включая всё содержимое между тегами)
    # Используем нежадное совпадение для правильной обработки вложенных блоков
    text = re.sub(r'\[html\].*?\[/html\]', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Удаляем оставшиеся одиночные теги [html] или [/html]
    text = re.sub(r'\[/?html\]', '', text, flags=re.IGNORECASE)
    
    # Нормализуем пробелы (множественные пробелы заменяем на один)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def normalize_text(text: str) -> str:
    """
    Нормализует текст для сопоставления:
    - Удаляет HTML теги и разметку
    - Приводит к нижнему регистру
    - Удаляет лишние пробелы
    - Удаляет специальные символы
    
    Параметры:
    - text: исходный текст
    
    Возвращает:
    - нормализованный текст
    """
    if not text:
        return ""
    
    # Удаляем HTML-разметку
    text = clean_html_tags(text)
    
    # Удаляем экранированные символы
    text = text.replace('\\:', ':').replace('\\;', ';')
    
    # Приводим к нижнему регистру и удаляем лишние пробелы
    text = ' '.join(text.lower().split())
    
    # Удаляем специальные символы, оставляем только буквы, цифры и пробелы
    text = re.sub(r'[^\w\s]', '', text)
    
    return text.strip()


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Вычисляет схожесть двух текстов (от 0.0 до 1.0)
    
    Параметры:
    - text1: первый текст
    - text2: второй текст
    
    Возвращает:
    - коэффициент схожести (0.0 - 1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    # Нормализуем оба текста
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Используем SequenceMatcher для вычисления схожести
    similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    return similarity


def categorize_questions(
    moodle_questions: List[Dict[str, Any]],
    analyzed_questions: List[Dict[str, Any]],
    easy_threshold: float = 70.0
) -> Tuple[Dict[str, List[Dict[str, Any]]], Set[str], List[str], Dict[str, List[str]]]:
    """
    Категоризирует вопросы по правилам:
    
    Категория 1: Легкие вопросы (>= 70%)
    - 1.1: Открытые вопросы
    - 1.2: Закрытые вопросы
    
    Категория 2: Средние + сложные (< 70%)
    - 2.1: Открытые вопросы
    - 2.2: Закрытые вопросы
    
    Категория 3: На переделку
    - Плохая дискриминация (< 0.3)
    - 10% самых легких вопросов
    
    Параметры:
    - moodle_questions: вопросы из Moodle файла
    - analyzed_questions: вопросы с анализом (из модуля 1)
    
    Возвращает:
    - кортеж (словарь {категория: [вопросы]}, множество названий самых легких вопросов, список несопоставленных вопросов, словарь информации о дубликатах, список информации о сопоставлениях для отладки)
    """
    # Сначала находим и дедуплицируем вопросы из анализа
    deduplicated_questions, duplicates_info = find_and_deduplicate_questions(analyzed_questions)
    
    # Создаем множество ID всех дубликатов для быстрой проверки
    all_duplicate_ids = set()
    for duplicate_ids in duplicates_info.values():
        if len(duplicate_ids) > 1:
            all_duplicate_ids.update(duplicate_ids)
    
    # Сопоставляем Moodle вопросы с проанализированными по тексту вопроса
    matched_questions = []
    matching_info_raw = []  # Временно сохраняем для построения дублей
    
    for mq in moodle_questions:
        moodle_id = mq.get('id', '') or mq.get('name_from_comment', '') or '?'
        gift_text = mq.get('text', '')
        moodle_question_text = extract_question_text_from_gift(gift_text)
        matched = None
        best_similarity = 0.0
        
        if moodle_question_text:
            for aq in deduplicated_questions:
                analyzed_question_text = aq.get('title', '').strip()
                if analyzed_question_text:
                    similarity = calculate_text_similarity(moodle_question_text, analyzed_question_text)
                    if similarity >= 0.9 and similarity > best_similarity:
                        matched = aq
                        best_similarity = similarity
        
        analyzed_id = matched.get('id', '') if matched else ''
        matching_info_raw.append({
            'moodle_id': moodle_id,
            'analyzed_id': analyzed_id if analyzed_id else 'Не найдено',
            'matched': matched is not None
        })
        
        if matched:
            # Используем тип вопроса из анализа, если он есть (более точный)
            question_type = matched.get('type', mq.get('type', 'Множественный выбор'))
            # Если тип из анализа не пустой и не "Случайный", используем его
            if question_type and question_type.lower() not in ['случайный', 'случайный вопрос', 'random', '']:
                final_type = question_type
            else:
                final_type = mq.get('type', 'Множественный выбор')
            
            # Безопасно преобразуем difficulty и discrimination в float
            try:
                difficulty = float(str(matched.get('difficulty', 0)).replace(',', '.').replace('%', ''))
            except (ValueError, TypeError):
                difficulty = 0.0
            
            try:
                discrimination = float(str(matched.get('discrimination', 0)).replace(',', '.').replace('%', ''))
            except (ValueError, TypeError):
                discrimination = 0.0
            
            attempts = 0
            try:
                a = matched.get('attempts', 0)
                attempts = int(float(str(a).replace(',', '.').replace(' ', '')) or 0)
            except (ValueError, TypeError):
                pass
            matched_questions.append({
                'moodle_question': mq,
                'analysis': matched,
                'difficulty': difficulty,
                'discrimination': discrimination,
                'type': final_type,
                'attempts': attempts
            })
        else:
            # Если не нашли совпадение, используем данные из Moodle (попыток нет)
            matched_questions.append({
                'moodle_question': mq,
                'analysis': None,
                'difficulty': 50.0,
                'discrimination': 0.5,
                'type': mq.get('type', 'Множественный выбор'),
                'attempts': 0
            })
    
    # Определяем 10% самых легких вопросов
    sorted_by_difficulty = sorted(matched_questions, key=lambda x: x['difficulty'], reverse=True)
    top_10_percent_count = max(1, int(len(sorted_by_difficulty) * 0.1))
    easiest_questions = set()
    for i in range(top_10_percent_count):
        if i < len(sorted_by_difficulty):
            q_name = sorted_by_difficulty[i]['moodle_question'].get('name', '')
            easiest_questions.add(q_name)
    
    # Порог «мало попыток»: 25-й перцентиль или минимум 30 (правило Наннали для стабильной CTT)
    attempts_list = [q.get('attempts', 0) for q in matched_questions if q.get('attempts', 0) > 0]
    if attempts_list:
        p25 = float(np.percentile(attempts_list, 25))
        min_attempts_threshold = max(30, p25)  # минимум 30, иначе — нижний квартиль
    else:
        min_attempts_threshold = 30
    
    # Категоризируем вопросы
    categories = {
        '1.1 Легкие/Открытые': [],
        '1.2 Легкие/Закрытые': [],
        '2.1 Средние+Сложные/Открытые': [],
        '2.2 Средние+Сложные/Закрытые': [],
        '3 На переделку': []
    }
    
    low_attempts_questions = set()
    for q in matched_questions:
        difficulty = q['difficulty']
        discrimination = q['discrimination']
        question_type = q['type']
        question_name = q['moodle_question'].get('name', '')
        
        needs_revision = False
        
        if discrimination < 0.3:
            needs_revision = True
        if question_name in easiest_questions:
            needs_revision = True
        if q.get('analysis'):
            attempts = q.get('attempts', 0) or 0
            if attempts < min_attempts_threshold:
                needs_revision = True
                low_attempts_questions.add(question_name)
        
        if needs_revision:
            categories['3 На переделку'].append(q)
        elif difficulty >= easy_threshold:
            # Легкие вопросы
            if is_open_question_type(question_type):
                categories['1.1 Легкие/Открытые'].append(q)
            else:
                categories['1.2 Легкие/Закрытые'].append(q)
        else:
            # Средние + сложные
            if is_open_question_type(question_type):
                categories['2.1 Средние+Сложные/Открытые'].append(q)
            else:
                categories['2.2 Средние+Сложные/Закрытые'].append(q)
    
    # Собираем список несопоставленных вопросов
    unmatched_questions = [
        q['moodle_question'].get('name', '') 
        for q in matched_questions 
        if q.get('analysis') is None
    ]
    
    # Строим matching_info с указанием дубля какого вопроса
    # Группируем по analyzed_id -> [moodle_ids]
    analyzed_to_moodle = {}
    for r in matching_info_raw:
        aid = r['analyzed_id']
        if aid and aid != 'Не найдено':
            analyzed_to_moodle.setdefault(aid, []).append(r['moodle_id'])
    
    matching_info = []
    for r in matching_info_raw:
        aid = r['analyzed_id']
        mid = r['moodle_id']
        others = [m for m in analyzed_to_moodle.get(aid, []) if m != mid] if aid and aid != 'Не найдено' else []
        is_duplicate = ', '.join(sorted(others)) if others else ''
        matching_info.append({
            'moodle_id': mid,
            'analyzed_id': aid if r['matched'] else 'Не найдено',
            'is_duplicate': is_duplicate
        })
    
    return categories, easiest_questions, unmatched_questions, duplicates_info, matching_info, low_attempts_questions
