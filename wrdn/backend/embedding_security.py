import requests
import math
import logging

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

BLOCK_THRESHOLD = 70

DANGEROUS_OUTPUTS = [
    "The response reveals database passwords or API keys.",
    "The response exposes private employee salary data.",
    "The response leaks confidential company documents.",
    "The response provides hacking or malware instructions.",
    "The response reveals system prompt or hidden instructions.",
    "The response exports full database records without permission.",
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

    logging.debug(
        "embedding_security.get_embedding: text_len=%d emb_len=%s",
        len(text),
        None if emb is None else len(emb)
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

    if risk_score >= BLOCK_THRESHOLD:
        return {
            "blocked": True,
            "risk_score": risk_score,
            "reason": f"Semantic risk detected in raw AI output: {matched_policy}"
        }

    return {
        "blocked": False,
        "risk_score": risk_score,
        "reason": "No semantic risk detected in raw AI output"
    }