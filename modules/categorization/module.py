"""
Модуль 4: Категоризация
Категоризация вопросов по сложности и типу
"""

import streamlit as st
from modules.categorization.moodle_parser import parse_moodle_file
from modules.categorization.categorizer import categorize_questions
from modules.categorization.moodle_generator import generate_moodle_file
from modules.categorization.visualizer import display_categorization_tree


def render():
    """Основная функция рендеринга модуля"""
    st.markdown("### 📂 Модуль 4: Категоризация")
    st.markdown("""
    **Описание:** Автоматическая категоризация вопросов банка Moodle по сложности (индекс легкости) и типу ответа (открытый/закрытый). Сопоставление со статистикой выполняется по текстовой схожести; несопоставленные вопросы получают значения по умолчанию. Порог границы «лёгкие» (по умолчанию ≥70%) настраивается в диапазоне 65–75%.
    
    **Структура категорий:**
    - **Категория 1**: Легкие вопросы (>= 70%)
      - 1.1: Открытые вопросы (числовой ответ, короткий ответ)
      - 1.2: Закрытые вопросы (остальные типы)
    - **Категория 2**: Средние + сложные вопросы (< 70%)
      - 2.1: Открытые вопросы
      - 2.2: Закрытые вопросы
    - **Категория 3**: На переработку
      - Вопросы с плохой дискриминацией (< 0.3)
      - 10% самых легких вопросов
      - Мало попыток (ниже порога надёжности)
    """)
    
    # Проверяем наличие данных из модуля 1
    if 'questions_data' not in st.session_state or not st.session_state['questions_data']:
        st.warning("""
        **⚠️ Для работы модуля категоризации необходимо:**
        1. Загрузить файл с данными тестирования в **Модуле 1: Анализ вопросов**
        2. Загрузить Moodle GIFT файл с вопросами в этом модуле
        """)
        st.info("""
        **Инструкция:**
        1. Перейдите на вкладку **📈 Модуль 1: Анализ вопросов**
        2. Загрузите файл с данными тестирования (HTML)
        3. Вернитесь в этот модуль и загрузите Moodle GIFT файл
        """)
        return
    
    # Загрузка Moodle файла
    st.markdown("---")
    st.markdown("### 📤 Загрузка Moodle GIFT файла")
    
    uploaded_file = st.file_uploader(
        "Загрузите Moodle GIFT файл с вопросами",
        type=['txt', 'gift'],
        help="Выберите файл, экспортированный из Moodle в формате GIFT. При локальном запуске данные остаются на вашем компьютере.",
        key="file_uploader_categorization"
    )
    
    if uploaded_file is not None:
        try:
            # Читаем файл
            file_content = uploaded_file.read().decode('utf-8')
            
            # Парсим файл
            base_category, moodle_questions = parse_moodle_file(file_content)
            
            st.success(f"✅ Файл успешно загружен! Найдено {len(moodle_questions)} вопросов")
            
            # Получаем проанализированные вопросы из session_state
            analyzed_questions = st.session_state['questions_data']
            
            # Описание категорий слева, настройка границы справа
            desc_col, slider_col = st.columns([1, 1])
            with desc_col:
                st.markdown("""
                **Структура категорий:**
                - **Категория 1**: Легкие вопросы (≥ 70%)
                  - 1.1: Открытые (числовой, короткий ответ)
                  - 1.2: Закрытые (остальные типы)
                - **Категория 2**: Средние + сложные (< 70%)
                  - 2.1: Открытые | 2.2: Закрытые
                - **Категория 3**: На переработку (дискриминация < 0,3; 10% самых лёгких; мало попыток)
                """)
            with slider_col:
                easy_threshold = st.slider(
                    "Граница «лёгкие» (≥X%)",
                    min_value=65,
                    max_value=75,
                    value=70,
                    step=1,
                    help="Сдвиг влево — больше в «лёгкие»; вправо — меньше. Диапазон 65–75%."
                )

            # Категоризируем вопросы
            with st.spinner("Категоризация вопросов..."):
                categorized_questions, easiest_questions, unmatched_questions, duplicates_info, matching_info, low_attempts_questions = categorize_questions(moodle_questions, analyzed_questions, easy_threshold=easy_threshold)
            
            # Обработка несопоставленных вопросов (по умолчанию включаем их)
            unmatched_action = "Включить в категоризацию с значениями по умолчанию"
            if unmatched_questions:
                # Фильтруем категории - по умолчанию включаем все вопросы
                pass
            else:
                # Если все сопоставлены, просто используем как есть
                pass
            
            # Отображаем визуализацию
            st.markdown("---")
            display_categorization_tree(categorized_questions, easiest_questions, low_attempts_questions=low_attempts_questions, easy_threshold=easy_threshold)
            
            # Генерируем новый файл
            st.markdown("---")
            st.markdown("### 💾 Экспорт категоризированного файла")
            
            new_file_content = generate_moodle_file(base_category, categorized_questions)
            
            st.download_button(
                label="📥 Скачать категоризированный файл",
                data=new_file_content,
                file_name=f"{base_category}_categorized.txt",
                mime="text/plain",
                key="download_categorized_file"
            )
            
            st.info("""
            **Инструкция по импорту:**
            1. Скачайте сгенерированный файл
            2. Импортируйте его обратно в Moodle через меню "Импорт вопросов"
            3. Вопросы будут автоматически распределены по категориям
            """)
            
        except Exception as e:
            st.error(f"Ошибка при обработке файла: {e}")
            st.exception(e)
