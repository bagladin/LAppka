"""
Модуль для построения диаграммы соответствия распределений
"""

import plotly.graph_objects as go
import numpy as np
from typing import List, Dict, Any, Tuple, Optional


def question_difficulty_percent_to_logit(difficulty_percent: float) -> float:
    """
    Преобразует индекс легкости вопроса (facility, 0..100%)
    в логит сложности: b = ln((1-p)/p).
    При такой шкале большие значения соответствуют более сложным вопросам.
    """
    p = np.clip(float(difficulty_percent) / 100.0, 0.01, 0.99)
    return float(np.log((1.0 - p) / p))


def _safe_int(x, default=0):
    try:
        return int(float(str(x).replace(',', '.').replace(' ', '')) or 0)
    except (ValueError, TypeError):
        return default


def _prepare_map_inputs(
    questions_data: List[Dict[str, Any]],
    student_ability_distribution: Optional[List[float]] = None,
    apply_alignment_shift: bool = True,
) -> Tuple[List[float], List[str], List[str], np.ndarray, int]:
    """Готовит данные для диаграммы соответствия."""
    qs = [q for q in questions_data if not q.get('is_main_question', False)]

    difficulties = []
    question_ids = []
    question_types = []

    for question in qs:
        try:
            difficulty = float(question.get('difficulty', 0))
            if 0 < difficulty < 100:
                difficulty_logit = question_difficulty_percent_to_logit(difficulty)
                difficulties.append(float(difficulty_logit))
                qid = question.get('display_id') or question.get('id', '')
                question_ids.append(qid)
                question_types.append(question.get('type', ''))
        except (ValueError, TypeError, ZeroDivisionError):
            continue

    if student_ability_distribution is None:
        abilities = np.array([], dtype=float)
        num_students = 0
    else:
        abilities = np.array([x for x in student_ability_distribution if x is not None], dtype=float)
        abilities = abilities[np.isfinite(abilities)]
        # Опциональная привязка шкалы студентов к шкале сложности вопросов.
        if apply_alignment_shift and difficulties:
            abilities = abilities + float(np.mean(difficulties))
        abilities = np.clip(abilities, -4, 4)
        num_students = int(abilities.size)

    return difficulties, question_ids, question_types, abilities, num_students


def calculate_kstr(
    student_abilities: List[float],
    question_difficulties_logit: List[float],
    bins: int = 20,
    value_range: Tuple[float, float] = (-4, 4),
) -> Dict[str, Any]:
    """
    Коэффициент структурного соответствия распределений.
    КСС = 1 - 0.5 * ∫ |S(x) - Q(x)| dx, где S и Q — плотности распределений.
    """
    abilities = np.array(student_abilities, dtype=float)
    difficulties = np.array(question_difficulties_logit, dtype=float)

    if abilities.size == 0 or difficulties.size == 0:
        return {'kstr': 0.0, 'distance': 1.0}

    s_hist, edges = np.histogram(abilities, bins=bins, range=value_range, density=True)
    q_hist, _ = np.histogram(difficulties, bins=bins, range=value_range, density=True)
    bin_width = (value_range[1] - value_range[0]) / bins

    l1_distance = float(np.sum(np.abs(s_hist - q_hist)) * bin_width)
    kstr = float(max(0.0, min(1.0, 1.0 - 0.5 * l1_distance)))

    deficit = np.maximum(0.0, s_hist - q_hist) * bin_width
    centers = (edges[:-1] + edges[1:]) / 2
    top_idx = np.argsort(deficit)[::-1][:3]
    top_deficit_bins = [
        {
            'center': float(centers[i]),
            'deficit_area': float(deficit[i]),
            'range': (float(edges[i]), float(edges[i + 1])),
        }
        for i in top_idx if deficit[i] > 0
    ]

    return {
        'kstr': kstr,
        'distance': l1_distance,
        'top_deficit_bins': top_deficit_bins,
    }


