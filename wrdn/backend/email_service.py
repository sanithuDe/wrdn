import smtplib
from email.message import EmailMessage

from wrdn.config import (
    MAIL_APP_PASSWORD,
    MAIL_FROM_NAME,
    MAIL_USERNAME,
    SMTP_HOST,
    SMTP_PORT,
)


def validate_email_configuration() -> None:
    """
    Check whether the Gmail sender settings exist.
    """

    if not MAIL_USERNAME:
        raise RuntimeError(
            "MAIL_USERNAME is missing in the .env file."
        )

    if not MAIL_APP_PASSWORD:
        raise RuntimeError(
            "MAIL_APP_PASSWORD is missing in the .env file."
        )


def send_requirement_approval_email(
    receiver_email: str,
    receiver_name: str,
    request_code: str,
    original_filename: str,
    approve_url: str,
    reject_url: str,
    expires_in_minutes: int,
) -> None:
    """
    Send an approval email containing Approve and Reject links.
    """

    validate_email_configuration()

    message = EmailMessage()

    message["Subject"] = (
        f"WRDN Requirement Approval - {request_code}"
    )

    message["From"] = (
        f"{MAIL_FROM_NAME} <{MAIL_USERNAME}>"
    )

    message["To"] = receiver_email

    text_content = f"""
Hello {receiver_name},

A new requirement file is waiting for your approval.

Request ID: {request_code}
File name: {original_filename}
Expires in: {expires_in_minutes} minutes

Approve:
{approve_url}

Reject:
{reject_url}

If you did not request this change, reject it immediately.

WRDN Security
""".strip()

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body
    style="
        font-family: Arial, sans-serif;
        background: #f4f6f8;
        padding: 30px;
    "
>
    <div
        style="
            max-width: 600px;
            margin: auto;
            background: white;
            border-radius: 10px;
            padding: 30px;
            border: 1px solid #dddddd;
        "
    >
        <h2 style="margin-top: 0;">
            WRDN Requirement Approval
        </h2>

        <p>Hello {receiver_name},</p>

        <p>
            A new requirement file is waiting
            for your approval.
        </p>

        <table
            style="
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            "
        >
            <tr>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                        font-weight: bold;
                    "
                >
                    Request ID
                </td>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                    "
                >
                    {request_code}
                </td>
            </tr>

            <tr>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                        font-weight: bold;
                    "
                >
                    File name
                </td>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                    "
                >
                    {original_filename}
                </td>
            </tr>

            <tr>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                        font-weight: bold;
                    "
                >
                    Expires in
                </td>
                <td
                    style="
                        padding: 10px;
                        border: 1px solid #dddddd;
                    "
                >
                    {expires_in_minutes} minutes
                </td>
            </tr>
        </table>

        <div style="margin-top: 25px;">
            <a
                href="{approve_url}"
                style="
                    display: inline-block;
                    padding: 12px 20px;
                    background: #167c3a;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    margin-right: 10px;
                "
            >
                Approve Requirement
            </a>

            <a
                href="{reject_url}"
                style="
                    display: inline-block;
                    padding: 12px 20px;
                    background: #b42318;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                "
            >
                Reject Requirement
            </a>
        </div>

        <p
            style="
                margin-top: 30px;
                font-size: 13px;
                color: #555555;
            "
        >
            If you did not request this change,
            reject it immediately.
        </p>
    </div>
</body>
</html>
""".strip()

    message.set_content(text_content)

    message.add_alternative(
        html_content,
        subtype="html",
    )

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=30,
        ) as smtp_server:
            smtp_server.ehlo()
            smtp_server.starttls()
            smtp_server.ehlo()

            smtp_server.login(
                MAIL_USERNAME,
                MAIL_APP_PASSWORD,
            )

            smtp_server.send_message(
                message
            )

    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError(
            "Gmail authentication failed. "
            "Check MAIL_USERNAME and MAIL_APP_PASSWORD."
        ) from error

    except Exception as error:
        raise RuntimeError(
            f"Requirement approval email failed: {error}"
        ) from error