"""
Модуль загрузки данных
Отвечает за загрузку и первичную обработку файлов
"""

import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
from config.settings import SUPPORTED_FILE_TYPES, PARSING_CONFIG


def parse_moodle_html(file_content):
    """Парсинг HTML файла Moodle через BeautifulSoup"""
    # Импортируем новый HTML парсер
    from modules.base.html_parser import parse_moodle_html as parse_html
    
    # Используем новый парсер
    return parse_html(file_content)


def load_data(file):
    """Загрузка и обработка данных из файла"""
    try:
        # Проверяем тип файла
        if hasattr(file, 'name'):
            if file.name.endswith('.html'):
                # Парсим HTML через BeautifulSoup
                file_content = file.read().decode('utf-8')
                return parse_moodle_html(file_content)
            else:
                # Для CSV файлов читаем без заголовка, все как строки
                df = pd.read_csv(file, encoding='utf-8', dtype=str, header=None)
                return df
        else:
            # Если это строка пути к файлу
            if str(file).endswith('.html'):
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return parse_moodle_html(content)
            else:
                df = pd.read_csv(file, encoding='utf-8', dtype=str, header=None)
                return df
    except:
        try:
            df = pd.read_csv(file, encoding='cp1251', dtype=str, header=None)
            return df
        except Exception as e:
            st.error(f"Ошибка загрузки файла: {e}")
            return None
