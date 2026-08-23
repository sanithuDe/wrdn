import json
from pathlib import Path

from wrdn.backend.database import get_connection


DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "policies"
    / "default_policy.json"
)


def load_default_policy() -> dict:
    """
    Load the default WRDN security policy.
    """

    with DEFAULT_POLICY_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_active_policy(
    client_id: str,
) -> dict:
    """
    Load the client's active policy.

    If no active client policy exists,
    use the default WRDN policy.
    """

    normalized_client_id = (
        client_id or "default"
    ).strip()

    if normalized_client_id == "default":
        return load_default_policy()

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT
                PolicyID,
                ClientID,
                RequirementFileID,
                Version,
                PolicyJSON
            FROM ClientPolicies
            WHERE ClientID = ?
              AND Status = 'ACTIVE'
            ORDER BY Version DESC
            LIMIT 1
            """,
            (normalized_client_id,),
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        policy = load_default_policy()

        policy["client_id"] = (
            normalized_client_id
        )

        policy["policy_source"] = (
            "default_fallback"
        )

        return policy

    policy = json.loads(
        row["PolicyJSON"]
    )

    policy["policy_id"] = row["PolicyID"]
    policy["client_id"] = row["ClientID"]

    policy["requirement_file_id"] = (
        row["RequirementFileID"]
    )

    policy["version"] = row["Version"]
    policy["policy_source"] = "client"

    return policy