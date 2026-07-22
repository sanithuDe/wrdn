import logging
import sqlite3
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

# ==========================================
# DATABASE LOCATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "wrdn.db"


# ==========================================
# SAMPLE DATA
# ==========================================

FALLBACK_EMPLOYEES = [
    {
        "FullName": "Kasun Perera",
        "Email": "kasun@company.com",
        "RoleName": "Manager",
        "Salary": "450000",
        "PhoneNumber": "0771234567",
        "AddressLine": "Colombo",
        "NationalID": "991234567V",
    },
    {
        "FullName": "Nimal Silva",
        "Email": "nimal@company.com",
        "RoleName": "Developer",
        "Salary": "250000",
        "PhoneNumber": "0779876543",
        "AddressLine": "Kandy",
        "NationalID": "981112223V",
    },
    {
        "FullName": "Ama Fernando",
        "Email": "ama@company.com",
        "RoleName": "HR Officer",
        "Salary": "300000",
        "PhoneNumber": "0711111111",
        "AddressLine": "Galle",
        "NationalID": "975556667V",
    },
    {
        "FullName": "Sahan Jayawardena",
        "Email": "sahan@company.com",
        "RoleName": "Cyber Security Analyst",
        "Salary": "500000",
        "PhoneNumber": "0722222222",
        "AddressLine": "Negombo",
        "NationalID": "962223334V",
    },
]


FALLBACK_SECRETS = [
    {
        "SecretName": "Admin Password",
        "SecretValue": "admin@12345",
        "RiskLevel": "HIGH",
    },
    {
        "SecretName": "API Key",
        "SecretValue": "sk-test-company-secret-key-999",
        "RiskLevel": "HIGH",
    },
    {
        "SecretName": "Database Password",
        "SecretValue": "db_pass_2026_secret",
        "RiskLevel": "HIGH",
    },
    {
        "SecretName": "AWS Root Key",
        "SecretValue": "aws-root-secret-2026",
        "RiskLevel": "CRITICAL",
    },
    {
        "SecretName": "Internal VPN Password",
        "SecretValue": "vpn-company-pass",
        "RiskLevel": "HIGH",
    },
]


FALLBACK_CONTRACTS = [
    {
        "ClientName": "ABC Holdings",
        "ProjectName": "AI Security Integration",
        "PaymentAmount": "$250000",
        "ContractDetails": (
            "Enterprise AI integration with WRDN Prompt Shield"
        ),
        "ConfidentialNotes": (
            "Client requested private deployment"
        ),
    },
    {
        "ClientName": "Global Finance Ltd",
        "ProjectName": "Internal AI Assistant",
        "PaymentAmount": "$500000",
        "ContractDetails": (
            "Secure AI deployment with database monitoring"
        ),
        "ConfidentialNotes": (
            "Contains confidential banking workflows"
        ),
    },
]


FALLBACK_TOKENS = [
    {
        "TokenName": "JWT Token",
        "TokenValue": "jwt-prod-token-123456",
        "ExpireDate": "2027-01-01",
    },
    {
        "TokenName": "Azure Access Token",
        "TokenValue": "azure-access-secret-999",
        "ExpireDate": "2027-06-01",
    },
    {
        "TokenName": "OpenAI Internal Token",
        "TokenValue": "openai-company-token-777",
        "ExpireDate": "2026-12-31",
    },
]


