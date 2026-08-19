"""
Модуль 2: Соответствие распределений
Диаграмма соответствия банка вопросов и контингента
"""

import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO
from modules.irt_analysis.visualizer import display_irt_analysis


def _safe_float(value):
    if value is None:
        return None
    try:
        s = str(value).strip().replace(" ", "").replace("%", "").replace(",", ".")
        if s == "":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _read_grades_file(uploaded_file):
    name = (uploaded_file.name or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)

    # Для CSV используем автоопределение разделителя и наборы кодировок.
    payload = uploaded_file.getvalue()
    last_error = None
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return pd.read_csv(
                BytesIO(payload),
                encoding=enc,
                sep=None,
                engine="python",
            )
        except Exception as e:
            last_error = e
    raise ValueError(f"Не удалось прочитать файл журнала оценок: {last_error}")


def _build_student_logit_distribution(
    df: pd.DataFrame,
    score_col: str,
    score_mode: str,
    transform_mode: str,
    max_score_value: float,
    denom_col: str,
    fixed_denom_n: float,
) -> dict:
    if score_col not in df.columns:
        return {"abilities": [], "count": 0, "message": "Не выбрана колонка с оценкой."}

    ability_values = []
    used_rows = 0

    for _, row in df.iterrows():
        raw_score = _safe_float(row.get(score_col))
        if raw_score is None:
            continue

        p = None
        if score_mode == "fraction":
            p = raw_score
        elif score_mode == "percent":
            p = raw_score / 100.0
        else:
            max_score = max_score_value
            if max_score is None or max_score <= 0:
                continue
            p = raw_score / max_score

        if p is None:
            continue
        p = min(1.0, max(0.0, p))

        denom = None
        if transform_mode == "empirical":
            if denom_col and denom_col in df.columns:
                denom = _safe_float(row.get(denom_col))
            else:
                denom = fixed_denom_n
            if denom is not None and denom <= 0:
                denom = None

        # Если есть denominator (число вопросов/наблюдений), применяем empirical logit:
        # log((y + 0.5) / (n - y + 0.5)), где y = p*n.
        # Иначе используем стандартный logit с отсечкой p в [0.01; 0.99].
        if transform_mode == "empirical" and denom is not None:
            y = min(denom, max(0.0, p * denom))
            logit = float(np.log((y + 0.5) / ((denom - y) + 0.5)))
        else:
            p_clip = min(0.99, max(0.01, p))
            logit = float(np.log(p_clip / (1.0 - p_clip)))

        if np.isfinite(logit):
            ability_values.append(float(np.clip(logit, -4, 4)))
            used_rows += 1

    return {
        "abilities": ability_values,
        "count": used_rows,
        "message": None if used_rows > 0 else "Не удалось получить валидные значения подготовленности из файла.",
    }


def _parse_max_score_from_header(col_name: str):
    """
    Пытается извлечь максимум из заголовка вида "Оценка/10,0".
    """
    if not col_name:
        return None
    m = re.search(r"/\s*([0-9]+(?:[.,][0-9]+)?)", str(col_name))
    if not m:
        return None
    return _safe_float(m.group(1))


def _detect_question_columns(columns):
    return [
        c for c in columns
        if re.match(r"^В\.\s*\d+\s*/", str(c)) or re.match(r"^В\s*\d+\s*/", str(c))
    ]


