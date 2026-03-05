# Cloud Compare

Production-ready backend for an AI-powered cloud server price comparison system.

## Tech stack

- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.0 (async)
- **Migrations:** Alembic
- **Environment:** python-dotenv

## Project structure

```
cloud_compare/
├── app/
│   ├── main.py
│   ├── core/          # config, database
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # recommendation service
│   ├── api/           # routes and router
│   └── utils/         # pricing helpers
├── frontend/
│   └── index.html     # single-page UI (Syne + DM Mono, dark theme)
├── alembic/
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Setup

### 1. Create virtual environment and install dependencies

```bash
cd cloud_compare
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or with **uv**:

```bash
cd cloud_compare
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env

```

Ensure PostgreSQL is running and the database exists:

```bash
createdb cloud_compare   # if using local Postgres
```

### 3. Run migrations

From the project root (`cloud_compare/`):

```bash
export PYTHONPATH=.
alembic upgrade head
```

Or from the same directory:

```bash
PYTHONPATH=. alembic upgrade head
```

If you see **"permission denied for schema public"** (common on PostgreSQL 15+ or managed Postgres), the database user needs permission on `public`. Connect as a superuser (e.g. `psql -U postgres -d cloud_compare`) and run:

```sql
-- Replace your_app_user with the user from your DATABASE_URL (e.g. ai_bug_agent)
GRANT USAGE, CREATE ON SCHEMA public TO your_app_user;
```

Then run `alembic upgrade head` again.

If you see **"permission denied for table ..."** (e.g. `instance_pricing`, `regions`) when calling the API or running the seed script, the app user needs privileges on **all** tables. As superuser, run (this applies to `providers`, `regions`, `instance_types`, `instance_pricing`):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO your_app_user;
```

Example with user from `.env`: `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_bug_agent;`

**Optional – seed sample data** (so `POST /recommend` returns results):

```bash
PYTHONPATH=. python scripts/seed_data.py
```

Then try `POST /recommend` with body: `{"cpu": 4, "ram": 16, "budget": 100, "region": "Europe"}`.

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

- **Web app:** **http://127.0.0.1:8000/** — CloudCompare UI (configure requirements, view recommendations, optional AI explanation).
- **API docs:** **http://127.0.0.1:8000/docs**

## Ollama (optional)

For natural-language queries and AI-generated explanations, run [Ollama](https://ollama.com) locally and pull a model:

```bash
ollama serve    # if not already running
ollama pull llama3.2
```

Set in `.env` (optional):

- `OLLAMA_BASE_URL` – default `http://localhost:11434`
- `OLLAMA_MODEL` – default `llama3.2`

If Ollama is not running or the model is missing, the API still works with structured input and omits the explanation.

## API

### POST /recommend

**Structured request:**

```json
{
  "cpu": 4,
  "ram": 16,
  "budget": 100,
  "region": "Europe"
}
```

**Natural-language request** (requires Ollama):

```json
{
  "query": "I need 4 vCPUs, 16GB RAM in Europe, max $100 per month"
}
```

**With AI explanation** (requires Ollama):

```json
{
  "cpu": 4,
  "ram": 16,
  "budget": 100,
  "region": "Europe",
  "include_explanation": true
}
```

Response:

```json
{
  "recommendations": [
    {
      "provider": "DigitalOcean",
      "instance": "s-4vcpu-16gb",
      "vcpu": 4,
      "ram": 16,
      "price_monthly": 96
    }
  ],
  "explanation": null
}
```

Recommendations are filtered by:

- `vcpu` ≥ requested CPU
- `ram_gb` ≥ requested RAM
- `monthly_price_usd` ≤ budget
- Region continent matches the given `region` (case-insensitive)

Results are sorted by monthly price ascending; up to 3 options are returned.
