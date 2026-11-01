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


def main():
    st.set_page_config(page_title="Empório da Música | Customer service", page_icon="♪", layout="centered")
    st.caption("EMPÓRIO DA MÚSICA  /  CUSTOMER SERVICE")
    st.title("Find your next instrument.")
    st.write("Explore products, compare prices, and ask about store policies or your demo order.")
    st.info("Local synthetic demonstration · Fictitious products and policies · No purchases or order changes")
    with st.sidebar:
        st.subheader("Your conversation")
        st.caption("Runs with local Ollama. No external model or private source files are used.")
        st.caption("Demo customer 1 is fixed for this session. Chat cannot change identity. This is not production authentication.")
        reset = st.button("Reset conversation", use_container_width=True)
        st.caption("Reset clears memory. A browser refresh may also start a new session. Messages are not saved to a transcript file.")
    if "shop_session" not in st.session_state:
        try:
            st.session_state.shop_session = ChatSession()
            st.session_state.messages = []
        except Exception:
            st.error("The local demo could not start. Check the Ollama model and loopback endpoint configuration, then reload this page.")
            st.stop()
    if reset:
        st.session_state.shop_session.reset()
        st.session_state.messages = []
    if not st.session_state.messages:
        st.subheader("How can we help?")
        st.caption('Try “List all available products, cheapest first”, “What is the PIX price for product 1?”, or “What is the returns policy?”')
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.text(message["text"])
            else:
                show_answer(message)
    question = st.chat_input("Ask about instruments, pricing, policies, or your demo order…", max_chars=4000)
    if question:
        st.session_state.messages.append({"role": "user", "text": question})
        with st.chat_message("user"):
            st.text(question)
        with st.chat_message("assistant"):
            with st.spinner("Checking the demo store…"):
                answer = st.session_state.shop_session.ask(question)
            message = {"role": "assistant", "text": answer.text, "references": answer.references, "error": answer.error}
            show_answer(message)
        st.session_state.messages.append(message)
        # Bound display memory as well as the existing agent's four-exchange memory.
        st.session_state.messages = st.session_state.messages[-8:]


if __name__ == "__main__":
    main()
