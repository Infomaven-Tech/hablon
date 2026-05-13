from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Literal

Task = dict[str, Any]
Bucket = Literal["past", "today", "week", "month", "future"]
BUCKET_ORDER: tuple[Bucket, ...] = ("past", "today", "week", "month", "future")
BUCKET_LABELS: dict[Bucket, str] = {
    "past": "Past due",
    "today": "Today",
    "week": "This week",
    "month": "2–4 weeks",
    "future": "Future",
}


def bucket_for(due: date, today: date) -> Bucket:
    delta = (due - today).days
    if delta < 0:
        return "past"
    if delta == 0:
        return "today"
    if delta <= 7:
        return "week"
    if delta <= 28:
        return "month"
    return "future"


def assign_buckets(tasks: Iterable[Task], today: date) -> dict[str, Bucket]:
    """Return {task_id: Bucket} for every task.

    Terminal tasks (done/cancelled): bucket_for(completed, today).
    Other dated tasks: bucket_for(due, today).
    No-due tasks: bucket of the next task with a due date in the forward
    dependency chain. Isolated no-due tasks fall back to 'future'.
    """
    task_list: list[Task] = list(tasks)
    by_id: dict[str, Task] = {t["id"]: t for t in task_list}

    depends: dict[str, set[str]] = {
        t["id"]: set(t.get("depends_on") or []) for t in task_list
    }

    depended_by: dict[str, set[str]] = {t["id"]: set() for t in task_list}
    for tid, deps in depends.items():
        for dep in deps:
            if dep in depended_by:
                depended_by[dep].add(tid)

    result: dict[str, Bucket] = {}

    for t in task_list:
        tid: str = t["id"]

        if t["status"] in ("done", "cancelled"):
            completed: str | None = t.get("completed")
            if completed:
                completed_date = date.fromisoformat(completed[:10])
                result[tid] = bucket_for(completed_date, today)
            else:
                result[tid] = "future"
            continue

        due: str | None = t.get("due")
        if due:
            result[tid] = bucket_for(date.fromisoformat(due), today)
            continue

        visited: set[str] = set()
        stack: list[str] = [tid]
        found_bucket: Bucket | None = None

        while stack and not found_bucket:
            current: str = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            for dependent in depended_by[current]:
                if dependent in visited:
                    continue
                dep_task: Task = by_id[dependent]
                dep_due: str | None = dep_task.get("due")
                if dep_due:
                    found_bucket = bucket_for(date.fromisoformat(dep_due), today)
                    break
                stack.append(dependent)

        result[tid] = found_bucket or "future"

    return result
