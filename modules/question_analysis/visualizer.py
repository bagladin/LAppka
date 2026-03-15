"""
Модуль визуализации для анализа вопросов
Отвечает за отображение вопросов и их анализа
"""

import streamlit as st
import pandas as pd
from utils.helpers import get_difficulty_color, get_metric_class, safe_float
from modules.question_analysis.charts import create_difficulty_distribution_plot


def display_question_analysis(questions, answers_data):
    """Отображение анализа вопросов"""
    
    # Объединяем вопросы с ответами (по порядку блоков)
    if questions and answers_data:
        for i, question in enumerate(questions):
            if i < len(answers_data):
                question['answers'] = answers_data[i]
    
    if questions:
        # Фильтруем основные вопросы (без точки)
        display_questions = [q for q in questions if not q.get('is_main_question', False)]
        # Реальное количество уникальных вопросов (без дублей)
        unique_count = len(display_questions)
        
        with st.expander("Отладка (колонки и счетчики)"):
            st.write({"questions": unique_count, "answer_groups": len(answers_data), "total_including_main": len(questions)})
        st.markdown(f"**Найдено вопросов:** {unique_count}")
        if answers_data:
            st.markdown(f"**Найдено групп ответов:** {len(answers_data)}")
        
        # Фильтры
        max_attempts = max((safe_float(q.get('attempts', 0)) for q in display_questions), default=1000)
        max_attempts = max(1, int(max_attempts))
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Исключаем "случайный" из списка типов - это не тип вопроса, а способ выбора
            question_types = list(set([
                q['type'] for q in display_questions 
                if q['type'] and q['type'].lower() not in ['случайный', 'случайный вопрос', 'random']
            ]))
            selected_type = st.selectbox("Тип вопроса", ["Все"] + question_types)
        
        with col2:
            difficulty_range = st.slider(
                "Диапазон сложности (%)",
                min_value=0, max_value=100, value=(0, 100)
            )
        
        with col3:
            attempts_range = st.slider(
                "Попыток (ответов на вопрос)",
                min_value=0, max_value=max_attempts, value=(0, max_attempts)
            )
        
        with col4:
            sort_by = st.selectbox(
                "Сортировка",
                ["По умолчанию", "По сложности", "По дискриминации", "По типу"]
            )
        
        # Фильтрация вопросов (используем display_questions, но для графика нужны все вопросы)
        filtered_questions = display_questions
        
        if selected_type != "Все":
            filtered_questions = [q for q in filtered_questions if q['type'] == selected_type]
        
        filtered_questions = [
            q for q in filtered_questions 
            if difficulty_range[0] <= safe_float(q['difficulty']) <= difficulty_range[1]
        ]
        
        filtered_questions = [
            q for q in filtered_questions
            if attempts_range[0] <= safe_float(q.get('attempts', 0)) <= attempts_range[1]
        ]
        
        # Сортировка
        if sort_by == "По сложности":
            filtered_questions.sort(key=lambda x: safe_float(x['difficulty']), reverse=True)
        elif sort_by == "По дискриминации":
            filtered_questions.sort(key=lambda x: safe_float(x['discrimination']), reverse=True)
        elif sort_by == "По типу":
            filtered_questions.sort(key=lambda x: x['type'])
        
        st.markdown(f"**Отфильтровано вопросов:** {len(filtered_questions)}")
        
        # Графики распределения вопросов по категориям (слева — количество, справа — средние показатели)
        try:
            fig_left, fig_right = create_difficulty_distribution_plot(questions, question_type_filter=selected_type)
            if fig_left.data or fig_right.data:
                filter_text = f" (тип: {selected_type})" if selected_type != "Все" else ""
                st.markdown(f"### Распределение вопросов по категориям{filter_text}")
                col_left, col_right = st.columns(2)
                with col_left:
                    st.plotly_chart(fig_left, use_container_width=True)
                with col_right:
                    st.plotly_chart(fig_right, use_container_width=True)
        except Exception as e:
            st.warning(f"Не удалось построить график распределения: {e}")
        
        # Отображение вопросов
        if filtered_questions:
            st.caption("Строка с серым фоном — самый частый неправильный ответ.")
        
        for i, question in enumerate(filtered_questions):
            display_single_question(question)


def display_single_question(question):
    """Отображение одного вопроса"""
    difficulty_class = get_difficulty_color(question['difficulty'])
    display_id = question.get('display_id') or question.get('id', '')
    
    st.markdown(f"""
    <div class="question-block {difficulty_class}">
        <h4>Вопрос {display_id}: {question['title']}</h4>
        <p><strong>Тип:</strong> {question['type']} | <strong>Попыток:</strong> {question['attempts']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Метрики в колонках
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        diff_class = get_metric_class(question['difficulty'], "difficulty")
        st.markdown(f"""
        <div class="metric-badge {diff_class}">
            Сложность: {question['difficulty']}%
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        disc_class = get_metric_class(question['discrimination'], "discrimination")
        st.markdown(f"""
        <div class="metric-badge {disc_class}">
            Дискриминация: {question['discrimination']}%
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-badge metric-warning">
            Эффективность: {question['efficiency']}%
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-badge metric-warning">
            Вес: {question['weight']}%
        </div>
        """, unsafe_allow_html=True)
    
    # Показываем ответы с частотами, если они есть
    if question.get('answers') and len(question['answers']) > 0:
        st.markdown("**Варианты ответов с частотами:**")
        # Представляем ответы в табличном виде, с русскими заголовками
        ans_df = pd.DataFrame(question['answers'])
        # Переименуем ключи в русские подписи
        rename_map = {
            'part': 'Часть вопроса',
            'model_answer': 'Модель ответа',
            'actual_answer': 'Фактический ответ',
            'partial_credit': 'Частичная оценка',
            'count': 'Количество ответов',
            'frequency': 'Частота, %',
        }
        ans_df = ans_df.rename(columns=rename_map)
        preferred_cols = [c for c in ['Часть вопроса','Модель ответа','Фактический ответ','Частичная оценка','Количество ответов','Частота, %'] if c in ans_df.columns]
        if preferred_cols:
            ans_df = ans_df[preferred_cols]
        # Выделяем строку с самым популярным неправильным ответом
        answers = question.get('answers', [])
        incorrect_indices = [
            i for i in range(len(answers))
            if safe_float(answers[i].get('partial_credit', 0)) < 99.9
        ]
        best_wrong_idx = None
        if incorrect_indices:
            best_wrong_idx = max(
                incorrect_indices,
                key=lambda i: safe_float(answers[i].get('count', 0))
            )
        if best_wrong_idx is not None:
            styler = ans_df.style.apply(
                lambda row: ['background-color: #e8e8e8' if row.name == best_wrong_idx else ''] * len(row),
                axis=1
            )
            st.dataframe(styler, use_container_width=True, hide_index=True)
        else:
            st.dataframe(ans_df, use_container_width=True, hide_index=True)
        st.markdown("---")
