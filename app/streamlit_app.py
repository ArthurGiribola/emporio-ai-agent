"""One-page local demonstration. Launch with python -m app.web."""

import re
from html import escape

import streamlit as st

from app.web_session import ChatSession
from app.grounding import brl
from app.catalog_ui import show_catalog, reset_catalog_navigation


def show_answer(message):
    if message.get("error"):
        st.warning(message["text"])
    else:
        # BRL dollar signs are currency, not Markdown/LaTeX math delimiters.
        text = re.sub(r"(?<!\\)\$", r"\\$", message["text"])
        st.markdown(text, unsafe_allow_html=False)
        if message.get('catalog_token') == st.session_state.get('catalog_token') and message.get('catalog_token') is not None:
            if st.button('Abrir catálogo', key=f"catalog_open_{message['catalog_token']}"):
                st.session_state.view = 'catalog'
                st.rerun()
    references = message.get("references", ())
    if references:
        # A single compact source note avoids one spaced block per section.
        prefix = "Synthetic policy · " if references[0].startswith("Synthetic policy · ") else "Store policy · "
        st.caption(prefix + "; ".join(reference.removeprefix(prefix) for reference in references))


SUGGESTIONS = {
    "Ver produtos": "Quais produtos sintéticos estão disponíveis? Liste todos do mais barato ao mais caro.",
    "Preços": "Qual é o preço do produto sintético 1 pagando com PIX?",
    "Meu pedido": "Qual é o status e o total registrado do pedido sintético 1? Há rastreamento?",
    "Políticas": "Qual é a política sintética de devolução? Cite as seções e páginas disponíveis.",
}

LOCAL_SUGGESTIONS = {
    "Ver produtos": "Liste o catálogo completo, incluindo produtos indisponíveis e inativos, do mais barato ao mais caro.",
    "Preços": "Quais promoções estão disponíveis?",
    "Meu pedido": "Qual é o status do meu pedido?",
    "Políticas": "Qual é a política de devolução para compras online? Cite as seções e páginas disponíveis.",
}


def toggle_theme():
    st.session_state.light_theme = not st.session_state.get("light_theme", False)