def _compute_deficit_zones(
    student_abilities: np.ndarray,
    question_difficulties_logit: List[float],
    bins: int = 20,
    value_range: Tuple[float, float] = (-4, 4),
) -> List[Dict[str, Any]]:
    """
    Вычисляет зоны дефицита по оси сложности:
    D(x) = S(x) - Q(x), зоны дефицита там, где D(x) > 0.
    """
    if student_abilities.size == 0 or not question_difficulties_logit:
        return []

    difficulties = np.array(question_difficulties_logit, dtype=float)
    s_hist, edges = np.histogram(student_abilities, bins=bins, range=value_range, density=True)
    q_hist, _ = np.histogram(difficulties, bins=bins, range=value_range, density=True)
    bin_width = (value_range[1] - value_range[0]) / bins

    deficit = np.maximum(0.0, s_hist - q_hist) * bin_width
    max_deficit = float(np.max(deficit)) if deficit.size else 0.0
    if max_deficit <= 0:
        return []

    zones = []
    for i, d in enumerate(deficit):
        if d <= 0:
            continue
        rel = d / max_deficit
        if rel >= 0.66:
            level = "высокий"
        elif rel >= 0.33:
            level = "средний"
        else:
            level = "низкий"
        zones.append({
            'y0': float(edges[i]),
            'y1': float(edges[i + 1]),
            'deficit_area': float(d),
            'relative': float(rel),
            'level': level,
        })
    return zones


def logit_to_difficulty_percent(logit_value: float) -> float:
    """
    Преобразует логит сложности в индекс легкости (facility, 0..100%).
    Обратная функция к b = ln((1-p)/p): p = 1 / (1 + e^b).
    """
    p = 1.0 / (1.0 + np.exp(float(logit_value)))
    return float(p * 100.0)


def classify_difficulty_level_from_logit(logit_value: float) -> str:
    """Классифицирует логит-уровень в категории L/M/H."""
    diff_pct = logit_to_difficulty_percent(logit_value)
    if diff_pct >= 70:
        return 'L'
    if diff_pct >= 40:
        return 'M'
    return 'H'


def _allocate_largest_remainder(weights: Dict[str, float], total: int) -> Dict[str, int]:
    allocation = {k: 0 for k in weights.keys()}
    if total <= 0:
        return allocation

    positive = {k: max(0.0, float(v)) for k, v in weights.items() if float(v) > 0}
    if not positive:
        return allocation

    weight_sum = sum(positive.values())
    if weight_sum <= 0:
        return allocation

    raw = {k: total * (positive[k] / weight_sum) for k in positive}
    floors = {k: int(raw[k]) for k in positive}
    for k in floors:
        allocation[k] = floors[k]

    rest = total - sum(floors.values())
    if rest > 0:
        ranked_frac = sorted(positive.keys(), key=lambda k: raw[k] - floors[k], reverse=True)
        for k in ranked_frac[:rest]:
            allocation[k] += 1

    if sum(allocation.values()) == 0 and total > 0:
        top = max(positive.keys(), key=lambda k: positive[k])
        allocation[top] = total

    return allocation


def _select_active_levels(area_by_level: Dict[str, float], n_total: int) -> List[str]:
    ranked = sorted(area_by_level.items(), key=lambda x: x[1], reverse=True)
    total_area = sum(v for _, v in ranked)
    if total_area <= 0 or not ranked:
        return []

    if n_total <= 4:
        active = [ranked[0][0]]
        if len(ranked) > 1 and (ranked[1][1] / total_area) >= 0.30:
            active.append(ranked[1][0])
        return active

    if n_total <= 7:
        return [lvl for lvl, _ in ranked[:2]]

    active = [lvl for lvl, w in ranked if (w / total_area) >= 0.15]
    if not active:
        active = [ranked[0][0]]
    return active