FALLBACK_USER_ROLES = [
    {
        "Username": "admin_user",
        "UserRole": "Administrator",
        "AccessLevel": "HIGH",
    },
    {
        "Username": "security_analyst",
        "UserRole": "SOC Analyst",
        "AccessLevel": "MEDIUM",
    },
    {
        "Username": "employee_user",
        "UserRole": "Employee",
        "AccessLevel": "LOW",
    },
]


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection() -> sqlite3.Connection:
    """
    Create and return a SQLite database connection.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=15,
    )

    connection.row_factory = sqlite3.Row

    return connection


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def initialize_database() -> None:
    """
    Create all required tables and insert
    demonstration records when the tables are empty.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS Employees (
                EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
                FullName TEXT NOT NULL,
                Email TEXT NOT NULL,
                RoleName TEXT NOT NULL,
                Salary TEXT,
                PhoneNumber TEXT,
                AddressLine TEXT,
                NationalID TEXT
            );

            CREATE TABLE IF NOT EXISTS CompanySecrets (
                SecretID INTEGER PRIMARY KEY AUTOINCREMENT,
                SecretName TEXT NOT NULL,
                SecretValue TEXT NOT NULL,
                RiskLevel TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ClientContracts (
                ContractID INTEGER PRIMARY KEY AUTOINCREMENT,
                ClientName TEXT NOT NULL,
                ProjectName TEXT NOT NULL,
                PaymentAmount TEXT,
                ContractDetails TEXT,
                ConfidentialNotes TEXT
            );

            CREATE TABLE IF NOT EXISTS SystemTokens (
                TokenID INTEGER PRIMARY KEY AUTOINCREMENT,
                TokenName TEXT NOT NULL,
                TokenValue TEXT NOT NULL,
                ExpireDate TEXT
            );

            CREATE TABLE IF NOT EXISTS AuditLogs (
                LogID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserPrompt TEXT,
                RawAIOutput TEXT,
                ShieldStatus TEXT,
                RiskScore INTEGER,
                DetectionReason TEXT,
                CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS UserRoles (
                RoleID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT NOT NULL,
                UserRole TEXT NOT NULL,
                AccessLevel TEXT NOT NULL
            );
            """
        )

        _seed_employees(cursor)
        _seed_secrets(cursor)
        _seed_contracts(cursor)
        _seed_tokens(cursor)
        _seed_user_roles(cursor)

        connection.commit()

        logger.info(
            "SQLite database initialized successfully: %s",
            DATABASE_PATH,
        )

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to initialize SQLite database."
        )
        raise

    finally:
        connection.close()


# ==========================================
# SEED FUNCTIONS
# ==========================================

def _table_is_empty(
    cursor: sqlite3.Cursor,
    table_name: str,
) -> bool:
    cursor.execute(
        f"SELECT COUNT(*) AS record_count FROM {table_name}"
    )

    row = cursor.fetchone()

    return row["record_count"] == 0


def _seed_employees(
    cursor: sqlite3.Cursor,
) -> None:
    if not _table_is_empty(
        cursor,
        "Employees",
    ):
        return

    cursor.executemany(
        """
        INSERT INTO Employees (
            FullName,
            Email,
            RoleName,
            Salary,
            PhoneNumber,
            AddressLine,
            NationalID
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                employee["FullName"],
                employee["Email"],
                employee["RoleName"],
                employee["Salary"],
                employee["PhoneNumber"],
                employee["AddressLine"],
                employee["NationalID"],
            )
            for employee in FALLBACK_EMPLOYEES
        ],
    )


def _seed_secrets(
    cursor: sqlite3.Cursor,
) -> None:
    if not _table_is_empty(
        cursor,
        "CompanySecrets",
    ):
        return

    cursor.executemany(
        """
        INSERT INTO CompanySecrets (
            SecretName,
            SecretValue,
            RiskLevel
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                secret["SecretName"],
                secret["SecretValue"],
                secret["RiskLevel"],
            )
            for secret in FALLBACK_SECRETS
        ],
    )


def _seed_contracts(
    cursor: sqlite3.Cursor,
) -> None:
    if not _table_is_empty(
        cursor,
        "ClientContracts",
    ):
        return

    cursor.executemany(
        """
        INSERT INTO ClientContracts (
            ClientName,
            ProjectName,
            PaymentAmount,
            ContractDetails,
            ConfidentialNotes
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                contract["ClientName"],
                contract["ProjectName"],
                contract["PaymentAmount"],
                contract["ContractDetails"],
                contract["ConfidentialNotes"],
            )
            for contract in FALLBACK_CONTRACTS
        ],
    )


