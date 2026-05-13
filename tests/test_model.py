import pytest

from hablon import model


def _t(tid, status="open", **kw):
    base = model.new_task(tid, f"task {tid}", created="2026-05-13T09:00:00-08:00")
    base["status"] = status
    base.update(kw)
    return base


def test_transition_active_stamps_started():
    t = _t("T1")
    model.transition(t, "active", "2026-05-14T10:00:00-08:00")
    assert t["status"] == "active"
    assert t["started"] == "2026-05-14T10:00:00-08:00"
    assert t["completed"] is None


def test_transition_done_stamps_completed():
    t = _t("T1", status="active", started="2026-05-14T10:00:00-08:00")
    model.transition(t, "done", "2026-05-15T10:00:00-08:00")
    assert t["status"] == "done"
    assert t["completed"] == "2026-05-15T10:00:00-08:00"


def test_transition_cancel_stamps_completed():
    t = _t("T1")
    model.transition(t, "cancelled", "2026-05-15T10:00:00-08:00")
    assert t["status"] == "cancelled"
    assert t["completed"] == "2026-05-15T10:00:00-08:00"


def test_transition_reopen_clears_completed():
    t = _t("T1", status="done", completed="2026-05-15T10:00:00-08:00", started="2026-05-14T10:00:00-08:00")
    model.transition(t, "open", "2026-05-16T10:00:00-08:00")
    assert t["status"] == "open"
    assert t["completed"] is None
    assert t["started"] == "2026-05-14T10:00:00-08:00"


def test_started_preserved_on_subsequent_active():
    t = _t("T1", status="active", started="2026-05-14T10:00:00-08:00")
    model.transition(t, "delegated", "2026-05-15T10:00:00-08:00")
    model.transition(t, "active", "2026-05-16T10:00:00-08:00")
    assert t["started"] == "2026-05-14T10:00:00-08:00"


def test_validate_rejects_duplicate_ids():
    data = {"project": "x", "next_id": 3, "tasks": [_t("T1"), _t("T1")]}
    with pytest.raises(model.ValidationError):
        model.validate(data)


def test_validate_rejects_missing_dep():
    t = _t("T1")
    t["depends_on"] = ["T99"]
    data = {"project": "x", "next_id": 2, "tasks": [t]}
    with pytest.raises(model.ValidationError):
        model.validate(data)


def test_validate_rejects_cycle():
    a = _t("T1")
    b = _t("T2")
    a["depends_on"] = ["T2"]
    b["depends_on"] = ["T1"]
    data = {"project": "x", "next_id": 3, "tasks": [a, b]}
    with pytest.raises(model.ValidationError):
        model.validate(data)


def test_validate_done_requires_completed():
    t = _t("T1", status="done")
    data = {"project": "x", "next_id": 2, "tasks": [t]}
    with pytest.raises(model.ValidationError):
        model.validate(data)


def test_validate_active_requires_started():
    t = _t("T1", status="active")
    data = {"project": "x", "next_id": 2, "tasks": [t]}
    with pytest.raises(model.ValidationError):
        model.validate(data)


def test_validate_open_rejects_completed():
    t = _t("T1", completed="2026-05-15T10:00:00-08:00")
    data = {"project": "x", "next_id": 2, "tasks": [t]}
    with pytest.raises(model.ValidationError):
        model.validate(data)
