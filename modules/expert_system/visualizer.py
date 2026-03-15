"""
Модуль визуализации для экспертной системы
Отвечает за отображение экспертного анализа
"""

import streamlit as st
import plotly.graph_objects as go

from modules.expert_system.expert_system import generate_expert_analysis, compute_kbtb


def display_expert_system(questions):
    """Отображение экспертной системы"""
    questions = [q for q in questions if not q.get('is_main_question', False)]
    try:
        expert_analysis = generate_expert_analysis(questions)
        
        if not expert_analysis:
            st.warning("Не удалось сгенерировать экспертный анализ")
            return
        
        # Рекомендации экспертной системы — СРАЗУ НАВЕРХУ
        general_recommendations = expert_analysis.get('general_recommendations', [])
        target_level = st.session_state.get('kbtb_target_level') or {'L': 30, 'M': 50, 'H': 20}
        question_analysis = expert_analysis.get('question_analysis', {})
        n = question_analysis.get('total_questions', 0)
        easy_a, medium_a, hard_a = (
            question_analysis.get('easy_questions', 0),
            question_analysis.get('medium_questions', 0),
            question_analysis.get('hard_questions', 0),
        )
        if general_recommendations:
            st.markdown("### 💡 Рекомендации экспертной системы")
            for rec in general_recommendations:
                if "Слишком много легких" in rec:
                    add_hard = max(0, round(n * target_level.get('H', 20) / 100) - hard_a)
                    if add_hard > 0:
                        rec = f"{rec} (ориентировочно +{add_hard} сложных)"
                elif "Слишком много сложных" in rec:
                    add_easy = max(0, round(n * target_level.get('L', 30) / 100) - easy_a)
                    if add_easy > 0:
                        rec = f"{rec} (ориентировочно +{add_easy} лёгких)"
                if "критически" in rec.lower() or "критическое" in rec.lower():
                    st.error(f"🚨 **Критично:** {rec}")
                elif "рекомендуется" in rec.lower() or "следует" in rec.lower():
                    st.warning(f"⚠️ **Рекомендация:** {rec}")
                else:
                    st.info(f"ℹ️ **Информация:** {rec}")
            st.markdown("---")
        
        # Анализ соответствия
        match_analysis = expert_analysis.get('match_analysis', {})
        if match_analysis:
            st.markdown("### 🎯 Анализ соответствия способностей и сложности")
            
            overlap_pct = match_analysis.get('overlap_percentage', 0)
            match_quality = match_analysis.get('match_quality', 'неизвестно')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Перекрытие распределений", 
                    f"{overlap_pct:.1f}%",
                    help="Процент перекрытия между способностями студентов и сложностью вопросов"
                )
            
            with col2:
                quality_color = {
                    'отличное': '🟢',
                    'хорошее': '🟡', 
                    'удовлетворительное': '🟠',
                    'плохое': '🔴'
                }.get(match_quality, '⚪')
                
                st.metric(
                    "Качество соответствия", 
                    f"{quality_color} {match_quality}",
                    help="Оценка соответствия между способностями и сложностью"
                )
            
            # Рекомендации по соответствию
            match_recommendations = match_analysis.get('recommendations', [])
            if match_recommendations:
                st.markdown("**Рекомендации по соответствию:**")
                for rec in match_recommendations:
                    st.write(f"• {rec}")
            
            # Справка с формулой коэффициента покрытия - ПЕРЕД объяснением
            with st.expander("📖 Справка: Формула коэффициента перекрытия"):
                st.markdown("""
                ### Коэффициент перекрытия (Overlap Index)
                
                Доля диапазона способностей студентов, пересекающаяся с диапазоном сложности вопросов теста (в логит-шкале).
                
                $$
                \\text{Перекрытие} = \\frac{L_{\\text{пересечение}}}{L_{\\text{общий}}} \\cdot 100\\%
                $$
                
                где:
                
                - $L_{\\text{пересечение}}$ — длина пересечения диапазонов сложности вопросов и способностей студентов  
                - $L_{\\text{общий}}$ — общий диапазон, охватывающий и студентов, и вопросы  
                
                **Пересечение вычисляется как:**
                
                $$
                L_{\\text{пересечение}} = \\max(0, \\min(\\theta_{\\max}, b_{\\max}) - \\max(\\theta_{\\min}, b_{\\min}))
                $$
                
                **Общий диапазон:**
                
                $$
                L_{\\text{общий}} = \\max(\\theta_{\\max}, b_{\\max}) - \\min(\\theta_{\\min}, b_{\\min})
                $$
                
                где:
                - $\\theta_{\\min}, \\theta_{\\max}$ — минимальная и максимальная способность студентов  
                - $b_{\\min}, b_{\\max}$ — минимальная и максимальная сложность вопросов
                """)
            
            # Добавляем объяснение для преподавателей
            st.markdown("""
            **📚 Объяснение для преподавателей:**
            
            **Соответствие способностей и сложности** показывает, насколько хорошо вопросы подходят для ваших студентов.
            - **Высокое перекрытие (>70%)**: вопросы хорошо подходят для студентов
            - **Низкое перекрытие (<30%)**: вопросы слишком легкие или сложные для студентов
            
            **Что означает качество соответствия:**
            - **Отличное**: тест идеально подходит для студентов
            - **Хорошее**: тест в целом подходит, есть небольшие проблемы
            - **Удовлетворительное**: тест подходит, но нужны улучшения
            - **Плохое**: тест не подходит для студентов, требуется серьезная переработка
            """)
        
        # KBTB
        _render_kbtb_block(questions)
        
    except Exception as e:
        st.error(f"Ошибка при выполнении экспертного анализа: {e}")
        st.write("Попробуйте загрузить файл с корректными данными или обратитесь к разработчику.")