def build_deficit_recommendation_plan(
    total_questions: int,
    kstr: float,
    deficit_zones: List[Dict[str, Any]],
    total_override: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Формирует план пополнения банка только по дефицитным зонам.
    Возвращает суммарный объём и распределение по L/M/H.
    """
    zones = deficit_zones or []
    area_by_level = {'L': 0.0, 'M': 0.0, 'H': 0.0}
    relative_by_level = {'L': [], 'M': [], 'H': []}

    for z in zones:
        y0 = float(z.get('y0', 0.0))
        y1 = float(z.get('y1', 0.0))
        center = (y0 + y1) / 2.0
        lvl = classify_difficulty_level_from_logit(center)
        area_by_level[lvl] += float(z.get('deficit_area', 0.0))
        relative_by_level[lvl].append(float(z.get('relative', 0.0)))

    total_deficit_area = sum(area_by_level.values())
    if total_deficit_area <= 0:
        return {
            'total': 0,
            'counts': {'L': 0, 'M': 0, 'H': 0},
            'areas': area_by_level,
            'mean_relative': {'L': 0.0, 'M': 0.0, 'H': 0.0},
        }

    if total_override is not None:
        n_total = max(0, int(total_override))
    else:
        base_ratio = 0.08 if kstr >= 0.80 else (0.10 if kstr >= 0.60 else 0.12)
        n_total = max(3, int(round(base_ratio * max(int(total_questions), 1))))
    active_levels = _select_active_levels(area_by_level, n_total)
    active_weights = {lvl: (area_by_level[lvl] if lvl in active_levels else 0.0) for lvl in area_by_level}
    counts = _allocate_largest_remainder(active_weights, n_total)

    mean_relative = {}
    for lvl in ['L', 'M', 'H']:
        vals = relative_by_level[lvl]
        mean_relative[lvl] = float(sum(vals) / len(vals)) if vals else 0.0

    return {
        'total': n_total,
        'counts': counts,
        'areas': area_by_level,
        'mean_relative': mean_relative,
    }


def add_deficit_zone_overlay(
    fig: go.Figure,
    student_abilities: np.ndarray,
    question_difficulties_logit: List[float],
) -> None:
    """Добавляет полупрозрачную красную заливку зон дефицита."""
    zones = _compute_deficit_zones(student_abilities, question_difficulties_logit)
    if not zones:
        return

    for z in zones:
        alpha = 0.08 + 0.22 * z['relative']  # от слабой до заметной
        fig.add_hrect(
            y0=z['y0'],
            y1=z['y1'],
            fillcolor=f"rgba(220, 53, 69, {alpha:.3f})",
            line_width=0,
            layer="below",
        )


def create_person_item_map(questions_data: List[Dict[str, Any]], 
                          student_ability_distribution: Optional[List[float]] = None,
                          apply_alignment_shift: bool = True,
                          highlight_rework: bool = False,
                          rework_question_ids: Optional[set] = None) -> go.Figure:
    """
    Создает диаграмму соответствия распределений
    
    Параметры:
    - questions_data: список данных о вопросах
    - student_ability_distribution: распределение способностей студентов (опционально)
    
    Возвращает:
    - Plotly график диаграммы соответствия
    """
    
    difficulties, question_ids, question_types, abilities, _ = _prepare_map_inputs(
        questions_data,
        student_ability_distribution=student_ability_distribution,
        apply_alignment_shift=apply_alignment_shift,
    )
    
    # Создаем график
    fig = go.Figure()

    # Подсветка дефицитных зон и левая часть доступны только при наличии данных студентов.
    if abilities.size > 0:
        add_deficit_zone_overlay(fig, abilities, difficulties)
        add_student_distribution(fig, abilities.tolist())
    
    # Добавляем распределение сложности вопросов (правая сторона)
    add_question_distribution(
        fig,
        difficulties,
        question_ids,
        question_types,
        highlight_rework=highlight_rework,
        rework_question_ids=rework_question_ids or set(),
    )
    
    # Настраиваем макет
    fig.update_layout(
        title={
            'text': 'Диаграмма соответствия распределений: студенты и банк вопросов',
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
            title="Логит-шкала подготовленности и сложности",
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


def create_distribution_alignment_metrics(
    questions_data: List[Dict[str, Any]],
    student_ability_distribution: Optional[List[float]] = None,
    apply_alignment_shift: bool = True,
) -> Dict[str, Any]:
    """Метрики соответствия распределений для визуализации модуля 2."""
    difficulties, _, _, abilities, num_students = _prepare_map_inputs(
        questions_data,
        student_ability_distribution=student_ability_distribution,
        apply_alignment_shift=apply_alignment_shift,
    )
    if abilities.size == 0 or not difficulties:
        return {
            'kstr': 0.0,
            'distance': 1.0,
            'top_deficit_bins': [],
            'deficit_zones': [],
            'num_students': num_students,
            'has_student_data': abilities.size > 0,
        }
    kstr_data = calculate_kstr(abilities.tolist(), difficulties)
    deficit_zones = _compute_deficit_zones(abilities, difficulties)
    return {
        'kstr': kstr_data.get('kstr', 0.0),
        'distance': kstr_data.get('distance', 1.0),
        'top_deficit_bins': kstr_data.get('top_deficit_bins', []),
        'deficit_zones': deficit_zones,
        'num_students': num_students,
        'has_student_data': True,
    }


def add_student_distribution(fig: go.Figure, abilities: List[float]) -> None:
    """
    Добавляет распределение подготовленности студентов на график
    (по данным загруженного журнала оценок).
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
        name='Выборка по журналу оценок',
        marker=dict(
            color='lightblue',
            line=dict(color='blue', width=1)
        ),
        hovertemplate='<b>Выборка по журналу оценок</b><br>Число в интервале: %{customdata}<br>Логит-уровень: %{y:.2f}<extra></extra>',
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
        hovertemplate=f'<b>Средний логит-уровень</b><br>Значение: {mean_ability:.2f}<extra></extra>'
    ))
    
    # Маркеры ±SD убраны по запросу: оставляем только средний уровень.


