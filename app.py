import uuid
import streamlit as st
from systems.monitoring import tracing_status
from systems.runner import run_agent

st.set_page_config(page_title="Agent IA avec Mémoire - Grossiste Mada", page_icon="🤖", layout="wide")
st.title("🤖 Agent Intelligent avec Mémoire Persistante (PostgreSQL)")

# --- GESTION DU THREAD_ID (SESSION) ---
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Barre latérale pour gérer la conversation
with st.sidebar:
    st.header("⚙️ Session de Chat")
    st.info(f"ID Session actuelle :\n`{st.session_state.thread_id}`")
    
    if st.button("➕ Nouvelle Conversation"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.header("📊 Observabilité")
    tracing_active, tracing_label = tracing_status()
    if tracing_active:
        st.success(tracing_label)
        st.link_button("Ouvrir LangSmith", "https://smith.langchain.com")
    else:
        st.warning(tracing_label)

# Historique UI local
if "messages" not in st.session_state:
    st.session_state.messages = []

# Affichage des anciens messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrée Utilisateur
if user_input := st.chat_input("Posez votre question... (l'agent se souviendra du contexte)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("L'agent se remémore le contexte et exécute les outils..."):
            # Envoi du thread_id à LangGraph
            answer, tools_used = run_agent(user_input, thread_id=st.session_state.thread_id)
            
            if tools_used:
                tools_str = ", ".join([f"`{t}`" for t in set(tools_used)])
                st.caption(f"🛠️ Outils utilisés : {tools_str}")

            st.markdown(answer)

            full_response = answer
            if tools_used:
                full_response += f"\n\n*(Outils activés: {', '.join(set(tools_used))})*"
            st.session_state.messages.append({"role": "assistant", "content": full_response})