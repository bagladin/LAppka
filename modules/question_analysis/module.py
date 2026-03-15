"""
Модуль 1: Анализ вопросов
Визуализация тестовых вопросов с вариантами ответов и частотами
"""

import streamlit as st
from modules.base.data_loader import load_data
from modules.base.data_parser import parse_question_data, parse_answers_data
from modules.question_analysis.visualizer import display_question_analysis
from config.settings import SUPPORTED_FILE_TYPES


def render():
    """Основная функция рендеринга модуля"""
    st.markdown("### 📈 Модуль 1: Визуализация вопросов с вариантами ответов")
    st.markdown("**Описание:** Этот модуль помогает визуализировать все тестовые вопросы с их вариантами ответов и частотами ответов. Позволяет ранжировать их по сложности и фильтровать по типу, сложности и количеству попыток.")
    
    # Загрузка файла
    uploaded_file = st.file_uploader(
        "Загрузите файл с данными тестирования",
        type=SUPPORTED_FILE_TYPES,
        help="Выберите HTML файл с экспортированными данными из Moodle. При локальном запуске данные остаются на вашем компьютере.",
        key="file_uploader_question_analysis"
    )
    
    if uploaded_file is not None:
        df = load_data(uploaded_file)
        
        if df is not None:
            st.success("✅ Файл успешно загружен!")
            
            # Парсинг данных о вопросах
            questions = parse_question_data(df)
            
            # Парсинг данных об ответах
            answers_data = parse_answers_data(df)
            
            # Сохраняем данные в session_state для использования в других модулях
            st.session_state['questions_data'] = questions
            st.session_state['answers_data'] = answers_data
            st.session_state['raw_data'] = df
            
            if questions:
                display_question_analysis(questions, answers_data)
            else:
                st.warning("Не удалось найти данные о вопросах в загруженном файле.")
        else:
            st.error("Ошибка при обработке файла.")
    elif 'questions_data' in st.session_state:
        # Если файл не загружен, но есть сохраненные данные, используем их
        questions = st.session_state.get('questions_data', [])
        answers_data = st.session_state.get('answers_data', [])
        if questions:
            display_question_analysis(questions, answers_data)
