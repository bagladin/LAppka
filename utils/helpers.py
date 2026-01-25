"""
Вспомогательные функции
"""

def get_difficulty_color(difficulty):
    """Определение цвета на основе сложности вопроса"""
    try:
        diff_val = float(difficulty)
        if diff_val >= 70:
            return "easy"
        elif diff_val >= 40:
            return "medium"
        else:
            return "hard"
    except:
        return "medium"

def get_metric_class(value, metric_type):
    """Определение класса для метрики"""
    try:
        val = float(value)
        if metric_type == "discrimination":
            if val >= 30:
                return "metric-good"
            elif val >= 15:
                return "metric-warning"
            else:
                return "metric-bad"
        elif metric_type == "difficulty":
            if 30 <= val <= 70:
                return "metric-good"
            elif 20 <= val <= 80:
                return "metric-warning"
            else:
                return "metric-bad"
        else:
            return "metric-warning"
    except:
        return "metric-warning"

def safe_float(value, default=0.0):
    """Безопасное преобразование в float"""
    try:
        return float(value)
    except:
        return default

def safe_int(value, default=0):
    """Безопасное преобразование в int"""
    try:
        return int(float(value))
    except:
        return default