def _render_kbtb_block(questions):
    """Блок KBTB: целевые доли, расчёт, интерпретация, разбивка штрафов и график."""
    st.markdown("### ⚖️ Коэффициент сбалансированности тестовой базы (КБTБ)")

    with st.expander("🎯 Целевая модель (доли)", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            target_o = st.slider("Доля открытых (О), %", 0, 100, 40, step=5, key="kbtb_o")
            st.caption(f"Закрытые (З): {100 - target_o}%")
        with c2:
            min_q = st.number_input("Мин. число вопросов (0 = не учитывать)", 0, 1000, 0, key="kbtb_min")
        st.markdown("**Доли сложности (л + с + т ≤ 100%, шаг 5%):**")
        l1, l2, l3 = st.columns(3)
        prev = st.session_state.get('kbtb_lmh', {'L': 30, 'M': 50, 'H': 20})
        with l1:
            target_l = st.slider("Лёгкие (л), %", 0, 100, int(prev.get('L', prev.get('л', 30))), step=5, key="kbtb_l",
                                help="Сумма л+с+Т не должна превышать 100%")
        max_m = 100 - target_l
        with l2:
            default_m = min(prev.get('M', prev.get('с', 50)), max_m) if max_m > 0 else 0
            default_m = (default_m // 5) * 5
            if max_m <= 0:
                target_m = 0
                st.metric("Средние (с), %", 0, help="При л=100% остаётся 0% для с и т")
            else:
                target_m = st.slider("Средние (с), %", 0, max_m, default_m, step=5, key="kbtb_m",
                                    help="Остаток для с: до " + str(max_m) + "%")
        max_h = 100 - target_l - target_m
        with l3:
            default_h = min(prev.get('H', prev.get('т', prev.get('Т', 20))), max_h) if max_h > 0 else 0
            default_h = (default_h // 5) * 5
            if max_h <= 0:
                target_h = 0
                st.metric("Сложные (т), %", 0, help="л+с=100%, для т остаётся 0%")
            else:
                target_h = st.slider("Сложные (т), %", 0, max_h, default_h, step=5, key="kbtb_h",
                                    help="Остаток для т: до " + str(max_h) + "%")
        st.session_state['kbtb_lmh'] = {'L': target_l, 'M': target_m, 'H': target_h}

    target_type = {'O': float(target_o), 'Z': float(100 - target_o)}
    target_level = {'L': float(target_l), 'M': float(target_m), 'H': float(target_h)}
    st.session_state['kbtb_target_level'] = target_level
    res = compute_kbtb(questions, target_type, target_level, min_questions=int(min_q))

    kbtb = res['kbtb']
    interp = res['interpretation']
    p_type = res['penalty_type']
    p_level = res['penalty_level']
    p_rework = res['penalty_rework']
    p_count = res['penalty_count']

    # Итоговый коэффициент и интерпретация
    st.metric("KБTБ", f"{kbtb * 100:.1f}%", f"Интерпретация: {interp}")
    # Разбивка штрафов
    st.markdown("**Влияние на коэффициент:**")
    if p_type > 0.001:
        st.caption(f"−{p_type * 100:.1f}% из-за перекоса по типам вопросов (О/З)")
    if p_level > 0.001:
        st.caption(f"−{p_level * 100:.1f}% из-за перекоса по сложности (л/с/Т)")
    if p_rework > 0.001:
        st.caption(f"−{p_rework * 100:.1f}% из-за вопросов на переработку")
    if p_count > 0.001:
        st.caption(f"−{p_count * 100:.1f}% из-за недостатка количества вопросов")
    if p_type <= 0.001 and p_level <= 0.001 and p_rework <= 0.001 and p_count <= 0.001:
        st.caption("Штрафы отсутствуют.")

    # График: целевые vs фактические (O, Z, L, M, H)
    cats = ['О (открытые)', 'З (закрытые)', 'л (лёгкие)', 'с (средние)', 'т (сложные)']
    target_pct = [
        res['target_type']['O'] * 100, res['target_type']['Z'] * 100,
        res['target_level']['L'] * 100, res['target_level']['M'] * 100, res['target_level']['H'] * 100
    ]
    actual_pct = [
        res['actual_type']['O'] * 100, res['actual_type']['Z'] * 100,
        res['actual_level']['L'] * 100, res['actual_level']['M'] * 100, res['actual_level']['H'] * 100
    ]
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Целевая доля, %', x=cats, y=target_pct, marker_color='#3498db'))
    fig.add_trace(go.Bar(name='Фактическая доля, %', x=cats, y=actual_pct, marker_color='#e74c3c'))
    fig.update_layout(barmode='group', xaxis_tickangle=-30, height=320, margin=dict(t=20, b=80),
                      legend=dict(orientation='h', yanchor='bottom', y=1.02),
                      yaxis=dict(title='Доля, %', range=[0, 105]))
    st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Всего вопросов: {res['n']}, из них «на переработку»: {res['n_rework']} ({res['R']*100:.1f}%).")
    
    # Справка с формулой KBTB
    with st.expander("📖 Справка: Формула KBTB"):
        st.markdown("""
        ### Коэффициент сбалансированности тестовой базы (KBTB)
        
        $$
        \\text{КБТБ} = 1 - w_1 \\cdot D_{\\text{тип}} - w_2 \\cdot D_{\\text{уровень}} - w_3 \\cdot P_{\\text{переделка}} - w_4 \\cdot P_{\\text{количество}}
        $$
        
        где:
        
        **Отклонения:**
        - $D_{\\text{тип}} = 0.5 \\cdot (|a_О - t_О| + |a_З - t_З|)$ — отклонение по типам (открытые/закрытые)
        - $D_{\\text{уровень}} = 0.5 \\cdot (|a_Л - t_Л| + |a_С - t_С| + |a_Т - t_Т|)$ — отклонение по сложности (легкие/средние/трудные)
        
        **Штрафы:**
        - $P_{\\text{переработка}} = 1 - e^{-3R}$ — штраф за вопросы на переработку
        - $P_{\\text{количество}} = \\begin{cases} 0 & \\text{если } n \\geq n_{\\text{мин}} \\\\ 1 - \\frac{n}{n_{\\text{мин}}} & \\text{иначе} \\end{cases}$ — штраф за недостаток вопросов
        
        **Веса:** $w_1 = 0.3$, $w_2 = 0.3$, $w_3 = 0.2$, $w_4 = 0.2$
        
        **Обозначения:**
        - $a_О, a_З$ — фактические доли открытых/закрытых вопросов
        - $t_О, t_З$ — целевые доли открытых/закрытых вопросов
        - $a_Л, a_С, a_Т$ — фактические доли легких/средних/трудных вопросов
        - $t_Л, t_С, t_Т$ — целевые доли легких/средних/трудных вопросов
        - $R$ — доля вопросов на переработку
        - $n$ — количество вопросов
        - $n_{\\text{мин}}$ — минимальное требуемое количество вопросов
        
        **Интерпретация:** КБТБ ∈ [0, 1]; 1 — идеальная сбалансированность.
        """)
    
    st.markdown("---")