def add_question_distribution(fig: go.Figure, difficulties: List[float], 
                            question_ids: List[str], question_types: List[str],
                            highlight_rework: bool = False,
                            rework_question_ids: Optional[set] = None) -> None:
    """
    Добавляет распределение сложности вопросов на график.
    Для каждого типа вопросов — своя вертикальная «ось» (x-смещение), чтобы снизить перекрытие.
    """
    type_colors = {
        'Числовой ответ': 'red',
        'Короткий ответ': 'darkorange',
        'Множественный выбор': 'green',
        'Верно/Неверно': 'blue',
        'На соответствие': 'steelblue',  # Отличается от darkorange (короткий ответ)
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

        if highlight_rework and rework_question_ids:
            rw_y = []
            rw_text = []
            for d, qid in zip(type_difficulties, type_ids):
                if str(qid) in rework_question_ids:
                    rw_y.append(d)
                    rw_text.append(qid)
            if rw_y:
                fig.add_trace(go.Scatter(
                    x=[x_position] * len(rw_y),
                    y=rw_y,
                    mode='markers',
                    marker=dict(
                        symbol='x',
                        size=12,
                        color='crimson',
                        line=dict(width=2, color='darkred')
                    ),
                    name='На переработку',
                    showlegend=(i == 0),
                    hovertemplate='<b>Вопрос на переработку</b><br>ID: %{customdata}<br>Сложность: %{y:.2f}<extra></extra>',
                    customdata=rw_text,
                ))


def create_irt_summary_stats(questions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Создает сводную статистику для анализа распределений.
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
            difficulties_logit.append(question_difficulty_percent_to_logit(d))
    
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
    
    # Цветовая схема для типов вопросов (совпадает с основной диаграммой)
    type_colors = {
        'Числовой ответ': 'red',
        'Короткий ответ': 'darkorange',
        'Множественный выбор': 'green',
        'Верно/Неверно': 'blue',
        'На соответствие': 'steelblue',
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