def style(light):
    colors = ("#f6f6f6", "#ffffff", "#ededed", "#171717", "#737373", "#dedede", "#252525", "#ffffff") if light else (
        "#000000", "#111111", "#242424", "#f5f5f5", "#a3a3a3", "#303030", "#e8e8e8", "#171717")
    bg, panel, bubble, text, muted, border, user, user_text = colors
    # Static CSS only. Keys scope styling; the few native chat selectors are
    # covered by browser checks against the pinned optional Streamlit version.
    st.html(f"""<style>
    .stApp {{background:{bg};color:{text};font-family:Inter,ui-sans-serif,system-ui,sans-serif;}}
    header[data-testid="stHeader"] {{display:none;}}
    .stMainBlockContainer {{max-width:650px;padding: max(32px,7vh) 16px 24px;}}
    .st-key-mini_chat {{background:{panel};border:1px solid {border};border-radius:22px;padding:22px 22px 16px;box-shadow:none;color:{text};}}
    .st-key-mini_chat p, .st-key-mini_chat label {{color:{text};}}
    .st-key-mini_chat [data-testid="stCaptionContainer"] p {{color:{muted};font-size:11px;}}
    .st-key-mini_chat h3 {{color:{text};font-size:20px;}}
    .st-key-order_detail {{border-top:1px solid {border};padding-top:14px;}}
    .st-key-order_detail [data-testid="stVerticalBlock"] {{gap:10px;}}
    .st-key-catalog_screen [data-testid="stVerticalBlock"] {{gap:8px;}}
    .catalog-price {{font-weight:600;white-space:nowrap;font-size:13px;}}
    .catalog-stock {{margin-top:14px;font-size:13px;}}
    .st-key-catalog_controls [data-testid="stWidgetLabel"] p {{font-size:11px;}}
    .stMainBlockContainer:has(.st-key-catalog_screen) {{padding-top:24px;}}
    /* Streamlit 1.66: the full-width button contains two centered flex wrappers.
       Stretch its text wrapper; the native right icon stays outside that column. */
    .st-key-mini_chat .st-key-catalog_rows button {{width:100%;text-align:left;border:0;border-bottom:1px solid {border};border-radius:0;min-height:68px;padding:8px 10px;margin:0;}}
    .st-key-catalog_rows button > div {{width:100%;justify-content:flex-start;}}
    .st-key-catalog_rows button [data-has-shortcut] {{flex:1;min-width:0;justify-content:flex-start;}}
    .st-key-catalog_rows button [data-testid="stMarkdownContainer"] {{flex:1;width:100%;min-width:0;text-align:left;}}
    .st-key-catalog_rows button [data-testid="stMarkdownContainer"] p {{text-align:left;font-size:11px;line-height:16px;margin:0;padding:0;}}
    .st-key-catalog_rows button [data-testid="stMarkdownContainer"] p:first-child {{color:{muted};font-size:10px;line-height:14px;}}
    .st-key-catalog_rows button strong {{display:block;font-size:13px;font-weight:500;line-height:18px;}}
    .st-key-catalog_rows button:focus-visible {{outline:2px solid {muted};outline-offset:-2px;}}
    .order-summary {{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px;}}
    .order-summary h2 {{font-size:26px;letter-spacing:-.8px;margin:0;color:{text};padding:0;}}
    .order-label {{font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:{muted};font-weight:600;}}
    .order-badge {{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid {border};border-radius:99px;background:{bubble};color:{text};font-size:11px;font-weight:600;}}
    .order-badge::before {{content:"";width:5px;height:5px;border-radius:50%;background:currentColor;}}
    .order-card {{border:1px solid {border};border-radius:14px;padding:14px 16px;margin-bottom:10px;color:{text};}}
    .order-item {{display:flex;align-items:center;gap:12px;margin-top:12px;font-size:13px;line-height:1.4;overflow-wrap:anywhere;}}
    .order-quantity {{display:flex;align-items:center;justify-content:center;min-width:32px;height:32px;border:1px solid {border};border-radius:9px;background:{bubble};font-size:12px;font-weight:600;}}
    .order-total {{display:flex;justify-content:space-between;align-items:center;gap:12px;}}
    .order-total strong {{font-size:25px;letter-spacing:-.6px;white-space:nowrap;color:{text};}}
    .order-note {{font-size:11px;line-height:1.55;color:{muted};margin-top:8px;}}
    .order-empty {{display:flex;align-items:center;gap:12px;margin-top:12px;}}
    .order-icon {{width:34px;height:34px;flex-shrink:0;border:1px solid {border};border-radius:10px;display:flex;align-items:center;justify-content:center;color:{muted};}}
    .order-empty strong {{font-size:12px;font-weight:500;color:{text};}}
    .order-tracking {{font-size:13px;margin-top:10px;overflow-wrap:anywhere;}}
    .st-key-order_detail [data-testid="stCaptionContainer"] * {{color:{muted} !important;}}
    .order-progress {{height:4px;border-radius:4px;background:{border};overflow:hidden;}}
    .order-progress > div {{height:100%;background:{muted};}}
    .brand {{display:flex;gap:12px;align-items:center;margin:0 0 12px;}}
    .brand-mark {{border:1px solid {border};border-radius:12px;width:40px;height:40px;display:flex;align-items:center;justify-content:center;gap:3px;flex-shrink:0;}}
    .brand-mark i {{display:block;width:3px;background:{text};border-radius:4px;}}
    .brand strong {{font-size:20px;font-weight:700;letter-spacing:-.6px;line-height:1.2;}}
    .brand small {{display:block;color:{muted};font-size:12px;margin-top:4px;}}
    .brand .mode-indicator {{display:inline;color:{muted};font-size:10px;letter-spacing:.6px;margin-left:8px;}}
    .st-key-mini_chat button {{background:transparent;color:{text};border:1px solid {border};border-radius:12px;font-size:12px;box-shadow:none;}}
    .st-key-mini_chat button:hover {{background:{bubble};border-color:{muted};color:{text};}}
    .st-key-mini_chat [data-testid="stHorizontalBlock"] {{flex-wrap:nowrap;}}
    .st-key-mini_chat [data-testid="stColumn"] {{min-width:0 !important;}}
    .st-key-actions button {{border-radius:24px;min-height:36px;}}
    .st-key-mini_chat [data-testid="stChatMessage"] {{background:{bubble};border-radius:16px;padding:14px;margin:0 0 12px;gap:0;}}
    .st-key-mini_chat [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{background:{user};margin-left:56px;width:calc(100% - 56px);}}
    .st-key-mini_chat [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{color:{user_text};}}
    .st-key-mini_chat [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) * {{color:{user_text} !important;white-space:pre-wrap;overflow-wrap:anywhere;}}
    .st-key-mini_chat [data-testid="stChatMessageAvatarUser"],.st-key-mini_chat [data-testid="stChatMessageAvatarAssistant"] {{display:none;}}
    .st-key-mini_chat [data-testid="stChatMessage"] * {{color:{text};}}
    .st-key-mini_chat [data-testid="stChatMessage"] p {{font-size:14px;line-height:1.6;}}
    .st-key-mini_chat [data-testid="stChatInput"] {{border:1px solid {border};border-radius:14px;background:{bubble};}}
    .st-key-mini_chat [data-testid="stChatInput"] > div {{background:{bubble};color:{text};border-color:{border};box-shadow:none;}}
    .st-key-mini_chat [data-testid="stChatInput"]:focus-within > div {{border-color:{muted};}}
    .st-key-mini_chat textarea {{background:{bubble};color:{text};font-size:14px;}}
    .st-key-mini_chat textarea::placeholder {{color:{muted};}}
    .st-key-mini_chat [data-testid="stChatInput"] button {{background:{user};color:{user_text};border-radius:10px;}}
    .st-key-conversation {{border-top:1px solid {border};padding-top:20px;}}
    @media(max-width:500px) {{.stMainBlockContainer {{padding:16px 10px;}} .st-key-mini_chat {{padding:16px 12px 12px;border-radius:18px;}} .brand strong {{font-size:17px;}} .brand-mark {{display:none;}}}}
    </style>""")


