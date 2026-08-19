"""
Настройки приложения
Здесь хранятся все конфигурационные параметры
"""

# Настройки страницы Streamlit
PAGE_CONFIG = {
    "page_title": "Учебная аналитика Moodle",
    "page_icon": "📊",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Настройки модулей
MODULES = {
    "question_analysis": {
        "name": "📈 Модуль 1: Анализ вопросов",
        "description": "Визуализация тестовых вопросов с вариантами ответов и частотами"
    },
    "irt_analysis": {
        "name": "🎯 Модуль 2: Соответствие распределений",
        "description": "Диаграмма соответствия распределений и коэффициент Kstr"
    },
    "expert_system": {
        "name": "🧠 Модуль 3: Экспертная система: Интеллектуальный анализ",
        "description": "Экспертная система для интеллектуального анализа"
    },
    "categorization": {
        "name": "📂 Модуль 4: Категоризация",
        "description": "Категоризация вопросов"
    }
}

# Поддерживаемые типы файлов
SUPPORTED_FILE_TYPES = ['csv', 'html']

# Настройки парсинга
PARSING_CONFIG = {
    "encoding": ['utf-8', 'cp1251'],
    "difficulty_thresholds": {
        "easy": 70,
        "medium": 40,
        "hard": 0
    },
    "discrimination_thresholds": {
        "good": 30,
        "warning": 15,
        "bad": 0
    }
}
