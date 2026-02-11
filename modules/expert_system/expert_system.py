"""
Экспертная система для анализа IRT данных
Предоставляет интеллектуальные рекомендации на основе статистического анализа
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple

from modules.categorization.moodle_parser import is_open_question_type


# --- KBTB: Коэффициент сбалансированности тестовой базы ---

def _safe_float(x, default=0.0):
    if x is None:
        return default
    try:
        s = str(x).replace(',', '.').replace('%', '').strip()
        return float(s)
    except (ValueError, TypeError):
        return default


def compute_kbtb(
    questions: List[Dict[str, Any]],
    target_type: Dict[str, float],
    target_level: Dict[str, float],
    min_questions: int = 0,
) -> Dict[str, Any]:
    """
    Коэффициент сбалансированности тестовой базы (KBTB).
    target_type: {'O': 40, 'Z': 60} в процентах, сумма 100
    target_level: {'L': 30, 'M': 50, 'H': 20} в процентах, сумма 100
    min_questions: минимальное число вопросов (0 = не учитывать)
    """
    # Нормализуем целевые доли в доли 0…1
    tO = (target_type.get('O', 40) or 40) / 100.0
    tZ = (target_type.get('Z', 60) or 60) / 100.0
    s = tO + tZ
    if s > 0:
        tO, tZ = tO / s, tZ / s
    else:
        tO, tZ = 0.4, 0.6

    tL = (target_level.get('L', 30) or 30) / 100.0
    tM = (target_level.get('M', 50) or 50) / 100.0
    tH = (target_level.get('H', 20) or 20) / 100.0
    s = tL + tM + tH
    if s > 0:
        tL, tM, tH = tL / s, tM / s, tH / s
    else:
        tL, tM, tH = 0.3, 0.5, 0.2

    # Берём только подвопросы (без is_main_question)
    qs = [q for q in questions if not q.get('is_main_question', False)]
    n = len(qs)
    if n == 0:
        return {
            'kbtb': 0.0,
            'interpretation': 'Нет данных для расчёта',
            'penalty_type': 0.0,
            'penalty_level': 0.0,
            'penalty_rework': 0.0,
            'penalty_count': 1.0 if min_questions > 0 else 0.0,
            'actual_type': {'O': 0.0, 'Z': 0.0},
            'actual_level': {'L': 0.0, 'M': 0.0, 'H': 0.0},
            'R': 0.0,
            'n': 0,
            'n_rework': 0,
            'target_type': {'O': tO, 'Z': tZ},
            'target_level': {'L': tL, 'M': tM, 'H': tH},
        }

    # R: «на переделку» — дискриминация < 0.3 или 10% самых лёгких (по difficulty %)
    rework_idx = set()
    for i, q in enumerate(qs):
        d = _safe_float(q.get('discrimination'))
        if d < 0.3:
            rework_idx.add(i)
    # 10% самых лёгких = наибольшие difficulty
    diff_list = [(_safe_float(q.get('difficulty')), i) for i, q in enumerate(qs)]
    diff_list.sort(key=lambda x: (-x[0], x[1]))
    n_top = max(1, int(math.ceil(0.1 * n)))
    for j in range(min(n_top, len(diff_list))):
        rework_idx.add(diff_list[j][1])

    R = len(rework_idx) / n
    non_r = [q for i, q in enumerate(qs) if i not in rework_idx]
    nn = len(non_r)

    # Фактические доли по типам и уровням (на non-R), в 0…1
    if nn == 0:
        aO, aZ = 0.5, 0.5
        aL, aM, aH = tL, tM, tH  # нет данных — не штрафуем по уровню
    else:
        o_count = sum(1 for q in non_r if is_open_question_type(q.get('type', '')))
        aO = o_count / nn
        aZ = 1.0 - aO
        # Уровни: L >= 70, 40 <= M < 70, H < 40
        l_count = sum(1 for q in non_r if _safe_float(q.get('difficulty')) >= 70)
        m_count = sum(1 for q in non_r if 40 <= _safe_float(q.get('difficulty')) < 70)
        h_count = sum(1 for q in non_r if _safe_float(q.get('difficulty')) < 40)
        aL = l_count / nn
        aM = m_count / nn
        aH = h_count / nn

    # D_type = 0.5 * (|aO-tO| + |aZ-tZ|) — в [0,1]
    D_type = 0.5 * (abs(aO - tO) + abs(aZ - tZ))
    # D_level = 0.5 * (|aL-tL| + |aM-tM| + |aH-tH|)
    D_level = 0.5 * (abs(aL - tL) + abs(aM - tM) + abs(aH - tH))
    # P_rework = 1 - exp(-3*R)
    P_rework = 1.0 - math.exp(-3.0 * R)
    # P_count: 0 если n>=min, иначе 1 - n/min
    if min_questions <= 0:
        P_count = 0.0
    else:
        P_count = 0.0 if n >= min_questions else 1.0 - n / min_questions

    w1, w2, w3, w4 = 0.3, 0.3, 0.2, 0.2
    KBTB = 1.0 - w1 * D_type - w2 * D_level - w3 * P_rework - w4 * P_count
    KBTB = max(0.0, min(1.0, KBTB))

    # Интерпретация
    if KBTB >= 0.85:
        interpretation = 'Отлично сбалансировано'
    elif KBTB >= 0.70:
        interpretation = 'Хорошо'
    elif KBTB >= 0.50:
        interpretation = 'Есть перекосы'
    else:
        interpretation = 'Требует переработки'

    return {
        'kbtb': KBTB,
        'interpretation': interpretation,
        'penalty_type': w1 * D_type,
        'penalty_level': w2 * D_level,
        'penalty_rework': w3 * P_rework,
        'penalty_count': w4 * P_count,
        'actual_type': {'O': aO, 'Z': aZ},
        'actual_level': {'L': aL, 'M': aM, 'H': aH},
        'target_type': {'O': tO, 'Z': tZ},
        'target_level': {'L': tL, 'M': tM, 'H': tH},
        'R': R,
        'n': n,
        'n_rework': len(rework_idx),
    }


def analyze_student_ability_distribution(abilities: List[float]) -> Dict[str, Any]:
    """
    Анализирует распределение способностей студентов
    
    Параметры:
    - abilities: список способностей студентов
    
    Возвращает:
    - словарь с анализом распределения
    """
    if not abilities:
        return {}
    
    abilities = np.array(abilities)
    
    # Базовые статистики
    mean_ability = np.mean(abilities)
    std_ability = np.std(abilities)
    median_ability = np.median(abilities)
    
    # Классификация уровней способностей
    low_threshold = mean_ability - std_ability
    high_threshold = mean_ability + std_ability
    
    low_ability = int(np.sum(abilities < low_threshold))
    medium_ability = int(np.sum((abilities >= low_threshold) & (abilities <= high_threshold)))
    high_ability = int(np.sum(abilities > high_threshold))
    
    total_students = len(abilities)
    
    # Анализ распределения
    distribution_analysis = {
        'total_students': total_students,
        'mean_ability': mean_ability,
        'std_ability': std_ability,
        'median_ability': median_ability,
        'low_ability_count': low_ability,
        'medium_ability_count': medium_ability,
        'high_ability_count': high_ability,
        'low_ability_percent': (low_ability / total_students) * 100,
        'medium_ability_percent': (medium_ability / total_students) * 100,
        'high_ability_percent': (high_ability / total_students) * 100,
        'distribution_type': classify_distribution(abilities)
    }
    
    return distribution_analysis


def analyze_question_difficulty_distribution(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Анализирует распределение сложности вопросов
    
    Параметры:
    - questions: список вопросов с данными
    
    Возвращает:
    - словарь с анализом сложности
    """
    if not questions:
        return {}
    
    difficulties = []
    discriminations = []
    question_types = {}
    low_discrimination_questions = []
    low_attempts_questions = []
    min_attempts = 30  # правило Наннали для надёжной статистики
    
    for question in questions:
        try:
            difficulty = float(question.get('difficulty', 0))
            discrimination = float(question.get('discrimination', 0))
            q_type = question.get('type', '')
            q_id = question.get('id', '')
            
            difficulties.append(difficulty)
            discriminations.append(discrimination)
            
            # Подсчет по типам (пропускаем "случайный" - это не тип вопроса, а способ выбора)
            if q_type.lower() not in ['случайный', 'случайный вопрос', 'random', '']:
                if q_type in question_types:
                    question_types[q_type] += 1
                else:
                    question_types[q_type] = 1
            
            # Вопросы с низкой дискриминацией
            if discrimination < 0.3:
                title = question.get('title', '')
                title_preview = title[:150] + '...' if len(title) > 150 else title
                display_id = question.get('display_id') or q_id
                low_discrimination_questions.append({
                    'id': q_id,
                    'display_id': display_id,
                    'type': q_type,
                    'difficulty': difficulty,
                    'discrimination': discrimination,
                    'title': title_preview
                })
            
            # Вопросы с малым числом попыток (ненадёжная статистика)
            try:
                attempts = int(float(str(question.get('attempts', 0)).replace(',', '.').replace(' ', '')) or 0)
                if 0 < attempts < min_attempts:
                    display_id_att = question.get('display_id') or q_id
                    low_attempts_questions.append({'display_id': display_id_att, 'attempts': attempts})
            except (ValueError, TypeError):
                pass
                
        except (ValueError, TypeError):
            continue
    
    if not difficulties:
        return {}
    
    difficulties = np.array(difficulties)
    discriminations = np.array(discriminations)
    
    # Классификация сложности
    easy_questions = int(np.sum(difficulties >= 70))
    medium_questions = int(np.sum((difficulties >= 40) & (difficulties < 70)))
    hard_questions = int(np.sum(difficulties < 40))
    
    total_questions = len(difficulties)
    
    difficulty_analysis = {
        'total_questions': total_questions,
        'easy_questions': easy_questions,
        'medium_questions': medium_questions,
        'hard_questions': hard_questions,
        'easy_percent': (easy_questions / total_questions) * 100,
        'medium_percent': (medium_questions / total_questions) * 100,
        'hard_percent': (hard_questions / total_questions) * 100,
        'mean_difficulty': np.mean(difficulties),
        'mean_discrimination': np.mean(discriminations),
        'question_types': question_types,
        'low_discrimination_questions': low_discrimination_questions,
        'low_attempts_questions': low_attempts_questions,
        'distribution_balance': analyze_difficulty_balance(easy_questions, medium_questions, hard_questions)
    }
    
    return difficulty_analysis


