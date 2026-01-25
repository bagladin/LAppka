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
    
    # Извлекаем данные о сложности вопросов
    difficulties = []
    question_ids = []
    question_types = []
    
    for question in questions_data:
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
                question_ids.append(question.get('id', ''))
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
    Добавляет распределение способностей студентов на график
    """
    # Создаем гистограмму способностей
    hist, bin_edges = np.histogram(abilities, bins=20, range=(-4, 4))
    
    # Добавляем гистограмму (левая сторона)
    fig.add_trace(go.Bar(
        x=[-0.3] * len(hist),
        y=bin_edges[:-1],
        width=0.2,
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
    Добавляет распределение сложности вопросов на график
    """
    # Группируем вопросы по типам для разных цветов
    type_colors = {
        'Числовой ответ': 'red',
        'Множественный выбор': 'green', 
        'На соответствие': 'orange',
        'Выбор пропущенных слов': 'purple'
    }
    
    # Создаем scatter plot для вопросов
    for q_type in set(question_types):
        # Пропускаем "случайный" - это не тип вопроса, а способ выбора вопроса из категории
        if q_type.lower() in ['случайный', 'случайный вопрос', 'random', '']:
            continue
        if q_type in type_colors:
            type_difficulties = [d for d, t in zip(difficulties, question_types) if t == q_type]
            type_ids = [id for id, t in zip(question_ids, question_types) if t == q_type]
            
            # Определяем позицию выноски в зависимости от типа вопроса
            if q_type in ['На соответствие', 'Числовой ответ']:
                text_position = 'middle left'
                x_position = 0.3
            else:  # 'Множественный выбор', 'Выбор пропущенных слов'
                text_position = 'middle right'
                x_position = 0.3
            
            fig.add_trace(go.Scatter(
                x=[x_position] * len(type_difficulties),
                y=type_difficulties,
                mode='markers+text',
                marker=dict(
                    symbol='circle',
                    size=8,
                    color=type_colors[q_type],
                    line=dict(width=1, color='black')
                ),
                text=type_ids,
                textposition=text_position,
                name=q_type,
                hovertemplate='<b>Question %{text}</b><br>Type: ' + q_type + '<br>Difficulty: %{y:.2f}<extra></extra>'
            ))


def create_irt_summary_stats(questions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Создает сводную статистику для IRT анализа
    
    Параметры:
    - questions_data: список данных о вопросах
    
    Возвращает:
    - словарь со статистикой
    """
    difficulties = []
    discriminations = []
    
    for question in questions_data:
        try:
            difficulty = float(question.get('difficulty', 0))
            discrimination = float(question.get('discrimination', 0))
            
            if difficulty > 0:
                difficulties.append(difficulty)
                discriminations.append(discrimination)
        except (ValueError, TypeError):
            continue
    
    if not difficulties:
        return {}
    
    # Преобразуем в логит-шкалу безопасно
    difficulties_logit = []
    for d in difficulties:
        p = d / 100
        p = np.clip(p, 0.01, 0.99)  # Ограничиваем значения
        logit = np.log(p / (1 - p))
        difficulties_logit.append(logit)
    
    stats = {
        'total_questions': len(difficulties),
        'difficulty_mean': np.mean(difficulties),
        'difficulty_std': np.std(difficulties),
        'difficulty_logit_mean': np.mean(difficulties_logit),
        'difficulty_logit_std': np.std(difficulties_logit),
        'discrimination_mean': np.mean(discriminations),
        'discrimination_std': np.std(discriminations),
        'easy_questions': len([d for d in difficulties if d > 80]),
        'medium_questions': len([d for d in difficulties if 40 <= d <= 80]),
        'hard_questions': len([d for d in difficulties if d < 40])
    }
    
    return stats


def create_difficulty_by_type_boxplot(questions_data: List[Dict[str, Any]]) -> go.Figure:
    """
    Создает boxplot распределения сложности по типам вопросов
    
    Параметры:
    - questions_data: список данных о вопросах
    
    Возвращает:
    - Plotly график boxplot
    """
    # Собираем данные по типам вопросов
    type_difficulties = {}
    
    for question in questions_data:
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
    
    # Цветовая схема для типов вопросов
    type_colors = {
        'Числовой ответ': 'red',
        'Множественный выбор': 'green', 
        'На соответствие': 'orange',
        'Выбор пропущенных слов': 'purple'
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
