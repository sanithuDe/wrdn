# WRDN (WARDEN)

**Enterprise Prompt Shield** — real-time protection for AI assistants against prompt injection, sensitive data leaks, and unsafe outbound actions.

Final-year demo: signup and role-based access, client policies with email activation, chat shielding, HR CV attack demos, live registry, and Brevo outbound email.

---

## Table of contents

1. [What you need to install](#1-what-you-need-to-install)
2. [How to run (Docker — recommended)](#2-how-to-run-docker--recommended)
3. [How to run (without Docker)](#3-how-to-run-without-docker)
4. [Environment file (`.env`)](#4-environment-file-env)
5. [Accounts and roles](#5-accounts-and-roles)
6. [URLs and pages](#6-urls-and-pages)
7. [How to test / demo](#7-how-to-test--demo)
8. [Project layout](#8-project-layout)
9. [Troubleshooting](#9-troubleshooting)
10. [Other README files](#10-other-readme-files)

---

## 1. What you need to install

### Option A — Docker (easiest)

| Software | Why | Download |
| --- | --- | --- |
| **Git** | Clone the repo | [https://git-scm.com/downloads](https://git-scm.com/downloads) |
| **Docker Desktop** | Runs backend + frontend | [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) |

Also create:

| Account / key | Required? | Where |
| --- | --- | --- |
| **Gemini API key** | **Yes** | [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| **Brevo** SMTP | For policy + HR emails | [https://app.brevo.com](https://app.brevo.com) |

After installing Docker Desktop:

1. Open Docker Desktop
2. Wait until it says **Engine running**
3. Then run the project commands below

You do **not** need to install Python or Node when using Docker.

### Option B — Local (no Docker)

| Software | Version | Why |
| --- | --- | --- |
| **Git** | Latest | Clone repo |
| **Python** | 3.11+ (3.12 OK) | Backend |
| **Node.js** | 20+ LTS | Frontend |

Plus the same **Gemini API key** (and optional Brevo SMTP).

---

## 2. How to run (Docker — recommended)

### Step 1 — Clone

```powershell
git clone https://github.com/sanithuDe/demo-wrdn-.git
cd demo-wrdn-
git checkout version2.7
```

### Step 2 — Create environment file

```powershell
copy .env.example .env
```

### Step 3 — Edit `.env`

**Minimum (app will run):**

```env
GEMINI_API_KEY=paste_your_gemini_key_here
```

**For Brevo emails (policy activation + HR):**

```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
MAIL_USERNAME=your_brevo_login_email
MAIL_APP_PASSWORD=your_brevo_smtp_key
MAIL_FROM_NAME=WRDN Security
MAIL_FROM_EMAIL=your_verified_sender@example.com
POLICY_APPROVAL_EMAIL=admin@example.com
POLICY_APPROVAL_NAME=Admin
```

In Brevo:

1. SMTP & API → create an **SMTP key** (use it as `MAIL_APP_PASSWORD`)
2. Verify the **sender** used in `MAIL_FROM_EMAIL`
3. If login fails with **Unauthorized IP**, add this computer's public IP under **Authorised IPs**

Keep these unless you change ports:

```env
NEXT_PUBLIC_API_URL=http://localhost:18000
BACKEND_URL=http://127.0.0.1:18000
FRONTEND_URL=http://localhost:18085
```

**Never commit** `.env` **or share your real keys.**

### Step 4 — Start

```powershell
docker compose up -d --build
```

### Step 5 — Open

| What | URL |
| --- | --- |
| **Website** | [http://localhost:18085](http://localhost:18085) |
| **API docs** | [http://localhost:18000/docs](http://localhost:18000/docs) |

### Step 6 — Useful Docker commands

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
docker compose up -d --build
```

---

## 3. How to run (without Docker)

### 3.1 Backend

From the repo root:

```powershell
copy .env.example .env
py -m pip install -r wrdn/backend/requirements.txt
py -m uvicorn wrdn.backend.main:app --reload --host 127.0.0.1 --port 18000
```

API: [http://127.0.0.1:18000/docs](http://127.0.0.1:18000/docs)

### 3.2 Frontend

```powershell
cd wrdn\frontend
npm install
npm run dev -- -p 18085
```

UI: [http://localhost:18085](http://localhost:18085)

---

## 4. Environment file (`.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | **Yes** | Google Gemini access |
| `GEMINI_MODEL` | No | Chat / policy model |
| `NEXT_PUBLIC_API_URL` | Yes for UI | Frontend → backend (`http://localhost:18000`) |
| `SMTP_HOST` | For email | `smtp-relay.brevo.com` |
| `SMTP_PORT` | For email | `587` |
| `MAIL_USERNAME` | For email | Brevo login email |
| `MAIL_APP_PASSWORD` | For email | Brevo SMTP key |
| `MAIL_FROM_EMAIL` | For email | Verified Brevo sender |
| `MAIL_FROM_NAME` | For email | Sender display name |
| `POLICY_APPROVAL_EMAIL` | For email | Inbox that receives activation + HR mail |
| `FRONTEND_URL` | Recommended | Links inside emails |
| `BACKEND_URL` | Recommended | Backend base URL |

Template: [`.env.example`](.env.example)

---

## 5. Accounts and roles

Users are **not** auto-created on startup.

| Who | How |
| --- | --- |
| **First user** | Sign up at `/signup` — becomes **Admin** |
| **Later public signups** | Always **Employee** |
| **More admins / employees** | Admin → **Users** page |

| Role | Can do |
| --- | --- |
| **ADMIN** | Chat, policies, users, HR, dashboard, protection toggle |
| **EMPLOYEE** | Chat (own history). Admin can review employee chats for the same client (read-only) |

---

## 6. URLs and pages

| Port | Service |
| --- | --- |
| **18085** | Frontend (Next.js) |
| **18000** | Backend (FastAPI) |

| Feature | Where |
| --- | --- |
| Sign up | `/signup` |
| Sign in | `/signin` |
| AI Chat + history | `/` |
| Policy Upload | `/policies` (admin) |
| Policy activation | `/policies/activation` (from email) |
| Users | `/users` (admin) |
| HR Candidates | `/hr` |
| Security Dashboard | Sidebar → Security Dashboard |
| Live Registry / logs | Sidebar sections |
| Settings | Sidebar → Settings (protection on/off) |

---

## 7. How to test / demo

### 7.1 Sign up and chat

1. Open [http://localhost:18085](http://localhost:18085)
2. Create the first admin on **Sign up**
3. Ask a normal question → **ALLOWED**
4. Ask for a blocked salary/password (after policy is active) → **BLOCKED**

### 7.2 Policy checklist + Brevo activation

1. Admin → **Policy Upload**
2. Tick ALLOWED / BLOCKED categories (and optional extra notes)
3. Generate → Activate
4. Open the Brevo inbox for `POLICY_APPROVAL_EMAIL`
5. Click **Confirm Activation** (policy does not go live until this)

### 7.3 HR Candidates

Sample PDFs: `wrdn/hr_demo_cvs/`

| File | WRDN | Expected |
| --- | --- | --- |
| `01_safe_david_miller_ALLOWED.pdf` | ON | **ALLOWED** (+ Brevo email if configured) |
| `02_attack_mallory_salary_leak.pdf` | **OFF** | **BYPASSED** (leak + email) |
| `02_attack_mallory_salary_leak.pdf` | **ON** | **BLOCKED** (no email) |
| `03_suspicious_pdf_javascript.pdf` | any | **Inbound BLOCK** (YARA, Gemini not called) |

### 7.4 Users

Admin → **Users** → create Employee/Admin → delete (cannot delete the last admin).

---

## 8. Project layout

```text
demo-wrdn-/
├── docker-compose.yml
├── .env.example
├── README.md
└── wrdn/
    ├── backend/                 FastAPI API
    ├── frontend/                Next.js UI
    ├── hr_demo_cvs/             Demo PDF CVs
    ├── demo-requirements/       Sample policy texts
    └── demo-wrdn--simulator/    Optional terminal demo
```

---

## 9. Troubleshooting

| Problem | Fix |
| --- | --- |
| `docker` not found | Install Docker Desktop and restart the terminal |
| Build fails / port in use | Free 18000/18085; `docker compose down` then up |
| Gemini errors | Set `GEMINI_API_KEY` in `.env`, rebuild |
| UI loads but API fails | Check `docker compose logs backend` |
| No emails in Brevo | Fill SMTP + `MAIL_FROM_EMAIL` + `POLICY_APPROVAL_EMAIL`; authorise your IP |
| SMTP 525 Unauthorized IP | Brevo → SMTP & API → Authorised IPs |
| Old features missing | `git checkout version2.7` then `docker compose up -d --build` |

---

## 10. Other README files

| File | Contents |
| --- | --- |
| [wrdn/backend/README.md](wrdn/backend/README.md) | Backend APIs, HR pipeline, DB |
| [wrdn/frontend/README.md](wrdn/frontend/README.md) | UI pages and demo flow |
| [wrdn/demo-wrdn--simulator/README.md](wrdn/demo-wrdn--simulator/README.md) | Optional terminal simulator |

Friends who only want to test the web app: **this root README is enough**.

---

## What WRDN does

| Feature | Description |
| --- | --- |
| **Signup / users** | First user is Admin; later public signups are Employee |
| **AI Chat shield** | Answers judged by policy → `ALLOWED` / `BLOCKED` / `BYPASSED` |
| **Chat history** | Newest chats on top; admin can open team chats read-only |
| **Protection toggle** | Admin OFF → `BYPASSED` for demos |
| **Client policies** | Checklist → generate → Brevo confirm → activate |
| **HR Candidates** | CV upload → inbound scan → 2 agents → outbound shield |
| **Live registry** | Audit of shield decisions |
| **Brevo email** | Policy activation + HR candidate mail |

---

## Security notes

- For education and demos only
- Attack CVs try to leak salary data on purpose
- Never commit `.env` or real secrets
- WRDN ON blocks leaks; WRDN OFF shows `BYPASSED` for comparison

---

## Academic use

Final Year Project demo — team and examiners.