def show_order():
    back, heading = st.columns([1, 8], vertical_alignment="center")
    if back.button("←", key="back_to_chat", help="Voltar à conversa"):
        st.session_state.view = "chat"
        st.rerun()
    heading.markdown('**Meu pedido**')
    with st.container(height=410, border=False, key="order_detail"):
        result = st.session_state.shop_session.order_details()
        if result.status == "error":
            st.warning("Não foi possível consultar o pedido. Tente novamente mais tarde.")
            return
        if result.status != "available" or result.order is None:
            st.info("As informações do pedido não estão disponíveis para esta sessão. O acesso exige uma identidade de demonstração autorizada, configurada ao iniciar o aplicativo. A conversa não pode configurar ou alterar essa identidade.")
            return
        order = result.order
        statuses = {"pending": "Pendente", "confirmed": "Confirmado", "shipped": "Enviado", "delivered": "Entregue", "cancelled": "Cancelado"}
        # Only escaped, authorized DTO fields enter this presentation markup.
        status = statuses.get(order.status, "Não informada")
        st.markdown(f'<div class="order-summary"><h2>Pedido #{escape(str(order.order_id))}</h2><span class="order-badge" aria-label="Status: {status}">{status}</span></div>', unsafe_allow_html=True)
        progress = {"pending": 10, "confirmed": 33, "shipped": 66, "delivered": 100}
        if order.status in progress:
            percent = progress[order.status]
            st.html(f'<div class="order-progress" role="progressbar" aria-label="Situação registrada" aria-valuenow="{percent}" aria-valuemin="0" aria-valuemax="100"><div style="width:{percent}%"></div></div>')
            st.caption("Status registrado · sem histórico de transporte")
        elif order.status == "cancelled":
            st.caption("Este pedido consta como cancelado. Nenhuma alteração foi realizada.")
        items = "".join(f'<div class="order-item"><span class="order-quantity">{escape(str(item.quantity))}×</span><span>{escape(item.product_name)}</span></div>' for item in order.items)
        if not items:
            items = '<div class="order-note">Os produtos deste pedido não estão informados no registro.</div>'
        st.markdown(f'<section class="order-card" aria-label="Produtos"><div class="order-label">Produtos</div>{items}</section>', unsafe_allow_html=True)
        note = '<div class="order-note">Total histórico preservado; os preços atuais não recalculam este pedido.</div>' if "historical_total_difference" in order.warnings else ""
        st.markdown(f'<section class="order-card"><div class="order-total"><span class="order-label">Total registrado</span><strong>{escape(brl(order.total_brl))}</strong></div>{note}</section>', unsafe_allow_html=True)
        if order.tracking_code:
            tracking = f'<div class="order-tracking">{escape(order.tracking_code)}</div>'
        else:
            tracking = '<div class="order-empty"><span class="order-icon" aria-hidden="true">◇</span><div><strong>Rastreamento ainda não informado</strong><div class="order-note" style="margin-top:3px">Código de rastreamento não informado no registro.</div></div></div>'
        st.markdown(f'<section class="order-card"><div class="order-label">Rastreamento</div>{tracking}</section>', unsafe_allow_html=True)
        st.caption('Data efetiva de entrega não informada no registro.')



