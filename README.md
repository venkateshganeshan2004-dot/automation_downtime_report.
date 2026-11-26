# TDConnex — Automation Downtime Report (Full-Stack Package)

## Included
- `frontend/index.html` — Complete TDConnex UI (pearl-light multi-tone theme, TDConnex logo, manual equipment & spare search, Unit 1 & Unit 2 spare stores, PM verifier sign-off, full Kaizen Before/After details).
- `backend/main.py` & `backend/schema.sql` — FastAPI + SQLite backend with atomic downtime + spare deduction, low-stock alerts, Red-severity auto-CAPA, PM verification, and Kaizen endpoints.
- `Dockerfile` & `render.yaml` — Ready for 1-click deployment on Render, Railway, or Docker.

## Run Locally
```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```
Open `http://127.0.0.1:8000/` for the app and `http://127.0.0.1:8000/docs` for the interactive API docs.
