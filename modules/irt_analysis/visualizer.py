"""
Модуль визуализации для анализа соответствия распределений
Отвечает за отображение диаграммы соответствия и анализа модельной подготовленности
"""

import streamlit as st
import pandas as pd
import numpy as np
from modules.irt_analysis.person_item_map import (
    create_person_item_map,
    create_irt_summary_stats,
    create_difficulty_by_type_boxplot,
    create_distribution_alignment_metrics,
    logit_to_difficulty_percent,
    build_deficit_recommendation_plan,
    question_difficulty_percent_to_logit,
)
from modules.expert_system.expert_system import get_rework_question_ids, compute_kbtb


def _classify_deficit_level(relative_value: float) -> str:
    if relative_value >= 0.66:
        return "Высокий"
    if relative_value >= 0.33:
        return "Средний"
    return "Низкий"


def _build_deficit_recommendation_table(questions, metrics):
    zones = metrics.get('deficit_zones', []) or []
    if not zones:
        return None

    kstr = float(metrics.get("kstr", 0.0))
    total_questions = len([q for q in questions if not q.get("is_main_question", False)])

    # Синхронизация с модулем 3: бюджет зонального плана равен структурному дефициту
    # после выбытия вопросов "на переработку".
    target_o = float(st.session_state.get("kbtb_o", 40))
    target_type = {"O": target_o, "Z": float(100 - target_o)}
    target_level = st.session_state.get("kbtb_target_level") or st.session_state.get("kbtb_lmh") or {"L": 30, "M": 50, "H": 20}
    min_q = int(st.session_state.get("kbtb_min", 0))
    weights = st.session_state.get("kbtb_weights", {"type": 0.3, "level": 0.3, "rework": 0.2, "count": 0.2})
    kbtb_res = compute_kbtb(questions, target_type, target_level, min_questions=min_q, weights=weights)
    clean_level_counts = kbtb_res.get("clean_level_counts", {"L": 0, "M": 0, "H": 0})
    n_total = int(kbtb_res.get("n", total_questions))
    target_frac = {
        "L": max(0.0, float(target_level.get("L", 30.0)) / 100.0),
        "M": max(0.0, float(target_level.get("M", 50.0)) / 100.0),
        "H": max(0.0, float(target_level.get("H", 20.0)) / 100.0),
    }
    struct_plan = {}
    for lvl in ["L", "M", "H"]:
        target_count = n_total * target_frac[lvl]
        actual_count = float(clean_level_counts.get(lvl, 0))
        struct_plan[lvl] = int(max(0, round(target_count - actual_count)))
    struct_total = int(sum(struct_plan.values()))

    plan = build_deficit_recommendation_plan(
        total_questions=total_questions,
        kstr=kstr,
        deficit_zones=zones,
        total_override=struct_total,
    )
    level_counts = {
        "Легкие": int(plan.get("counts", {}).get("L", 0)),
        "Средние": int(plan.get("counts", {}).get("M", 0)),
        "Сложные": int(plan.get("counts", {}).get("H", 0)),
    }
    mean_rel_map = {
        "Легкие": float(plan.get("mean_relative", {}).get("L", 0.0)),
        "Средние": float(plan.get("mean_relative", {}).get("M", 0.0)),
        "Сложные": float(plan.get("mean_relative", {}).get("H", 0.0)),
    }

    if sum(level_counts.values()) <= 0:
        return None

    target_type = st.session_state.get("kbtb_target_type", {"O": 40.0, "Z": 60.0})
    t_open = float(target_type.get("O", 40.0)) / 100.0
    t_open = min(1.0, max(0.0, t_open))

    sub_questions = [q for q in questions if not q.get("is_main_question", False)]

    rows = []
    for level_name in ["Сложные", "Средние", "Легкие"]:
        n_level = level_counts.get(level_name, 0)
        if n_level <= 0:
            continue

        mean_rel = mean_rel_map.get(level_name, 0.0)
        deficit_level = _classify_deficit_level(mean_rel)
        n_open = int(round(n_level * t_open))
        n_closed = max(0, n_level - n_open)

        centers = []
        for z in zones:
            center = (float(z.get("y0", 0.0)) + float(z.get("y1", 0.0))) / 2.0
            diff_pct = logit_to_difficulty_percent(center)
            if level_name == "Легкие" and diff_pct >= 70:
                centers.append(center)
            elif level_name == "Средние" and 40 <= diff_pct < 70:
                centers.append(center)
            elif level_name == "Сложные" and diff_pct < 40:
                centers.append(center)
        center_logit = sum(centers) / len(centers) if centers else 0.0

        anchors = []
        for q in sub_questions:
            try:
                d = float(q.get("difficulty", 0))
                if not (0 < d < 100):
                    continue
                q_logit = float(question_difficulty_percent_to_logit(d))
                qid = q.get("display_id") or q.get("id", "")
                anchors.append((abs(q_logit - center_logit), str(qid)))
            except (ValueError, TypeError, ZeroDivisionError):
                continue
        anchors.sort(key=lambda x: x[0])
        anchor_text = ", ".join([a[1] for a in anchors[:3]]) if anchors else "—"

        rows.append({
            "Диапазон": level_name,
            "Дефицит": deficit_level,
            "Рекомендация (+вопросов)": n_level,
            "Открытые": n_open,
            "Закрытые": n_closed,
            "Похожие по сложности": anchor_text,
        })

    if not rows:
        return None
    return pd.DataFrame(rows)


