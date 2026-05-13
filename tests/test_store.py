import json

import pytest

from hablon import model, store


def test_save_load_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    data = {
        "project": "demo",
        "next_id": 2,
        "tasks": [
            model.new_task("T1", "Do thing", created="2026-05-13T09:00:00-08:00"),
        ],
    }
    store.save("demo", data)
    loaded = store.load("demo")
    assert loaded == data


def test_save_validates(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    t = model.new_task("T1", "x", created="2026-05-13T09:00:00-08:00")
    t["depends_on"] = ["T99"]
    data = {"project": "demo", "next_id": 2, "tasks": [t]}
    with pytest.raises(model.ValidationError):
        store.save("demo", data)


def test_list_projects_sorted(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    (tmp_path / "zeta").mkdir()
    (tmp_path / "alpha").mkdir()
    (tmp_path / ".hidden").mkdir()
    assert store.list_projects() == ["alpha", "zeta"]


def test_save_writes_pretty_json(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    data = {
        "project": "demo",
        "next_id": 2,
        "tasks": [
            model.new_task("T1", "Has\nmulti", created="2026-05-13T09:00:00-08:00", notes="a\nb"),
        ],
    }
    store.save("demo", data)
    raw = (tmp_path / "demo" / "tasks.json").read_text(encoding="utf-8")
    assert "\n  " in raw  # indented
    # notes newline encoded as \n in the JSON source, not raw newline:
    assert '"notes": "a\\nb"' in raw
    # And it round-trips back to a real newline:
    assert json.loads(raw)["tasks"][0]["notes"] == "a\nb"