def analyze_ability_difficulty_match(student_abilities: List[float], question_difficulties: List[float]) -> Dict[str, Any]:
    """
    Анализирует соответствие между способностями студентов и сложностью вопросов
    
    Параметры:
    - student_abilities: способности студентов
    - question_difficulties: сложность вопросов
    
    Возвращает:
    - словарь с анализом соответствия
    """
    if not student_abilities or not question_difficulties:
        return {}
    
    student_abilities = np.array(student_abilities)
    question_difficulties = np.array(question_difficulties)
    
    # Преобразуем сложность в логит-шкалу для сравнения
    question_logits = []
    for diff in question_difficulties:
        if 0 < diff < 100:
            p = np.clip(diff / 100, 0.01, 0.99)
            logit = np.log(p / (1 - p))
            question_logits.append(logit)
    
    if not question_logits:
        return {}
    
    question_logits = np.array(question_logits)
    
    # Анализ перекрытия распределений
    student_min, student_max = float(np.min(student_abilities)), float(np.max(student_abilities))
    question_min, question_max = float(np.min(question_logits)), float(np.max(question_logits))
    
    # Вычисляем перекрытие
    overlap_start = max(student_min, question_min)
    overlap_end = min(student_max, question_max)
    overlap_range = max(0, overlap_end - overlap_start)
    
    student_range = student_max - student_min
    question_range = question_max - question_min
    total_range = max(student_max, question_max) - min(student_min, question_min)
    
    overlap_percentage = (overlap_range / total_range) * 100 if total_range > 0 else 0
    
    # Анализ соответствия
    match_analysis = {
        'overlap_percentage': overlap_percentage,
        'student_range': (student_min, student_max),
        'question_range': (question_min, question_max),
        'overlap_range': (overlap_start, overlap_end),
        'match_quality': classify_match_quality(overlap_percentage),
        'recommendations': generate_match_recommendations(overlap_percentage, student_range, question_range)
    }
    
    return match_analysis


