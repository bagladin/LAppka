"""
Парсер HTML файлов Moodle
Понятный код для начинающих программистов
"""

from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any, Tuple


def parse_moodle_html(file_content):
    """
    Парсинг HTML файла Moodle
    
    Что делает эта функция:
    1. Находит таблицу с вопросами
    2. Читает каждую строку таблицы
    3. Извлекает данные о вопросах
    4. Находит ответы для каждого вопроса
    5. Возвращает список вопросов с ответами
    """
    # Создаем объект для парсинга HTML
    soup = BeautifulSoup(file_content, "html.parser")
    
    # Находим таблицу с вопросами
    # Ищем таблицу, которая содержит заголовки "№", "Тип вопроса", "Название вопроса"
    questions_table = None
    
    # Ищем все таблицы в HTML
    tables = soup.find_all('table')
    
    for table in tables:
        # Ищем заголовки таблицы
        headers = table.find_all('th')
        if headers:
            # Получаем текст заголовков
            header_texts = [th.get_text(strip=True) for th in headers]
            
            # Проверяем, есть ли нужные заголовки
            if '№' in header_texts and 'Тип вопроса' in header_texts and 'Название вопроса' in header_texts:
                questions_table = table
                break
    
    if not questions_table:
        print("Не найдена таблица с вопросами")
        return []
    
    print(f"Найдена таблица с вопросами")
    
    # Получаем все строки таблицы (кроме заголовка)
    rows = questions_table.find_all('tr')[1:]  # Пропускаем первую строку (заголовок)
    
    questions = []
    subquestion_index = 0  # Отдельный счетчик только для подвопросов (для сопоставления с блоками вопросов в HTML)
    
    # Обрабатываем каждую строку
    for row in rows:
        # Получаем все ячейки в строке
        cells = row.find_all('td')
        
        if len(cells) < 11:  # Проверяем, что в строке достаточно ячеек
            continue
            
        # Извлекаем данные из ячеек
        question_data = extract_question_data(cells)
        
        if not question_data:
            continue
        
        # Берем только подвопросы (с точкой в ID) для основного списка вопросов
        # Это соответствует логике CSV парсера
        if is_subquestion(question_data['id']):
            # Ищем полный текст вопроса и ответы используя индекс подвопросов
            full_question_text = find_question_text_by_order(soup, subquestion_index)
            if full_question_text:
                question_data['title'] = full_question_text
            
            # Ищем ответы для этого вопроса
            question_data['answers'] = find_question_answers_by_order(soup, subquestion_index)
            questions.append(question_data)
            subquestion_index += 1  # Увеличиваем счетчик только для подвопросов
        else:
            # Основные вопросы (без точки) добавляем для структуры категорий
            question_data['is_main_question'] = True
            questions.append(question_data)
    
    questions = _deduplicate_questions(questions)
    unique_count = len([q for q in questions if not q.get('is_main_question', False)])
    print(f"Найдено вопросов: {unique_count} (уникальных, без дублей)")
    return questions


def extract_question_data(cells):
    """
    Извлекает данные о вопросе из ячеек таблицы
    
    Параметры:
    - cells: список ячеек <td> из HTML таблицы
    
    Возвращает:
    - словарь с данными о вопросе или None, если данные некорректны
    """
    try:
        # Извлекаем данные из каждой ячейки
        question_id = cells[0].get_text(strip=True)  # Номер вопроса (например, "1.1")
        question_type = cells[1].get_text(strip=True)  # Тип вопроса
        question_title = cells[2].get_text(strip=True)  # Название вопроса
        attempts = cells[3].get_text(strip=True)  # Количество попыток
        difficulty = cells[4].get_text(strip=True)  # Индекс легкости
        std_dev = cells[5].get_text(strip=True)  # Стандартное отклонение
        guess_prob = cells[6].get_text(strip=True)  # Вероятность угадывания
        weight = cells[7].get_text(strip=True)  # Предполагаемый вес
        effective_weight = cells[8].get_text(strip=True)  # Эффективный вес
        discrimination = cells[9].get_text(strip=True)  # Индекс дискриминации
        efficiency = cells[10].get_text(strip=True)  # Эффективность дискриминации
        
        # Создаем словарь с данными о вопросе
        question = {
            'id': question_id,
            'type': question_type,
            'title': question_title,
            'attempts': clean_number(attempts),
            'difficulty': clean_percentage(difficulty),
            'discrimination': clean_percentage(discrimination),
            'efficiency': clean_percentage(efficiency),
            'weight': clean_percentage(weight),
            'effective_weight': clean_percentage(effective_weight),
            'std_dev': clean_percentage(std_dev),
            'guess_prob': clean_percentage(guess_prob),
            'answers': []  # Пока пустой список ответов
        }
        
        return question
        
    except Exception as e:
        print(f"Ошибка при извлечении данных: {e}")
        return None


