# WRDN - AI Output Sanitizer

WRDN is a FastAPI + Ollama based AI security system that detects and blocks harmful AI-generated outputs using regex filtering and LLM-based classification.

---

# Project Structure

```text
WRDN/
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
python -m uvicorn main:app --reload
```

Backend runs on:

```text
http://127.0.0.1:8000
```

---

# Ollama Setup

Install Ollama:

https://ollama.com

Run model:

```bash
ollama run llama3.2
```

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