def _seed_tokens(
    cursor: sqlite3.Cursor,
) -> None:
    if not _table_is_empty(
        cursor,
        "SystemTokens",
    ):
        return

    cursor.executemany(
        """
        INSERT INTO SystemTokens (
            TokenName,
            TokenValue,
            ExpireDate
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                token["TokenName"],
                token["TokenValue"],
                token["ExpireDate"],
            )
            for token in FALLBACK_TOKENS
        ],
    )


def _seed_user_roles(
    cursor: sqlite3.Cursor,
) -> None:
    if not _table_is_empty(
        cursor,
        "UserRoles",
    ):
        return

    cursor.executemany(
        """
        INSERT INTO UserRoles (
            Username,
            UserRole,
            AccessLevel
        )
        VALUES (?, ?, ?)
        """,
        [
            (
                role["Username"],
                role["UserRole"],
                role["AccessLevel"],
            )
            for role in FALLBACK_USER_ROLES
        ],
    )


# ==========================================
# AI DATABASE CONTEXT
# ==========================================

def get_database_context() -> str:
    """
    Read company data and return it as AI context.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()
        context_parts: list[str] = []

        cursor.execute(
            """
            SELECT
                FullName,
                Email,
                RoleName,
                Salary
            FROM Employees
            """
        )

        employee_lines = [
            "EMPLOYEE DATA:"
        ]

        for employee in cursor.fetchall():
            employee_lines.append(
                f"Name: {employee['FullName']}, "
                f"Email: {employee['Email']}, "
                f"Role: {employee['RoleName']}, "
                f"Salary: {employee['Salary']}"
            )

        context_parts.append(
            "\n".join(employee_lines)
        )

        cursor.execute(
            """
            SELECT
                SecretName,
                SecretValue,
                RiskLevel
            FROM CompanySecrets
            """
        )

        secret_lines = [
            "COMPANY SECRET DATA:"
        ]

        for secret in cursor.fetchall():
            secret_lines.append(
                f"Secret Name: {secret['SecretName']}, "
                f"Secret Value: {secret['SecretValue']}, "
                f"Risk Level: {secret['RiskLevel']}"
            )

        context_parts.append(
            "\n".join(secret_lines)
        )

        cursor.execute(
            """
            SELECT
                ClientName,
                ProjectName,
                PaymentAmount,
                ConfidentialNotes
            FROM ClientContracts
            """
        )

        contract_lines = [
            "CLIENT CONTRACT DATA:"
        ]

        for contract in cursor.fetchall():
            contract_lines.append(
                f"Client: {contract['ClientName']}, "
                f"Project: {contract['ProjectName']}, "
                f"Payment: {contract['PaymentAmount']}, "
                f"Notes: {contract['ConfidentialNotes']}"
            )

        context_parts.append(
            "\n".join(contract_lines)
        )

        cursor.execute(
            """
            SELECT
                TokenName,
                TokenValue,
                ExpireDate
            FROM SystemTokens
            """
        )

        token_lines = [
            "SYSTEM TOKEN DATA:"
        ]

        for token in cursor.fetchall():
            token_lines.append(
                f"Token Name: {token['TokenName']}, "
                f"Token Value: {token['TokenValue']}, "
                f"Expire Date: {token['ExpireDate']}"
            )

        context_parts.append(
            "\n".join(token_lines)
        )

        return "\n\n".join(
            context_parts
        )

    except Exception as error:
        logger.exception(
            "Failed to load SQLite database context: %s",
            error,
        )
        raise

    finally:
        connection.close()


# ==========================================
# AUDIT LOG
# ==========================================

def save_audit_log(
    user_prompt: str,
    raw_output: str,
    shield_status: str,
    risk_score: int,
    detection_reason: str,
) -> None:
    """
    Save WRDN security results into AuditLogs.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO AuditLogs (
                UserPrompt,
                RawAIOutput,
                ShieldStatus,
                RiskScore,
                DetectionReason
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_prompt,
                raw_output,
                shield_status,
                risk_score,
                detection_reason,
            ),
        )

        connection.commit()

    except Exception as error:
        connection.rollback()

        logger.exception(
            "Failed to save audit log: %s",
            error,
        )

        raise

    finally:
        connection.close()


# ==========================================
# READ AUDIT LOGS
# ==========================================

def get_audit_logs(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return the newest audit log records.
    """

    safe_limit = max(
        1,
        min(limit, 500),
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                LogID,
                UserPrompt,
                RawAIOutput,
                ShieldStatus,
                RiskScore,
                DetectionReason,
                CreatedAt
            FROM AuditLogs
            ORDER BY LogID DESC
            LIMIT ?
            """,
            (safe_limit,),
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    finally:
        connection.close()


# ==========================================
# DATABASE STATUS
# ==========================================

def test_database_connection() -> dict[str, Any]:
    """
    Return basic SQLite database information.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS employee_count
            FROM Employees
            """
        )

        employee_count = cursor.fetchone()[
            "employee_count"
        ]

        cursor.execute(
            """
            SELECT COUNT(*) AS audit_count
            FROM AuditLogs
            """
        )

        audit_count = cursor.fetchone()[
            "audit_count"
        ]

        return {
            "status": "connected",
            "database_type": "SQLite",
            "database_path": str(
                DATABASE_PATH
            ),
            "employee_count": employee_count,
            "audit_count": audit_count,
        }

    finally:
        connection.close()


# Create the database automatically when this module loads.
initialize_database()