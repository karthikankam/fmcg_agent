"""
app.py — FMCG Beverages Assistant (Streamlit frontend)

Run with: streamlit run app.py
"""

import re
import streamlit as st
import plotly.express as px
import pandas as pd
from agent import ask, reset_memory

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Beverages AI",
    page_icon="🥤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS — minimal, production-clean ───────────────────────────
st.markdown("""
<style>
/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Chat message bubbles */
.user-bubble {
    background: #eeedfe;
    color: #26215c;
    border-radius: 16px 16px 4px 16px;
    padding: 10px 16px;
    margin: 4px 0;
    display: inline-block;
    max-width: 75%;
    float: right;
    clear: both;
}
.ai-bubble {
    background: #f1efe8;
    color: #2c2c2a;
    border-radius: 16px 16px 16px 4px;
    padding: 10px 16px;
    margin: 4px 0;
    display: inline-block;
    max-width: 85%;
    float: left;
    clear: both;
}
.clearfix { clear: both; }

/* Sidebar suggested question buttons */
.stButton > button {
    width: 100%;
    text-align: left;
    background: #3c3c3a;
    color: #d3d1c7;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    margin-bottom: 4px;
}
.stButton > button:hover {
    background: #534ab7;
    color: white;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []   # list of {role, content, sql}
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Beverages AI")
    st.caption("FMCG Category Intelligence")
    st.divider()

    st.markdown("**Suggested questions**")
    suggestions = [
        "What are the total units sold per region?",
        "Which promotion type drove the highest average units sold?",
        "Which product had the highest revenue overall?",
        "How many stockout events happened in each region?",
        "Compare revenue across all brands.",
        "Which week had the highest sales?",
    ]
    for s in suggestions:
        if st.button(s, key=f"btn_{s[:20]}"):
            st.session_state.pending_question = s

    st.divider()
    st.caption("Model: Llama 3.1 70B (NVIDIA NIM)")
    st.caption("Database: Supabase PostgreSQL")
    st.divider()

    if st.button("New conversation", type="secondary"):
        st.session_state.messages = []
        reset_memory()
        st.rerun()

# ── Helper: try to extract a chart from the answer ───────────────────
def try_render_chart(answer: str):
    """
    Looks for patterns like 'X: 153,090' or 'X — £89,789' in the answer.
    If 2+ items found, renders a horizontal bar chart automatically.
    """
    # Match patterns like "West: 153,090" or "Spark Cola 1L: £89,789.24"
    pattern = r"([A-Za-z][\w\s\-\.]+?):\s*[£$]?([\d,]+(?:\.\d+)?)"
    matches = re.findall(pattern, answer)

    if len(matches) < 2:
        return

    labels = [m[0].strip() for m in matches]
    values = [float(m[1].replace(",", "")) for m in matches]

    df = pd.DataFrame({"label": labels, "value": values})
    df = df.sort_values("value", ascending=True)

    fig = px.bar(
        df, x="value", y="label", orientation="h",
        color="value",
        color_continuous_scale=["#cecbf6", "#534ab7"],
        template="plotly_white",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=8, b=0),
        height=max(160, len(df) * 36),
        showlegend=False,
        coloraxis_showscale=False,
        xaxis_title="",
        yaxis_title="",
        font=dict(family="sans-serif", size=12),
    )
    fig.update_traces(hovertemplate="%{y}: %{x:,.0f}<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)

# ── Main chat area ────────────────────────────────────────────────────
st.markdown("### Beverages category intelligence")
st.caption("Ask anything about sales, promotions, inventory, or products.")
st.divider()

# Render existing messages
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="user-bubble">{msg["content"]}</div>'
            '<div class="clearfix"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ai-bubble">{msg["content"]}</div>'
            '<div class="clearfix"></div>',
            unsafe_allow_html=True,
        )
        # Show chart if data is in the answer
        try_render_chart(msg["content"])

        # Show generated SQL in an expander
        if msg.get("sql"):
            with st.expander("View generated SQL"):
                st.code(msg["sql"], language="sql")

st.divider()

# ── Input bar ─────────────────────────────────────────────────────────
col1, col2 = st.columns([8, 1])
with col1:
    user_input = st.text_input(
        label="question",
        label_visibility="collapsed",
        placeholder="Ask anything about your beverages data...",
        value=st.session_state.pending_question,
        key="chat_input",
    )
with col2:
    send = st.button("Ask", type="primary", use_container_width=True)

# Clear pending question after it's been put in the input
if st.session_state.pending_question:
    st.session_state.pending_question = ""

# ── Handle submission ─────────────────────────────────────────────────
question = user_input.strip()
if (send or user_input) and question:
    # Only process if this question isn't already the last message
    already_asked = (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
        and st.session_state.messages[-1]["content"] == question
    )

    if not already_asked:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": question})

        # Call agent with spinner
        with st.spinner("Thinking..."):
            result = ask(question)
            answer = result["answer"]

        # Extract SQL from verbose output if present (agent logs it)
        sql_match = re.search(
            r"SELECT\b.*?(?=\n\n|\Z)", answer, re.IGNORECASE | re.DOTALL
        )
        extracted_sql = sql_match.group(0).strip() if sql_match else ""

        # Add AI message
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sql": extracted_sql,
        })

        st.rerun()