def classify_distribution(abilities: np.ndarray) -> str:
    """Классифицирует тип распределения способностей"""
    skewness = calculate_skewness(abilities)
    
    if abs(skewness) < 0.5:
        return "нормальное"
    elif skewness > 0.5:
        return "смещенное влево (много слабых студентов)"
    else:
        return "смещенное вправо (много сильных студентов)"


def calculate_skewness(data: np.ndarray) -> float:
    """Вычисляет асимметрию распределения"""
    mean = np.mean(data)
    std = np.std(data)
    if std == 0:
        return 0
    return np.mean(((data - mean) / std) ** 3)


def analyze_difficulty_balance(easy: int, medium: int, hard: int) -> str:
    """Анализирует баланс сложности вопросов"""
    total = easy + medium + hard
    if total == 0:
        return "недостаточно данных"
    
    easy_pct = (easy / total) * 100
    medium_pct = (medium / total) * 100
    hard_pct = (hard / total) * 100
    
    if medium_pct >= 40:
        return "сбалансированное"
    elif easy_pct > 50:
        return "смещенное к легким вопросам"
    elif hard_pct > 50:
        return "смещенное к сложным вопросам"
    else:
        return "несбалансированное"


def classify_match_quality(overlap_percentage: float) -> str:
    """Классифицирует качество соответствия"""
    if overlap_percentage >= 70:
        return "отличное"
    elif overlap_percentage >= 50:
        return "хорошее"
    elif overlap_percentage >= 30:
        return "удовлетворительное"
    else:
        return "плохое"


