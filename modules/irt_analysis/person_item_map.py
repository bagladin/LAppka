"""
Модуль для построения Person-Item Map в IRT анализе
"""

import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
from typing import List, Dict, Any


def create_person_item_map(questions_data: List[Dict[str, Any]], 
                          student_ability_distribution: List[float] = None) -> go.Figure:
    """
    Создает Person-Item Map график для IRT анализа
    
    Параметры:
    - questions_data: список данных о вопросах
    - student_ability_distribution: распределение способностей студентов (опционально)
    
    Возвращает:
    - Plotly график Person-Item Map
    """
    
    # Берём только подвопросы (без is_main_question) — как в модуле 1
    qs = [q for q in questions_data if not q.get('is_main_question', False)]
    
    difficulties = []
    question_ids = []
    question_types = []
    
    for question in qs:
        try:
            # Преобразуем сложность в логит-шкалу
            difficulty = float(question.get('difficulty', 0))
            if 0 < difficulty < 100:  # Избегаем крайних значений
                # Безопасное преобразование в логит
                p = difficulty / 100
                # Ограничиваем значения для избежания проблем
                p = np.clip(p, 0.01, 0.99)
                difficulty_logit = np.log(p / (1 - p))
                difficulties.append(difficulty_logit)
                # Для дублей показываем display_id (5.1 (6.1)), иначе id
                qid = question.get('display_id') or question.get('id', '')
                question_ids.append(qid)
                question_types.append(question.get('type', ''))
        except (ValueError, TypeError, ZeroDivisionError):
            continue
    
    # Создаем распределение способностей студентов (если не предоставлено)
    if student_ability_distribution is None:
        # Генерируем нормальное распределение на основе данных
        mean_ability = np.mean(difficulties) if difficulties else 0
        std_ability = np.std(difficulties) if difficulties else 1
        student_ability_distribution = np.random.normal(mean_ability, std_ability, 1000)
    
    # Создаем график
    fig = go.Figure()
    
    # Добавляем распределение способностей студентов (левая сторона)
    add_student_distribution(fig, student_ability_distribution)
    
    # Добавляем распределение сложности вопросов (правая сторона)
    add_question_distribution(fig, difficulties, question_ids, question_types)
    
    # Настраиваем макет
    fig.update_layout(
        title={
            'text': 'Person-Item Map (IRT Analysis)',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16}
        },
        xaxis=dict(
            title="",
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[-0.6, 0.6]  # Ограничиваем диапазон по X
        ),
        yaxis=dict(
            title="Ability / Difficulty Scale (Logits)",
            range=[-4, 4],
            tickmode='linear',
            tick0=-4,
            dtick=1,
            showgrid=True,
            gridcolor='lightgray'
        ),
        width=900,  # Увеличиваем ширину
        height=700,  # Увеличиваем высоту
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)  # Добавляем отступы
    )
    
    return fig


def add_student_distribution(fig: go.Figure, abilities: List[float]) -> None:
    """
    Добавляет распределение способностей студентов на график.
    Высота (длина) столбиков пропорциональна количеству студентов в каждом интервале.
    """
    hist, bin_edges = np.histogram(abilities, bins=20, range=(-4, 4))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Масштабируем длину столбиков: max_count -> -0.3 (в пределах оси)
    max_count = max(hist) if hist.size and np.max(hist) > 0 else 1
    bar_lengths = [-h * (0.3 / max_count) for h in hist]
    
    fig.add_trace(go.Bar(
        x=bar_lengths,
        y=bin_centers,
        width=0.15,
        orientation='h',
        name='Students',
        marker=dict(
            color='lightblue',
            line=dict(color='blue', width=1)
        ),
        hovertemplate='<b>Students</b><br>Count: %{customdata}<br>Ability: %{y:.2f}<extra></extra>',
        customdata=hist
    ))
    
    # Добавляем статистические маркеры
    mean_ability = np.mean(abilities)
    std_ability = np.std(abilities)
    
    # Средняя способность
    fig.add_trace(go.Scatter(
        x=[-0.4],
        y=[mean_ability],
        mode='markers+text',
        marker=dict(symbol='diamond', size=12, color='blue'),
        text=['M'],
        textposition='middle left',
        name='Mean',
        showlegend=False,
        hovertemplate=f'<b>Mean Ability</b><br>Value: {mean_ability:.2f}<extra></extra>'
    ))
    
    # Стандартные отклонения
    for i, (offset, label) in enumerate([(1, 'S'), (-1, 'S')]):
        fig.add_trace(go.Scatter(
            x=[-0.4],
            y=[mean_ability + offset * std_ability],
            mode='markers+text',
            marker=dict(symbol='square', size=10, color='darkblue'),
            text=[label],
            textposition='middle left',
            name=f'±{i+1}SD' if i == 0 else None,
            showlegend=i == 0,
            hovertemplate=f'<b>±{i+1} Standard Deviation</b><br>Value: {mean_ability + offset * std_ability:.2f}<extra></extra>'
        ))


