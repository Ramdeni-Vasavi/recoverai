# RecoverAI

Initial scaffold for an AI-powered payment recovery system built for a Razorpay buildathon.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "."
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Health check: `GET /api/v1/health`.

Run tests from `backend` with `pytest`.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` to configure `VITE_API_BASE_URL`.

This scaffold intentionally excludes ML, database schema, AI agent, Razorpay integration, recovery logic, authentication, and the final dashboard.