def main():
    st.set_page_config(page_title="Empório da Música", page_icon="♪", layout="centered")
    style(st.session_state.get("light_theme", False))
    if "shop_session" not in st.session_state:
        try:
            st.session_state.shop_session = ChatSession()
            st.session_state.messages = []
        except Exception:
            st.error("The local interface could not start. Check the selected data mode, authorized files, and Ollama settings, then restart.")
            st.stop()
    busy = bool(st.session_state.get("pending_question"))
    with st.container(key="mini_chat"):
        brand, theme, reset = st.columns([8, 1, 1], gap="small", vertical_alignment="center")
        with brand:
            mode = escape(st.session_state.shop_session.mode)
            st.html('<div class="brand"><div class="brand-mark" aria-hidden="true"><i style="height:12px"></i><i style="height:24px"></i><i style="height:32px"></i><i style="height:20px"></i><i style="height:10px"></i></div><div><strong>Empório da Música</strong><small>Atendimento inteligente'
                    f'<span class="mode-indicator">{mode}</span></small></div></div>')
        with theme:
            st.button("☾" if st.session_state.get("light_theme", False) else "☀", key="theme_toggle", help="Alternar tema claro/escuro", on_click=toggle_theme, disabled=busy)
        with reset:
            if st.button("↻", key="reset_chat", help="Reiniciar conversa", disabled=busy):
                st.session_state.shop_session.reset()
                st.session_state.messages = []
                st.session_state.view = 'chat'
                st.session_state.catalog_view = None
                st.session_state.catalog_category = 0
                st.session_state.catalog_search = ''
                st.session_state.catalog_filters = ('', 0)
                reset_catalog_navigation()
        if st.session_state.get("view") == "order":
            show_order()
            return
        if st.session_state.get('view') == 'catalog' and st.session_state.get('catalog_view') is not None:
            with st.container(key='catalog_screen'):
                show_catalog()
            return
        conversation = st.container(height=330, border=False, key="conversation")
        with conversation:
            with st.chat_message("assistant"):
                st.markdown("**Olá! Como posso te ajudar hoje?**")
                st.write("Posso ajudar com produtos, preços, políticas da loja ou o status do seu pedido.")
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    if message["role"] == "user":
                        st.text(message["text"])
                    else:
                        show_answer(message)
        selected = None
        with st.container(key="actions"):
            suggestions = SUGGESTIONS if st.session_state.shop_session.mode == 'DEMO' else LOCAL_SUGGESTIONS
            for column, (label, prompt) in zip(st.columns(4, gap="small"), suggestions.items()):
                if column.button(label, use_container_width=True, disabled=busy):
                    if label == "Meu pedido":
                        st.session_state.view = "order"
                        st.rerun()
                    selected = prompt
        submitted = st.chat_input("Digite sua mensagem…", max_chars=4000, disabled=busy) or selected
        if submitted and not busy:
            st.session_state.pending_question = submitted
            st.rerun()
        question = st.session_state.get("pending_question")
        if question:
            st.session_state.messages.append({"role": "user", "text": question})
            with conversation:
                with st.chat_message("user"):
                    st.text(question)
                with st.chat_message("assistant"):
                    with st.spinner("Consultando…"):
                        answer = st.session_state.shop_session.ask(question)
                    message = {"role": "assistant", "text": answer.text, "references": answer.references, "error": answer.error}
                    if answer.catalog is not None:
                        st.session_state.catalog_view = answer.catalog if answer.catalog.entries else None
                        st.session_state.catalog_token = st.session_state.get('catalog_token', 0) + 1
                        st.session_state.catalog_category = 0
                        st.session_state.catalog_search = ''
                        st.session_state.catalog_filters = ('', 0)
                        reset_catalog_navigation()
                        if answer.catalog.entries:
                            message['catalog_token'] = st.session_state.catalog_token
                    show_answer(message)
            st.session_state.messages.append(message)
            # Visible session transcript is independent of bounded model memory.
            # Only the explicit reset action may clear these messages.
            st.session_state.pending_question = None
            if answer.catalog is not None and answer.catalog.entries:
                st.session_state.view = 'catalog'
            st.rerun()


if __name__ == "__main__":
    main()
