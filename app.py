import os
import time
import streamlit as st
from datetime import datetime
import uuid
from dotenv import load_dotenv
from groq import Groq
from core.message import Message
from core.protocols import USER
from supervisor.agent import SupervisorAgent

# ── CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal AI",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ── ENV ────────────────────────────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "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"

client = Groq(api_key=GROQ_API_KEY)
supervisor = SupervisorAgent(client)

# ── Initialize conversations in session state ──────────────────────────────
if "conversations" not in st.session_state:
    st.session_state.conversations = {}

if "current_chat_id" not in st.session_state:
    new_id = str(uuid.uuid4())
    st.session_state.conversations[new_id] = {
        "title": "New Conversation",
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    st.session_state.current_chat_id = new_id

# Helpers
def get_current_messages():
    return st.session_state.conversations[st.session_state.current_chat_id]["messages"]

def create_new_chat():
    new_id = str(uuid.uuid4())
    st.session_state.conversations[new_id] = {
        "title": f"Chat {len(st.session_state.conversations) + 1}",
        "messages": [],
        "created_at": datetime.now().isoformat()
    }
    st.session_state.current_chat_id = new_id
    st.rerun()

# ── USER PROFILE ───────────────────────────────────────────────────────────
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {
        "name": "SATHWIK",
        "recent_topic": None,
        "emoji_level": "low",
        "session_start": time.time()
    }

# ── IMPROVED STYLE (better sidebar readability) ────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: radial-gradient(circle at top, #2a004f, #05000f);
    color: white;
}

header, footer, #MainMenu {
    visibility: hidden;
}

.block-container {
    max-width: 900px;
    padding-top: 1.5rem;
}

/* === SIDEBAR IMPROVEMENTS === */
section[data-testid="stSidebar"] {
    background: rgba(35, 25, 65, 0.97) !important;
    border-right: 1px solid rgba(140, 100, 220, 0.3) !important;
    backdrop-filter: blur(12px);
}

section[data-testid="stSidebar"] * {
    color: #f8f0ff !important;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #d5c0ff !important;
    font-weight: 600;
}

/* Buttons */
section[data-testid="stSidebar"] button {
    background: rgba(90, 50, 170, 0.45) !important;
    border: 1px solid rgba(170, 130, 255, 0.4) !important;
    border-radius: 10px;
    color: white !important;
    padding: 10px 14px !important;
    margin: 4px 0 !important;
    transition: all 0.18s;
    text-align: left !important;
}

section[data-testid="stSidebar"] button:hover {
    background: rgba(130, 90, 220, 0.65) !important;
    border-color: rgba(190, 150, 255, 0.7) !important;
    transform: translateX(3px);
}

section[data-testid="stSidebar"] button[kind="primary"],
section[data-testid="stSidebar"] button[type="primary"] {
    background: linear-gradient(135deg, #c084fc, #7c3aed) !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(168, 85, 247, 0.4);
}

section[data-testid="stSidebar"] button[kind="secondary"] {
    background: rgba(100, 60, 180, 0.35) !important;
}

/* Chat preview text */
section[data-testid="stSidebar"] button div:nth-child(2),
section[data-testid="stSidebar"] button small,
section[data-testid="stSidebar"] button span:not(:first-child) {
    color: #d4c6ff !important;
    opacity: 0.92 !important;
    font-size: 0.93em !important;
    line-height: 1.3;
}

/* Dividers */
section[data-testid="stSidebar"] hr {
    background: rgba(180, 140, 255, 0.2) !important;
    margin: 16px 0 !important;
}

/* Clear All button */
section[data-testid="stSidebar"] button:contains("Clear All") {
    color: #ffbbcc !important;
    background: rgba(180, 60, 90, 0.3) !important;
}

section[data-testid="stSidebar"] button:contains("Clear All"):hover {
    background: rgba(220, 80, 110, 0.55) !important;
}

/* === CHAT BUBBLES === */
.chat {
    padding: 14px 18px;
    border-radius: 20px;
    margin-bottom: 12px;
    max-width: 92%;
    line-height: 1.55;
}

.user {
    background: linear-gradient(135deg, #d946ef, #7c3aed);
    margin-left: auto;
}

.assistant {
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.14);
}

/* Chat input */
[data-testid="stChatInput"] {
    background: transparent !important;
}

[data-testid="stChatInput"] > div {
    background: rgba(255,255,255,0.07) !important;
    border-radius: 28px;
    padding: 6px;
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.15);
}