def generate_match_recommendations(overlap_percentage: float, student_range: float, question_range: float) -> List[str]:
    """Генерирует рекомендации по улучшению соответствия"""
    recommendations = []
    
    if overlap_percentage < 30:
        recommendations.append("Критически низкое перекрытие распределений")
        recommendations.append("Рекомендуется добавить вопросы средней сложности")
    elif overlap_percentage < 50:
        recommendations.append("Недостаточное перекрытие распределений")
        recommendations.append("Следует пересмотреть баланс сложности вопросов")
    
    if student_range < 2:
        recommendations.append("Студенты имеют схожие способности - нужны более дифференцированные вопросы")
    
    if question_range < 2:
        recommendations.append("Вопросы имеют схожую сложность - нужна большая вариативность")
    
    return recommendations


def generate_expert_analysis(questions: List[Dict[str, Any]], student_abilities: List[float] = None) -> Dict[str, Any]:
    """
    Генерирует полный экспертный анализ IRT данных
    
    Параметры:
    - questions: список вопросов
    - student_abilities: способности студентов (опционально)
    
    Возвращает:
    - словарь с полным анализом
    """
    # Извлекаем сложность вопросов
    question_difficulties = []
    for question in questions:
        try:
            difficulty = float(question.get('difficulty', 0))
            if 0 < difficulty < 100:
                question_difficulties.append(difficulty)
        except (ValueError, TypeError):
            continue
    
    # Генерируем способности студентов, если не предоставлены
    if student_abilities is None:
        if question_difficulties:
            # Определяем количество студентов на основе реальных данных о попытках
            # Используем максимальное количество попыток среди всех вопросов
            # (предполагаем, что все студенты отвечали на все вопросы)
            num_students = 0
            for question in questions:
                try:
                    attempts = int(question.get('attempts', 0))
                    if attempts > num_students:
                        num_students = attempts
                except (ValueError, TypeError):
                    continue
            
            # Если не удалось определить количество студентов из попыток,
            # используем среднее количество попыток или минимальное разумное значение
            if num_students == 0:
                attempts_list = []
                for question in questions:
                    try:
                        attempts = int(question.get('attempts', 0))
                        if attempts > 0:
                            attempts_list.append(attempts)
                    except (ValueError, TypeError):
                        continue
                if attempts_list:
                    num_students = int(np.mean(attempts_list))
                else:
                    # Если вообще нет данных о попытках, используем разумное значение по умолчанию
                    num_students = 100
            
            # Преобразуем сложность в логит-шкалу
            logit_difficulties = []
            for diff in question_difficulties:
                p = np.clip(diff / 100, 0.01, 0.99)
                logit = np.log(p / (1 - p))
                logit_difficulties.append(logit)
            
            # Генерируем нормальное распределение на основе сложности
            mean_ability = float(np.mean(logit_difficulties))
            std_ability = float(np.std(logit_difficulties))
            # Используем реальное количество студентов вместо фиксированного 1000
            student_abilities = np.random.normal(mean_ability, std_ability, num_students)
            student_abilities = np.clip(student_abilities, -4, 4)
            student_abilities = student_abilities.tolist()  # Преобразуем в список
        else:
            student_abilities = []
    
    # Выполняем все анализы
    student_analysis = analyze_student_ability_distribution(student_abilities)
    question_analysis = analyze_question_difficulty_distribution(questions)
    match_analysis = analyze_ability_difficulty_match(student_abilities, question_difficulties)
    
    # Генерируем общие рекомендации
    general_recommendations = generate_general_recommendations(student_analysis, question_analysis, match_analysis)
    
    expert_analysis = {
        'student_analysis': student_analysis,
        'question_analysis': question_analysis,
        'match_analysis': match_analysis,
        'general_recommendations': general_recommendations,
        'summary': generate_summary(student_analysis, question_analysis, match_analysis)
    }
    
    return expert_analysis


