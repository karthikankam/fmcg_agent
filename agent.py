"""
agent.py — FMCG Beverages SQL Agent
Uses LangChain + NVIDIA NIM (Llama 3.1 70B) + Supabase PostgreSQL

Memory: ConversationBufferMemory is passed directly into the agent via
`agent_kwargs`. LangChain injects chat_history into the prompt automatically
on every call — no manual string building needed.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_classic.memory import ConversationBufferMemory

load_dotenv(Path(__file__).parent / ".env")

db = SQLDatabase.from_uri(
    os.getenv("SUPABASE_DB_URL"),
    sample_rows_in_table_info=3,
    include_tables=["products", "stores", "sales", "inventory"],
)

llm = ChatOpenAI(
    model="meta/llama-3.1-70b-instruct",
    openai_api_key=os.getenv("NVIDIA_API_KEY"),
    openai_api_base="https://integrate.api.nvidia.com/v1",
    temperature=0,
)

# return_messages=True keeps history as a list of HumanMessage/AIMessage objects.
# LangChain's agent natively appends to this list — no manual save_context needed.
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
)

SYSTEM_PREFIX = """You are an AI assistant for a Consumer Goods (FMCG) company's Beverages category.
Help business users get insights from sales, inventory, product, and store data.
if the user question is unrelevent to your knowledge and functions do not run any query just answer that i do not know the answer
or the question is irrelevent to my knowledge
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

# Passing memory + prefix directly into the agent via agent_kwargs.
# LangChain automatically:
#   - injects {chat_history} into the prompt before each call
#   - appends the new Human + AI turn to memory after each call
# No manual prompt building or save_context calls needed.
agent = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,
    agent_type="openai-tools",
    max_iterations=5,
    handle_parsing_errors=True,
    agent_kwargs={
        "system_message": SYSTEM_PREFIX,
        "extra_prompt_messages": [memory.chat_memory.messages],
        "memory": memory,
    },
)


def ask(question: str) -> dict:
    # Just pass the question — memory is fully handled by agent_kwargs
    result = agent.invoke({"input": question})

    raw = result.get("output", "No answer returned.")
    if isinstance(raw, list):
        answer = " ".join(
            part["text"] if isinstance(part, dict) and "text" in part else str(part)
            for part in raw
        ).strip()
    else:
        answer = str(raw).strip()

    return {"answer": answer, "question": question}


def reset_memory():
    memory.clear()


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
