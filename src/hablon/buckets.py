from __future__ import annotations

from datetime import date
from typing import Iterable, Literal

Bucket = Literal["past", "week", "month", "future"]
BUCKET_ORDER: tuple[Bucket, ...] = ("past", "week", "month", "future")
BUCKET_LABELS: dict[Bucket, str] = {
    "past": "Past due",
    "week": "This week",
    "month": "2–4 weeks",
    "future": "Future",
}


def bucket_for(due: date, today: date) -> Bucket:
    delta = (due - today).days
    if delta < 0:
        return "past"
    if delta <= 7:
        return "week"
    if delta <= 28:
        return "month"
    return "future"


def _bucket_rank(b: Bucket) -> int:
    return BUCKET_ORDER.index(b)


def assign_buckets(tasks: Iterable[dict], today: date) -> dict[str, Bucket]:
    """Return {task_id: Bucket} for every task.

    Dated tasks: bucket_for(due, today).
    No-due tasks: latest bucket among dated members of the same connected
    component (dependency graph, edges either direction). Isolated no-due
    tasks fall back to 'future'.
    """
    tasks = list(tasks)
    by_id = {t["id"]: t for t in tasks}

    adj: dict[str, set[str]] = {t["id"]: set() for t in tasks}
    for t in tasks:
        for dep in t.get("depends_on") or []:
            if dep in adj:
                adj[t["id"]].add(dep)
                adj[dep].add(t["id"])

    components: list[set[str]] = []
    seen: set[str] = set()
    for tid in adj:
        if tid in seen:
            continue
        stack = [tid]
        comp: set[str] = set()
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            seen.add(n)
            stack.extend(adj[n] - comp)
        components.append(comp)

    result: dict[str, Bucket] = {}
    for comp in components:
        dated_buckets: list[Bucket] = []
        for tid in comp:
            due = by_id[tid].get("due")
            if due:
                dated_buckets.append(bucket_for(date.fromisoformat(due), today))
        latest: Bucket = (
            max(dated_buckets, key=_bucket_rank) if dated_buckets else "future"
        )
        for tid in comp:
            due = by_id[tid].get("due")
            if due:
                result[tid] = bucket_for(date.fromisoformat(due), today)
            else:
                result[tid] = latest

    return result
