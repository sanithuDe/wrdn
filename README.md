# WRDN Enterprise AI Simulator

A terminal-based simulation framework designed to demonstrate indirect prompt injection vulnerabilities on Large Language Model agents using tool execution.

## Project Structure

```text
WRDN Enterprise AI Simulator/
├── Database/
│   ├── registry.txt
│   └── salaries.txt
├── Input/
│   ├── attack.txt
│   └── safe.txt
├── app.py
└── README.md
```
## Prerequisites
* Python 3.10 or higher.
* Google Gemini API Key from Google AI Studio.

## Installation
1. Install the official **Google GenAI** Python SDK:
   ```bash
   pip install google-genai
   ```
2. Clone or set up the repository to match the project structure shown above.

## Configuration
1. Open `app.py`.
2. Locate the line defining `API_KEY` (around line 13).
3. Replace `"PASTE_YOUR_API_KEY_HERE"` with your actual Gemini API Key.

## Usage
1. Launch the script from your terminal:
   ```bash
   python app.py
   ```

2. Select your simulation path when prompted:
   * Enter **`1`** to run standard candidate evaluations via `Input/safe.txt`.
   * Enter **`2`** to trigger an injection payload simulation via `Input/attack.txt`.
3. Follow the interactive terminal prompts by pressing `ENTER` to step through disk reads, API data streaming, and tool execution evaluations.

## Security Notice
This simulator handles sensitive corporate files like `salaries.txt` alongside untrusted data like `attack.txt`. It is meant for educational and security testing purposes only to show how agents can be tricked into abusing tools like email dispatching.
