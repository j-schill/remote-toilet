import asyncio
from datetime import datetime, timedelta
from typing import Any

from pylitterbot import Account

from core.config import Config
from core.usage_store import (
    CENTRAL_TZ,
    as_record_mapping,
    get_db_connection,
    now_in_central,
    store_new_usage_records,
)

config = Config()


async def fetch_recent_usage_history(
    robot: Any, days_back: int = 14
) -> list[dict[str, Any]]:
    """
    Fetch usage history from the robot and filter to the last N days.

    Different pylitterbot versions expose this under different names. This helper
    tries the common variations and falls back to common properties.
    """
    candidate_methods = (
        "get_usage_history",
        "get_activity_history",
        "get_activities",
        "get_history",
    )
    candidate_attrs = ("usage_history", "activity_history", "history", "activities")

    cutoff = now_in_central() - timedelta(days=days_back)
    records: list[dict[str, Any]] = []

    for name in candidate_methods:
        method = getattr(robot, name, None)
        if method is None:
            continue

        try:
            result = method()
            if asyncio.iscoroutine(result):
                result = await result
        except Exception:
            continue

        if result is None:
            continue

        if isinstance(result, dict):
            for key in (
                "history",
                "usage_history",
                "activity_history",
                "activities",
                "items",
                "data",
            ):
                if key in result:
                    result = result[key]
                    break

        if isinstance(result, (list, tuple)):
            for item in result:
                item = as_record_mapping(item)
                if not item:
                    continue
                ts = (
                    item.get("timestamp")
                    or item.get("time")
                    or item.get("event_time")
                    or item.get("date")
                )
                if ts is None:
                    records.append(item)
                    continue
                try:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is not None:
                    dt = dt.astimezone(CENTRAL_TZ)
                else:
                    dt = dt.replace(tzinfo=CENTRAL_TZ)
                if dt >= cutoff:
                    records.append(item)
            if records:
                return records

    for name in candidate_attrs:
        value = getattr(robot, name, None)
        if value is None:
            continue
        if isinstance(value, dict):
            value = (
                value.get("history")
                or value.get("items")
                or value.get("data")
                or [value]
            )
        if isinstance(value, (list, tuple)):
            for item in value:
                item = as_record_mapping(item)
                if not item:
                    continue
                ts = (
                    item.get("timestamp")
                    or item.get("time")
                    or item.get("event_time")
                    or item.get("date")
                )
                if ts is None:
                    records.append(item)
                    continue
                try:
                    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is not None:
                    dt = dt.astimezone(CENTRAL_TZ)
                else:
                    dt = dt.replace(tzinfo=CENTRAL_TZ)
                if dt >= cutoff:
                    records.append(item)
            if records:
                return records

    return records


async def sync_usage_history() -> int:
    username = config.credentials.username
    password = config.credentials.password
    account = Account()

    try:
        await account.connect(username=username, password=password, load_robots=True)
        if not account.robots:
            return 0

        robot = account.robots[0]
        history = await fetch_recent_usage_history(robot, days_back=14)
        robot_id = (
            getattr(robot, "serial_number", None)
            or getattr(robot, "name", None)
            or "robot-1"
        )

        conn = get_db_connection()
        inserted = store_new_usage_records(conn, str(robot_id), history)
        conn.close()
        print(f"Inserted {inserted} new usage-history records for robot {robot_id}.")
        return inserted
    finally:
        await account.disconnect()


if __name__ == "__main__":
    asyncio.run(sync_usage_history())
