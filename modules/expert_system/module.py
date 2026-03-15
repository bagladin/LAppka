"""
Модуль 3: Экспертная система: Интеллектуальный анализ
Экспертная система для интеллектуального анализа
"""

import streamlit as st
from modules.expert_system.visualizer import display_expert_system


def render():
    """Основная функция рендеринга модуля"""
    # Используем данные, загруженные в модуле 1
    if 'questions_data' in st.session_state and st.session_state['questions_data']:
        questions = st.session_state['questions_data']
        display_expert_system(questions)
    else:
        st.info("📋 Для работы этого модуля необходимо сначала загрузить файл в **Модуле 1: Анализ вопросов**.")
        st.markdown("""
        **Инструкция:**
        1. Перейдите на вкладку **📈 Модуль 1: Анализ вопросов**
        2. Загрузите файл с данными тестирования (HTML)
        3. После успешной загрузки вернитесь в этот модуль
        """)
