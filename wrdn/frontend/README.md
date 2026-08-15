# WRDN Frontend

Next.js (App Router) UI for WRDN Enterprise Prompt Shield.

Talks to the FastAPI backend at `http://localhost:18000` by default.

---

## What you can do in the UI

| Section | Path | Who | Purpose |
|---|---|---|---|
| Login | `/login` | Everyone | Sign in |
| AI Chat | `/` | Everyone | Ask Gemini through WRDN shield |
| Policy Upload | `/policies` | ADMIN | Build / activate client policies |
| Policy activation | `/policies/activation` | Email link | Confirm or reject activation |
| HR Candidates | `/hr` | Everyone (admin toggle) | Upload CV → agents → shielded email |
| Security Dashboard | `/?section=dashboard` | Everyone | Overview |
| Live Registry | `/?section=live-registry` | Everyone | Recent shield decisions |
| Allowed / Blocked / Risk | sidebar sections | Everyone | Filtered logs |
| Settings | `/?section=settings` | ADMIN | Enable / disable WRDN protection |

---

## Folder structure

```text
wrdn/frontend/
├── app/
│   ├── page.tsx                 # Chat + registry shell
│   ├── login/page.tsx
│   ├── hr/page.tsx              # HR Candidate Processor
│   ├── policies/
│   │   ├── page.tsx             # Policy wizard
│   │   └── activation/page.tsx  # Email confirm/reject page
│   ├── globals.css
│   └── layout.tsx
├── components/
│   ├── AppSidebar.tsx
│   ├── ChatInterface.tsx
│   ├── RegistryDashboard.tsx
│   └── ...
├── lib/
│   ├── api.ts                   # Policies, protection, HR APIs
│   ├── authApi.ts
│   ├── chatApi.ts
│   └── registryApi.ts
├── Dockerfile
├── package.json
└── README.md
```

---

## Prerequisites

- Node.js 20+ (Docker image uses Node 20)
- Backend running on port **18000**
- Root `.env` / compose env with `NEXT_PUBLIC_API_URL=http://localhost:18000`

---

## Run with Docker (recommended)

From repo root:

```powershell
docker compose up -d --build frontend
```

Or start both services:

```powershell
docker compose up -d --build
```

Open: http://localhost:18085

---

## Run locally (without Docker)

```powershell
cd wrdn/frontend
npm install
npm run dev -- -p 18085
```

Open: http://localhost:18085

Production-style local build:

```powershell
npm run build
npm run start -- -p 18085
```

---

## Environment

The browser calls the backend using:

```env
NEXT_PUBLIC_API_URL=http://localhost:18000
```

In Docker Compose this is set as a build arg + runtime env.

If you change the backend port, update this value and rebuild the frontend image.

---

## Demo login

| Username | Password | Role |
|---|---|---|
| `adminA` | `AdminA@2026!` | ADMIN |
| `employeeA` | `EmpA@2026!` | EMPLOYEE |
| `adminB` | `AdminB@2026!` | ADMIN |
| `employeeB` | `EmpB@2026!` | EMPLOYEE |

Use **adminA** for Policy Upload, protection toggle, and full HR demos.

---

## HR Candidates page (`/hr`)

### Flow
1. Upload a **PDF / DOCX / TXT** CV (file only — no paste box)
2. Optional: set target role
3. Click **Process uploaded CV**
4. File is sent to `POST /api/hr/process-cv-upload`
5. Results show Agent 1 evaluation, Agent 2 email, WRDN status, Mailtrap send status

### Sample buttons
- **Load safe CV** / **Load attack CV** create a temporary `.txt` file and still go through the upload API.

### Demo files on disk
```text
wrdn/hr_demo_cvs/
├── 01_safe_david_miller_ALLOWED.pdf
├── 02_attack_mallory_salary_leak.pdf
└── 03_suspicious_pdf_javascript.pdf
```

| Scenario | Action | Expect |
|---|---|---|
| Safe | Upload `01_...` with WRDN ON | `ALLOWED` + email if Mailtrap configured |
| Attack leak | Disable WRDN → upload `02_...` | `BYPASSED` + email |
| Attack blocked | Enable WRDN → upload `02_...` | `BLOCKED` + no email |
| Hostile PDF marker | Upload `03_...` | Inbound YARA **BLOCK**, no Gemini |

---

## Policy Upload page (`/policies`)

Admin-only wizard:
1. Upload requirement file
2. Generate policy with Gemini
3. Request activation → confirmation email (Mailtrap)
4. Open email link → confirm on `/policies/activation`
5. View history / rollback

---

## Protection toggle

Admins can disable WRDN in **Settings** or on the HR page.

| Mode | Chat / HR meaning |
|---|---|
| ON | Normal shield → `ALLOWED` or `BLOCKED` |
| OFF | Raw path → `BYPASSED` (demo comparison) |

---

## API helpers

Main client wrappers live in `lib/api.ts`:

- Policies: upload, analyze, activate, list, rollback, delete
- Protection: `getProtectionStatus`, `setProtectionStatus`
- HR: `processHrCvUpload`, `extractHrCv`, `getHrSampleCvs`

Auth: `lib/authApi.ts`  
Chat: `lib/chatApi.ts`  
Registry: `lib/registryApi.ts`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| UI loads but APIs fail | Backend must be on `18000`; check `NEXT_PUBLIC_API_URL` |
| HR page missing after pull | Rebuild frontend: `docker compose up -d --build frontend` |
| TypeScript build error in Docker | Rebuild after pulling latest; `AppSection` includes `hr` |
| Login loop | Clear site data / check backend auth seed users |
| Email confirm tab issues | Links open frontend activation page; return to Policy Upload tab |

---

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |

---

## Related docs

- [Root README](../../README.md) — clone, `.env`, Docker for friends
- [Backend README](../backend/README.md)
- [Simulator README](../demo-wrdn--simulator/README.md)
