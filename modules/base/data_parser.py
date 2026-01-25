"""
Модуль парсинга данных
Отвечает за извлечение и структурирование данных из загруженных файлов
"""

import pandas as pd
from utils.helpers import safe_int, safe_float


def parse_question_data(data):
    """Умный парсинг данных о вопросах из CSV или HTML"""
    questions = []
    
    # Если это HTML данные (список словарей с полными данными)
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        # Проверяем, есть ли уже готовые данные из HTML парсера
        if 'id' in data[0] and 'type' in data[0] and 'title' in data[0]:
            # Это уже обработанные данные из HTML парсера
            return data
        elif 'question' in data[0]:
            # Это старый формат HTML данных
            for i, item in enumerate(data, 1):
                question = {
                    'id': str(i),
                    'type': 'HTML',
                    'title': item.get('question', ''),
                    'attempts': 0,
                    'difficulty': '0',
                    'discrimination': '0',
                    'efficiency': '0',
                    'weight': '0',
                    'effective_weight': '0',
                    'std_dev': '0',
                    'guess_prob': '0',
                    'answers': item.get('answers', [])
                }
                questions.append(question)
            return questions
    
    # Если это CSV данные (DataFrame) без заголовка
    if isinstance(data, pd.DataFrame):
        data = data.fillna('')
        # Первую строку с заголовками находим по совпадениям
        header_row_idx = None
        for i, row in data.iterrows():
            row_vals = [str(v) for v in row.values]
            norm = ' '.join(row_vals).lower()
            if ('№' in row_vals[0] or '№' in ''.join(row_vals)) and 'тип вопроса' in norm and 'название вопроса' in norm:
                header_row_idx = i
                break
        if header_row_idx is None:
            return questions
            
        # Построим индекс колонок по заголовку
        headers = [str(v) for v in data.iloc[header_row_idx].values]
        
        # Построим карту "нормализованное имя" -> оригинал для устойчивых запросов
        def norm_name(s: str) -> str:
            txt = str(s)
            # нормализуем пробелы и неразрывные пробелы
            txt = txt.replace('\xa0', ' ').replace('\u00a0', ' ')
            txt = txt.replace('"', '').replace("'", '')
            txt = ' '.join(txt.split())  # схлопываем повторные пробелы
            return txt.lower().strip()
            
        col_map = {norm_name(c): idx for idx, c in enumerate(headers)}
        
        def pick_col(*aliases):
            # 1) точное совпадение нормализованного имени
            for a in aliases:
                n = norm_name(a)
                if n in col_map:
                    return col_map[n]
            # 2) частичное совпадение по подстрокам
            def find_by_tokens(*tokens):
                tokens_n = [norm_name(t) for t in tokens]
                for k_norm, original in col_map.items():
                    if all(t in k_norm for t in tokens_n):
                        return original
                return None
            # Попытки подобрать по ключевым словам
            fallback = None
            if not fallback and any('тип' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('тип','вопрос')
            if not fallback and any('назв' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('назв','вопрос')
            if not fallback and any('попыт' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('попыт')
            if not fallback and any('легк' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('индекс','легк')
            if not fallback and any('дискр' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('дискр')
            if not fallback and any('эффект' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('эффект','дискр')
            if not fallback and any('предполагаемый вес' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('предполагаем','вес')
            if not fallback and any('эффективный вес' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('эффективн','вес')
            if not fallback and any('стандартное отклонение' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('стандартн','отклон')
            if not fallback and any('угадыв' in norm_name(a) for a in aliases):
                fallback = find_by_tokens('угадыв')
            return fallback

        num_col = pick_col('№', 'no', 'n') or 0
        type_col = pick_col('тип вопроса')
        title_col = pick_col('название вопроса')
        attempts_col = pick_col('попытки')
        idx_easy_col = pick_col('индекс легкости')
        idx_disc_col = pick_col('индекс дискриминации')
        eff_disc_col = pick_col('эффективность дискриминации')
        weight_col = pick_col('предполагаемый вес')
        eff_weight_col = pick_col('эффективный вес')
        std_col = pick_col('стандартное отклонение')
        guess_col = pick_col('вероятность угадывания')
        
        # Находим строки с вопросами (только подвопросы 1.1, 1.2, ...), до первой секции ответов
        for r in range(header_row_idx + 1, len(data)):
            row = data.iloc[r]
            raw_first_col = str(row.values[num_col]) if num_col is not None else ''
            # Стоп, если началась секция ответов
            if (str(raw_first_col) == 'Модель ответа' or 'Модель ответа' in str(row.values)
                or 'Часть вопроса' in str(row.values)):
                break

            if pd.isna(raw_first_col) or raw_first_col == '':
                continue

            question_id_str = str(raw_first_col).strip()

            # Берем только подвопросы (с точкой), родительские "1","2" пропускаем
            if (question_id_str.replace('.', '').isdigit() and '.' in question_id_str):
                def safe_get_value(value, default=''):
                    if pd.isna(value) or value == '' or value is None:
                        return default
                    return str(value)

                def clean_percentage(value):
                    if pd.isna(value) or value == '' or value is None:
                        return '0'
                    return str(value).replace('%', '').replace(',', '.')

                question = {
                    'id': question_id_str,
                    'type': safe_get_value(row.values[type_col] if type_col is not None else ''),
                    'title': safe_get_value(row.values[title_col] if title_col is not None else ''),
                    'attempts': safe_int(safe_get_value(row.values[attempts_col] if attempts_col is not None else '0', '0')),
                    'difficulty': clean_percentage(row.values[idx_easy_col] if idx_easy_col is not None else '0'),
                    'discrimination': clean_percentage(row.values[idx_disc_col] if idx_disc_col is not None else '0'),
                    'efficiency': clean_percentage(row.values[eff_disc_col] if eff_disc_col is not None else '0'),
                    'weight': clean_percentage(row.values[weight_col] if weight_col is not None else '0'),
                    'effective_weight': clean_percentage(row.values[eff_weight_col] if eff_weight_col is not None else '0'),
                    'std_dev': clean_percentage(row.values[std_col] if std_col is not None else '0'),
                    'guess_prob': clean_percentage(row.values[guess_col] if guess_col is not None else '0'),
                    'answers': []
                }
                questions.append(question)
    
    return questions


def parse_answers_data(data):
    """Парсинг данных об ответах из CSV файла по повторяющимся блокам заголовков."""
    answers_data = []

    if not isinstance(data, pd.DataFrame):
        return answers_data

    current_block = []
    header_positions = None  # индексы колонок для нужных полей в текущем блоке

    def flush_block():
        nonlocal current_block
        if current_block:
            answers_data.append(current_block)
            current_block = []

    for _, row in data.iterrows():
        cells = list(row.values)
        cells_str = ["" if pd.isna(v) else str(v) for v in cells]

        # Новый заголовок блока?
        if ('Модель ответа' in cells_str and 'Частота' in cells_str) or ('Часть вопроса' in cells_str and 'Частота' in cells_str):
            # Сбрасываем предыдущий блок
            flush_block()
            # Определяем позиции по текущей строке-заголовку
            header_positions = {
                'part': cells_str.index('Часть вопроса') if 'Часть вопроса' in cells_str else None,
                'model': cells_str.index('Модель ответа') if 'Модель ответа' in cells_str else None,
                'actual': cells_str.index('Фактический ответ') if 'Фактический ответ' in cells_str else None,
                'credit': cells_str.index('Частичный кредит') if 'Частичный кредит' in cells_str else (cells_str.index('Частичная оценка') if 'Частичная оценка' in cells_str else None),
                'count': cells_str.index('Количество ответов') if 'Количество ответов' in cells_str else (cells_str.index('Количество') if 'Количество' in cells_str else None),
                'freq': cells_str.index('Частота') if 'Частота' in cells_str else None,
            }
            continue

        # Внутри блока: читаем строки данных
        if header_positions and any(idx is not None for idx in [header_positions.get('model'), header_positions.get('count'), header_positions.get('freq')]):
            def get_at(pos):
                if pos is None:
                    return ''
                if pos < 0 or pos >= len(cells_str):
                    return ''
                return cells_str[pos]

            model_answer = get_at(header_positions.get('model'))
            part_val = get_at(header_positions.get('part'))
            # Пустые строки пропускаем
            if model_answer == '' and part_val == '':
                continue

            answer = {
                'model_answer': model_answer,
                'actual_answer': get_at(header_positions.get('actual')),
                'partial_credit': get_at(header_positions.get('credit')),
                'count': get_at(header_positions.get('count')),
                'frequency': get_at(header_positions.get('freq')),
            }
            if header_positions.get('part') is not None:
                answer['part'] = part_val
            current_block.append(answer)

    # Финальный блок
    flush_block()

    return answers_data
