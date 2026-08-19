"""
Модуль визуализации для экспертной системы
Отвечает за отображение экспертного анализа
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from modules.expert_system.expert_system import generate_expert_analysis, compute_kbtb
from modules.irt_analysis.person_item_map import (
    create_distribution_alignment_metrics,
    build_deficit_recommendation_plan,
)


def _build_recommendation_alignment_table(questions, kbtb_res, target_level):
    """Согласование структурных и распределенческих рекомендаций."""
    n = int(kbtb_res.get('n', 0))
    if n <= 0:
        return None

    # 1) Структурный план после выбытия вопросов "на переработку".
    # Целевая мощность сохраняется по исходному n, а фактическая база берется по cleaned-bank.
    clean_level_counts = kbtb_res.get('clean_level_counts', {'L': 0, 'M': 0, 'H': 0})
    rework_level_counts = kbtb_res.get('rework_level_counts', {'L': 0, 'M': 0, 'H': 0})
    target_frac = {
        'L': max(0.0, float(target_level.get('L', 30.0)) / 100.0),
        'M': max(0.0, float(target_level.get('M', 50.0)) / 100.0),
        'H': max(0.0, float(target_level.get('H', 20.0)) / 100.0),
    }
    struct_plan = {}
    for lvl in ['L', 'M', 'H']:
        target_count = n * target_frac[lvl]
        actual_count = float(clean_level_counts.get(lvl, 0))
        struct_plan[lvl] = int(max(0, round(target_count - actual_count)))

    struct_total = sum(struct_plan.values())

    # 2) План по дефицитным зонам (распределенческий, идентичен модулю 2).
    student_abilities = st.session_state.get("student_abilities_logit") or None
    apply_alignment_shift = bool(st.session_state.get("apply_alignment_shift", True))
    dist_metrics = create_distribution_alignment_metrics(
        questions,
        student_ability_distribution=student_abilities,
        apply_alignment_shift=apply_alignment_shift,
    )
    has_student_data = bool(dist_metrics.get('has_student_data', False))
    kstr = float(dist_metrics.get('kstr', 0.0))
    if has_student_data:
        deficit_plan = build_deficit_recommendation_plan(
            total_questions=n,
            kstr=kstr,
            deficit_zones=dist_metrics.get('deficit_zones', []) or [],
            total_override=struct_total,
        )
        dist_plan = deficit_plan.get('counts', {'L': 0, 'M': 0, 'H': 0})
        dist_total = int(deficit_plan.get('total', 0))
    else:
        dist_plan = {'L': 0, 'M': 0, 'H': 0}
        dist_total = 0

    if dist_total <= 0 and struct_total <= 0:
        return None

    if has_student_data:
        # 3) Коэффициент согласованности рекомендаций C.
        num = sum(abs(struct_plan[l] - dist_plan[l]) for l in ['L', 'M', 'H'])
        den = sum(struct_plan[l] + dist_plan[l] for l in ['L', 'M', 'H'])
        c_agree = 1.0 if den == 0 else max(0.0, min(1.0, 1.0 - (num / den)))

        # 4) Адаптивный вес структурного плана α(C):
        # при низком C приоритет структуры выше, при высоком C — баланс ближе к данным зон.
        alpha = 0.35 + 0.45 * (1.0 - c_agree)
        alpha = max(0.35, min(0.80, alpha))

        # 5) Итоговый согласованный план (структура + распределение).
        final_plan = {}
        for lvl in ['L', 'M', 'H']:
            final_plan[lvl] = int(round(alpha * struct_plan[lvl] + (1.0 - alpha) * dist_plan[lvl]))
    else:
        c_agree = None
        alpha = 1.0
        final_plan = dict(struct_plan)

    target_type = st.session_state.get("kbtb_target_type", {"O": 40.0, "Z": 60.0})
    open_ratio = max(0.0, min(1.0, float(target_type.get("O", 40.0)) / 100.0))

    def split_open_closed(total_count: int):
        if total_count <= 0:
            return 0, 0
        open_count = int(round(total_count * open_ratio))
        open_count = max(0, min(total_count, open_count))
        closed_count = total_count - open_count
        return open_count, closed_count

    l_open, l_closed = split_open_closed(final_plan['L'])
    m_open, m_closed = split_open_closed(final_plan['M'])
    h_open, h_closed = split_open_closed(final_plan['H'])

    df = pd.DataFrame([
        {
            'Уровень сложности': 'Легкие (L)',
            'На переработку (текущие)': int(rework_level_counts.get('L', 0)),
            'План по структуре КБТБ': struct_plan['L'],
            'План по дефицитным зонам': dist_plan['L'],
            'Добавить (согласованный итог)': final_plan['L'],
            'Открытые (итог)': l_open,
            'Закрытые (итог)': l_closed,
        },
        {
            'Уровень сложности': 'Средние (M)',
            'На переработку (текущие)': int(rework_level_counts.get('M', 0)),
            'План по структуре КБТБ': struct_plan['M'],
            'План по дефицитным зонам': dist_plan['M'],
            'Добавить (согласованный итог)': final_plan['M'],
            'Открытые (итог)': m_open,
            'Закрытые (итог)': m_closed,
        },
        {
            'Уровень сложности': 'Сложные (H)',
            'На переработку (текущие)': int(rework_level_counts.get('H', 0)),
            'План по структуре КБТБ': struct_plan['H'],
            'План по дефицитным зонам': dist_plan['H'],
            'Добавить (согласованный итог)': final_plan['H'],
            'Открытые (итог)': h_open,
            'Закрытые (итог)': h_closed,
        },
    ])
    return {
        'table': df,
        'agreement_c': c_agree,
        'kstr': kstr,
        'alpha': alpha,
        'has_student_data': has_student_data,
        'totals': {
            'struct': struct_total,
            'dist': dist_total,
            'final': sum(final_plan.values()),
        },
    }


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
        # Согласуем верхние текстовые рекомендации с логикой cleaned-bank.
        target_o = float(st.session_state.get('kbtb_o', 40))
        target_type = {'O': target_o, 'Z': float(100 - target_o)}
        weights_for_rec = st.session_state.get('kbtb_weights', {'type': 0.3, 'level': 0.3, 'rework': 0.2, 'count': 0.2})
        kbtb_for_rec = compute_kbtb(
            questions,
            target_type=target_type,
            target_level=target_level,
            min_questions=int(st.session_state.get('kbtb_min', 0)),
            weights=weights_for_rec,
        )
        n = int(kbtb_for_rec.get('n', 0))
        clean_levels = kbtb_for_rec.get('clean_level_counts', {'L': 0, 'M': 0, 'H': 0})
        target_h_count = int(round(n * float(target_level.get('H', 20)) / 100.0))
        target_l_count = int(round(n * float(target_level.get('L', 30)) / 100.0))
        add_hard = max(0, target_h_count - int(clean_levels.get('H', 0)))
        add_easy = max(0, target_l_count - int(clean_levels.get('L', 0)))
        if general_recommendations:
            st.markdown("### 💡 Рекомендации экспертной системы")
            for rec in general_recommendations:
                if "Слишком много легких" in rec:
                    if add_hard > 0:
                        rec = (
                            "Структура банка смещена к лёгким вопросам; "
                            f"по целевой структуре дефицит сложных ≈ {add_hard}. "
                            "Точный объём смотрите в согласованном плане ниже."
                        )
                    else:
                        rec = (
                            "Структура банка смещена к лёгким вопросам; "
                            "уточнение объёма пополнения смотрите в согласованном плане ниже."
                        )
                elif "Слишком много сложных" in rec:
                    if add_easy > 0:
                        rec = (
                            "Структура банка смещена к сложным вопросам; "
                            f"по целевой структуре дефицит лёгких ≈ {add_easy}. "
                            "Точный объём смотрите в согласованном плане ниже."
                        )
                    else:
                        rec = (
                            "Структура банка смещена к сложным вопросам; "
                            "уточнение объёма пополнения смотрите в согласованном плане ниже."
                        )
                if "критически" in rec.lower() or "критическое" in rec.lower():
                    st.error(f"🚨 **Критично:** {rec}")
                elif "рекомендуется" in rec.lower() or "следует" in rec.lower():
                    st.warning(f"⚠️ **Рекомендация:** {rec}")
                else:
                    st.info(f"ℹ️ **Информация:** {rec}")
            st.markdown("---")
        
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

        st.markdown("**Веса компонентов KBTB (сумма не более 1):**")
        w1c, w2c, w3c, w4c = st.columns(4)
        prev_w = st.session_state.get('kbtb_weights', {'type': 0.3, 'level': 0.3, 'rework': 0.2, 'count': 0.2})
        with w1c:
            w_type_default = min(1.0, max(0.0, float(prev_w.get('type', 0.3))))
            w_type = st.number_input("w тип", min_value=0.0, max_value=1.0, value=w_type_default, step=0.05, key="kbtb_w_type")
        with w2c:
            max_w_level = max(0.0, 1.0 - w_type)
            w_level_default = min(max_w_level, max(0.0, float(prev_w.get('level', 0.3))))
            w_level = st.number_input("w уровень", min_value=0.0, max_value=max_w_level, value=w_level_default, step=0.05, key="kbtb_w_level")
        with w3c:
            max_w_rework = max(0.0, 1.0 - w_type - w_level)
            w_rework_default = min(max_w_rework, max(0.0, float(prev_w.get('rework', 0.2))))
            w_rework = st.number_input("w дораб.", min_value=0.0, max_value=max_w_rework, value=w_rework_default, step=0.05, key="kbtb_w_rework")
        with w4c:
            max_w_count = max(0.0, 1.0 - w_type - w_level - w_rework)
            w_count_default = min(max_w_count, max(0.0, float(prev_w.get('count', 0.2))))
            w_count = st.number_input("w кол-во", min_value=0.0, max_value=max_w_count, value=w_count_default, step=0.05, key="kbtb_w_count")
        st.session_state['kbtb_weights'] = {'type': w_type, 'level': w_level, 'rework': w_rework, 'count': w_count}
        w_sum = w_type + w_level + w_rework + w_count
        if w_sum > 1.000001:
            st.error("Сумма весов не должна превышать 1. Уменьшите другой вес.")
        else:
            st.caption(f"Сумма весов: {w_sum:.2f} / 1.00")

    target_type = {'O': float(target_o), 'Z': float(100 - target_o)}
    target_level = {'L': float(target_l), 'M': float(target_m), 'H': float(target_h)}
    weights = st.session_state.get('kbtb_weights', {'type': 0.3, 'level': 0.3, 'rework': 0.2, 'count': 0.2})
    st.session_state['kbtb_target_level'] = target_level
    res = compute_kbtb(questions, target_type, target_level, min_questions=int(min_q), weights=weights)

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
    ws = res.get('weights', {'type': 0.3, 'level': 0.3, 'rework': 0.2, 'count': 0.2})
    st.caption(
        "Нормализованные веса: "
        f"тип={ws['type']:.2f}, уровень={ws['level']:.2f}, доработка={ws['rework']:.2f}, количество={ws['count']:.2f}"
    )

    # Справка с формулой KBTB (перед графиком структуры)
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
        
        **Веса:** задаются пользователем в интерфейсе, затем нормализуются так, чтобы сумма была равна 1.
        
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

    aligned = _build_recommendation_alignment_table(questions, res, target_level)
    if aligned is not None:
        st.markdown("### 🧩 Согласованный план пополнения банка")
        c = aligned['agreement_c']
        has_student_data = bool(aligned.get('has_student_data', False))
        c_label = (
            ("высокая" if c >= 0.75 else ("средняя" if c >= 0.50 else "низкая"))
            if c is not None else "недоступна"
        )
        st.table(aligned['table'])
        t = aligned['totals']
        n_rework = int(res.get('n_rework', 0))
        st.caption(
            f"Суммарно: на переработку={n_rework} / структура={t['struct']} / зоны={t['dist']} / добавить={t['final']} вопросов."
        )
        if not has_student_data:
            st.info(
                "Журнал оценок не загружен: зональная часть и коэффициент согласованности не рассчитываются, "
                "показан структурный план КБТБ."
            )
        with st.expander("📘 Как формируется согласованный план пополнения", expanded=False):
            st.markdown("""
            Для согласования рекомендаций используются два независимых источника:
            - **структурный план** (по целевой модели КБТБ),
            - **зональный план** (по дефицитным зонам диаграммы соответствия распределений).

            Обозначим уровни сложности как $u \\in \\{Л, С, Т\\}$:
            - $n^{\\text{стр}}_u$ — число вопросов для уровня $u$ из структурного плана;
            - $n^{\\text{деф}}_u$ — число вопросов для уровня $u$ из дефицитных зон;
            - $n^{\\text{итог}}_u$ — итоговая согласованная рекомендация.

            **1) Коэффициент согласованности рекомендаций**

            $$
            C = 1 - \\frac{\\sum\\limits_{u} \\left|n^{\\text{стр}}_u - n^{\\text{деф}}_u\\right|}
            {\\sum\\limits_{u} \\left(n^{\\text{стр}}_u + n^{\\text{деф}}_u\\right)}
            $$

            Интерпретация:
            - $C \\to 1$ — источники почти не конфликтуют;
            - $C \\to 0$ — источники расходятся, требуется более консервативное объединение.

            **2) Адаптивный вес структурного плана**

            $$
            \\alpha(C)=0.35+0.45(1-C), \\quad C\\in[0,1]
            $$

            где $\\alpha$ — доля структурного плана в итоговой формуле.
            Следовательно, автоматически выполняется ограничение $\\alpha\\in[0.35,0.80]$:
            при низком $C$ вес структуры выше, при высоком $C$ система больше доверяет данным дефицитных зон.

            **3) Итоговое объединение по уровням**

            $$
            n^{\\text{итог}}_u = \\left\\lfloor \\alpha\\,n^{\\text{стр}}_u + (1-\\alpha)\\,n^{\\text{деф}}_u + \\frac{1}{2} \\right\\rfloor
            $$

            После этого итог по каждому уровню делится на открытые/закрытые вопросы
            пропорционально целевой доле типов в КБТБ.
            """)
            if has_student_data and c is not None:
                st.markdown(
                    f"Текущие значения: согласованность **{c_label}** "
                    f"($C={c:.3f}$), $K_{{сс}}={aligned['kstr']:.3f}$, "
                    f"$\\alpha={aligned['alpha']:.1f}$."
                )
            else:
                st.markdown(
                    "Текущие значения: согласованность **недоступна**, "
                    "так как отсутствуют данные журнала оценок; используется только структурная часть КБТБ."
                )
    
    st.markdown("---")