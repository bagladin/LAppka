# Архитектура LAppka

## Обзор

Модульная система учебной аналитики для Moodle: сопоставление HTML-статистики с GIFT-банком вопросов, категоризация, расчёт KBTB, рекомендации экспертной системы, Person-Item Map.

## Структура проекта

```
LAppka/
├── app_new.py              # Главный файл
├── config/
│   └── settings.py         # Настройки, список модулей
├── modules/
│   ├── base/               # Базовый слой
│   │   ├── data_loader.py  # Загрузка HTML
│   │   ├── data_parser.py  # Парсинг и структурирование
│   │   └── html_parser.py  # Парсинг HTML Moodle
│   ├── question_analysis/  # Модуль 1: Анализ вопросов
│   ├── irt_analysis/       # Модуль 2: Person-Item Map
│   ├── expert_system/      # Модуль 3: KBTB, рекомендации
│   └── categorization/    # Модуль 4: Категоризация, GIFT
├── utils/                  # helpers.py, constants.py
├── static/                 # CSS, изображения (static/css/, static/images/)
├── data/                   # Тестовые данные (data/test_files/)
└── docs/
```

## Принципы

- **Модульность**: каждый модуль — отдельная функциональность
- **Разделение ответственности**: base — парсинг; модули — анализ, визуализация, экспорт
- **Единый источник данных**: HTML + GIFT загружаются один раз, используются во всех модулях

## Модули

| Модуль | Функции |
|--------|---------|
| **base** | Парсинг HTML (BeautifulSoup), загрузка данных |
| **question_analysis** | Таблица вопросов, метрики, цветовое кодирование по сложности |
| **irt_analysis** | Person-Item Map в логит-шкале, коэффициент перекрытия |
| **expert_system** | KBTB, целевые доли L/M/H (связанные слайдеры), рекомендации с количеством |
| **categorization** | Сопоставление с GIFT, категории, экспорт в GIFT с суффиксом (Lappka) |

## Поток данных

1. HTML-отчёт → `html_parser` / `data_loader` → структурированные данные вопросов
2. GIFT → `moodle_parser` → список вопросов банка
3. Сопоставление (SequenceMatcher) → обогащённые данные
4. Категоризация → L/M/H, O/Z, «на переработку»
5. KBTB, рекомендации, визуализация

## Диаграмма компонентов

```mermaid
flowchart LR
    U[Пользователь] --> A[app_new.py / Streamlit UI]
    A --> Q[Модуль 1: question_analysis]
    A --> I[Модуль 2: irt_analysis]
    A --> E[Модуль 3: expert_system]
    A --> C[Модуль 4: categorization]

    Q --> B[base: data_loader + html_parser + data_parser]
    C --> MP[moodle_parser]
    C --> CAT[categorizer]
    E --> K[KBTB + overlap]

    B --> S[(st.session_state)]
    Q --> S
    I --> S
    E --> S
    C --> S
```

## Контракты обмена данными

| Модуль | Вход | Выход |
|--------|------|-------|
| `question_analysis` | HTML-выгрузка Moodle | `questions_data`, `answers_data` в `session_state` |
| `irt_analysis` | `questions_data` | Person-Item Map, overlap-метрики |
| `expert_system` | `questions_data` | KBTB, рекомендации, штрафы |
| `categorization` | GIFT + `questions_data` | Категории 1.1/1.2/2.1/2.2/3 и экспорт GIFT |

## Добавление модуля

1. Создать `modules/<name>/` с `__init__.py`, `module.py`
2. В `module.py` реализовать `def render():`
3. Добавить в `config/settings.py` (MODULES)
4. Импортировать и добавить в `app_new.py` (tab_functions)
