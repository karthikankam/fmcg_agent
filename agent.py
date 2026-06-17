"""
agent.py — FMCG Beverages SQL Agent
Uses LangChain + NVIDIA NIM (Llama 3.1 70B) + Supabase PostgreSQL

Memory: implemented as a simple in-process message list — no external
dependency required. History is injected into the system prompt on
every call so follow-up questions resolve context correctly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).parent / ".env")

# Try to read from Streamlit secrets if running on Streamlit Cloud
def _get_secret(key: str) -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key, "")

_chat_history = []
_agent = None   # lazy-initialised on first ask()

SYSTEM_PREFIX = """You are an AI assistant for a Consumer Goods (FMCG) company's Beverages category.
Help business users get insights from sales, inventory, product, and store data.
If the user question is irrelevant to your data, say so without running any query.

Tables:
- sales: weekly sales per product per store. promotion_flag=1 = promo active.
- inventory: stock levels per product per store per week.
- products: product names, brands, categories, prices.
- stores: store names, regions (North/South/East/West), formats.

Rules:
1. Only use SELECT. Never INSERT, UPDATE, DELETE, DROP.
2. Always add LIMIT 100 unless user asks for full export.
3. JOIN to products/stores for human-readable names instead of IDs.
4. If a question cannot be answered from the schema, say so clearly.
5. Always end with a plain-English summary of the result.
6. Round currency to 2 decimal places.

promotion_type values: Price Cut, BOGO, Display Feature, Bundle
"""

def _build_agent():
    db_url = _get_secret("SUPABASE_DB_URL")
    nvidia_key = _get_secret("NVIDIA_API_KEY")

    if not db_url:
        raise ValueError("SUPABASE_DB_URL is not set. Add it to Streamlit secrets or .env.")
    if not nvidia_key:
        raise ValueError("NVIDIA_API_KEY is not set. Add it to Streamlit secrets or .env.")

    db = SQLDatabase.from_uri(
        db_url,
        sample_rows_in_table_info=3,
        include_tables=["products", "stores", "sales", "inventory"],
    )
    llm = ChatOpenAI(
        model="meta/llama-3.1-70b-instruct",
        openai_api_key=nvidia_key,
        openai_api_base="https://integrate.api.nvidia.com/v1",
        temperature=0,
    )
    return create_sql_agent(
        llm=llm,
        db=db,
        verbose=True,
        agent_type="openai-tools",
        max_iterations=5,
        handle_parsing_errors=True,
    )


def ask(question: str) -> dict:
    global _agent
    if _agent is None:
        _agent = _build_agent()

    # Build prompt: system context + conversation history + new question
    history_text = ""
    for msg in _chat_history[-6:]:   # last 3 turns (6 messages)
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    if history_text:
        full_input = (
            SYSTEM_PREFIX
            + "\n\nConversation so far:\n" + history_text
            + "\nUser question: " + question
        )
    else:
        full_input = SYSTEM_PREFIX + "\n\nUser question: " + question

    result = _agent.invoke({"input": full_input})

    raw = result.get("output", "No answer returned.")
    if isinstance(raw, list):
        answer = " ".join(
            part["text"] if isinstance(part, dict) and "text" in part else str(part)
            for part in raw
        ).strip()
    else:
        answer = str(raw).strip()

    # Save turn to history
    _chat_history.append({"role": "user",      "content": question})
    _chat_history.append({"role": "assistant", "content": answer})

    return {"answer": answer, "question": question}


def reset_memory():
    _chat_history.clear()


if __name__ == "__main__":
    print("FMCG Beverages Assistant (type 'bye' to quit, 'reset' to clear memory)")
    print("-" * 60)
    while True:
        ques = input("\nQuestion: ").strip()
        if ques.lower() == "bye":
            break
        if ques.lower() == "reset":
            reset_memory()
            print("Memory cleared.")
            continue
        if not ques:
            continue
        print("\n" + ask(ques)["answer"])
