# Run PerfMind AI In Antigravity

## Project Folder

Open this folder in Antigravity:

```text
E:\B-Tech\coding\Projects\Frontend Performance Monitoring Agent
```

## 1. Backend Connection

The FastAPI backend uses SQLAlchemy, so it needs a PostgreSQL connection string in:

```text
apps/api/.env
```

Required value:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/neondb?sslmode=require
```

Get this from Neon:

```text
Neon Dashboard -> Project -> Connection Details -> Connection string
```

The Neon REST endpoint you shared is:

```env
NEON_REST_URL=https://ep-bitter-frog-aom2hy3h.apirest.c-2.ap-southeast-1.aws.neon.tech/neondb/rest/v1
```

That REST URL is useful later for REST-style Neon access, but the current backend still needs `DATABASE_URL`.

## 2. Frontend Connection

The frontend should call the local FastAPI server. This file has been added:

```text
apps/web/.env.local
```

With:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_NEON_REST_URL=https://ep-bitter-frog-aom2hy3h.apirest.c-2.ap-southeast-1.aws.neon.tech/neondb/rest/v1
```

## 3. Run Backend

In Antigravity terminal:

```powershell
cd "E:\B-Tech\coding\Projects\Frontend Performance Monitoring Agent\apps\api"
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Open:

```text
http://localhost:8000
```

## 4. Run Frontend

Open another Antigravity terminal:

```powershell
cd "E:\B-Tech\coding\Projects\Frontend Performance Monitoring Agent\apps\web"
npm run dev
```

Open:

```text
http://localhost:3000
```

## 5. GitHub Setup

Before pushing to GitHub, keep generated dependency folders out of Git. A root `.gitignore` has been added for:

- `node_modules/`
- `venv/`
- `.next/`
- `.env`
- `.env.*`

Run from the project root:

```powershell
git init
git add .
git commit -m "Initial PerfMind AI setup"
git branch -M main
git remote add origin https://github.com/PEELARAGHAVENDRA/Frontend-Performance-Monitoring-Agent.git
git push -u origin main
```

Only run the GitHub remote commands after creating that repository on GitHub.

## 6. Still Needed For Full Product

The current project can run as a basic frontend and backend. To become the full PerfMind AI platform, these still need implementation:

- Database tables and migrations.
- Metric ingestion endpoints.
- Web Vitals SDK.
- Redis worker queue.
- Regression, root cause, prediction, optimization, and notification agents.
- Dashboard UI screens.
- Chat assistant.
- GitHub, Slack, Sentry, OpenTelemetry, and Lighthouse CI integrations.

