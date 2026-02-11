"""
Визуализация категоризации вопросов
"""

import html as html_module
import streamlit as st
from typing import Dict, List, Any, Set, Optional

from modules.categorization.categorizer import extract_question_text_from_gift, clean_html_tags


def _make_expand_callback(expand_id: str):
    def _():
        st.session_state['expanded_in_cat'] = expand_id
    return _


def _get_formulation(question: Dict[str, Any]) -> str:
    """Полная формулировка: из анализа, из GIFT или название."""
    analysis = question.get('analysis')
    moodle_q = question['moodle_question']
    if analysis and analysis.get('title'):
        return (analysis.get('title') or '').strip()
    raw = extract_question_text_from_gift(moodle_q.get('text', ''))
    if raw:
        return clean_html_tags(raw)
    return (moodle_q.get('name') or '').strip()


def _render_compact_card(
    q: Dict[str, Any],
    easiest_questions: Optional[Set[str]],
    low_attempts_questions: Optional[Set[str]],
    key_suffix: str,
) -> None:
    """Компактная карточка: формулировка, метрики, кнопка «Развернуть». Без таблицы ответов."""
    moodle_q = q['moodle_question']
    analysis = q.get('analysis')
    qid = moodle_q.get('id', '') or moodle_q.get('name_from_comment', '') or '?'
    # Добавляем позиции из анализа (5.1, 6.1) к ID из GIFT
    if analysis:
        pos_parts = [analysis.get('id', '')] + list(analysis.get('duplicate_ids') or [])
        pos_parts = [p for p in pos_parts if p]
        if pos_parts:
            qid = f"{qid} ({', '.join(pos_parts)})"
    qtype = q.get('type', 'Множественный выбор')
    try:
        difficulty = float(q.get('difficulty', 0))
    except (ValueError, TypeError):
        difficulty = 0.0
    try:
        discrimination = float(q.get('discrimination', 0))
    except (ValueError, TypeError):
        discrimination = 0.0

    formulation = _get_formulation(q)
    trunc = (formulation or '')[:180] + ('...' if len(formulation or '') > 180 else '')
    safe = html_module.escape(trunc).replace('\n', ' ')

    st.markdown(
        f'<div style="border:1px solid #ddd;border-radius:6px;padding:8px;margin:4px 0;font-size:0.9em">'
        f'<strong>{html_module.escape(str(qid))}</strong> · {html_module.escape(qtype)}<br/>'
        f'<span style="color:#555">{safe}</span><br/>'
        f'<small>Сложность {difficulty:.0f}% · Дискр. {discrimination:.2f}</small>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Причина «на переделку» для категории 3
    name = moodle_q.get('name', '')
    rev_reasons = []
    if discrimination < 0.3:
        rev_reasons.append('Низкая дискриминация')
    if easiest_questions and name in easiest_questions:
        rev_reasons.append('10% самых лёгких')
    if low_attempts_questions and name in low_attempts_questions:
        rev_reasons.append('Мало попыток')
    if rev_reasons:
        st.caption('⚠️ ' + ', '.join(rev_reasons))

    expand_id = ''
    if analysis and analysis.get('id') is not None:
        expand_id = str(analysis['id'])
    else:
        expand_id = str(moodle_q.get('id') or moodle_q.get('name_from_comment') or key_suffix)
    st.button(
        'Развернуть',
        key=f'expand_{key_suffix}',
        on_click=_make_expand_callback(expand_id),
    )


def _render_cards_row(questions: List[Dict[str, Any]], easiest: Optional[Set[str]], low_attempts: Optional[Set[str]], prefix: str) -> None:
    """Сетка по 3 карточки в ряд."""
    cols = 3
    for i in range(0, len(questions), cols):
        columns = st.columns(cols)
        for j in range(cols):
            idx = i + j
            if idx < len(questions):
                with columns[j]:
                    _render_compact_card(questions[idx], easiest, low_attempts, f"{prefix}_{idx}")


def display_categorization_tree(
    categorized_questions: Dict[str, List[Dict[str, Any]]],
    easiest_questions: Optional[Set[str]] = None,
    low_attempts_questions: Optional[Set[str]] = None,
    easy_threshold: float = 70.0,
) -> None:
    """
    Отображает категоризацию: слева — закрытые, справа — открытые в компактных карточках.
    Без таблицы ответов; формулировка в карточке; кнопка «Открыть в Модуле 1».
    """
    total = sum(len(lst) for lst in categorized_questions.values())
    without = sum(
        1
        for lst in categorized_questions.values()
        for q in lst
        if q.get('analysis') is None
    )
    if without > 0:
        st.warning(
            f"⚠️ {without} вопросов не сопоставлены с данными анализа. "
            "Для них использованы значения по умолчанию."
        )
    if total == 0:
        st.warning("Нет вопросов для категоризации")
        return

    # Развёрнутый вопрос поверх (по кнопке «Развернуть» в карточке)
    expanded = st.session_state.get('expanded_in_cat')
    if expanded is not None:
        found = None
        for _, items in categorized_questions.items():
            for q in items:
                a = q.get('analysis')
                m = q['moodle_question']
                if (a and str(a.get('id')) == str(expanded)) or str(m.get('id') or '') == str(expanded) or str(m.get('name_from_comment') or '') == str(expanded):
                    found = q
                    break
            if found:
                break
        if found:
            from modules.question_analysis.visualizer import display_single_question
            a = found.get('analysis') or {}
            m = found['moodle_question']
            adapter = {
                'id': a.get('id') or m.get('id') or m.get('name_from_comment') or '?',
                'title': _get_formulation(found),
                'type': found.get('type', 'Множественный выбор'),
                'attempts': a.get('attempts', '0'),
                'difficulty': found.get('difficulty', 0),
                'discrimination': found.get('discrimination', 0),
                'efficiency': a.get('efficiency', '0'),
                'weight': a.get('weight', '0'),
                'answers': a.get('answers', []),
            }
            st.markdown("---")
            st.markdown("#### 📌 Развёрнутый вопрос")
            display_single_question(adapter)
            if st.button("Закрыть", key="close_expanded_cat"):
                st.session_state['expanded_in_cat'] = None
                st.rerun()
            st.markdown("---")
        else:
            st.session_state['expanded_in_cat'] = None

    tab1, tab2, tab3 = st.tabs([
        "📁 Категория 1: Легкие вопросы",
        "📁 Категория 2: Средние + Сложные вопросы",
        "⚠️ Категория 3: На переделку",
    ])

    # --- Категория 1: Легкие ---
    with tab1:
        st.markdown(f"### 📁 Категория 1: Легкие вопросы (≥ {easy_threshold:.0f}%)")
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("#### Закрытые вопросы")
            st.caption("Остальные типы вопросов")
            closed = categorized_questions.get('1.2 Легкие/Закрытые', [])
            if closed:
                _render_cards_row(closed, easiest_questions, low_attempts_questions, "c1_closed")
            else:
                st.info("Нет вопросов")
        with col_right:
            st.markdown("#### Открытые вопросы")
            st.caption("Числовой ответ, Короткий ответ")
            open_q = categorized_questions.get('1.1 Легкие/Открытые', [])
            if open_q:
                _render_cards_row(open_q, easiest_questions, low_attempts_questions, "c1_open")
            else:
                st.info("Нет вопросов")

    # --- Категория 2: Средние + Сложные ---
    with tab2:
        st.markdown(f"### 📁 Категория 2: Средние + Сложные (< {easy_threshold:.0f}%)")
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("#### Закрытые вопросы")
            st.caption("Остальные типы вопросов")
            closed = categorized_questions.get('2.2 Средние+Сложные/Закрытые', [])
            if closed:
                _render_cards_row(closed, easiest_questions, low_attempts_questions, "c2_closed")
            else:
                st.info("Нет вопросов")
        with col_right:
            st.markdown("#### Открытые вопросы")
            st.caption("Числовой ответ, Короткий ответ")
            open_q = categorized_questions.get('2.1 Средние+Сложные/Открытые', [])
            if open_q:
                _render_cards_row(open_q, easiest_questions, low_attempts_questions, "c2_open")
            else:
                st.info("Нет вопросов")

    # --- Категория 3: На переделку ---
    with tab3:
        st.markdown("### ⚠️ Категория 3: На переделку")
        st.caption("Плохая дискриминация (< 0.3), 10% самых лёгких, мало попыток")
        rev = categorized_questions.get('3 На переделку', [])
        if rev:
            st.markdown(f"**Всего: {len(rev)}**")
            _render_cards_row(rev, easiest_questions, low_attempts_questions, "c3")
        else:
            st.info("Нет вопросов")

        st.markdown("---")
        st.markdown("""
**📚 Объяснение для преподавателей:**

**Дискриминация** — это способность вопроса различать сильных и слабых студентов.
- **Высокая дискриминация (>0.3)**: вопрос хорошо различает студентов по способностям
- **Низкая дискриминация (<0.3)**: вопрос плохо различает студентов, требует пересмотра

**Что делать с проблемными вопросами:**
1. **Пересмотрите формулировку** — возможно, вопрос слишком очевидный или запутанный
2. **Проверьте варианты ответов** — возможно, неправильные ответы слишком очевидны
3. **Добавьте промежуточные варианты** — сделайте вопрос более дифференцирующим
4. **Рассмотрите удаление** — если вопрос не улучшается после правок
        """)


def get_revision_reason(question: Dict[str, Any], easiest_questions: Optional[Set[str]] = None) -> str:
    reasons = []
    if question.get('discrimination', 0) < 0.3:
        reasons.append("Низкая дискриминация")
    name = question.get('moodle_question', {}).get('name', '')
    if easiest_questions and name in easiest_questions:
        reasons.append("10% самых лёгких")
    return ", ".join(reasons) if reasons else "Не указано"
