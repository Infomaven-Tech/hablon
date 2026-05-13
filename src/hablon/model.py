from __future__ import annotations

from datetime import datetime
from typing import Iterable, Literal

Status = Literal["open", "active", "delegated", "done", "cancelled"]
STATUSES: tuple[Status, ...] = ("open", "active", "delegated", "done", "cancelled")
TERMINAL_STATUSES: frozenset[str] = frozenset({"done", "cancelled"})


class ValidationError(ValueError):
    pass


def new_task(
    task_id: str,
    title: str,
    *,
    created: str,
    due: str | None = None,
    depends_on: list[str] | None = None,
    notes: str = "",
    big_ticket: bool = False,
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "status": "open",
        "big_ticket": big_ticket,
        "due": due,
        "depends_on": list(depends_on or []),
        "notes": notes,
        "created": created,
        "started": None,
        "completed": None,
    }


def transition(task: dict, new_status: Status, now: str) -> None:
    """In-place status transition with timestamp bookkeeping."""
    if new_status not in STATUSES:
        raise ValidationError(f"unknown status: {new_status!r}")

    if new_status == "active" and not task.get("started"):
        task["started"] = now

    if new_status in TERMINAL_STATUSES:
        task["completed"] = now
    else:
        task["completed"] = None

    task["status"] = new_status


def check_acyclic(tasks: Iterable[dict]) -> None:
    """DFS-based cycle detection over depends_on edges."""
    tasks = list(tasks)
    by_id = {t["id"]: t for t in tasks}
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in by_id}

    def visit(tid: str, stack: list[str]) -> None:
        color[tid] = GREY
        for dep in by_id[tid].get("depends_on") or []:
            if dep not in by_id:
                continue
            if color[dep] == GREY:
                cycle = " -> ".join(stack + [tid, dep])
                raise ValidationError(f"dependency cycle: {cycle}")
            if color[dep] == WHITE:
                visit(dep, stack + [tid])
        color[tid] = BLACK

    for tid in by_id:
        if color[tid] == WHITE:
            visit(tid, [])


def validate(data: dict) -> None:
    tasks = data.get("tasks") or []
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate task IDs")

    id_set = set(ids)
    for t in tasks:
        for dep in t.get("depends_on") or []:
            if dep not in id_set:
                raise ValidationError(
                    f"{t['id']} depends_on missing task: {dep}"
                )
        if t["status"] not in STATUSES:
            raise ValidationError(f"{t['id']} has unknown status {t['status']!r}")
        if t["status"] == "active" and not t.get("started"):
            raise ValidationError(f"{t['id']} is active but has no started date")
        if t["status"] in TERMINAL_STATUSES and not t.get("completed"):
            raise ValidationError(
                f"{t['id']} is {t['status']} but has no completed date"
            )
        if t["status"] not in TERMINAL_STATUSES and t.get("completed"):
            raise ValidationError(
                f"{t['id']} is {t['status']} but completed is set"
            )

    check_acyclic(tasks)


def now_iso_offset() -> str:
    s = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]
