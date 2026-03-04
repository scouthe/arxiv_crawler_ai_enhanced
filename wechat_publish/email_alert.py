import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_recipients(raw: str) -> list[str]:
    recipients = [item.strip() for item in raw.split(",") if item.strip()]
    return recipients


@dataclass
class EmailAlertConfig:
    enabled: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_ssl: bool
    smtp_starttls: bool
    smtp_from: str
    smtp_timeout_seconds: int
    recipients: list[str]


def load_email_alert_config_from_env() -> EmailAlertConfig:
    enabled = _as_bool(os.environ.get("WECHAT_ALERT_EMAIL_ENABLED"), True)
    raw_recipients = os.environ.get("EMAIL", "")
    recipients = _parse_recipients(raw_recipients)

    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port_raw = os.environ.get("SMTP_PORT", "").strip()
    smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_use_ssl = _as_bool(os.environ.get("SMTP_USE_SSL"), True)
    smtp_starttls = _as_bool(os.environ.get("SMTP_STARTTLS"), False)
    smtp_from = os.environ.get("SMTP_FROM", "").strip() or smtp_username
    timeout_raw = os.environ.get("SMTP_TIMEOUT_SECONDS", "15").strip()

    if not enabled:
        return EmailAlertConfig(
            enabled=False,
            smtp_host=smtp_host,
            smtp_port=0,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_ssl=smtp_use_ssl,
            smtp_starttls=smtp_starttls,
            smtp_from=smtp_from,
            smtp_timeout_seconds=15,
            recipients=recipients,
        )

    missing: list[str] = []
    if not recipients:
        missing.append("EMAIL")
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_port_raw:
        missing.append("SMTP_PORT")
    if not smtp_username:
        missing.append("SMTP_USERNAME")
    if not smtp_password:
        missing.append("SMTP_PASSWORD")

    if missing:
        raise ValueError(
            "邮件告警已启用，但以下环境变量缺失: " + ", ".join(missing)
        )

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise ValueError(f"SMTP_PORT 不是有效整数: {smtp_port_raw}") from exc
    if smtp_port <= 0:
        raise ValueError(f"SMTP_PORT 必须大于0: {smtp_port}")

    if smtp_use_ssl and smtp_starttls:
        raise ValueError("SMTP_USE_SSL 与 SMTP_STARTTLS 不能同时为 true")

    try:
        smtp_timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError(f"SMTP_TIMEOUT_SECONDS 不是有效整数: {timeout_raw}") from exc
    if smtp_timeout_seconds <= 0:
        raise ValueError(
            f"SMTP_TIMEOUT_SECONDS 必须大于0: {smtp_timeout_seconds}"
        )

    return EmailAlertConfig(
        enabled=True,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_use_ssl=smtp_use_ssl,
        smtp_starttls=smtp_starttls,
        smtp_from=smtp_from,
        smtp_timeout_seconds=smtp_timeout_seconds,
        recipients=recipients,
    )


def send_email(config: EmailAlertConfig, subject: str, body: str) -> None:
    if not config.enabled:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.smtp_from
    msg["To"] = ", ".join(config.recipients)
    msg.set_content(body)

    if config.smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            config.smtp_host,
            config.smtp_port,
            timeout=config.smtp_timeout_seconds,
            context=context,
        ) as server:
            server.login(config.smtp_username, config.smtp_password)
            server.send_message(msg)
        return

    with smtplib.SMTP(
        config.smtp_host,
        config.smtp_port,
        timeout=config.smtp_timeout_seconds,
    ) as server:
        server.ehlo()
        if config.smtp_starttls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        server.login(config.smtp_username, config.smtp_password)
        server.send_message(msg)


def send_failure_email(config: EmailAlertConfig, subject: str, body: str) -> None:
    send_email(config, subject, body)


def is_ip_whitelist_failure(text: str) -> bool:
    lowered = text.lower()
    if "40164" in lowered:
        return True
    return "invalid ip" in lowered and "whitelist" in lowered


def extract_hinted_ip(text: str) -> str | None:
    m = re.search(
        r"invalid ip\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
        text,
        flags=re.I,
    )
    if m:
        return m.group(1)
    return None
