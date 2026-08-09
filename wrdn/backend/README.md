# WRDN Backend

FastAPI service that powers WRDN: Gemini chat, output shielding, client policies, HR candidate processing, auth, and Mailtrap email.

---

## Role in the project

```text
Frontend (18085)  →  Backend API (18000)  →  Gemini + SQLite + SMTP (Mailtrap)
```

Main responsibilities:
- Authenticate users (ADMIN / EMPLOYEE)
- Answer chat prompts with Gemini, then apply WRDN policy / sanitizer
- Manage client policies (upload → analyze → email confirm → activate)
- Enable / disable WRDN protection per client (`ALLOWED` / `BLOCKED` / `BYPASSED`)
- Run HR CV pipeline (upload file → 2 agents → shield → optional email send)
- Store audit logs in SQLite

---

## Folder structure

```text
wrdn/backend/
├── main.py                 # FastAPI app, chat, protection APIs
├── database.py             # SQLite schema, seeds, audit helpers
├── email_service.py        # Mailtrap SMTP (policy + HR emails)
├── requirement_service.py  # Requirement approval flow helpers
├── embedding_security.py   # Embedding-based risk signals
├── Dockerfile
├── requirements.txt
├── README.md
├── data/                   # SQLite DB (created at runtime)
├── policies/
│   └── default_policy.json
├── routes/
│   ├── auth.py             # Login / session
│   ├── policies.py         # Policy upload & activation
│   └── hr.py               # HR CV extract + process
└── services/
    ├── auth_service.py
    ├── hr_candidate_service.py
    ├── policy_agent.py
    ├── policy_judge.py
    ├── policy_loader.py
    ├── policy_activation_service.py
    ├── policy_enrichment.py
    ├── policy_validator.py
    └── requirement_parser.py   # PDF / DOCX / TXT / JSON text extract
```

---

## Requirements

- Python 3.11+ recommended (Docker uses 3.12)
- Gemini API key
- Optional: Mailtrap SMTP credentials for email demos

Install packages:

```powershell
cd "path\to\demo-wrdn-"
py -m pip install -r wrdn/backend/requirements.txt
```

Key packages: `fastapi`, `uvicorn`, `google-genai`, `pypdf`, `python-docx`, `python-multipart`, `python-dotenv`.

---

## Environment

Create `.env` in the **repo root** (not inside `backend/`):

```powershell
copy .env.example .env
```

Backend reads config via `wrdn/config.py` (loads `.env`).

Minimum:

```env
GEMINI_API_KEY=your_key
```

Email (policy activation + HR outbound):

```env
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=587
MAIL_USERNAME=...
MAIL_APP_PASSWORD=...
MAIL_FROM_NAME=WRDN Security
POLICY_APPROVAL_EMAIL=admin@demo.local
POLICY_APPROVAL_NAME=Admin
FRONTEND_URL=http://localhost:18085
BACKEND_URL=http://127.0.0.1:18000
```

---

## Run with Docker (recommended)

From repo root:

```powershell
docker compose up -d --build backend
```

API: http://localhost:18000  
Docs: http://localhost:18000/docs

---

## Run locally (without Docker)

From repo root:

```powershell
py -m uvicorn wrdn.backend.main:app --reload --host 127.0.0.1 --port 18000
```

Open: http://127.0.0.1:18000/docs

---

## Important API groups

### Auth
- `POST /api/auth/login` — username / password
- Session helpers used by the frontend

### Protection
- `GET /api/protection-status?client_id=...`
- `POST /api/admin/protection-status` — enable / disable WRDN

### Chat
- Chat endpoint in `main.py` — returns answer + `shield_status`
  - Protection ON → `ALLOWED` or `BLOCKED`
  - Protection OFF → `BYPASSED` (raw output)

### Policies (admin)
- Upload requirement file
- Analyze / generate policy with Gemini
- Request activation → email confirm / reject links
- List / rollback / delete policies

### HR Candidates
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/hr/sample-cvs` | Safe + attack sample text |
| `POST` | `/api/hr/extract-cv` | Upload file → extracted text |
| `POST` | `/api/hr/process-cv` | Process CV text JSON |
| `POST` | `/api/hr/process-cv-upload` | Upload PDF/DOCX/TXT → full pipeline |

Accepted CV types: `.pdf`, `.docx`, `.txt`, `.json`

---

## HR pipeline (backend view)

```text
CV file
  → extract text
  → Agent 1 (evaluate vs HR DB context)
  → Agent 2 (draft candidate email)
  → WRDN outbound leak check
       ├─ protection OFF → BYPASSED → send via Mailtrap
       ├─ leak + protection ON → BLOCKED → do not send
       └─ clean + protection ON → ALLOWED → send via Mailtrap
  → audit log
```

Mailtrap delivery uses `POLICY_APPROVAL_EMAIL` as the demo inbox. The intended candidate address is kept in the message body / headers.

---

## Database

- Engine: SQLite
- Default path: `wrdn/backend/data/wrdn.db`
- Created/seeded on startup (`initialize_database`)
- Docker volume: `wrdn_database`

Seeded data includes employees, secrets, clients, and demo users.

### Demo logins

| Username | Password | Role | Client |
|---|---|---|---|
| `adminA` | `AdminA@2026!` | ADMIN | `clientA` |
| `employeeA` | `EmpA@2026!` | EMPLOYEE | `clientA` |
| `adminB` | `AdminB@2026!` | ADMIN | `clientB` |
| `employeeB` | `EmpB@2026!` | EMPLOYEE | `clientB` |

---

## Useful demo assets

- Sample CVs: `wrdn/hr_demo_cvs/`
- Sample policy requirements: `wrdn/demo-requirements/`

---

## Troubleshooting

| Problem | What to check |
|---|---|
| `GEMINI_API_KEY` errors | `.env` in repo root; rebuild/restart backend |
| SMTP / Mailtrap auth failed | `MAIL_USERNAME`, `MAIL_APP_PASSWORD`, `SMTP_HOST` |
| HR upload 400 | File type must be PDF/DOCX/TXT; file not empty |
| CORS errors from UI | Frontend must call `http://localhost:18000`; CORS allows `18085` |
| Old code in Docker | `docker compose up -d --build backend` |

Logs:

```powershell
docker compose logs -f backend
```

---

## Related docs

- [Root README](../../README.md) — full project + friend setup
- [Frontend README](../frontend/README.md)
- [Simulator README](../demo-wrdn--simulator/README.md)
