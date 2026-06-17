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

from langchain_community.utilities import SQLDatabase  # also used as SQLDatabase(engine, ...)
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

IMPORTANT: You already know the full schema below. Do NOT call list_tables or sql_db_schema — go straight to writing and running the query.

Schema:
  products(product_id TEXT PK, product_name TEXT, brand TEXT, category TEXT, sub_category TEXT, pack_size_ml INT, unit_price REAL)
  stores(store_id TEXT PK, store_name TEXT, region TEXT, city TEXT, store_format TEXT)
  sales(week_start_date TEXT, product_id TEXT FK, store_id TEXT FK, region TEXT, units_sold INT, revenue REAL, promotion_flag INT, promotion_type TEXT, discount_pct REAL)
  inventory(week_start_date TEXT, product_id TEXT FK, store_id TEXT FK, opening_stock INT, units_received INT, units_sold INT, closing_stock INT, stockout_flag INT)

Sample values:
  region: North, South, East, West
  promotion_type: Price Cut, BOGO, Display Feature, Bundle
  promotion_flag: 1 = promo active, 0 = no promo
  stockout_flag: 1 = stockout occurred
  brand: Spark, ZestUp, PureFlow, Blast, MilkMate
  category: Carbonated, Juice, Water, Energy, Dairy

Rules:
1. Only use SELECT. Never INSERT, UPDATE, DELETE, DROP.
2. Always add LIMIT 100 unless user asks for full export.
3. JOIN to products/stores for human-readable names instead of raw IDs.
4. If a question cannot be answered from the schema, say so clearly.
5. Always end with a plain-English summary of the result.
6. Round currency to 2 decimal places.
"""

def _build_agent():
    nvidia_key = _get_secret("NVIDIA_API_KEY")
    if not nvidia_key:
        raise ValueError("NVIDIA_API_KEY is not set. Add it to Streamlit secrets or .env.")

    # Build engine from parts — avoids % and @ in password breaking URI string parsing.
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL as SAUrl

    engine = create_engine(
        SAUrl.create(
            drivername="postgresql+psycopg2",
            username=_get_secret("SUPABASE_USER") or "postgres",
            password=_get_secret("SUPABASE_PASSWORD"),
            host=_get_secret("SUPABASE_HOST"),
            port=int(_get_secret("SUPABASE_PORT") or 5432),
            database=_get_secret("SUPABASE_DB") or "postgres",
        )
    )

    db = SQLDatabase(
        engine,
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
        verbose=False,
        agent_type="openai-tools",
        max_iterations=3,
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
