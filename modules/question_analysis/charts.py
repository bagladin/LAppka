"""
Графики для модуля анализа вопросов
"""

from typing import List, Dict, Any
import numpy as np
import plotly.graph_objects as go


def _safe_metric(value, default=0.0):
    """Приведение к float (поддержка запятой и %)."""
    if value is None:
        return default
    s = str(value).replace(',', '.').replace('%', '').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def create_difficulty_distribution_plot(questions_data: List[Dict[str, Any]], question_type_filter: str = None):
    """
    Создаёт два графика «Распределение вопросов по категориям»:
    - Слева: количество вопросов (подвопросов) в категории.
    - Справа: средняя сложность, средний индекс дискриминации, средняя эффективность дискриминации (три столбика).
    Логика пропуска столбиков для «тянущих» категорий сохраняется.
    
    Параметры:
    - questions_data: список данных о вопросах
    - question_type_filter: фильтр по типу (None — все типы)
    
    Возвращает:
    - (fig_left, fig_right) — две фигуры Plotly
    """
    # Сначала собираем ВСЕ категории из всех вопросов (без фильтрации)
    # Это нужно для правильного определения помеченных категорий и для оси X
    all_categories = {}  # category_id -> {'questions': [], 'difficulties': [], 'main_questions': [], 'main_question_ids': []}
    
    for question in questions_data:
        try:
            question_id = str(question.get('id', ''))
            if not question_id:
                continue
            
            # Определяем категорию: берем основную часть ID (до точки)
            if '.' in question_id:
                category_id = question_id.split('.')[0]
                is_main_question = False
            else:
                category_id = question_id
                is_main_question = True
            
            # Инициализируем категорию, если её еще нет
            if category_id not in all_categories:
                all_categories[category_id] = {
                    'questions': [],
                    'difficulties': [],
                    'main_questions': [],
                    'main_question_ids': []
                }
            
            all_categories[category_id]['questions'].append(question_id)
            
            try:
                difficulty = float(question.get('difficulty', 0))
                all_categories[category_id]['difficulties'].append(difficulty)
            except (ValueError, TypeError):
                all_categories[category_id]['difficulties'].append(0)
            
            if is_main_question:
                all_categories[category_id]['main_questions'].append(question_id)
                all_categories[category_id]['main_question_ids'].append(question_id)
        except (ValueError, TypeError):
            continue
    
    if not all_categories:
        return go.Figure(), go.Figure()
    
    # Теперь фильтруем вопросы по типу для данных столбиков
    filtered_questions = questions_data
    if question_type_filter and question_type_filter != "Все":
        filtered_questions = [q for q in questions_data if q.get('type', '') == question_type_filter]
    
    # Группируем отфильтрованные вопросы по категориям (для данных столбиков)
    categories = {}  # category_id -> {'questions': [], 'difficulties': [], 'main_questions': [], 'main_question_ids': []}
    
    for question in filtered_questions:
        try:
            question_id = str(question.get('id', ''))
            difficulty = float(question.get('difficulty', 0))
            
            # Пропускаем только если нет ID или difficulty некорректное (но не 0, т.к. 0% - это валидная сложность)
            if not question_id:
                continue
            
            # Проверяем, что difficulty - это число (может быть 0, но должно быть числом)
            try:
                float(difficulty)
            except (ValueError, TypeError):
                continue
            
            # Определяем категорию: берем основную часть ID (до точки)
            # "1.1" -> "1", "3.2" -> "3", "10" -> "10"
            if '.' in question_id:
                category_id = question_id.split('.')[0]
                is_main_question = False  # Это подвопрос
            else:
                category_id = question_id
                is_main_question = True  # Это основной вопрос категории
            
            # Инициализируем категорию, если её еще нет
            if category_id not in categories:
                categories[category_id] = {
                    'questions': [],
                    'difficulties': [],
                    'discriminations': [],
                    'efficiencies': [],
                    'main_questions': [],
                    'main_question_ids': []
                }
            
            categories[category_id]['questions'].append(question_id)
            categories[category_id]['difficulties'].append(difficulty)
            categories[category_id]['discriminations'].append(_safe_metric(question.get('discrimination')))
            categories[category_id]['efficiencies'].append(_safe_metric(question.get('efficiency')))
            
            if is_main_question:
                categories[category_id]['main_questions'].append(question_id)
                categories[category_id]['main_question_ids'].append(question_id)
            
        except (ValueError, TypeError):
            continue
    
    # Определяем категории с двумя и более подряд основными вопросами
    # Используем all_categories для определения помеченных категорий (все вопросы, без фильтрации)
    def sort_key(x):
        try:
            return float(x)
        except ValueError:
            return 0
    
    # Сортируем все категории (из всех вопросов) для определения помеченных
    sorted_all_cat_ids = sorted(all_categories.keys(), key=sort_key)
    marked_categories = set()
    
    # Проверяем последовательности из двух и более подряд категорий с основными вопросами
    i = 0
    while i < len(sorted_all_cat_ids) - 1:
        # Начинаем последовательность с текущей категории
        sequence_start = i
        sequence_length = 1
        
        # Проверяем, что текущая категория содержит только основные вопросы
        try:
            current_num = float(sorted_all_cat_ids[i])
            current_cat = sorted_all_cat_ids[i]
            current_only_main = (len(all_categories[current_cat]['main_questions']) > 0 and 
                               len(all_categories[current_cat]['main_questions']) == len(all_categories[current_cat]['questions']))
            
            if current_only_main:
                # Ищем последовательность подряд идущих категорий с основными вопросами
                j = i + 1
                while j < len(sorted_all_cat_ids):
                    try:
                        next_num = float(sorted_all_cat_ids[j])
                        next_cat = sorted_all_cat_ids[j]
                        
                        # Проверяем, что номер идет подряд
                        if next_num == current_num + sequence_length:
                            next_only_main = (len(all_categories[next_cat]['main_questions']) > 0 and 
                                            len(all_categories[next_cat]['main_questions']) == len(all_categories[next_cat]['questions']))
                            
                            if next_only_main:
                                sequence_length += 1
                                current_num = next_num
                            else:
                                break
                        else:
                            break
                    except ValueError:
                        break
                    j += 1
                
                # Если нашли последовательность из двух и более, помечаем все категории
                if sequence_length >= 2:
                    for k in range(sequence_start, sequence_start + sequence_length):
                        marked_categories.add(sorted_all_cat_ids[k])
                    i = sequence_start + sequence_length
                    continue
                
                # Дополнительная проверка: если текущая категория содержит только основные вопросы
                # и следующая категория имеет подвопросы (т.е. "тянет" вопросы из следующей категории)
                if current_only_main and j < len(sorted_all_cat_ids):
                    try:
                        next_num = float(sorted_all_cat_ids[j])
                        next_cat = sorted_all_cat_ids[j]
                        
                        # Проверяем, что следующая категория идет подряд и имеет подвопросы
                        if next_num == current_num + 1:
                            next_has_subquestions = (len(all_categories[next_cat]['main_questions']) < 
                                                    len(all_categories[next_cat]['questions']))
                            
                            # Если следующая категория имеет подвопросы, помечаем текущую
                            if next_has_subquestions:
                                marked_categories.add(current_cat)
                    except (ValueError, IndexError):
                        pass
        except ValueError:
            pass
        
        i += 1
    
    # Подготавливаем данные для обоих графиков
    category_ids = sorted_all_cat_ids
    question_counts = []
    avg_difficulties = []
    avg_discriminations = []
    avg_efficiencies = []
    colors_count = []
    colors_metrics = []  # для правого графика (одна заливка на след не используется)

    for cat_id in category_ids:
        if cat_id in categories:
            cat_data = categories[cat_id]
            subquestions = [q for q in cat_data['questions'] if '.' in q]
            sub_diffs, sub_discs, sub_effs = [], [], []
            for q_id, diff, disc, eff in zip(
                cat_data['questions'],
                cat_data['difficulties'],
                cat_data['discriminations'],
                cat_data['efficiencies']
            ):
                if '.' in q_id:
                    sub_diffs.append(diff)
                    sub_discs.append(disc)
                    sub_effs.append(eff)
            num_subquestions = len(subquestions)
        else:
            num_subquestions = 0
            sub_diffs, sub_discs, sub_effs = [], [], []

        if cat_id in marked_categories:
            question_counts.append(None)
            avg_difficulties.append(None)
            avg_discriminations.append(None)
            avg_efficiencies.append(None)
            colors_count.append('rgba(0,0,0,0)')
        else:
            question_counts.append(num_subquestions if num_subquestions > 0 else 0)
            avg_difficulties.append(float(np.mean(sub_diffs)) if sub_diffs else 0)
            avg_discriminations.append(float(np.mean(sub_discs)) if sub_discs else 0)
            avg_efficiencies.append(float(np.mean(sub_effs)) if sub_effs else 0)
            colors_count.append('#3498db')

    # Тексты для тултипов и подписей
    texts_count = [str(c) if c is not None and c > 0 else '' for c in question_counts]
    texts_diff = [f'{v:.1f}' if v is not None and v > 0 else '' for v in avg_difficulties]
    texts_disc = [f'{v:.2f}' if v is not None else '' for v in avg_discriminations]
    texts_eff = [f'{v:.1f}' if v is not None and v > 0 else '' for v in avg_efficiencies]

    ann = []
    if marked_categories:
        ann = [dict(
            text="Пропуск столбиков: категория тянет вопросы из следующей категории",
            xref="paper", yref="paper", x=0.5, y=-0.12,
            showarrow=False, font=dict(size=10, color="#7f8c8d")
        )]

    valid_counts = [c for c in question_counts if c is not None and c >= 0]
    valid_metrics = [v for v in avg_difficulties + avg_discriminations + avg_efficiencies if v is not None and v >= 0]
    y_max_count = max(valid_counts) * 1.15 if valid_counts else 1
    y_max_metrics = max(max(valid_metrics) * 1.1, 100) if valid_metrics else 100

    # ---- Левый график: количество вопросов ----
    fig_left = go.Figure()
    fig_left.add_trace(go.Bar(
        name='Количество вопросов',
        x=category_ids,
        y=question_counts,
        marker_color=colors_count,
        text=texts_count,
        textposition='outside',
        hovertemplate='<b>Категория %{x}</b><br>Количество вопросов: %{y}<extra></extra>'
    ))
    fig_left.update_layout(
        title=dict(text='Количество вопросов по категориям', x=0.5, xanchor='center'),
        xaxis=dict(title='Категория вопроса', type='category'),
        yaxis=dict(title='Количество вопросов', range=[0, y_max_count], tickformat='.0f'),
        barmode='group',
        width=450,
        height=500,
        showlegend=False,
        margin=dict(l=50, r=30, t=60, b=60),
        annotations=ann
    )

    # ---- Правый график: средняя сложность, средняя дискриминация, средняя эффективность ----
    fig_right = go.Figure()
    fig_right.add_trace(go.Bar(
        name='Средняя сложность (%)',
        x=category_ids,
        y=avg_difficulties,
        offsetgroup=1,
        marker_color='#e74c3c',
        text=texts_diff,
        textposition='outside',
        hovertemplate='<b>Категория %{x}</b><br>Средняя сложность: %{y:.1f}%<extra></extra>'
    ))
    fig_right.add_trace(go.Bar(
        name='Сред. индекс дискриминации',
        x=category_ids,
        y=avg_discriminations,
        offsetgroup=2,
        marker_color='#2ecc71',
        text=texts_disc,
        textposition='outside',
        hovertemplate='<b>Категория %{x}</b><br>Сред. индекс дискриминации: %{y:.2f}<extra></extra>'
    ))
    fig_right.add_trace(go.Bar(
        name='Сред. эффективность дискриминации',
        x=category_ids,
        y=avg_efficiencies,
        offsetgroup=3,
        marker_color='#f39c12',
        text=texts_eff,
        textposition='outside',
        hovertemplate='<b>Категория %{x}</b><br>Сред. эффективность дискриминации: %{y:.1f}<extra></extra>'
    ))
    fig_right.update_layout(
        title=dict(text='Средние показатели по категориям', x=0.5, xanchor='center'),
        xaxis=dict(title='Категория вопроса', type='category'),
        yaxis=dict(title='Средние показатели', range=[0, y_max_metrics], tickformat='.1f'),
        barmode='group',
        width=450,
        height=500,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        margin=dict(l=50, r=30, t=60, b=60),
        annotations=ann
    )

    return fig_left, fig_right
