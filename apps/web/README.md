# Quant-OS Web (dashboard)

Next.js (App Router, TypeScript) + Tailwind CSS v4 dashboard over the Quant-OS
API. Phase-1 skeleton: renders the strategy registry (lifecycle buckets + table).
The full dashboard (equity curves, drawdowns, trade distributions, live-book
monitor) lands in Phase 3.

## Run

```bash
# 1) backend (from the repo root)
python scripts/build_registry.py
.venv/Scripts/uvicorn.exe apps.api.main:app --port 8000

# 2) frontend (from apps/web)
cp .env.local.example .env.local
npm install
npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` points the frontend at the FastAPI backend (default
`http://localhost:8000`).
