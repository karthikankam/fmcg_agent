# FMCG Beverages Category Intelligence Assistant

A conversational AI assistant that lets FMCG category managers query sales, inventory, and promotion data in plain English — no SQL required. Ask questions like *"which promotion type drove the most uplift?"* or *"how many stockouts happened in the North?"* and get accurate, chart-backed answers in seconds.

---

## Demo

![App Screenshot](https://placehold.co/800x400?text=Beverages+AI+Assistant)

---

## Features

- **Natural language querying** — ask anything about sales, promotions, inventory, or products
- **Conversational memory** — follow-up questions resolve context from prior turns
- **Auto-generated charts** — numeric answers automatically render as bar charts
- **SQL transparency** — every answer shows the SQL query that produced it
- **Suggested questions** — one-click sidebar questions for non-technical users
- **Conversation reset** — clear memory and start fresh at any time
- **Read-only safety** — agent is restricted to SELECT only, no data modification possible

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit + Plotly |
| Agent | LangChain SQL Agent (`create_sql_agent`) |
| LLM | Llama 3.1 70B via NVIDIA NIM |
| Memory | ConversationBufferMemory (langchain_classic) |
| Database | Supabase PostgreSQL (cloud) |
| Data Pipeline | Python (synthetic data generation) |
| Environment | python-dotenv |

---

## Project Structure

```
fmcg_assistant/
├── app.py                  # Streamlit frontend
├── agent.py                # LangChain SQL agent + memory
├── generate_data.py        # Synthetic data generation (CSVs + local SQLite)
├── push_to_supabase.py     # Push generated data to Supabase PostgreSQL
├── beverages.db            # Local SQLite (offline backup)
├── products.csv            # 15 beverages, 5 brands, 5 categories
├── stores.csv              # 30 stores across 4 UK regions
├── sales.csv               # 7,200 rows — 16 weeks of weekly sales + promo flags
├── inventory.csv           # 7,200 rows — stock levels + stockout flags
└── .env                    # API keys (not committed)
```

---

## Database Schema

```
products    — product_id, product_name, brand, category, sub_category, pack_size_ml, unit_price
stores      — store_id, store_name, region, city, store_format
sales       — week_start_date, product_id, store_id, region, units_sold, revenue, promotion_flag, promotion_type, discount_pct
inventory   — week_start_date, product_id, store_id, opening_stock, units_received, units_sold, closing_stock, stockout_flag
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/karthikankam/fmcg_agent.git
cd fmcg_agent
```

### 2. Install dependencies

```bash
pip install langchain langchain-community langchain-classic langchain-openai langchain-google-genai python-dotenv sqlalchemy psycopg2-binary streamlit plotly pandas
```

### 3. Create `.env` file

```
NVIDIA_API_KEY=your_nvapi_key_here
SUPABASE_DB_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres
```

Get your NVIDIA NIM key at [build.nvidia.com](https://build.nvidia.com)  
Get your Supabase connection string from your project dashboard → Connect

### 4. Generate data and push to Supabase

```bash
python generate_data.py       # creates CSVs + local SQLite
python push_to_supabase.py    # pushes all 4 tables to Supabase
```

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## How It Works

```
User question
    → ConversationBufferMemory injects chat history into prompt
    → LangChain SQL Agent reads Supabase schema
    → Llama 3.1 70B writes a SELECT query
    → LangChain executes query on Supabase PostgreSQL
    → LLM summarises result rows in plain English
    → Streamlit renders answer + Plotly chart + SQL expander
```

---

## Dataset Design

The synthetic dataset was built with real signal, not random noise:

- **Promotion uplift** — promo weeks apply a 1.4x–2.2x units_sold multiplier so promotion effectiveness is genuinely measurable
- **Type-differentiated promos** — BOGO (~25% discount) drives higher volume than Price Cut (~15%), matching real FMCG behaviour
- **Stockouts emerge naturally** — from promo-driven demand spikes draining stock, not artificially planted flags
- **Fixed seed (42)** — fully reproducible, all answers verifiable against known ground truth

---

## Example Questions

- What are the total units sold per region?
- Which promotion type drove the highest average units sold?
- Which product had the highest revenue overall?
- How many stockout events happened in each region?
- Compare revenue across all brands.
- Which week had the highest sales?

---

## License

MIT