[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: white;
    border: none;
}

[data-testid="stChatInput"] button {
    background: linear-gradient(135deg, #d946ef, #7c3aed) !important;
    border-radius: 50% !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Conversations")

    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        create_new_chat()

    st.markdown("---")

    # Sort by most recent first (using created_at)
    sorted_chats = sorted(
        st.session_state.conversations.items(),
        key=lambda x: x[1].get("created_at", "2000-01-01"),
        reverse=True
    )

    for chat_id, chat_data in sorted_chats:
        title = chat_data["title"]
        preview = "No messages yet"
        if chat_data["messages"]:
            first_user_msg = next((m["content"] for m in chat_data["messages"] if m["role"] == "user"), "")
            preview = (first_user_msg[:38] + "...") if len(first_user_msg) > 38 else first_user_msg

        is_active = chat_id == st.session_state.current_chat_id

        if st.button(
            f"{title}\n{preview}",
            key=f"chatbtn_{chat_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
            disabled=is_active
        ):
            st.session_state.current_chat_id = chat_id
            st.rerun()

    st.markdown("---")

    if st.button("Clear All Chats", type="secondary"):
        if st.button("Confirm Clear All", type="primary"):
            st.session_state.conversations = {}
            create_new_chat()

# ── MAIN AREA ──────────────────────────────────────────────────────────────
hour = datetime.now().hour
greet = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 18 else "Good Evening"

st.markdown(f"""
<h2 style="text-align:center; font-weight:700; margin-bottom:0.4rem;">
{greet}, {st.session_state.user_profile['name']} 👋
</h2>
<p style="text-align:center; opacity:0.65; margin-top:0;">
Pick up where you left off — or start something new
</p>
""", unsafe_allow_html=True)

# ── Display current chat ──────────────────────────────────────────────────
current_messages = get_current_messages()

for msg in current_messages:
    cls = "user" if msg["role"] == "user" else "assistant"
    align = "flex-end" if cls == "user" else "flex-start"

    st.markdown(f"""
    <div style="display:flex; justify-content:{align}; margin: 8px 0;">
        <div class="chat {cls}">
            {msg["content"]}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Input & Response Logic ────────────────────────────────────────────────
if "pending_response" not in st.session_state:
    st.session_state.pending_response = False

if prompt := st.chat_input("Message AI…"):
    current_messages.append({"role": "user", "content": prompt})

    # Auto-update title from first message
    if len(current_messages) == 1:
        short_title = prompt[:32].strip()
        if len(prompt) > 32:
            short_title += "..."
        st.session_state.conversations[st.session_state.current_chat_id]["title"] = short_title

    st.session_state.pending_response = True
    st.rerun()

if st.session_state.pending_response:
    last_user_msg = current_messages[-1]["content"]

    with st.spinner("Thinking..."):
        user_message = Message(type=USER, payload={"text": last_user_msg})
        result = supervisor.handle(user_message)
        payload = result.payload or {}

        response = (
            payload.get("response_text")
            or payload.get("changes_summary")
            or payload.get("reasoning")
            or "Response generated ✓"
        )

    current_messages.append({
        "role": "assistant",
        "content": response + "<br><br><i style='opacity:0.65'>Anything else you'd like to explore?</i>"
    })

    st.session_state.user_profile["recent_topic"] = last_user_msg[:50]
    st.session_state.pending_response = False
    st.rerun()

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("""
<p style="text-align:center; opacity:0.4; margin-top:40px; font-size:0.9rem;">
Personal • Fast • Always-on
</p>
""", unsafe_allow_html=True)