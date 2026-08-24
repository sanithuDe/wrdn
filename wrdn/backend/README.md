# WRDN Backend

FastAPI service that powers WRDN: Gemini chat, output shielding, client policies, HR candidate processing, auth, and Brevo email.

---

## Role in the project

```text
Frontend (18085)  →  Backend API (18000)  →  Gemini + SQLite + SMTP (Brevo)
```

Main responsibilities:

- Authenticate users (ADMIN / EMPLOYEE)
- Answer chat prompts with Gemini, then apply WRDN policy / sanitizer
- Manage client policies (checklist → generate → email confirm → activate)
- Enable / disable WRDN protection per client (`ALLOWED` / `BLOCKED` / `BYPASSED`)
- Run HR CV pipeline (upload file → inbound scan → 2 agents → shield → optional email)
- Store audit logs in SQLite

---

## Folder structure

```text
wrdn/backend/
├── main.py                 FastAPI app, chat, protection APIs
├── database.py             SQLite schema, seeds, audit helpers
├── email_service.py        Brevo SMTP (policy + HR emails)
├── requirement_service.py  Requirement approval helpers
├── embedding_security.py   Embedding-based risk signals
├── Dockerfile
├── requirements.txt
├── data/                   SQLite DB (created at runtime)
├── routes/
│   ├── auth.py             Signup, login, users
│   ├── policies.py         Policy generate and activation
│   └── hr.py               HR CV extract + process
└── services/
    ├── auth_service.py
    ├── hr_candidate_service.py
    ├── policy_agent.py
    ├── policy_judge.py
    ├── policy_loader.py
    ├── policy_activation_service.py
    ├── policy_enrichment.py
    ├── policy_validator.py
    ├── inbound_guard.py
    ├── payload_analyzer.py
    └── yara_scanner.py
```

---

## Requirements

- Python 3.11+ (Docker uses 3.12)
- Gemini API key
- Optional: Brevo SMTP for email demos

```powershell
cd "path\to\demo-wrdn-"
py -m pip install -r wrdn/backend/requirements.txt
```

---

## Environment

Create `.env` in the **repo root**:

```powershell
copy .env.example .env
```

Minimum:

```env
GEMINI_API_KEY=your_key
```

Email (policy activation + HR outbound):

```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
MAIL_USERNAME=your_brevo_login_email
MAIL_APP_PASSWORD=your_brevo_smtp_key
MAIL_FROM_NAME=WRDN Security
MAIL_FROM_EMAIL=your_verified_sender@example.com
POLICY_APPROVAL_EMAIL=admin@example.com
POLICY_APPROVAL_NAME=Admin
FRONTEND_URL=http://localhost:18085
BACKEND_URL=http://127.0.0.1:18000
```

---

## Run

Docker (from repo root):

```powershell
docker compose up -d --build backend
```

Local:

```powershell
py -m uvicorn wrdn.backend.main:app --reload --host 127.0.0.1 --port 18000
```

API: http://localhost:18000  
Docs: http://localhost:18000/docs

---

## Important API groups

### Auth
- `POST /api/auth/signup` — first user becomes Admin; later public signups are Employee
- `POST /api/auth/login`
- Admin user create / list / delete

### Protection
- `GET /api/protection-status?client_id=...`
- `POST /api/admin/protection-status`

### Chat
- Returns answer + `shield_status`
  - Protection ON → `ALLOWED` or `BLOCKED`
  - Protection OFF → `BYPASSED`

### Policies (admin)
- Submit checklist / extra notes
- Generate policy with Gemini
- Request activation → Brevo confirm / reject links
- List / rollback / delete

### HR Candidates

Test cases and screenshots: [WRDN Test Case Document](../WRDN_Test_Case_Document.docx)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/hr/sample-cvs` | Safe + attack sample text |
| `POST` | `/api/hr/extract-cv` | Upload file → extracted text |
| `POST` | `/api/hr/process-cv-upload` | Upload PDF/DOCX/TXT → full pipeline |

---

## HR pipeline

```text
CV file
  → YARA + payload analyzer (inbound)
       └─ high-risk hostile file → BLOCK (Gemini not called)
  → extract text
  → Agent 1 (evaluate)
  → Agent 2 (draft candidate email)
  → WRDN outbound leak check
  → policy risk review
       ├─ protection OFF → BYPASSED → send via Brevo
       ├─ leak/policy fail + protection ON → BLOCKED → do not send
       └─ clean + protection ON → ALLOWED → send via Brevo
  → audit log
```

Inbound scan tests:

```powershell
python wrdn/backend/tests/test_inbound_scan.py
```

Brevo delivery uses the **email found on the CV**. If the CV has no address, it falls back to `POLICY_APPROVAL_EMAIL`.

---

## Database

- Engine: SQLite
- Default path: `wrdn/backend/data/wrdn.db`
- Created on startup
- Docker volume: `wrdn_database`

Users are created through signup / the Users page, not auto-seeded.

---

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `GEMINI_API_KEY` errors | `.env` in repo root; rebuild backend |
| SMTP / Brevo auth failed | `MAIL_USERNAME`, `MAIL_APP_PASSWORD`, `MAIL_FROM_EMAIL`, authorised IP |
| HR upload 400 | File type must be PDF/DOCX/TXT |
| CORS errors | Frontend must call `http://localhost:18000` |

```powershell
docker compose logs -f backend
```

---

## Related docs

- [Root README](../../README.md)
- [Frontend README](../frontend/README.md)
- [Simulator README](../demo-wrdn--simulator/README.md)