def add_question_distribution(fig: go.Figure, difficulties: List[float], 
                            question_ids: List[str], question_types: List[str]) -> None:
    """
    Добавляет распределение сложности вопросов на график.
    Для каждого типа вопросов — своя вертикальная «ось» (x-смещение), чтобы снизить перекрытие.
    """
    type_colors = {
        'Числовой ответ': 'red',
        'Короткий ответ': 'darkorange',
        'Множественный выбор': 'green',
        'Верно/Неверно': 'blue',
        'На соответствие': 'orange',
        'Выбор пропущенных слов': 'purple',
    }
    type_x_offsets = {
        'Числовой ответ': 0.22,
        'Короткий ответ': 0.28,
        'Множественный выбор': 0.34,
        'Верно/Неверно': 0.40,
        'На соответствие': 0.46,
        'Выбор пропущенных слов': 0.52,
    }
    
    valid_types = [t for t in set(question_types) 
                   if t and t.lower() not in ['случайный', 'случайный вопрос', 'random', '']]
    type_order = sorted(valid_types)
    unknown_offset = 0.58
    for i, q_type in enumerate(type_order):
        x_position = type_x_offsets.get(q_type, unknown_offset + i * 0.04)
        color = type_colors.get(q_type, ['teal', 'coral', 'darkviolet', 'saddlebrown'][i % 4])
        
        type_difficulties = [d for d, t in zip(difficulties, question_types) if t == q_type]
        type_ids = [id for id, t in zip(question_ids, question_types) if t == q_type]
        
        if not type_difficulties:
            continue
        
        # Чередование подписей: нечётная ось (i=0,2,...) — слева, чётная (i=1,3,...) — справа
        text_position = 'middle left' if i % 2 == 0 else 'middle right'
        
        fig.add_trace(go.Scatter(
            x=[x_position] * len(type_difficulties),
            y=type_difficulties,
            mode='markers+text',
            marker=dict(
                symbol='circle',
                size=8,
                color=color,
                line=dict(width=1, color='black')
            ),
            text=type_ids,
            textposition=text_position,
            name=q_type,
            hovertemplate='<b>Question %{text}</b><br>Type: ' + q_type + '<br>Difficulty: %{y:.2f}<extra></extra>'
        ))


def create_irt_summary_stats(questions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Создает сводную статистику для IRT анализа.
    total_questions — все подвопросы (без is_main_question).
    easy/medium/hard — по вопросам с difficulty > 0.
    """
    qs = [q for q in questions_data if not q.get('is_main_question', False)]
    difficulties = []
    discriminations = []
    
    for question in qs:
        try:
            difficulty = float(question.get('difficulty', 0))
            discrimination = float(question.get('discrimination', 0))
            
            if difficulty > 0:
                difficulties.append(difficulty)
                discriminations.append(discrimination)
        except (ValueError, TypeError):
            continue
    
    if not qs:
        return {}
    
    # Преобразуем в логит-шкалу (для расчётов; при пустых difficulties — заглушки)
    difficulties_logit = []
    if difficulties:
        for d in difficulties:
            p = np.clip(d / 100, 0.01, 0.99)
            difficulties_logit.append(np.log(p / (1 - p)))
    
    stats = {
        'total_questions': len(qs),  # Фактическое количество (как при импорте в модуле 1)
        'difficulty_mean': float(np.mean(difficulties)) if difficulties else 0,
        'difficulty_std': float(np.std(difficulties)) if difficulties else 0,
        'difficulty_logit_mean': float(np.mean(difficulties_logit)) if difficulties_logit else 0,
        'difficulty_logit_std': float(np.std(difficulties_logit)) if difficulties_logit else 0,
        'discrimination_mean': float(np.mean(discriminations)) if discriminations else 0,
        'discrimination_std': float(np.std(discriminations)) if discriminations else 0,
        'easy_questions': len([d for d in difficulties if d > 80]),
        'medium_questions': len([d for d in difficulties if 40 <= d <= 80]),
        'hard_questions': len([d for d in difficulties if d < 40]),
        'questions_with_valid_difficulty': len(difficulties),
    }
    
    return stats


def create_difficulty_by_type_boxplot(questions_data: List[Dict[str, Any]]) -> go.Figure:
    """
    Создает boxplot распределения сложности по типам вопросов.
    Учитываются только подвопросы (без is_main_question).
    """
    qs = [q for q in questions_data if not q.get('is_main_question', False)]
    type_difficulties = {}
    
    for question in qs:
        try:
            q_type = question.get('type', 'Неизвестный тип')
            difficulty = float(question.get('difficulty', 0))
            
            # Пропускаем некорректные значения
            if difficulty < 0 or difficulty > 100:
                continue
            
            # Пропускаем "случайный" - это не тип вопроса, а способ выбора вопроса из категории
            if q_type.lower() in ['случайный', 'случайный вопрос', 'random']:
                continue
            
            if q_type not in type_difficulties:
                type_difficulties[q_type] = []
            
            type_difficulties[q_type].append(difficulty)
        except (ValueError, TypeError):
            continue
    
    if not type_difficulties:
        return go.Figure()
    
    # Цветовая схема для типов вопросов (совпадает с Person-Item Map)
    type_colors = {
        'Числовой ответ': 'red',
        'Короткий ответ': 'darkorange',
        'Множественный выбор': 'green',
        'Верно/Неверно': 'blue',
        'На соответствие': 'orange',
        'Выбор пропущенных слов': 'purple',
    }
    
    # Создаем boxplot
    fig = go.Figure()
    
    for q_type, difficulties in type_difficulties.items():
        if len(difficulties) > 0:
            # Получаем цвет для типа вопроса или используем серый по умолчанию
            box_color = type_colors.get(q_type, 'gray')
            
            fig.add_trace(go.Box(
                y=difficulties,
                name=q_type,
                boxmean='sd',  # Показываем среднее и стандартное отклонение
                boxpoints=False,  # Не показываем выбросы (ромбики)
                marker_color=box_color,
                hovertemplate=f'<b>{q_type}</b><br>Сложность: %{{y:.1f}}%<extra></extra>'
            ))
    
    fig.update_layout(
        title={
            'text': 'Распределение сложности по типам вопросов',
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis=dict(
            title='Тип вопроса'
        ),
        yaxis=dict(
            title='Сложность (%)',
            range=[0, 100]
        ),
        showlegend=False,
        height=500,
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    return fig
