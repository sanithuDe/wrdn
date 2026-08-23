# WRDN Frontend

Next.js (App Router) UI for WRDN Enterprise Prompt Shield.

Talks to the FastAPI backend at `http://localhost:18000` by default.

---

## What you can do in the UI

| Section | Path | Who | Purpose |
| --- | --- | --- | --- |
| Sign up | `/signup` | Everyone | First user = Admin; later = Employee |
| Sign in | `/signin` | Everyone | Sign in |
| AI Chat | `/` | Everyone | Ask through the WRDN shield |
| Policy Upload | `/policies` | ADMIN | Checklist → generate → activate |
| Policy activation | `/policies/activation` | Email link | Confirm or reject |
| Users | `/users` | ADMIN | Create / delete accounts |
| HR Candidates | `/hr` | Everyone (admin toggle) | Upload CV → shielded email |
| Security Dashboard | `/?section=dashboard` | Everyone | Overview |
| Live Registry | `/?section=live-registry` | Everyone | Recent shield decisions |
| Settings | `/?section=settings` | ADMIN | Enable / disable WRDN |

---

## Folder structure

```text
wrdn/frontend/
├── app/
│   ├── page.tsx
│   ├── (auth)/signin/page.tsx
│   ├── (auth)/signup/page.tsx
│   ├── users/page.tsx
│   ├── hr/page.tsx
│   ├── policies/
│   │   ├── page.tsx
│   │   └── activation/page.tsx
│   ├── globals.css
│   └── layout.tsx
├── components/
│   ├── AppSidebar.tsx
│   ├── ChatInterface.tsx
│   └── RegistryDashboard.tsx
├── lib/
│   ├── api.ts
│   ├── authApi.ts
│   ├── chatApi.ts
│   └── chatHistory.ts
└── package.json
```

---

## Run

Docker (from repo root):

```powershell
docker compose up -d --build
```

Local:

```powershell
cd wrdn/frontend
npm install
npm run dev -- -p 18085
```

Open: http://localhost:18085

---

## Environment

```env
NEXT_PUBLIC_API_URL=http://localhost:18000
```

---

## Accounts

Create the first admin on **Sign up**. Later public signups are employees. Admins add more users on `/users`.

---

## HR Candidates (`/hr`)

1. Upload a PDF / DOCX / TXT CV
2. Click **Process uploaded CV**
3. Results show Agent 1, Agent 2, WRDN status, and Brevo send status

| Scenario | Action | Expect |
| --- | --- | --- |
| Safe | Upload `01_...` with WRDN ON | `ALLOWED` + email if Brevo is configured |
| Attack leak | Disable WRDN → upload `02_...` | `BYPASSED` + email |
| Attack blocked | Enable WRDN → upload `02_...` | `BLOCKED` + no email |
| Hostile PDF | Upload `03_...` | Inbound YARA **BLOCK** |

---

## Policy Upload (`/policies`)

1. Tick ALLOWED / BLOCKED categories
2. Generate policy
3. Activate → confirmation email (Brevo)
4. Confirm on `/policies/activation`

---

## Protection toggle

| Mode | Meaning |
| --- | --- |
| ON | `ALLOWED` or `BLOCKED` |
| OFF | `BYPASSED` (demo comparison) |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| UI loads but APIs fail | Backend must be on `18000` |
| Login loop | Create an account on `/signup` first |
| Email confirm tab issues | Links open `/policies/activation`; return to Policy Upload |

---

## Related docs

- [Root README](../../README.md)
- [Backend README](../backend/README.md)
- [Simulator README](../demo-wrdn--simulator/README.md)
