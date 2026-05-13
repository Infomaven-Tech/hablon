from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

from . import store
from .buckets import (
    BUCKET_LABELS,
    BUCKET_ORDER,
    Bucket,
    Task,
    assign_buckets,
)

Data = dict[str, Any]

HIDDEN_STATUSES = frozenset({"cancelled"})

CLASS_DEFS = """\
  classDef open fill:#eef,stroke:#557
  classDef active fill:#ffe7a8,stroke:#c89000,stroke-width:2px
  classDef delegated fill:#e8e0ff,stroke:#7a5cd6,stroke-dasharray:4 2
  classDef done fill:#dfd,stroke:#393,color:#666
  classDef overdue fill:#fdd,stroke:#c33
  classDef big_ticket fill:#ffeb99,stroke:#ff6b6b,stroke-width:5px"""


def truncate_notes(notes: str, max_lines: int = 2) -> tuple[list[str], bool]:
    lines = [line for line in (notes or "").split("\n") if line.strip()]
    if not lines:
        return [], False
    if len(lines) <= max_lines:
        return lines, False
    return lines[:max_lines], True


def format_node_label(task: Task) -> str:
    title = html.escape(task["title"])
    tid: str = task["id"]
    due: str = task.get("due") or "no due"
    parts: list[str] = [f"{tid} · {html.escape(due)}"]
    head_lines, more = truncate_notes(task.get("notes") or "")
    if head_lines:
        parts.extend(html.escape(line) for line in head_lines)
        if more:
            parts.append("…")
    small_body = "<br>".join(parts)
    return f'{tid}["<b>{title}</b><br><small>{small_body}</small>"]'


def _classes_for(task: Task, bucket: Bucket) -> list[str]:
    classes: list[str] = []
    if task.get("big_ticket"):
        classes.append("big_ticket")
    elif bucket == "past":
        classes.append("overdue")
    else:
        classes.append(task["status"])
    return classes


def to_mermaid(
    data: Data,
    today: date,
    *,
    no_past: bool = False,
    show_done: bool = False,
) -> str:
    all_tasks: list[Task] = data.get("tasks") or []

    drawn: list[Task] = []
    for t in all_tasks:
        if t["status"] in HIDDEN_STATUSES:
            continue
        if t["status"] == "done" and not show_done:
            continue
        drawn.append(t)

    buckets_map: dict[str, Bucket] = assign_buckets(drawn, today)

    if no_past:
        kept: list[Task] = []
        for t in drawn:
            if buckets_map.get(t["id"]) == "past" and t["status"] in ("done", "cancelled"):
                continue
            kept.append(t)
        drawn = kept
        drawn_id_set: set[str] = {t["id"] for t in drawn}
        buckets_map = {tid: b for tid, b in buckets_map.items() if tid in drawn_id_set}

    by_bucket: dict[Bucket, list[Task]] = {b: [] for b in BUCKET_ORDER}
    for t in drawn:
        tid: str = t["id"]
        bucket: Bucket = buckets_map[tid]
        by_bucket[bucket].append(t)

    lines: list[str] = ["flowchart LR"]
    sub_keys: dict[Bucket, str] = {
        "past": "past", "today": "today", "week": "week", "month": "month", "future": "fut",
    }
    for b in BUCKET_ORDER:
        items = by_bucket[b]
        if not items:
            continue
        lines.append(f'  subgraph {sub_keys[b]}["{BUCKET_LABELS[b]}"]')
        for t in items:
            lines.append("    " + format_node_label(t))
        lines.append("  end")

    drawn_ids: set[str] = {t["id"] for t in drawn}
    for t in drawn:
        deps: list[str] = t.get("depends_on") or []
        for dep in deps:
            if dep in drawn_ids:
                lines.append(f"  {dep} --> {t['id']}")

    for t in drawn:
        tid = t["id"]
        bucket = buckets_map[tid]
        cls = _classes_for(t, bucket)
        if cls:
            lines.append(f"  class {tid} {','.join(cls)}")

    lines.append("")
    lines.append(CLASS_DEFS)
    return "\n".join(lines)


def _header(data: Data, today: date, *, no_past: bool, show_done: bool) -> str:
    tasks: list[Task] = data.get("tasks") or []
    visible: list[Task] = [
        t for t in tasks
        if t["status"] not in HIDDEN_STATUSES
        and (show_done or t["status"] != "done")
    ]
    open_active = sum(1 for t in visible if t["status"] in ("open", "active"))
    buckets_map: dict[str, Bucket] = assign_buckets(visible, today)
    overdue = sum(
        1 for t in visible
        if buckets_map.get(t["id"]) == "past"
        and t["status"] in ("open", "active", "delegated")
    )
    flags: list[str] = []
    if no_past:
        flags.append("--no-past")
    if show_done:
        flags.append("--show-done")
    flag_str = f" ({', '.join(flags)})" if flags else ""
    return (
        f"_Last rendered: {today.isoformat()} "
        f"({open_active} open/active, {overdue} overdue){flag_str}_"
    )


def render_md(data: Data, today: date, *, no_past: bool = False, show_done: bool = False) -> str:
    body = to_mermaid(data, today, no_past=no_past, show_done=show_done)
    header = _header(data, today, no_past=no_past, show_done=show_done)
    return (
        f"# {data['project']} — tasks\n\n"
        f"{header}\n\n"
        "```mermaid\n"
        f"{body}\n"
        "```\n"
    )


def write_md(name: str, data: Data, today: date, *, no_past: bool = False, show_done: bool = False) -> Path:
    target = store.project_md(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_md(data, today, no_past=no_past, show_done=show_done), encoding="utf-8", newline="\n")
    return target
