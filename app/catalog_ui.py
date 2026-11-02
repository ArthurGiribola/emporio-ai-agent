"""Compact internal catalog view over trusted product DTOs, not generated prose."""

from html import escape

import streamlit as st

from app.catalog_view import catalog_page
from app.grounding import brl


def reset_catalog_navigation():
    st.session_state.catalog_page = 0
    st.session_state.catalog_pick = None


def _move_page(delta):
    st.session_state.catalog_page += delta
    st.session_state.catalog_pick = None


def show_catalog():
    view = st.session_state.catalog_view
    back, heading = st.columns([1, 8], vertical_alignment='center')
    if back.button('←', key='catalog_back', help='Voltar à conversa'):
        st.session_state.view = 'chat'
        st.rerun()
    heading.markdown(f'**Catálogo** · {st.session_state.shop_session.mode}')
    categories = {e.category_id: e.category for e in view.entries}
    st.session_state.setdefault('catalog_page', 0)
    st.session_state.setdefault('catalog_category', 0)
    st.session_state.setdefault('catalog_pick', None)
    with st.container(key='catalog_controls'):
        category, selection = st.columns(2, gap='small')
        category.selectbox('Categoria', [0, *sorted(categories, key=lambda i: categories[i].casefold())],
            format_func=lambda i: categories.get(i, 'Todas'), key='catalog_category', on_change=reset_catalog_navigation)
        rows, count, page, pages = catalog_page(view, st.session_state.catalog_category, st.session_state.catalog_page)
        st.session_state.catalog_page = page
        by_position = {e.position: e for e in rows}
        if st.session_state.catalog_pick not in by_position:
            st.session_state.catalog_pick = None
        selection.selectbox('Produto', [None, *by_position], key='catalog_pick',
            format_func=lambda p: 'Visão da página' if p is None else f'{p} · {by_position[p].name}')
    with st.container(height=260, border=False, key='catalog_rows'):
        selected = by_position.get(st.session_state.catalog_pick)
        if selected is not None:
            price = brl(selected.price_brl) if selected.price_brl is not None else 'Preço não confirmado'
            quantity = f'{selected.stock_quantity} unidades' if selected.stock_quantity is not None else 'não informado'
            available = 'Disponível' if selected.available else 'Indisponível'
            st.html(f'<section class="order-card"><div class="order-label">Item {selected.position}</div>'
                f'<h3>{escape(selected.name)}</h3><div class="catalog-price">{escape(price)}</div>'
                f'<div class="order-note">{escape(selected.category or "Categoria não informada")} · {available}</div>'
                f'<div class="catalog-stock">Estoque registrado: {quantity}</div></section>')
            for issue in selected.issues:
                st.caption(issue)
        else:
            for entry in rows:
                price = brl(entry.price_brl) if entry.price_brl is not None else 'Preço não confirmado'
                available = 'Disponível' if entry.available else 'Indisponível'
                st.html(f'<div class="catalog-row"><div class="catalog-head"><strong>{entry.position}. {escape(entry.name)}</strong>'
                    f'<span class="catalog-price">{escape(price)}</span></div>'
                    f'<div class="catalog-meta">{escape(entry.category or "Categoria não informada")} · {available}</div>' +
                    ''.join(f'<div class="catalog-meta">{escape(issue)}</div>' for issue in entry.issues) + '</div>')
            if not rows:
                st.caption('Nenhum produto nesta categoria para esta consulta.')
    previous, info, following = st.columns([1, 1, 1], vertical_alignment='center', gap='small')
    previous.button('Anterior', key='catalog_previous', on_click=_move_page, args=(-1,), disabled=page == 0, use_container_width=True)
    info.caption(f'Página {page + 1}/{pages} · {count} itens')
    following.button('Próxima', key='catalog_next', on_click=_move_page, args=(1,), disabled=page + 1 >= pages, use_container_width=True)
    if view.truncated:
        st.caption(f'Consulta parcial: {len(view.entries)} de {view.total_matches} resultados. Solicite todos para ampliar.')
    else:
        st.caption('Preços com promoções ativas, sem desconto extra de PIX. Números mantidos ao filtrar.')
    st.caption(st.session_state.shop_session.mode_caption)