def render():
    """Основная функция рендеринга модуля"""
    st.markdown("**Описание:** Диаграмма соответствия распределений студентов и сложности банка вопросов, коэффициент структурного соответствия (КСС) и диагностическая статистика.")
    
    # Используем данные, загруженные в модуле 1
    if 'questions_data' in st.session_state and st.session_state['questions_data']:
        questions = st.session_state['questions_data']

        st.markdown("#### 👥 Данные о результатах студентов")
        grade_file = st.file_uploader(
            "Загрузите журнал оценок (CSV/XLSX)",
            type=["csv", "xlsx", "xls"],
            key="student_grades_uploader_module2",
            help="Без этого файла левая часть графика и КСС не рассчитываются.",
        )

        if grade_file is not None:
            try:
                grades_df = _read_grades_file(grade_file)
                st.session_state["student_grades_df"] = grades_df
                st.success(f"✅ Файл оценок загружен: {grade_file.name} ({len(grades_df)} строк)")
            except Exception as e:
                st.error(f"Ошибка загрузки журнала оценок: {e}")

        student_abilities = None
        grades_df = st.session_state.get("student_grades_df")
        if grades_df is not None and not grades_df.empty:
            with st.expander("Настройка колонок файла оценок", expanded=True):
                columns = [str(c) for c in grades_df.columns]

                def pick_default(candidates):
                    lower = [c.lower() for c in columns]
                    for token in candidates:
                        for i, c in enumerate(lower):
                            if token in c:
                                return columns[i]
                    return columns[0]

                score_col = st.selectbox(
                    "Колонка с оценкой студента",
                    options=columns,
                    index=columns.index(pick_default(["grade", "оцен", "балл", "score", "итог", "result"])),
                    key="student_score_col",
                )
                header_max_score = _parse_max_score_from_header(score_col)
                if header_max_score is not None and header_max_score > 0:
                    score_mode = "points"
                    max_score_value = float(header_max_score)
                    st.caption(f"Максимум баллов определён автоматически из заголовка: {max_score_value:g}")
                else:
                    max_score_value = 100.0
                    score_mode = st.radio(
                        "Формат значения оценки",
                        options=[
                            ("percent", "Проценты (0..100)"),
                            ("fraction", "Доля (0..1)"),
                            ("points", "Баллы (требуется максимум)"),
                        ],
                        format_func=lambda x: x[1],
                        index=0,
                        key="student_score_mode",
                    )[0]
                    if score_mode == "points":
                        max_score_value = float(
                            st.number_input(
                                "Максимальный балл",
                                min_value=1.0,
                                value=100.0,
                                step=1.0,
                                key="student_max_fixed_fallback",
                            )
                        )

                question_cols = _detect_question_columns(columns)
                detected_n_questions = len(question_cols)

                transform_mode = st.radio(
                    "Режим преобразования в логит-шкалу",
                    options=["logit", "empirical"],
                    format_func=lambda x: (
                        "Обычный logit (рекомендуется по умолчанию)"
                        if x == "logit"
                        else "Empirical logit (устойчивее на крайних оценках)"
                    ),
                    index=0,
                    key="student_transform_mode",
                )

                denom_col = ""
                fixed_denom_n = float(detected_n_questions) if detected_n_questions > 0 else 0.0
                if transform_mode == "empirical":
                    st.markdown("**Настройка параметра n для empirical logit**")
                    denom_source = st.radio(
                        "Источник n",
                        options=["auto_questions", "fixed", "column"],
                        format_func=lambda x: (
                            f"Авто: число вопросов в тесте ({detected_n_questions})" if x == "auto_questions"
                            else ("Ввести вручную" if x == "fixed" else "Взять из колонки")
                        ),
                        index=0 if detected_n_questions > 0 else 1,
                        key="student_denom_source",
                    )
                    if denom_source == "fixed":
                        default_n = float(detected_n_questions) if detected_n_questions > 0 else 10.0
                        fixed_denom_n = float(
                            st.number_input("n (число вопросов в тесте)", min_value=1.0, value=default_n, step=1.0, key="student_denom_n")
                        )
                    elif denom_source == "column":
                        denom_col = st.selectbox(
                            "Колонка с n (числом заданий/наблюдений)",
                            options=columns,
                            index=columns.index(pick_default(["n", "кол", "count", "attempt", "попыт"])),
                            key="student_denom_col",
                        )
                        fixed_denom_n = 0.0
                    else:
                        if detected_n_questions <= 0:
                            st.warning("Не удалось автоматически определить число вопросов, задайте n вручную.")

                dist_res = _build_student_logit_distribution(
                    df=grades_df,
                    score_col=score_col,
                    score_mode=score_mode,
                    transform_mode=transform_mode,
                    max_score_value=max_score_value,
                    denom_col=denom_col,
                    fixed_denom_n=fixed_denom_n,
                )
                if dist_res["message"]:
                    st.warning(dist_res["message"])
                else:
                    mode_label = "empirical logit" if transform_mode == "empirical" else "logit с отсечкой"
                    st.caption(
                        f"Рассчитано логит-значений подготовленности: {dist_res['count']} "
                        f"(режим: {mode_label})."
                    )

                student_abilities = dist_res["abilities"]
                st.session_state["student_abilities_logit"] = student_abilities
        else:
            st.session_state["student_abilities_logit"] = []

        st.session_state["show_rework_on_map"] = st.checkbox(
            "Показывать на диаграмме вопросы, отнесенные к переработке",
            value=bool(st.session_state.get("show_rework_on_map", False)),
            key="show_rework_on_map_checkbox",
        )
        st.session_state["apply_alignment_shift"] = st.checkbox(
            "Привязка шкалы подготовленности к средней сложности банка (+b̄)",
            value=bool(st.session_state.get("apply_alignment_shift", True)),
            key="apply_alignment_shift_checkbox",
            help="При изменении флага КСС и дефицитные зоны пересчитываются в выбранном режиме.",
        )

        display_irt_analysis(
            questions,
            student_ability_distribution=student_abilities if student_abilities else None,
        )
    else:
        st.info("📋 Для работы этого модуля необходимо сначала загрузить файл в **Модуле 1: Анализ вопросов**.")
        st.markdown("""
        **Инструкция:**
        1. Перейдите на вкладку **📈 Модуль 1: Анализ вопросов**
        2. Загрузите файл с данными тестирования (HTML)
        3. После успешной загрузки вернитесь в этот модуль
        """)
