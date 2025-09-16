# quoteextractor-platform-29-39

Backend (FastAPI) quick start:
- Install dependencies: `pip install -r backend/requirements.txt`
- Run dev server: `uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000` (from backend/)
- Open API docs: http://localhost:8000/docs

Notes:
- MVP persistence is in-memory (resets on restart).
- TODO: Integrate DB (e.g., Postgres + SQLAlchemy) and real auth.