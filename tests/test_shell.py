import io
from contextlib import redirect_stdout
from datetime import date

import pytest

from hablon import store
from hablon.shell import Shell


@pytest.fixture
def shell(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    s = Shell()
    s.project = "demo"
    s.data = store.load("demo")
    store.save("demo", s.data)
    return s


def run(shell, cmd):
    buf = io.StringIO()
    with redirect_stdout(buf):
        shell.onecmd(cmd)
    return buf.getvalue()


def test_add_creates_task(shell):
    run(shell, 'add "First task" --due 2026-05-15')
    assert len(shell.data["tasks"]) == 1
    assert shell.data["tasks"][0]["title"] == "First task"
    assert shell.data["tasks"][0]["id"] == "T1"


def test_add_with_dep_validates(shell):
    run(shell, 'add "A" --due 2026-05-15')
    out = run(shell, 'add "B" --depends T99')
    assert "does not exist" in out
    assert len(shell.data["tasks"]) == 1


def test_add_with_existing_dep(shell):
    run(shell, 'add "A" --due 2026-05-15')
    run(shell, 'add "B" --due 2026-05-20 --depends T1')
    assert shell.data["tasks"][1]["depends_on"] == ["T1"]


def test_start_then_done(shell):
    run(shell, 'add "A"')
    run(shell, "start T1")
    assert shell.data["tasks"][0]["status"] == "active"
    assert shell.data["tasks"][0]["started"] is not None
    run(shell, "done T1")
    assert shell.data["tasks"][0]["status"] == "done"
    assert shell.data["tasks"][0]["completed"] is not None


def test_cancel_stamps_completed(shell):
    run(shell, 'add "A"')
    run(shell, "cancel T1")
    assert shell.data["tasks"][0]["status"] == "cancelled"
    assert shell.data["tasks"][0]["completed"] is not None


def test_reopen_clears_completed_preserves_started(shell):
    run(shell, 'add "A"')
    run(shell, "start T1")
    started = shell.data["tasks"][0]["started"]
    run(shell, "done T1")
    run(shell, "reopen T1")
    assert shell.data["tasks"][0]["status"] == "open"
    assert shell.data["tasks"][0]["completed"] is None
    assert shell.data["tasks"][0]["started"] == started


def test_tag_and_untag_big_ticket(shell):
    run(shell, 'add "A"')
    run(shell, "tag T1 --big-ticket")
    assert shell.data["tasks"][0]["big_ticket"] is True
    run(shell, "untag T1 --big-ticket")
    assert shell.data["tasks"][0]["big_ticket"] is False


def test_depend_and_cycle_detection(shell):
    run(shell, 'add "A"')
    run(shell, 'add "B"')
    run(shell, "depend T1 on T2")
    out = run(shell, "depend T2 on T1")
    assert "cycle" in out.lower()
    assert "T1" not in (shell.data["tasks"][1].get("depends_on") or [])


def test_rm_refuses_with_dependents(shell):
    run(shell, 'add "A"')
    run(shell, 'add "B" --depends T1')
    out = run(shell, "rm T1")
    assert "depend on T1" in out
    assert len(shell.data["tasks"]) == 2


def test_rm_force_drops_edges(shell):
    run(shell, 'add "A"')
    run(shell, 'add "B" --depends T1')
    run(shell, "rm T1 --force")
    assert len(shell.data["tasks"]) == 1
    assert shell.data["tasks"][0]["depends_on"] == []


def test_render_writes_md(shell):
    run(shell, 'add "A" --due 2026-05-15')
    run(shell, f"render --today 2026-05-13")
    md = store.project_md("demo").read_text(encoding="utf-8")
    assert "```mermaid" in md
    assert "<b>A</b>" in md


def test_notes_inline_decodes_backslash_n(shell):
    run(shell, 'add "A" --notes "line1\\nline2"')
    assert shell.data["tasks"][0]["notes"] == "line1\nline2"


def test_list_default_hides_done(shell):
    run(shell, 'add "A"')
    run(shell, 'add "B"')
    run(shell, "done T1")
    out = run(shell, "list")
    assert "T1" not in out
    assert "T2" in out


def test_list_all_shows_done(shell):
    run(shell, 'add "A"')
    run(shell, "done T1")
    out = run(shell, "list all")
    assert "T1" in out


def test_mkproject_creates_and_switches(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    s = Shell()
    out = run(s, "mkproject alpha")
    assert "Created project: alpha" in out
    assert s.project == "alpha"
    assert store.project_exists("alpha")


def test_mkproject_rejects_duplicate(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    s = Shell()
    run(s, "mkproject alpha")
    out = run(s, "mkproject alpha")
    assert "already exists" in out


def test_mkproject_rejects_bad_name(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECTS_DIR", tmp_path)
    s = Shell()
    out = run(s, "mkproject bad/name")
    assert "invalid path characters" in out
