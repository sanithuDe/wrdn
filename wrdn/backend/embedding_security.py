import math
import logging
try:
    from google import genai
except Exception:
    genai = None

from wrdn.config import GEMINI_API_KEY, GEMINI_EMBED_MODEL

BLOCK_THRESHOLD = 70

if GEMINI_API_KEY and genai is not None:
    # Prefer module-level configuration which the SDK supports across versions
    try:
        if hasattr(genai, "configure"):
            genai.configure(api_key=GEMINI_API_KEY)
            GEMINI_CLIENT = None
        else:
            GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        # Fall back to attempting a client instance
        try:
            GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            GEMINI_CLIENT = None
else:
    GEMINI_CLIENT = None

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

    if not GEMINI_CLIENT and genai is None:
        raise RuntimeError("GEMINI embedding client not configured. Set GEMINI_API_KEY and install google-genai in the backend environment.")

    resp = None
    last_exc = None

    # Try client-level embeddings via models.embed_content
    try:
        if GEMINI_CLIENT and hasattr(GEMINI_CLIENT, "models") and hasattr(GEMINI_CLIENT.models, "embed_content"):
            resp = GEMINI_CLIENT.models.embed_content(
                model=GEMINI_EMBED_MODEL,
                contents=[text],
            )
    except Exception as e:
        last_exc = e

    # Try module-level genai.models.embed_content if available
    if resp is None and genai is not None:
        try:
            if hasattr(genai, "models") and hasattr(genai.models, "embed_content"):
                resp = genai.models.embed_content(
                    model=GEMINI_EMBED_MODEL,
                    contents=[text],
                )
        except Exception as e:
            last_exc = e

    if resp is None:
        logging.error("embedding_security.get_embedding: no embeddings API available (%s)", last_exc)
        raise RuntimeError("No embeddings API available on google.genai client; ensure google-genai is up-to-date and GEMINI_API_KEY is set.")

    # SDK returns embeddings in various shapes; normalize.
    emb = None
    try:
        embeddings = getattr(resp, "embeddings", None)
        if embeddings and len(embeddings) > 0:
            first = embeddings[0]
            emb = getattr(first, "embedding", None) or (first.get("embedding") if isinstance(first, dict) else None)
    except Exception:
        emb = None

    if emb is None:
        try:
            data = getattr(resp, "data", None)
            if data and len(data) > 0:
                first = data[0]
                emb = getattr(first, "embedding", None) or (first.get("embedding") if isinstance(first, dict) else None)
        except Exception:
            emb = None

    if emb is None:
        try:
            if isinstance(resp, dict):
                emb = resp.get("data", [None])[0].get("embedding")
        except Exception:
            emb = getattr(resp, "embedding", None)

    if emb is None:
        logging.error("embedding_security.get_embedding: failed to extract embedding from response: %s", type(resp))
        raise ValueError("No embedding returned from Gemini")

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