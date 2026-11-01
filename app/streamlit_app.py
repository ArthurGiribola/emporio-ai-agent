"""One-page local demonstration. Launch with python -m app.web."""

import re

import streamlit as st

from app.web_session import ChatSession


def show_answer(message):
    if message.get("error"):
        st.warning(message["text"])
    else:
        # BRL dollar signs are currency, not Markdown/LaTeX math delimiters.
        st.markdown(re.sub(r"(?<!\\)\$", r"\\$", message["text"]), unsafe_allow_html=False)
    for reference in message.get("references", ()):
        st.caption(reference)


SUGGESTIONS = {
    "Ver produtos": "Quais produtos sintéticos estão disponíveis? Liste todos do mais barato ao mais caro.",
    "Preços": "Qual é o preço do produto sintético 1 pagando com PIX?",
    "Meu pedido": "Qual é o status e o total registrado do pedido sintético 1? Há rastreamento?",
    "Políticas": "Qual é a política sintética de devolução? Cite as seções e páginas disponíveis.",
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
    .brand {{display:flex;gap:12px;align-items:center;margin:0 0 12px;}}
    .brand-mark {{border:1px solid {border};border-radius:12px;width:40px;height:40px;display:flex;align-items:center;justify-content:center;gap:3px;flex-shrink:0;}}
    .brand-mark i {{display:block;width:3px;background:{text};border-radius:4px;}}
    .brand strong {{font-size:20px;font-weight:700;letter-spacing:-.6px;line-height:1.2;}}
    .brand small {{display:block;color:{muted};font-size:12px;margin-top:4px;}}
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


def main():
    st.set_page_config(page_title="Empório da Música", page_icon="♪", layout="centered")
    style(st.session_state.get("light_theme", False))
    if "shop_session" not in st.session_state:
        try:
            st.session_state.shop_session = ChatSession()
            st.session_state.messages = []
        except Exception:
            st.error("The local demo could not start. Check the Ollama model and loopback endpoint configuration, then reload this page.")
            st.stop()
    busy = bool(st.session_state.get("pending_question"))
    with st.container(key="mini_chat"):
        brand, theme, reset = st.columns([8, 1, 1], gap="small", vertical_alignment="center")
        with brand:
            st.html('<div class="brand"><div class="brand-mark" aria-hidden="true"><i style="height:12px"></i><i style="height:24px"></i><i style="height:32px"></i><i style="height:20px"></i><i style="height:10px"></i></div><div><strong>Empório da Música</strong><small>Atendimento inteligente</small></div></div>')
        with theme:
            st.button("☾" if st.session_state.get("light_theme", False) else "☀", key="theme_toggle", help="Alternar tema claro/escuro", on_click=toggle_theme, disabled=busy)
        with reset:
            if st.button("↻", key="reset_chat", help="Reiniciar conversa", disabled=busy):
                st.session_state.shop_session.reset()
                st.session_state.messages = []
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
            for column, (label, prompt) in zip(st.columns(4, gap="small"), SUGGESTIONS.items()):
                if column.button(label, use_container_width=True, disabled=busy):
                    selected = prompt
        submitted = st.chat_input("Digite sua mensagem…", max_chars=4000, disabled=busy) or selected
        if submitted and not busy:
            st.session_state.pending_question = submitted
            st.rerun()
        question = st.session_state.get("pending_question")
        st.caption("Demo sintética · Ollama local · Cliente 1 fixo · Sem alterações em pedidos")
        if question:
            st.session_state.messages.append({"role": "user", "text": question})
            with conversation:
                with st.chat_message("user"):
                    st.text(question)
                with st.chat_message("assistant"):
                    with st.spinner("Consultando…"):
                        answer = st.session_state.shop_session.ask(question)
                    message = {"role": "assistant", "text": answer.text, "references": answer.references, "error": answer.error}
                    show_answer(message)
            st.session_state.messages.append(message)
            st.session_state.messages = st.session_state.messages[-8:]
            st.session_state.pending_question = None
            st.rerun()


if __name__ == "__main__":
    main()