def _get_question_signature(question: Dict[str, Any]) -> str:
    """Подпись вопроса для поиска дубликатов (одинаковые метрики = один вопрос)."""
    def _norm(v):
        if v is None: return ''
        s = str(v).strip().replace(',', '.').replace('%', '')
        try:
            return f"{float(s):.2f}"
        except (ValueError, TypeError):
            return s.lower()
    title = (question.get('title', '') or '').strip().lower()
    return f"{title}|{_norm(question.get('type'))}|{_norm(question.get('attempts'))}|{_norm(question.get('difficulty'))}|{_norm(question.get('std_dev'))}|{_norm(question.get('guess_prob'))}|{_norm(question.get('weight'))}|{_norm(question.get('effective_weight'))}|{_norm(question.get('discrimination'))}|{_norm(question.get('efficiency'))}"


def _deduplicate_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет дубликаты: один и тот же вопрос (5.1, 6.1) показывается один раз с пометкой дублей.
    Возвращает список с полем duplicate_ids и display_id для отображения.
    """
    subqs = [q for q in questions if not q.get('is_main_question', False)]
    main_qs = [q for q in questions if q.get('is_main_question', False)]
    if not subqs:
        return questions
    groups = {}
    for q in subqs:
        sig = _get_question_signature(q)
        if sig not in groups:
            groups[sig] = []
        groups[sig].append(q)
    dedup_subqs = []
    for sig, grp in groups.items():
        rep = grp[0]
        ids = [q['id'] for q in grp]
        rep['duplicate_ids'] = ids[1:] if len(ids) > 1 else []
        rep['display_id'] = f"{ids[0]}" + (f" ({', '.join(ids[1:])})" if len(ids) > 1 else "")
        dedup_subqs.append(rep)
    result = []
    for m in main_qs:
        result.append(m)
    for s in dedup_subqs:
        result.append(s)
    return result


def is_subquestion(question_id):
    """
    Проверяет, является ли вопрос подвопросом
    
    Подвопросы имеют номера вида "1.1", "1.2", "2.1" и т.д.
    Категории имеют номера "1", "2", "3" и т.д.
    
    Параметры:
    - question_id: строка с номером вопроса
    
    Возвращает:
    - True, если это подвопрос
    - False, если это категория
    """
    # Проверяем, есть ли точка в номере
    return '.' in str(question_id)


def clean_percentage(value):
    """
    Очищает процентное значение от лишних символов
    
    Параметры:
    - value: строка с процентом (например, "84,21%")
    
    Возвращает:
    - очищенную строку (например, "84.21")
    """
    if not value or value.strip() == '':
        return '0'
    
    # Убираем пробелы
    value = value.strip()
    
    # Заменяем запятую на точку для корректного преобразования в float
    value = value.replace(',', '.')
    
    # Убираем знак процента
    value = value.replace('%', '')
    
    return value


def clean_number(value):
    """
    Очищает числовое значение
    
    Параметры:
    - value: строка с числом
    
    Возвращает:
    - очищенную строку или '0', если значение пустое
    """
    if not value or value.strip() == '':
        return '0'
    
    return value.strip()


def find_question_text_by_order(soup, question_index):
    """
    Находит полный текст вопроса по его порядковому номеру
    
    Параметры:
    - soup: объект BeautifulSoup для парсинга HTML
    - question_index: порядковый номер вопроса (начиная с 0)
    
    Возвращает:
    - полный текст вопроса или None
    """
    # Ищем все блоки с вопросами
    question_blocks = soup.find_all('div', class_='box py-3 questiontext boxaligncenter generalbox boxwidthnormal mdl-align')
    
    # Проверяем, что у нас есть достаточно вопросов
    if question_index >= len(question_blocks):
        return None
    
    # Получаем блок вопроса по индексу
    question_block = question_blocks[question_index]
    
    # Извлекаем текст вопроса с правильной обработкой
    question_text = clean_question_text(question_block)
    
    return question_text


def clean_question_text(question_block):
    """
    Очищает и форматирует текст вопроса, включая таблицы внутри него
    
    Параметры:
    - question_block: HTML блок с вопросом
    
    Возвращает:
    - очищенный текст вопроса
    """
    # Получаем весь текст из блока, включая таблицы
    # BeautifulSoup автоматически извлечет текст из всех элементов, включая таблицы
    text = question_block.get_text(separator=' ', strip=True)
    
    # Убираем лишние пробелы и переносы строк
    text = ' '.join(text.split())
    
    # Исправляем проблемы с двоеточиями
    text = text.replace(' :', ':')
    text = text.replace(': ', ':')
    text = text.replace(':.', ':')
    text = text.replace(':. ', ': ')
    text = text.replace(': .', ':')
    
    # Исправляем проблемы с числами и символами
    text = text.replace('( ', '(')
    text = text.replace(' )', ')')
    text = text.replace('[ ', '[')
    text = text.replace(' ]', ']')
    
    # Убираем лишние пробелы после исправлений
    text = ' '.join(text.split())
    
    # Исправляем множественные пробелы
    import re
    text = re.sub(r'\s+', ' ', text)
    
    return text


def find_question_answers_by_order(soup, question_index):
    """
    Находит ответы для вопроса по его порядковому номеру
    
    Параметры:
    - soup: объект BeautifulSoup для парсинга HTML
    - question_index: порядковый номер вопроса (начиная с 0)
    
    Возвращает:
    - список ответов с их статистикой
    """
    # Ищем все блоки с вопросами
    question_blocks = soup.find_all('div', class_='box py-3 questiontext boxaligncenter generalbox boxwidthnormal mdl-align')
    
    # Проверяем, что у нас есть достаточно вопросов
    if question_index >= len(question_blocks):
        return []
    
    # Получаем блок вопроса по индексу
    question_block = question_blocks[question_index]
    
    # Ищем все таблицы после блока вопроса
    # Пропускаем таблицы, которые находятся внутри блока вопроса
    # Ищем только таблицу с ответами (таблица с заголовками "Модель ответа", "Фактический ответ" и т.д.)
    all_tables = question_block.find_all_next('table')
    
    for table in all_tables:
        # Проверяем, что таблица не находится внутри блока вопроса
        # Если родительский элемент таблицы - это блок вопроса, пропускаем её
        parent = table.find_parent('div', class_='box py-3 questiontext boxaligncenter generalbox boxwidthnormal mdl-align')
        if parent == question_block:
            # Таблица внутри блока вопроса - пропускаем
            continue
        
        # Проверяем заголовки таблицы, чтобы убедиться, что это таблица с ответами
        headers = table.find_all('th')
        if headers:
            header_texts = [th.get_text(strip=True) for th in headers]
            # Таблица с ответами должна содержать заголовки типа "Модель ответа", "Фактический ответ" и т.д.
            answer_headers = ['Модель ответа', 'Фактический ответ', 'Частичный кредит', 'Частичная оценка', 
                            'Количество', 'Количество ответов', 'Частота', 'Часть вопроса']
            if any(header in header_texts for header in answer_headers):
                # Это таблица с ответами
                answers = extract_answers_from_table(table)
                return answers
    
    return []


def find_question_answers(soup, question_id):
    """
    Находит ответы для конкретного вопроса (старая функция)
    
    Параметры:
    - soup: объект BeautifulSoup для парсинга HTML
    - question_id: ID вопроса (например, "1.1")
    
    Возвращает:
    - список ответов с их статистикой
    """
    answers = []
    
    # Ищем все блоки с вопросами
    question_blocks = soup.find_all('div', class_='box questiontext')
    
    # Счетчик для отслеживания номера вопроса
    question_counter = 0
    
    for block in question_blocks:
        # Получаем текст вопроса
        question_text = block.get_text(strip=True)
        
        # Ищем следующую таблицу после блока вопроса
        answer_table = block.find_next('table')
        
        if answer_table:
            # Извлекаем ответы из таблицы
            table_answers = extract_answers_from_table(answer_table)
            if table_answers:
                # Добавляем номер вопроса к каждому ответу
                for answer in table_answers:
                    answer['question_number'] = question_counter + 1
                answers.extend(table_answers)
        
        question_counter += 1
    
    return answers


def extract_answers_from_table(table):
    """
    Извлекает ответы из таблицы
    
    Параметры:
    - table: HTML таблица с ответами
    
    Возвращает:
    - список ответов с их статистикой
    """
    answers = []
    
    # Получаем заголовки таблицы
    headers = table.find_all('th')
    if not headers:
        return answers
    
    header_texts = [th.get_text(strip=True) for th in headers]
    
    # Получаем все строки таблицы (кроме заголовка)
    rows = table.find_all('tr')[1:]
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < len(headers):
            continue
        
        # Создаем словарь ответа
        answer = {}
        
        for i, header in enumerate(header_texts):
            if i < len(cells):
                value = cells[i].get_text(strip=True)
                answer[header] = value
        
        # Очищаем числовые значения и переименовываем ключи для единообразия
        if 'Количество' in answer:
            answer['Количество'] = clean_number(answer['Количество'])
        if 'Количество ответов' in answer:
            answer['Количество ответов'] = clean_number(answer['Количество ответов'])
        if 'Частота' in answer:
            answer['Частота'] = clean_percentage(answer['Частота'])
        if 'Частичный кредит' in answer:
            answer['Частичный кредит'] = clean_percentage(answer['Частичный кредит'])
        if 'Частичная оценка' in answer:
            answer['Частичная оценка'] = clean_percentage(answer['Частичная оценка'])
        
        # Переименовываем русские ключи в английские для единообразия с data_parser
        rename_map = {
            'Часть вопроса': 'part',
            'Модель ответа': 'model_answer',
            'Фактический ответ': 'actual_answer',
            'Частичный кредит': 'partial_credit',
            'Частичная оценка': 'partial_credit',
            'Количество': 'count',
            'Количество ответов': 'count',
            'Частота': 'frequency',
        }
        
        # Создаем новый словарь с переименованными ключами
        normalized_answer = {}
        for key, value in answer.items():
            new_key = rename_map.get(key, key)
            normalized_answer[new_key] = value
        
        answers.append(normalized_answer)
    
    return answers


def get_test_info(file_content):
    """
    Извлекает общую информацию о тесте из HTML
    
    Параметры:
    - file_content: содержимое HTML файла
    
    Возвращает:
    - словарь с информацией о тесте
    """
    soup = BeautifulSoup(file_content, "html.parser")
    
    # Ищем таблицу с информацией о тесте
    test_info = {}
    
    # Ищем заголовок "Информация о тесте"
    info_header = soup.find('h3', string='Информация о тесте')
    
    if info_header:
        # Ищем следующую таблицу после заголовка
        info_table = info_header.find_next('table')
        
        if info_table:
            # Извлекаем данные из таблицы
            rows = info_table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    test_info[key] = value
    
    return test_info