def generate_general_recommendations(student_analysis: Dict, question_analysis: Dict, match_analysis: Dict) -> List[str]:
    """Генерирует общие рекомендации на основе всех анализов"""
    recommendations = []
    
    # Рекомендации по студентам
    if student_analysis.get('low_ability_percent', 0) > 40:
        recommendations.append("Большой процент студентов с низкими способностями - требуется дополнительная поддержка")
    
    if student_analysis.get('high_ability_percent', 0) > 40:
        recommendations.append("Много сильных студентов - нужны более сложные задания")
    
    # Рекомендации по вопросам
    if question_analysis.get('low_discrimination_questions'):
        low_disc = question_analysis['low_discrimination_questions']
        low_disc_count = len(low_disc)
        ids_str = ', '.join(str(q.get('display_id', q.get('id', ''))) for q in low_disc)
        recommendations.append(f"Найдено {low_disc_count} вопросов с низкой дискриминацией — требуют пересмотра ({ids_str})")
    
    if question_analysis.get('distribution_balance') == "смещенное к легким вопросам":
        recommendations.append("Слишком много легких вопросов — добавьте сложные задания")
    elif question_analysis.get('distribution_balance') == "смещенное к сложным вопросам":
        recommendations.append("Слишком много сложных вопросов — добавьте легкие задания")
    
    if question_analysis.get('low_attempts_questions'):
        low_att = question_analysis['low_attempts_questions']
        ids_str = ', '.join(str(q.get('display_id', '')) for q in low_att)
        recommendations.append(f"Необходимо протестировать большее количество студентов по вопросам с малым числом попыток (ниже порога надёжности) ({ids_str})")
    
    # Рекомендации по соответствию
    if match_analysis.get('match_quality') == "плохое":
        recommendations.append("Критическое несоответствие между способностями и сложностью - требуется полный пересмотр теста")
    
    return recommendations


def generate_summary(student_analysis: Dict, question_analysis: Dict, match_analysis: Dict) -> str:
    """Генерирует краткое резюме анализа"""
    total_students = student_analysis.get('total_students', 0)
    total_questions = question_analysis.get('total_questions', 0)
    overlap_pct = match_analysis.get('overlap_percentage', 0)
    
    summary = f"""
    **Анализ IRT данных:**
    - Проанализировано {total_students} студентов и {total_questions} вопросов
    - Перекрытие распределений: {overlap_pct:.1f}%
    - Качество соответствия: {match_analysis.get('match_quality', 'неизвестно')}
    """
    
    return summary.strip()
