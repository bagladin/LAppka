"""
Модуль 2: IRT Анализ
Item Response Theory анализ с Person-Item Map
"""

import streamlit as st
from modules.irt_analysis.visualizer import display_irt_analysis


def render():
    """Основная функция рендеринга модуля"""
    st.markdown("**Описание:** Item Response Theory анализ с Person-Item Map, экспертной системой и интеллектуальным анализом данных.")
    
    # Используем данные, загруженные в модуле 1
    if 'questions_data' in st.session_state and st.session_state['questions_data']:
        questions = st.session_state['questions_data']
        display_irt_analysis(questions)
    else:
        st.info("📋 Для работы этого модуля необходимо сначала загрузить файл в **Модуле 1: Анализ вопросов**.")
        st.markdown("""
        **Инструкция:**
        1. Перейдите на вкладку **📈 Модуль 1: Анализ вопросов**
        2. Загрузите файл с данными тестирования (HTML)
        3. После успешной загрузки вернитесь в этот модуль
        """)
