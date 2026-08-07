import json
import logging
import sqlite3
from datetime import datetime, timezone
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
    {
        "FullName": "Dilani Wickramasinghe",
        "Email": "dilani@company.com",
        "RoleName": "Finance Manager",
        "Salary": "480000",
        "PhoneNumber": "0765554433",
        "AddressLine": "Matara",
        "NationalID": "905551234V",
    },
    {
        "FullName": "Ruwan Bandara",
        "Email": "ruwan@company.com",
        "RoleName": "Sales Executive",
        "Salary": "220000",
        "PhoneNumber": "0756677889",
        "AddressLine": "Kurunegala",
        "NationalID": "943334455V",
    },
    {
        "FullName": "Ishara Gunasekara",
        "Email": "ishara@company.com",
        "RoleName": "QA Engineer",
        "Salary": "275000",
        "PhoneNumber": "0709988776",
        "AddressLine": "Ja-Ela",
        "NationalID": "967778899V",
    },
    {
        "FullName": "Tharindu Mendis",
        "Email": "tharindu@company.com",
        "RoleName": "DevOps Engineer",
        "Salary": "420000",
        "PhoneNumber": "0712233445",
        "AddressLine": "Battaramulla",
        "NationalID": "928889900V",
    },
    {
        "FullName": "Malsha Peris",
        "Email": "malsha@company.com",
        "RoleName": "Customer Support Lead",
        "Salary": "260000",
        "PhoneNumber": "0773344556",
        "AddressLine": "Panadura",
        "NationalID": "955556677V",
    },
    {
        "FullName": "Chamath Fernando",
        "Email": "chamath@company.com",
        "RoleName": "Legal Advisor",
        "Salary": "390000",
        "PhoneNumber": "0724455667",
        "AddressLine": "Nugegoda",
        "NationalID": "891112233V",
    },
]


