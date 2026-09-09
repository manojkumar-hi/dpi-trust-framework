# DPI Trust Framework Backend

Initial FastAPI backend foundation for the DPI Trust Framework.

## Setup

From the `backend` directory, create a virtual environment, install dependencies,
and copy `.env.example` to `.env`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Start the development server:

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`.

## Endpoints

- `GET /health` checks that the API is running.
- `GET /health/database` checks connectivity to PostgreSQL.
- `GET /docs` opens the interactive API documentation.
