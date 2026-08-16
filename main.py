import asyncio
from typing import Any

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover - optional dependency

    def flow(name: str | None = None):
        def decorator(func):
            return func

        return decorator

    def task(name: str | None = None):
        def decorator(func):
            return func

        return decorator


from batch_alert_check import check_clean_cycle_alert
from batch_usage_sync import sync_usage_history


@task(name="sync_usage_history")
def sync_usage_history_task() -> int:
    return asyncio.run(sync_usage_history())


@task(name="check_clean_cycle_alert")
def check_clean_cycle_alert_task() -> dict[str, Any]:
    return check_clean_cycle_alert()


@flow(name="remote-toilet-daily-orchestration")
def orchestrate_daily_litter_robot_jobs() -> dict[str, Any]:
    """Run both the sync and alert jobs in one workflow.

    This gives you a single Prefect flow to visualize in the Prefect UI, while
    still allowing the project to run as a standard Python script when Prefect is
    unavailable.
    """
    sync_result = sync_usage_history_task()
    alert_result = check_clean_cycle_alert_task()

    return {
        "usage_sync_inserted": sync_result,
        "alert_status": alert_result,
    }


def main() -> dict[str, Any]:
    return orchestrate_daily_litter_robot_jobs()


if __name__ == "__main__":
    result = main()
    print(result)