FALLBACK_SECRETS = [
    {
        "SecretName": "Admin Password",
        "SecretValue": "admin@12345",
        "RiskLevel": "HIGH",
    },
    {
        "SecretName": "Kasun Account Password",
        "SecretValue": "kasun@Work2026",
        "RiskLevel": "HIGH",
    },
    {
        "SecretName": "Dilani Account Password",
        "SecretValue": "dilani@Finance2026",
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
    {
        "SecretName": "Payroll System Password",
        "SecretValue": "payroll#Secure2026",
        "RiskLevel": "CRITICAL",
    },
    {
        "SecretName": "Email SMTP Secret",
        "SecretValue": "smtp-mail-secret-5544",
        "RiskLevel": "MEDIUM",
    },
    {
        "SecretName": "Backup Encryption Key",
        "SecretValue": "backup-enc-key-zx91",
        "RiskLevel": "CRITICAL",
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
    {
        "ClientName": "Lanka Health Group",
        "ProjectName": "Secure Triage Chatbot",
        "PaymentAmount": "$180000",
        "ContractDetails": (
            "Staff FAQ chatbot with output sanitization"
        ),
        "ConfidentialNotes": (
            "Must not expose patient identifiers"
        ),
    },
    {
        "ClientName": "Ceylon Retail PLC",
        "ProjectName": "Store Support Bot",
        "PaymentAmount": "$95000",
        "ContractDetails": (
            "Customer support assistant for store operations"
        ),
        "ConfidentialNotes": (
            "Discount approval matrix is confidential"
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
    {
        "TokenName": "GitHub Deploy Token",
        "TokenValue": "ghp_deploy_token_wrdn_2026",
        "ExpireDate": "2027-03-15",
    },
    {
        "TokenName": "Monitoring API Token",
        "TokenValue": "monitor-token-abc-7788",
        "ExpireDate": "2027-09-01",
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
    {
        "Username": "hr_officer",
        "UserRole": "HR Officer",
        "AccessLevel": "MEDIUM",
    },
    {
        "Username": "finance_viewer",
        "UserRole": "Finance Viewer",
        "AccessLevel": "MEDIUM",
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
    ClientID TEXT,
    PolicyID INTEGER,
    PolicyVersion INTEGER,
    RequirementFileID INTEGER,
    DetectionLayer TEXT,
    MatchedRule TEXT,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

            CREATE TABLE IF NOT EXISTS UserRoles (
                RoleID INTEGER PRIMARY KEY AUTOINCREMENT,
                Username TEXT NOT NULL,
                UserRole TEXT NOT NULL,
                AccessLevel TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS RequirementRequests (
    RequestID INTEGER PRIMARY KEY AUTOINCREMENT,
    RequestCode TEXT UNIQUE NOT NULL,
    UploadedBy TEXT NOT NULL,
    ApprovalEmail TEXT NOT NULL,
    OriginalFileName TEXT NOT NULL,
    StoredFileName TEXT NOT NULL,
    FilePath TEXT NOT NULL,
    FileHash TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'PENDING',
    ApproveTokenHash TEXT NOT NULL,
    RejectTokenHash TEXT NOT NULL,
    ExpiresAt TEXT NOT NULL,
    CreatedAt TEXT NOT NULL,
    ApprovedAt TEXT,
    RejectedAt TEXT,
    ProcessedAt TEXT,
    FailureReason TEXT
);

CREATE TABLE IF NOT EXISTS RequirementRules (
    RuleID INTEGER PRIMARY KEY AUTOINCREMENT,
    RequestID INTEGER NOT NULL,
    Resource TEXT NOT NULL,
    AllowedRoles TEXT NOT NULL,
    RestrictedRoles TEXT NOT NULL,
    Action TEXT NOT NULL,
    Note TEXT,
    IsActive INTEGER NOT NULL DEFAULT 1,
    CreatedAt TEXT NOT NULL,
    FOREIGN KEY (RequestID)
        REFERENCES RequirementRequests(RequestID)
);

CREATE TABLE IF NOT EXISTS SecurityAlerts (
    AlertID INTEGER PRIMARY KEY AUTOINCREMENT,
    RequestID INTEGER,
    AlertType TEXT NOT NULL,
    Severity TEXT NOT NULL,
    Message TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'OPEN',
    CreatedAt TEXT NOT NULL,
    FOREIGN KEY (RequestID)
        REFERENCES RequirementRequests(RequestID)
);

CREATE TABLE IF NOT EXISTS Clients (
    ClientID TEXT PRIMARY KEY,
    ClientName TEXT NOT NULL,
    CreatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ClientRequirementFiles (
    RequirementFileID INTEGER PRIMARY KEY AUTOINCREMENT,
    ClientID TEXT NOT NULL,
    OriginalFilename TEXT NOT NULL,
    StoredFilename TEXT NOT NULL,
    FileType TEXT NOT NULL,
    FileHash TEXT NOT NULL,
    ExtractedText TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'LOADED',
    UploadedAt TEXT NOT NULL,
    FOREIGN KEY (ClientID)
        REFERENCES Clients(ClientID)
);

CREATE TABLE IF NOT EXISTS ClientPolicies (
    PolicyID INTEGER PRIMARY KEY AUTOINCREMENT,
    ClientID TEXT NOT NULL,
    RequirementFileID INTEGER,
    PolicyName TEXT NOT NULL,
    Version INTEGER NOT NULL,
    PolicyJSON TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'DRAFT',
    ValidationErrors TEXT,
    CreatedAt TEXT NOT NULL,
    ActivatedAt TEXT,
    FOREIGN KEY (ClientID)
        REFERENCES Clients(ClientID),
    FOREIGN KEY (RequirementFileID)
        REFERENCES ClientRequirementFiles(RequirementFileID),
    UNIQUE (ClientID, Version)
);

CREATE INDEX IF NOT EXISTS idx_client_policies_status
ON ClientPolicies(ClientID, Status);

CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT UNIQUE NOT NULL,
    PasswordHash TEXT NOT NULL,
    Role TEXT NOT NULL,
    ClientID TEXT NOT NULL,
    CreatedAt TEXT NOT NULL,
    FOREIGN KEY (ClientID)
        REFERENCES Clients(ClientID)
);

CREATE INDEX IF NOT EXISTS idx_users_username
ON Users(Username);

CREATE INDEX IF NOT EXISTS idx_users_client_role
ON Users(ClientID, Role);
            """
        )
        
        for column_name, column_type in {
            "ClientID": "TEXT",
            "PolicyID": "INTEGER",
            "PolicyVersion": "INTEGER",
            "RequirementFileID": "INTEGER",
            "DetectionLayer": "TEXT",
            "MatchedRule": "TEXT",
        }.items():
            _ensure_column(
                cursor,
                "AuditLogs",
                column_name,
                column_type,
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

def _ensure_column(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:

    existing_columns = {
        row["name"]
        for row in cursor.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }

    if column_name not in existing_columns:
        cursor.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {column_type}
            """
        )


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
    for employee in FALLBACK_EMPLOYEES:
        existing = cursor.execute(
            """
            SELECT Email
            FROM Employees
            WHERE Email = ?
            """,
            (employee["Email"],),
        ).fetchone()

        if existing is not None:
            continue

        cursor.execute(
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
            (
                employee["FullName"],
                employee["Email"],
                employee["RoleName"],
                employee["Salary"],
                employee["PhoneNumber"],
                employee["AddressLine"],
                employee["NationalID"],
            ),
        )


def _seed_secrets(
    cursor: sqlite3.Cursor,
) -> None:
    for secret in FALLBACK_SECRETS:
        existing = cursor.execute(
            """
            SELECT SecretName
            FROM CompanySecrets
            WHERE SecretName = ?
            """,
            (secret["SecretName"],),
        ).fetchone()

        if existing is not None:
            continue

        cursor.execute(
            """
            INSERT INTO CompanySecrets (
                SecretName,
                SecretValue,
                RiskLevel
            )
            VALUES (?, ?, ?)
            """,
            (
                secret["SecretName"],
                secret["SecretValue"],
                secret["RiskLevel"],
            ),
        )


def _seed_contracts(
    cursor: sqlite3.Cursor,
) -> None:
    for contract in FALLBACK_CONTRACTS:
        existing = cursor.execute(
            """
            SELECT ClientName
            FROM ClientContracts
            WHERE ClientName = ?
              AND ProjectName = ?
            """,
            (
                contract["ClientName"],
                contract["ProjectName"],
            ),
        ).fetchone()

        if existing is not None:
            continue

        cursor.execute(
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
            (
                contract["ClientName"],
                contract["ProjectName"],
                contract["PaymentAmount"],
                contract["ContractDetails"],
                contract["ConfidentialNotes"],
            ),
        )


def _seed_tokens(
    cursor: sqlite3.Cursor,
) -> None:
    for token in FALLBACK_TOKENS:
        existing = cursor.execute(
            """
            SELECT TokenName
            FROM SystemTokens
            WHERE TokenName = ?
            """,
            (token["TokenName"],),
        ).fetchone()

        if existing is not None:
            continue

        cursor.execute(
            """
            INSERT INTO SystemTokens (
                TokenName,
                TokenValue,
                ExpireDate
            )
            VALUES (?, ?, ?)
            """,
            (
                token["TokenName"],
                token["TokenValue"],
                token["ExpireDate"],
            ),
        )


def _seed_user_roles(
    cursor: sqlite3.Cursor,
) -> None:
    for role in FALLBACK_USER_ROLES:
        existing = cursor.execute(
            """
            SELECT Username
            FROM UserRoles
            WHERE Username = ?
            """,
            (role["Username"],),
        ).fetchone()

        if existing is not None:
            continue

        cursor.execute(
            """
            INSERT INTO UserRoles (
                Username,
                UserRole,
                AccessLevel
            )
            VALUES (?, ?, ?)
            """,
            (
                role["Username"],
                role["UserRole"],
                role["AccessLevel"],
            ),
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
                Salary,
                PhoneNumber,
                AddressLine,
                NationalID
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
                f"Salary: {employee['Salary']}, "
                f"Phone: {employee['PhoneNumber']}, "
                f"Address: {employee['AddressLine']}, "
                f"NationalID: {employee['NationalID']}"
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


def find_secret_answer_for_prompt(
    user_prompt: str,
) -> str | None:
    """
    Match a password/secret/token question to a
    CompanySecrets or SystemTokens row.
    """

    matched = match_secret_name_for_prompt(
        user_prompt
    )

    if matched is None:
        return None

    connection = get_connection()

    try:
        cursor = connection.cursor()
        row = cursor.execute(
            """
            SELECT SecretName, SecretValue
            FROM CompanySecrets
            WHERE SecretName = ?
            """,
            (matched,),
        ).fetchone()

        if row is not None:
            return (
                f"{row['SecretName']}: "
                f"{row['SecretValue']}"
            )

        token_row = cursor.execute(
            """
            SELECT TokenName, TokenValue
            FROM SystemTokens
            WHERE TokenName = ?
            """,
            (matched,),
        ).fetchone()

        if token_row is not None:
            return (
                f"{token_row['TokenName']}: "
                f"{token_row['TokenValue']}"
            )

        return None
    finally:
        connection.close()


def get_employee_salary_by_name(
    full_name: str,
) -> str | None:
    connection = get_connection()

    try:
        cursor = connection.cursor()
        row = cursor.execute(
            """
            SELECT FullName, Salary, RoleName
            FROM Employees
            WHERE lower(FullName) = lower(?)
            """,
            (full_name.strip(),),
        ).fetchone()

        if row is None:
            return None

        return (
            f"{row['FullName']} "
            f"({row['RoleName']}) salary: "
            f"{row['Salary']}"
        )
    finally:
        connection.close()


def match_secret_name_for_prompt(
    user_prompt: str,
) -> str | None:
    """
    Return the CompanySecrets.SecretName that
    best matches the user question.
    """

    text = (user_prompt or "").lower()

    if not text:
        return None

    secret_aliases: list[tuple[str, tuple[str, ...]]] = [
        (
            "Admin Password",
            (
                "admin password",
                "admin pass",
                "the admin password",
            ),
        ),
        (
            "Kasun Account Password",
            (
                "kasun password",
                "kasun's password",
                "kasuns password",
                "kasun account password",
                "kasun perera password",
            ),
        ),
        (
            "Dilani Account Password",
            (
                "dilani password",
                "dilani's password",
                "dilanis password",
                "dilani account password",
                "dilani wickramasinghe password",
            ),
        ),
        (
            "API Key",
            (
                "api key",
                "the api key",
            ),
        ),
        (
            "Database Password",
            (
                "database password",
                "db password",
            ),
        ),
        (
            "AWS Root Key",
            (
                "aws root key",
                "aws root",
            ),
        ),
        (
            "JWT Token",
            (
                "jwt token",
                "jwt token value",
            ),
        ),
        (
            "GitHub Deploy Token",
            (
                "github deploy token",
                "github token",
            ),
        ),
    ]

    for secret_name, aliases in secret_aliases:
        if any(alias in text for alias in aliases):
            return secret_name

    return None


# ==========================================
# AUDIT LOG
# ==========================================

def save_audit_log(
    user_prompt: str,
    raw_output: str,
    shield_status: str,
    risk_score: int,
    detection_reason: str,
    client_id: str = "default",
    policy_id: int | None = None,
    policy_version: int | None = None,
    requirement_file_id: int | None = None,
    detection_layer: str | None = None,
    matched_rule: str | None = None,
) -> None:
    """
    Save a WRDN security decision and its applied policy.
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
                DetectionReason,
                ClientID,
                PolicyID,
                PolicyVersion,
                RequirementFileID,
                DetectionLayer,
                MatchedRule
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_prompt,
                raw_output,
                shield_status,
                risk_score,
                detection_reason,
                client_id,
                policy_id,
                policy_version,
                requirement_file_id,
                detection_layer,
                matched_rule,
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
                ClientID,
                PolicyID,
                PolicyVersion,
                RequirementFileID,
                DetectionLayer,
                MatchedRule,
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
        
# ==========================================
# DATE AND TIME
# ==========================================

def get_current_utc_time() -> str:
    """
    Return the current UTC time as an ISO string.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()
    
    # ==========================================
# CREATE REQUIREMENT REQUEST
# ==========================================

def create_requirement_request(
    request_code: str,
    uploaded_by: str,
    approval_email: str,
    original_filename: str,
    stored_filename: str,
    file_path: str,
    file_hash: str,
    approve_token_hash: str,
    reject_token_hash: str,
    expires_at: str,
) -> int:
    """
    Save a newly uploaded requirement file
    as a pending approval request.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO RequirementRequests (
                RequestCode,
                UploadedBy,
                ApprovalEmail,
                OriginalFileName,
                StoredFileName,
                FilePath,
                FileHash,
                Status,
                ApproveTokenHash,
                RejectTokenHash,
                ExpiresAt,
                CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_code,
                uploaded_by,
                approval_email,
                original_filename,
                stored_filename,
                file_path,
                file_hash,
                "PENDING",
                approve_token_hash,
                reject_token_hash,
                expires_at,
                get_current_utc_time(),
            ),
        )

        request_id = cursor.lastrowid

        connection.commit()

        if request_id is None:
            raise RuntimeError(
                "Requirement request ID was not created."
            )

        return int(request_id)

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to create requirement request."
        )
        raise

    finally:
        connection.close()
        
        # ==========================================
# FIND REQUEST BY TOKEN
# ==========================================

def get_requirement_request_by_token(
    token_hash: str,
    token_type: str,
) -> dict[str, Any] | None:
    """
    Find a pending requirement request using
    an approval or rejection token hash.
    """

    normalized_type = token_type.strip().lower()

    if normalized_type == "approve":
        token_column = "ApproveTokenHash"
    elif normalized_type == "reject":
        token_column = "RejectTokenHash"
    else:
        raise ValueError(
            "Token type must be approve or reject."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        query = f"""
            SELECT *
            FROM RequirementRequests
            WHERE {token_column} = ?
            LIMIT 1
        """

        cursor.execute(
            query,
            (token_hash,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        connection.close()
        
        # ==========================================
# UPDATE REQUIREMENT STATUS
# ==========================================

def update_requirement_request_status(
    request_id: int,
    status: str,
    file_path: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """
    Update the status and related timestamps
    of a requirement request.
    """

    normalized_status = status.strip().upper()
    current_time = get_current_utc_time()

    allowed_statuses = {
        "PENDING",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
        "PROCESSING",
        "ACTIVE",
        "FAILED",
    }

    if normalized_status not in allowed_statuses:
        raise ValueError(
            f"Unsupported requirement status: {status}"
        )

    approved_at = (
        current_time
        if normalized_status == "APPROVED"
        else None
    )

    rejected_at = (
        current_time
        if normalized_status == "REJECTED"
        else None
    )

    processed_at = (
        current_time
        if normalized_status
        in {"ACTIVE", "FAILED"}
        else None
    )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE RequirementRequests
            SET
                Status = ?,
                FilePath = COALESCE(?, FilePath),
                ApprovedAt = COALESCE(?, ApprovedAt),
                RejectedAt = COALESCE(?, RejectedAt),
                ProcessedAt = COALESCE(?, ProcessedAt),
                FailureReason = ?
            WHERE RequestID = ?
            """,
            (
                normalized_status,
                file_path,
                approved_at,
                rejected_at,
                processed_at,
                failure_reason,
                request_id,
            ),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to update requirement request."
        )
        raise

    finally:
        connection.close()
        
        # ==========================================
# SAVE REQUIREMENT RULES
# ==========================================

def save_requirement_rules(
    request_id: int,
    requirements: list[dict[str, Any]],
) -> int:
    """
    Save validated rules from an approved
    requirement file.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE RequirementRules
            SET IsActive = 0
            WHERE IsActive = 1
            """
        )

        created_at = get_current_utc_time()
        inserted_count = 0

        for requirement in requirements:
            allowed_roles = json.dumps(
                requirement.get(
                    "allowed_roles",
                    [],
                )
            )

            restricted_roles = json.dumps(
                requirement.get(
                    "restricted_roles",
                    [],
                )
            )

            cursor.execute(
                """
                INSERT INTO RequirementRules (
                    RequestID,
                    Resource,
                    AllowedRoles,
                    RestrictedRoles,
                    Action,
                    Note,
                    IsActive,
                    CreatedAt
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    requirement["resource"],
                    allowed_roles,
                    restricted_roles,
                    requirement["action"],
                    requirement.get(
                        "note",
                        "",
                    ),
                    1,
                    created_at,
                ),
            )

            inserted_count += 1

        connection.commit()

        return inserted_count

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to save requirement rules."
        )
        raise

    finally:
        connection.close()
        
        # ==========================================
# GET ACTIVE REQUIREMENT RULES
# ==========================================

def get_active_requirement_rules(
) -> list[dict[str, Any]]:
    """
    Return all currently active requirement rules.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                RuleID,
                RequestID,
                Resource,
                AllowedRoles,
                RestrictedRoles,
                Action,
                Note,
                IsActive,
                CreatedAt
            FROM RequirementRules
            WHERE IsActive = 1
            ORDER BY RuleID ASC
            """
        )

        rules: list[dict[str, Any]] = []

        for row in cursor.fetchall():
            rule = dict(row)

            try:
                rule["AllowedRoles"] = json.loads(
                    rule["AllowedRoles"]
                )
            except (TypeError, json.JSONDecodeError):
                rule["AllowedRoles"] = []

            try:
                rule["RestrictedRoles"] = json.loads(
                    rule["RestrictedRoles"]
                )
            except (TypeError, json.JSONDecodeError):
                rule["RestrictedRoles"] = []

            rules.append(rule)

        return rules

    finally:
        connection.close()
        
        # ==========================================
# LIST REQUIREMENT REQUESTS
# ==========================================

def get_requirement_requests(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return the newest requirement requests.
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
                RequestID,
                RequestCode,
                UploadedBy,
                ApprovalEmail,
                OriginalFileName,
                Status,
                ExpiresAt,
                CreatedAt,
                ApprovedAt,
                RejectedAt,
                ProcessedAt,
                FailureReason
            FROM RequirementRequests
            ORDER BY RequestID DESC
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
# CREATE SECURITY ALERT
# ==========================================

def create_security_alert(
    request_id: int | None,
    alert_type: str,
    severity: str,
    message: str,
) -> int:
    """
    Create a new security alert.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO SecurityAlerts (
                RequestID,
                AlertType,
                Severity,
                Message,
                Status,
                CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                alert_type.strip().upper(),
                severity.strip().upper(),
                message.strip(),
                "OPEN",
                get_current_utc_time(),
            ),
        )

        alert_id = cursor.lastrowid

        connection.commit()

        if alert_id is None:
            raise RuntimeError(
                "Security alert ID was not created."
            )

        return int(alert_id)

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to create security alert."
        )
        raise

    finally:
        connection.close()
        
        # ==========================================
# READ SECURITY ALERTS
# ==========================================

def get_security_alerts(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return the latest security alerts.
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
                AlertID,
                RequestID,
                AlertType,
                Severity,
                Message,
                Status,
                CreatedAt
            FROM SecurityAlerts
            ORDER BY AlertID DESC
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
# USERS
# ==========================================

def create_user(
    username: str,
    password_hash: str,
    role: str,
    client_id: str,
) -> int:
    """
    Create a user linked to one client.
    Role must be ADMIN or EMPLOYEE.
    """

    normalized_role = role.strip().upper()

    if normalized_role not in {"ADMIN", "EMPLOYEE"}:
        raise ValueError(
            "Role must be ADMIN or EMPLOYEE."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO Users (
                Username,
                PasswordHash,
                Role,
                ClientID,
                CreatedAt
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username.strip(),
                password_hash,
                normalized_role,
                client_id.strip(),
                get_current_utc_time(),
            ),
        )

        connection.commit()

        if cursor.lastrowid is None:
            raise RuntimeError(
                "User ID was not created."
            )

        return int(cursor.lastrowid)

    except Exception:
        connection.rollback()
        logger.exception(
            "Failed to create user."
        )
        raise

    finally:
        connection.close()


def get_user_by_username(
    username: str,
) -> dict[str, Any] | None:
    """
    Find one user by username.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                UserID,
                Username,
                PasswordHash,
                Role,
                ClientID,
                CreatedAt
            FROM Users
            WHERE Username = ?
            LIMIT 1
            """,
            (username.strip(),),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        connection.close()


# Create the database automatically when this module loads.
initialize_database()

