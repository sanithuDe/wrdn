# WRDN - AI Output Sanitizer

WRDN is a FastAPI + Google Gemini based AI security system that detects and blocks harmful AI-generated outputs using regex filtering and LLM-based classification.

---

# Project Structure

```textWRDN/
 └── version1/
     ├── backend/
     │   ├── main.py
     │   ├── requirements.txt
     │   └── .gitignore
     └── frontend/

```

---


# Backend Setup

```bash
cd version1/backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
py -m uvicorn main:app --reload
``` 

Backend runs on:

```text
http://127.0.0.1:8000
```

---

# Gemini (Google) Setup

Install the official Google GenAI Python SDK and set your API key:

```bash
pip install google-genai
set GEMINI_API_KEY=your_api_key_here  # Windows cmd
export GEMINI_API_KEY=your_api_key_here  # macOS / Linux
```

The backend expects `GEMINI_API_KEY` to be available in the environment. You can optionally set `GEMINI_MODEL` and `GEMINI_EMBED_MODEL` environment variables to override defaults.

---
# check 
# requirements.txt

```txt
fastapi
uvicorn

requests
pydantic
```

---
# check 
# .gitignore

```gitignore
venv/
__pycache__/
*.pyc
.env
```