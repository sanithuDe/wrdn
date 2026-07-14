import requests
import math
import logging

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

BLOCK_THRESHOLD = 70

DANGEROUS_OUTPUTS = [
    "The raw AI output reveals passwords, admin passwords, database passwords, or login credentials.",
    "The raw AI output reveals API keys, access tokens, JWT tokens, secret keys, or private keys.",
    "The raw AI output reveals employee salary, manager salary, payroll data, or private HR information.",
    "The raw AI output reveals confidential company records or internal database records.",
    "The raw AI output gives SQL queries that retrieve sensitive data such as salary, password, token, or secret.",
    "The raw AI output reveals system prompts or hidden instructions.",
    "The raw AI output provides harmful hacking, malware, or unauthorized access instructions.",
]


def get_embedding(text: str):
    response = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": EMBED_MODEL,
            "prompt": text
        },
        timeout=60
    )

    response.raise_for_status()
    emb = response.json().get("embedding")

    if emb is None:
        raise ValueError("No embedding returned from Ollama")

    logging.debug(
        "embedding_security.get_embedding: text_len=%d emb_len=%s",
        len(text),
        len(emb)
    )

    return emb


def cosine_similarity(vec1, vec2):
    dot = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = math.sqrt(sum(a * a for a in vec1))
    mag2 = math.sqrt(sum(b * b for b in vec2))

    if mag1 == 0 or mag2 == 0:
        return 0

    return dot / (mag1 * mag2)


def embedding_risk_check(raw_ai_output: str):
    if not raw_ai_output or not raw_ai_output.strip():
        return {
            "blocked": False,
            "risk_score": 0,
            "reason": "Raw AI output is empty"
        }

    output_vector = get_embedding(raw_ai_output)

    highest_similarity = 0
    matched_policy = ""

    for policy in DANGEROUS_OUTPUTS:
        policy_vector = get_embedding(policy)
        similarity = cosine_similarity(output_vector, policy_vector)

        logging.debug(
            "embedding_security.score: policy=%s similarity=%.4f",
            policy,
            similarity
        )

        if similarity > highest_similarity:
            highest_similarity = similarity
            matched_policy = policy

    risk_score = int(highest_similarity * 100)

    return {
        "blocked": risk_score >= BLOCK_THRESHOLD,
        "risk_score": risk_score,
        "reason": (
            f"Semantic risk detected in raw AI output: {matched_policy}"
            if risk_score >= BLOCK_THRESHOLD
            else "No semantic risk detected in raw AI output"
        )
    }