def display_irt_analysis(questions, student_ability_distribution=None):
    """Отображение диаграммы соответствия распределений."""
    questions = [q for q in questions if not q.get('is_main_question', False)]
    
    # Создаем диаграмму соответствия распределений
    try:
        highlight_rework = bool(st.session_state.get("show_rework_on_map", False))
        apply_alignment_shift = bool(st.session_state.get("apply_alignment_shift", True))
        rework_ids = get_rework_question_ids(questions) if highlight_rework else set()
        person_item_fig = create_person_item_map(
            questions,
            student_ability_distribution=student_ability_distribution,
            apply_alignment_shift=apply_alignment_shift,
            highlight_rework=highlight_rework,
            rework_question_ids=rework_ids,
        )
        st.plotly_chart(person_item_fig, use_container_width=True)

        metrics = create_distribution_alignment_metrics(
            questions,
            student_ability_distribution=student_ability_distribution,
            apply_alignment_shift=apply_alignment_shift,
        )
        has_student_data = bool(metrics.get('has_student_data', False))
        kstr = metrics.get('kstr', 0.0)
        num_students = metrics.get('num_students', 0)
        if has_student_data:
            if kstr >= 0.80:
                quality = "высокое"
                color = "🟢"
            elif kstr >= 0.60:
                quality = "умеренное"
                color = "🟡"
            else:
                quality = "низкое"
                color = "🔴"

            st.metric(
                "Коэффициент структурного соответствия (КСС)",
                f"{kstr:.3f}",
                help="КСС = 1 - 0.5 * ∫|S(x)-Q(x)|dx; ближе к 1 — лучшее соответствие распределений."
            )
            st.caption(f"{color} Качество соответствия: {quality}. Для построения использовано {num_students} записей журнала оценок.")
        else:
            st.info(
                "Для расчёта КСС и отображения левой части графика загрузите журнал оценок в формате CSV/XLSX "
                "в блоке «Данные о результатах студентов»."
            )
        
        # Добавляем описание
        st.info("""
        **Диаграмма соответствия распределений** показывает соотношение между распределением подготовленности
        студентов (по журналу оценок) и распределением сложности вопросов:
        - **Левая сторона**: распределение наблюдаемой подготовленности студентов (только при загруженном журнале оценок)
        - **Правая сторона**: сложность вопросов (выше по оси Y — сложнее)
        - **Красные полупрозрачные зоны**: дефицит вопросов для соответствующего диапазона сложности (при наличии данных студентов)
        - **Метки X**: вопросы, отнесенные к переработке (если включена подсветка)
        - **Интерпретация**: чем выше КСС, тем лучше структурное соответствие банка контингенту
        """)
        
        # Добавляем справку о шкале и коэффициенте КСС
        with st.expander("📖 Справка: шкала и коэффициент КСС"):
            st.markdown("""
            ### Шкала сопоставления распределений
            
            Для сопоставления распределений используется **логит-шкала** от **-4 до +4**, где:
            - **-4 до 0**: относительно низкий уровень подготовленности
            - **0**: средний уровень подготовленности
            - **0 до +4**: относительно высокий уровень подготовленности
            
            ### Как считается подготовленность по журналу оценок

            Для каждого студента используется итоговая оценка из журнала в виде `Оценка/Максимум`.
            Сначала рассчитывается доля:

            $$
            p_i = \\frac{\\text{Оценка}_i}{\\text{Максимум}}
            $$

            Далее рассчитывается «сырой» логит-уровень подготовленности $x_i^{(0)}$
            одним из двух режимов:

            **1) Обычный logit (режим по умолчанию):**

            $$
            x_i^{(0)} = \\ln\\left(\\frac{p_i}{1-p_i}\\right), \\quad p_i \\in [0.01, 0.99]
            $$

            **2) Empirical logit (дополнительный режим):**

            $$
            x_i^{(0)} = \\ln\\left(\\frac{y_i + 0.5}{(n_i - y_i) + 0.5}\\right), \\quad y_i = p_i\\,n_i
            $$

            После этого в текущей реализации выполняется привязка к шкале сложности банка:

            $$
            x_i = x_i^{(0)} + \\overline{b},
            $$

            где $\\overline{b}$ — средняя логит-сложность вопросов банка.

            где:
            - $x_i^{(0)}$ — логит-уровень подготовленности до привязки;
            - $x_i$ — логит-уровень подготовленности после привязки;
            - $p_i$ — доля набранных баллов;
            - $n_i$ — число вопросов/наблюдений (задаётся в настройках режима empirical logit).

            После расчёта значения ограничиваются диапазоном **[-4; +4]** для устойчивой визуализации.

            ### Как переводится сложность вопросов

            Для правой части диаграммы используется индекс легкости вопроса $p$ (доля правильных ответов),
            который переводится в **логит сложности**:

            $$
            b = \\ln\\left(\\frac{1-p}{p}\\right)
            $$

            При такой записи большие значения $b$ соответствуют более сложным вопросам.
            
            ### Почему используется логит-шкала?
            
            - **Симметричность**: одинаковые изменения в логитах соответствуют одинаковым изменениям в вероятностях
            - **Неограниченность**: логит может принимать любые значения, что удобно для статистических моделей
            - **Интерпретируемость**: удобно сравнивать подготовленность контингента и сложность банка вопросов
            
            ### Коэффициент структурного соответствия (КСС)

            $$
            K_{сс} = 1 - \\frac{1}{2}\\int |S(x)-Q(x)|dx
            $$

            где:
            - $S(x)$ — плотность распределения подготовленности по журналу оценок
            - $Q(x)$ — плотность распределения сложности вопросов

            $K_{сс}$ принадлежит отрезку [0, 1]:
            - ближе к **1** — распределения согласованы лучше;
            - ближе к **0** — выраженное рассогласование.

            ### Связь с диаграммой
            
            На графике:
            - **Левая сторона** показывает распределение подготовленности, рассчитанное из журнала оценок
            - **Правая сторона** показывает сложность вопросов (также в логит-шкале)
            - **Красная заливка по Y** показывает дефицитные диапазоны сложности (где студентов в зоне больше, чем вопросов)
            - Чем выше КСС, тем ближе структура сложности банка к наблюдаемому профилю подготовленности контингента
            """)

        rec_table = _build_deficit_recommendation_table(questions, metrics) if has_student_data else None
        if rec_table is not None and not rec_table.empty:
            st.markdown("### 📋 Рекомендации по пополнению банка (по дефицитным зонам)")
            st.table(rec_table)
        
    except Exception as e:
        st.error(f"Ошибка при создании диаграммы соответствия: {e}")
    
    # Создаем статистику
    try:
        stats = create_irt_summary_stats(questions)
        if stats:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Всего вопросов", stats['total_questions'])
                st.metric("Средняя сложность", f"{stats['difficulty_mean']:.1f}%")
            
            with col2:
                easy_pct = (stats['easy_questions'] / stats['total_questions']) * 100 if stats['total_questions'] > 0 else 0
                medium_pct = (stats['medium_questions'] / stats['total_questions']) * 100 if stats['total_questions'] > 0 else 0
                st.metric("Легкие вопросы", f"{stats['easy_questions']} ({easy_pct:.1f}%)")
                st.metric("Средние вопросы", f"{stats['medium_questions']} ({medium_pct:.1f}%)")
            
            with col3:
                hard_pct = (stats['hard_questions'] / stats['total_questions']) * 100 if stats['total_questions'] > 0 else 0
                st.metric("Сложные вопросы", f"{stats['hard_questions']} ({hard_pct:.1f}%)")
                st.metric("Средняя дискриминация", f"{stats['discrimination_mean']:.2f}")
                
    except Exception as e:
        st.error(f"Ошибка при создании статистики: {e}")
    
    # Создаем boxplot распределения сложности по типам вопросов
    try:
        boxplot_fig = create_difficulty_by_type_boxplot(questions)
        if boxplot_fig.data:
            st.subheader("📊 Распределение сложности по типам вопросов")
            st.plotly_chart(boxplot_fig, use_container_width=True)
    except Exception as e:
        st.error(f"Ошибка при создании boxplot: {e}")
    
    # Анализ распределения подготовленности из реального журнала оценок
    display_student_analysis(student_ability_distribution or [])


