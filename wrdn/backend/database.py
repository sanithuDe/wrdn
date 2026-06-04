import pyodbc

def get_connection():
    conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=METHNUKA_SILVA\\SQLEXPRESS;"
    "DATABASE=WRDN_Test_DB;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
    return conn


def get_database_context():
    conn = get_connection()
    cursor = conn.cursor()

    context = ""

    cursor.execute("SELECT FullName, Email, RoleName, Salary FROM Employees")
    employees = cursor.fetchall()

    context += "EMPLOYEE DATA:\n"
    for emp in employees:
        context += f"Name: {emp.FullName}, Email: {emp.Email}, Role: {emp.RoleName}, Salary: {emp.Salary}\n"

    cursor.execute("SELECT SecretName, SecretValue, RiskLevel FROM CompanySecrets")
    secrets = cursor.fetchall()

    context += "\nCOMPANY SECRET DATA:\n"
    for sec in secrets:
        context += f"Secret Name: {sec.SecretName}, Secret Value: {sec.SecretValue}, Risk Level: {sec.RiskLevel}\n"

    cursor.execute("SELECT ClientName, ProjectName, PaymentAmount, ConfidentialNotes FROM ClientContracts")
    contracts = cursor.fetchall()

    context += "\nCLIENT CONTRACT DATA:\n"
    for con in contracts:
        context += f"Client: {con.ClientName}, Project: {con.ProjectName}, Payment: {con.PaymentAmount}, Notes: {con.ConfidentialNotes}\n"

    cursor.execute("SELECT TokenName, TokenValue, ExpireDate FROM SystemTokens")
    tokens = cursor.fetchall()

    context += "\nSYSTEM TOKEN DATA:\n"
    for tok in tokens:
        context += f"Token Name: {tok.TokenName}, Token Value: {tok.TokenValue}, Expire Date: {tok.ExpireDate}\n"

    conn.close()
    return context


def save_audit_log(user_prompt, raw_output, shield_status, risk_score, detection_reason):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO AuditLogs
        (UserPrompt, RawAIOutput, ShieldStatus, RiskScore, DetectionReason)
        VALUES (?, ?, ?, ?, ?)
    """, user_prompt, raw_output, shield_status, risk_score, detection_reason)

    conn.commit()
    conn.close()