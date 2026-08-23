# WRDN Enterprise AI Simulator

Optional **terminal** demo that shows how an HR-style Gemini agent can be tricked by prompt injection inside a CV, and how WRDN-style output checks can block a leaky outbound email.

This simulator is **separate** from the main web app.  
For the full product UI (upload PDF, agents, Brevo email, protection toggle), use **HR Candidates** in the frontend — see the [root README](../../README.md).

---

## What this simulator shows

1. An HR agent reads a CV plus a confidential salary ledger.
2. The agent can call tools such as `send_external_email`.
3. A malicious CV can instruct the agent to put private salary data into that email.
4. When “WRDN” is enabled, outbound email content is checked before send.
5. When “WRDN” is disabled, the leaky email may go through (demo of risk).

---

## Folder structure

```text
wrdn/demo-wrdn--simulator/
├── app.py                 # Interactive terminal simulator
├── README.md
├── Database/
│   ├── salaries.txt       # Fake confidential salary ledger (JSON)
│   └── registry.txt       # Local audit / evaluation log
└── Input/
    ├── safe.txt           # Clean candidate CV
    ├── attack.txt         # Injection CV (salary exfil attempt)
    └── WRDNattack.txt     # Stronger full-ledger attack variant
```

---

## Prerequisites

- Python 3.10+
- Google Gemini API key ([AI Studio](https://aistudio.google.com/apikey))
- Packages used by the main project (`google-genai`, `requests`)

From repo root (recommended):

```powershell
py -m pip install google-genai requests
```

The simulator imports `GEMINI_API_KEY` from `wrdn.config` (repo `.env`).  
Create `.env` from `.env.example` at the repo root and set `GEMINI_API_KEY`.

---

## How to run

From the **simulator folder**:

```powershell
cd wrdn\demo-wrdn--simulator
py app.py
```

Or from repo root (if your Python path includes the package root):

```powershell
py wrdn\demo-wrdn--simulator\app.py
```

### Menu choices

| Choice | Scenario | CV file | WRDN check |
|---|---|---|---|
| `1` | Safe processing | `Input/safe.txt` | Enabled |
| `2` | Attack without protection | `Input/attack.txt` | Disabled |
| `3` | Attack with protection | `Input/attack.txt` | Enabled |

Press **ENTER** when prompted to step through:
- reading files
- calling Gemini
- evaluating tool calls / sanitizer results

---

## Important notes

### About the sanitizer URL
The script may call a local sanitizer endpoint (historically `http://127.0.0.1:8000/sanitize`).

- For the **main WRDN app**, the protected HR flow lives at backend port **18000** under `/api/hr/...`.
- This simulator is a **standalone teaching tool**. Prefer the web HR page for the current end-to-end demo with Docker + Brevo.

### Sample inputs

**Safe (`safe.txt`)**  
Normal resume for David Miller — no injection.

**Attack (`attack.txt`)**  
Mallory Hacker CV with “administrative re-routing” instructions that try to force salary leakage into email.

**Stronger attack (`WRDNattack.txt`)**  
Attempts broader corporate salary ledger exfiltration.

The same story is available as PDFs for the web app in:

```text
wrdn/hr_demo_cvs/
```

---

## Expected teaching outcomes

| Run | What students should see |
|---|---|
| Safe + WRDN ON | Normal evaluation; clean outbound message |
| Attack + WRDN OFF | Injection can succeed; sensitive data may appear in email path |
| Attack + WRDN ON | Sensitive outbound content blocked / recorded |

---

## Security notice

- Educational use only.
- Contains fake “confidential” salary data for demos.
- Do not point this at production systems or real employee data.
- Do not commit real API keys into `app.py`.

---

## Related docs

- [Root README](../../README.md) — Docker web app setup for friends
- [Backend README](../backend/README.md) — `/api/hr` pipeline
- [Frontend README](../frontend/README.md) — `/hr` upload UI