def _classify_distribution_type(values: np.ndarray) -> str:
    if values.size == 0:
        return "неизвестно"
    std = float(np.std(values))
    if std == 0:
        return "симметричное (без выраженной асимметрии)"
    skewness = float(np.mean(((values - np.mean(values)) / std) ** 3))
    if abs(skewness) < 0.5:
        return "симметричное (без выраженной асимметрии)"
    if skewness > 0.5:
        return "асимметрия влево (преобладают более низкие уровни)"
    return "асимметрия вправо (преобладают более высокие уровни)"


def display_student_analysis(student_ability_distribution):
    """Отображение анализа распределения подготовленности по журналу оценок."""
    
    st.subheader("👥 Анализ распределения подготовленности (по журналу оценок)")
    
    try:
        values = np.array(student_ability_distribution or [], dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            st.info("Журнал оценок не загружен или не содержит валидных числовых данных.")
            return

        mean_ability = float(np.mean(values))
        std_ability = float(np.std(values))
        low_threshold = mean_ability - std_ability
        high_threshold = mean_ability + std_ability

        low_count = int(np.sum(values < low_threshold))
        medium_count = int(np.sum((values >= low_threshold) & (values <= high_threshold)))
        high_count = int(np.sum(values > high_threshold))
        total = int(values.size)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Низкий уровень подготовленности",
                f"{low_count} ({(100.0 * low_count / total):.1f}%)",
                help="Логит-уровень ниже среднего минус одно стандартное отклонение",
            )
        with col2:
            st.metric(
                "Средний уровень подготовленности",
                f"{medium_count} ({(100.0 * medium_count / total):.1f}%)",
                help="Логит-уровень в пределах одного стандартного отклонения от среднего",
            )
        with col3:
            st.metric(
                "Высокий уровень подготовленности",
                f"{high_count} ({(100.0 * high_count / total):.1f}%)",
                help="Логит-уровень выше среднего плюс одно стандартное отклонение",
            )

        distribution_type = _classify_distribution_type(values)
        st.info(f"**Тип распределения подготовленности:** {distribution_type}")
        st.markdown(""" 
        **Типы распределения:**
        - **Симметричное (без выраженной асимметрии)**: основная масса наблюдений сосредоточена около центра шкалы
        - **Асимметрия влево**: больше наблюдений в области относительно низких уровней
        - **Асимметрия вправо**: больше наблюдений в области относительно высоких уровней
        """)
        st.caption(f"Оценка выполнена по {total} строкам журнала оценок.")
            
    except Exception as e:
        st.error(f"Ошибка при анализе распределения подготовленности: {e}")
