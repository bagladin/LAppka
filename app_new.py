"""
Главный файл приложения
Модульная архитектура для учебной аналитики Moodle
"""

import streamlit as st
from config.settings import PAGE_CONFIG, MODULES

# Импорт модулей
from modules.question_analysis.module import render as render_question_analysis
from modules.irt_analysis.module import render as render_irt_analysis
from modules.expert_system.module import render as render_expert_system
from modules.categorization.module import render as render_categorization


def load_css():
    """Загрузка CSS стилей"""
    try:
        with open('static/css/styles.css', 'r', encoding='utf-8') as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # Fallback CSS если файл не найден
        st.markdown("""
        <style>
        .main-header {
            text-align: center;
            padding: 2rem 0;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        </style>
        """, unsafe_allow_html=True)


def main():
    """Основная функция приложения"""
    # Настройка страницы
    st.set_page_config(**PAGE_CONFIG)
    
    # Загрузка CSS
    load_css()
    
    # Заголовок приложения с логотипом
    # Пытаемся найти логотип
    import os
    logo_paths = [
        'Лого.jpg',  # Основной логотип в корне проекта
        'static/images/logo.jpg',
        'logo.jpg'
    ]
    logo_path = None
    for path in logo_paths:
        if os.path.exists(path):
            logo_path = path
            break
    
    # Создаём шапку с логотипом и названием
    if logo_path:
        # Используем base64 для встраивания изображения в HTML
        import base64
        with open(logo_path, 'rb') as f:
            logo_data = base64.b64encode(f.read()).decode()
            logo_ext = os.path.splitext(logo_path)[1].lower().replace('.', '')
            if logo_ext == 'jpg':
                logo_ext = 'jpeg'
        
        st.markdown(f"""
        <div class="main-header">
            <div class="logo-container">
                <img src="data:image/{logo_ext};base64,{logo_data}" alt="LAppka Logo" />
            </div>
            <div class="title-container">
                <h1>LAppka</h1>
                <p class="subtitle">Learning Analytics app</p>
                <p class="tagline">Инструмент для системного анализа образовательных данных для учебного портала РХТУ им. Д.И. Менделеева</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Если логотип не найден, показываем только текст
        st.markdown("""
        <div class="main-header">
            <div class="title-container">
                <h1>LAppka</h1>
                <p class="subtitle">Learning Analytics app</p>
                <p class="tagline">Инструмент для системного анализа образовательных данных для учебного портала РХТУ им. Д.И. Менделеева</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Создание табов для модулей
    tab_names = [MODULES[key]["name"] for key in MODULES.keys()]
    tabs = st.tabs(tab_names)
    
    # Словарь для сопоставления табов с функциями
    tab_functions = {
        0: render_question_analysis,
        1: render_irt_analysis,
        2: render_expert_system,
        3: render_categorization,
    }
    
    # Рендеринг каждого таба
    for i, tab in enumerate(tabs):
        with tab:
            if i in tab_functions:
                tab_functions[i]()


if __name__ == "__main__":
    main()
