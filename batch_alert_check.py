import json
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any
from urllib import error, request

from usage_store import get_db_connection, is_clean_cycle_complete


def send_ntfy_notification(topic: str, title: str, message: str) -> None:
    if not topic:
        raise ValueError("NTFY topic is not configured.")

    payload = json.dumps({"topic": topic, "title": title, "message": message}).encode(
        "utf-8"
    )
    req = request.Request(
        url=f"https://ntfy.sh/{topic}",
        data=payload,
        headers={
            "Title": title,
            "Priority": "high",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            response.read()
    except error.URLError as exc:
        raise RuntimeError(f"Failed to send ntfy notification: {exc}") from exc


def send_email_notification(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM")
    email_to = os.getenv("EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_password, email_from, email_to]):
        raise RuntimeError("SMTP email configuration is incomplete.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = email_to
    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def check_clean_cycle_alert(threshold: int = 5, days_back: int = 7) -> dict[str, Any]:
    conn = get_db_connection()
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
    rows = conn.execute(
        "SELECT event_type, event_time FROM usage_history WHERE event_time >= ? ORDER BY event_time ASC",
        (cutoff,),
    ).fetchall()
    conn.close()

    counts_by_day: dict[str, int] = {}
    for row in rows:
        event_type = row["event_type"]
        if not is_clean_cycle_complete(event_type):
            continue

        event_time = row["event_time"]
        try:
            dt = datetime.fromisoformat(str(event_time).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            day_key = dt.date().isoformat()
        except ValueError:
            continue

        counts_by_day[day_key] = counts_by_day.get(day_key, 0) + 1

    today = datetime.utcnow().date().isoformat()
    count = counts_by_day.get(today, 0)
    triggered = count > threshold

    result = {
        "date": today,
        "count": count,
        "threshold": threshold,
        "triggered": triggered,
        "counts_by_day": counts_by_day,
    }

    if triggered:
        title = "Litter Robot: Clean cycle alert"
        body = (
            f"The litter robot recorded {count} clean cycle completions today, "
            f"which exceeds the threshold of {threshold}."
        )

        if os.getenv("NTFY_TOPIC"):
            send_ntfy_notification(os.getenv("NTFY_TOPIC"), title, body)
        elif os.getenv("SMTP_HOST"):
            send_email_notification(title, body)

    return result


if __name__ == "__main__":
    result = check_clean_cycle_alert()
    print(json.dumps(result, indent=2))
