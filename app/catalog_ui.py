"""Accessible compact catalog browser over trusted product DTOs."""

from html import escape
import re

import streamlit as st

from app.catalog_view import catalog_page
from app.grounding import brl


def reset_catalog_navigation():
    st.session_state.catalog_page = 0
    st.session_state.catalog_pick = None


def _filter_changed():
    # Widget keys are removed by Streamlit while the detail/chat view is shown.
    st.session_state.catalog_filters = (st.session_state.catalog_search, st.session_state.catalog_category)
    reset_catalog_navigation()


def _move_page(delta):
    st.session_state.catalog_page += delta


def _label(text):
    # Native button Markdown supports formatting, not untrusted markup.
    return re.sub(r'([\\`*_{}\[\]<>#!|])', r'\\\1', text)


def _details(entry):
    if st.button('← Voltar ao catálogo', key='catalog_detail_back'):
        st.session_state.catalog_pick = None
        st.rerun()
    price = brl(entry.price_brl) if entry.price_brl is not None else 'Preço não confirmado'
    quantity = f'{entry.stock_quantity} unidades' if entry.stock_quantity is not None else 'não informado'
    available = 'Disponível' if entry.available else 'Indisponível'
    with st.container(height=310, border=False, key='catalog_detail'):
        st.html(f'<section class="order-card"><div class="order-label">Item {entry.position} da lista</div>'
            f'<h3>{escape(entry.name)}</h3><div class="catalog-price">{escape(price)}</div>'
            f'<div class="order-note">{escape(entry.category or "Categoria não informada")} · {available}</div>'
            f'<div class="catalog-stock">Estoque registrado: {quantity}</div></section>')
        if entry.promotion_percent is not None:
            st.caption(f'Promoção ativa: {entry.promotion_percent.normalize():f}% de desconto sobre {brl(entry.base_price_brl)}. '
                       'Preço já inclui a promoção; não acumula desconto de PIX.')
        elif entry.price_brl is not None:
            st.caption('Sem promoção ativa. Preço exibido sem desconto de PIX.')
        for issue in entry.issues:
            st.caption(issue)
    if st.button('Perguntar sobre este produto', key='catalog_ask', use_container_width=True):
        # Agent resolves the stable list position to its record ID before tools.
        st.session_state.pending_question = f'Quero saber mais sobre o item {entry.position}: {entry.name}.'
        st.session_state.view = 'chat'
        st.rerun()


def show_catalog():
    view = st.session_state.catalog_view
    back, heading = st.columns([1, 8], vertical_alignment='center')
    if back.button('←', key='catalog_back', help='Voltar à conversa'):
        st.session_state.view = 'chat'
        st.rerun()
    heading.markdown('**Catálogo**')
    st.session_state.setdefault('catalog_page', 0)
    st.session_state.setdefault('catalog_pick', None)
    selected = next((e for e in view.entries if e.position == st.session_state.catalog_pick), None)
    if selected is not None:
        _details(selected)
        return
    search, category_id = st.session_state.get('catalog_filters', ('', 0))
    st.session_state.setdefault('catalog_search', search)
    st.session_state.setdefault('catalog_category', category_id)
    categories = {e.category_id: e.category for e in view.entries}
    with st.container(key='catalog_controls'):
        search_column, category = st.columns([3, 2], gap='small')
        search_column.text_input('Buscar produto', key='catalog_search', on_change=_filter_changed,
                                 placeholder='Nome do produto')
        category.selectbox('Categoria', [0, *sorted(categories, key=lambda i: categories[i].casefold())],
            format_func=lambda i: categories.get(i, 'Todas'), key='catalog_category', on_change=_filter_changed)
    rows, count, page, pages = catalog_page(view, st.session_state.catalog_category,
                                          st.session_state.catalog_page, st.session_state.catalog_search)
    st.session_state.catalog_page = page
    with st.container(height=310, border=False, key='catalog_rows'):
        for entry in rows:
            price = brl(entry.price_brl) if entry.price_brl is not None else 'Preço não confirmado'
            available = 'Disponível' if entry.available else 'Indisponível'
            label = f'Item {entry.position}\n\n**{_label(entry.name)}**\n\n{price} · {available}'
            if st.button(label, key=f'catalog_product_{entry.product_id}', width='stretch',
                         icon=':material/chevron_right:', icon_position='right'):
                st.session_state.catalog_pick = entry.position
                st.rerun()
        if not rows:
            st.caption('Nenhum produto corresponde a esta busca no catálogo consultado.')
    previous, info, following = st.columns([1, 1, 1], vertical_alignment='center', gap='small')
    previous.button('Anterior', key='catalog_previous', on_click=_move_page, args=(-1,), disabled=page == 0, use_container_width=True)
    info.caption(f'{page + 1}/{pages} · {count} itens')
    following.button('Próxima', key='catalog_next', on_click=_move_page, args=(1,), disabled=page + 1 >= pages, use_container_width=True)
    if rows:
        from app.catalog_view import PAGE_SIZE
        st.caption(f'Exibindo {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + len(rows)} de {count}. Itens mantêm os números da lista original.')
    if view.truncated:
        st.caption(f'Consulta parcial: {len(view.entries)} de {view.total_matches} resultados. Solicite todos para ampliar.')
