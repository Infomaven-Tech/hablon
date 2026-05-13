from __future__ import annotations

import json
import os
from pathlib import Path

from . import model

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"


def resolve_project_dir(name: str) -> Path:
    return PROJECTS_DIR / name


def project_json(name: str) -> Path:
    return resolve_project_dir(name) / "tasks.json"


def project_md(name: str) -> Path:
    return resolve_project_dir(name) / "tasks.md"


def list_projects() -> list[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(
        p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


def empty_project(name: str) -> dict:
    return {"project": name, "next_id": 1, "tasks": []}


def load(name: str) -> dict:
    path = project_json(name)
    if not path.exists():
        return empty_project(name)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(name: str, data: dict) -> None:
    model.validate(data)
    target = project_json(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, target)


def project_exists(name: str) -> bool:
    return project_json(name).exists()


def next_task_id(data: dict) -> tuple[str, int]:
    n = data.get("next_id", 1)
    return f"T{n}", n + 1
