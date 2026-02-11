# Руководство для разработчиков LAppka

## Быстрый старт

```bash
pip install -r requirements.txt
streamlit run app_new.py
```

## Структура

- **config/** — настройки (MODULES, PAGE_CONFIG)
- **modules/** — логика приложения
- **utils/** — вспомогательные функции

## Модули

| Модуль | Путь | Основные файлы |
|--------|------|----------------|
| Анализ вопросов | `modules/question_analysis/` | module.py, visualizer.py, charts.py |
| IRT | `modules/irt_analysis/` | module.py, person_item_map.py, visualizer.py |
| Экспертная система | `modules/expert_system/` | module.py, expert_system.py, visualizer.py |
| Категоризация | `modules/categorization/` | module.py, categorizer.py, moodle_parser.py, moodle_generator.py |

## Работа с данными

### Загрузка
```python
from modules.base.data_loader import load_data

data = load_data(uploaded_file)  # HTML или CSV
```

### Парсинг
```python
from modules.base.data_parser import parse_question_data, parse_answers_data

questions = parse_question_data(data)
answers = parse_answers_data(data)
```

HTML-парсер (`modules/base/html_parser.py`) используется автоматически при загрузке `.html`. GIFT загружается в модуле категоризации через `moodle_parser`.

## Добавление модуля

1. Создать `modules/<name>/__init__.py` и `module.py`
2. В `module.py`: `def render():` — главная функция
3. Добавить в `config/settings.py` (MODULES)
4. Импортировать в `app_new.py` и добавить в `tab_functions`

## Полезные функции

```python
from utils.helpers import safe_float, safe_int, get_metric_class, get_difficulty_color
```

## Ресурсы

- [Streamlit](https://docs.streamlit.io/)
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Plotly](https://plotly.com/python/)
