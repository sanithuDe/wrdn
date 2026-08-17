"""
Policy-page category keywords shared by chat and HR Layer 4.

HR Layer 4 only auto-scans harm categories on CV files
(malware, violence, illegal_activity). Salary/PII/credential
words stay email-side so a normal resume is not blocked.
"""

from __future__ import annotations


INPUT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "personal_information": (
        "national id",
        "nationalid",
        "nic",
        "phone number",
        "address",
        "home address",
    ),
    "customer_information": (
        "confidential notes",
        "contract payment",
        "payment amount",
        "client contract confidential",
    ),
    "financial_records": (
        "salary",
        "payroll",
        "how much does",
        "bank account",
        "paymentamount",
        "rs.",
        "lkr",
    ),
    "credentials": (
        "password",
        "api key",
        "access token",
        "private key",
        "secret value",
        "admin password",
        "kasun password",
        "kasun account password",
        "kasun perera password",
        "database password",
        "vpn password",
        "aws root",
        "company secret",
        "payroll system password",
        "smtp secret",
        "backup encryption",
        "github deploy token",
        "jwt token",
    ),
    "employee_information": (
        "employee salary",
        "staff salary",
        "salary list",
        "payroll list",
    ),
    "internal_documents": (
        "confidential notes",
        "internal security incident",
        "confidential contract",
    ),
    "source_code": (
        "source code",
        "dump the code",
        "show me the code base",
    ),
    "malware": (
        "malware",
        "ransomware",
        "write a virus",
        "computer virus",
        "trojan horse",
        "exploit payload",
        "shellcode",
        "weaponized",
        "keylogger",
        "backdoor",
        "rootkit",
        "botnet",
    ),
    "violence": (
        "how to attack",
        "how to kill",
        "make a bomb",
        "how to harm",
        "violent attack",
        "kill someone",
        "bomb making",
        "murder",
        "assault weapon",
    ),
    "illegal_activity": (
        "how to hack",
        "hack into",
        "steal data",
        "steal information",
        "commit fraud",
        "fraud",
        "fraudulent",
        "scam",
        "phishing",
        "illegal activity",
        "illegal",
        "crime",
        "criminal",
        "money laundering",
        "launder money",
        "embezzle",
        "bribery",
        "bribe",
        "identity theft",
        "unauthorized access",
        "bypass security",
        "theft",
        "robbery",
        "counterfeit",
        "smuggling",
        "hacking",
    ),
}

# CV/email Layer 4 uses these blocked policy-page sectors only.
HARM_POLICY_CATEGORIES = frozenset(
    {
        "malware",
        "violence",
        "illegal_activity",
    }
)
