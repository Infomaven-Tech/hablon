from datetime import date

from hablon import model, render
from hablon.render import truncate_notes

TODAY = date(2026, 5, 13)


def _t(tid, title="x", due=None, status="open", deps=None, notes="", big_ticket=False, started=None, completed=None):
    t = model.new_task(tid, title, created="2026-05-01T09:00:00-08:00", due=due, depends_on=deps, notes=notes, big_ticket=big_ticket)
    t["status"] = status
    if started:
        t["started"] = started
    if completed:
        t["completed"] = completed
    return t


def test_truncate_notes_no_notes():
    assert truncate_notes("") == ([], False)


def test_truncate_notes_two_lines_fit():
    assert truncate_notes("a\nb") == (["a", "b"], False)


def test_truncate_notes_overflow():
    lines, more = truncate_notes("a\nb\nc\nd")
    assert lines == ["a", "b"]
    assert more is True


def test_truncate_notes_skips_blank_lines():
    lines, more = truncate_notes("a\n\nb\nc")
    assert lines == ["a", "b"]
    assert more is True


def test_node_label_html_escape_and_format():
    t = _t("T1", title="Email <Sara> & Co", due="2026-05-15", notes="line1\nline2\nline3")
    label = render.format_node_label(t)
    assert "<b>Email &lt;Sara&gt; &amp; Co</b>" in label
    assert "T1 · 2026-05-15" in label
    assert "line1" in label and "line2" in label
    assert "line3" not in label
    assert "…" in label


def test_node_label_no_due():
    t = _t("T1", title="X")
    label = render.format_node_label(t)
    assert "T1 · no due" in label


def test_mermaid_hides_cancelled_and_done_by_default():
    data = {
        "project": "demo",
        "next_id": 4,
        "tasks": [
            _t("T1", due="2026-05-15"),
            _t("T2", due="2026-05-15", status="done", started="2026-05-01T09:00:00-08:00", completed="2026-05-10T09:00:00-08:00"),
            _t("T3", due="2026-05-15", status="cancelled", completed="2026-05-10T09:00:00-08:00"),
        ],
    }
    out = render.to_mermaid(data, TODAY)
    assert "T1[" in out
    assert "T2[" not in out
    assert "T3[" not in out


def test_mermaid_show_done():
    data = {
        "project": "demo",
        "next_id": 3,
        "tasks": [
            _t("T1", due="2026-05-15"),
            _t("T2", due="2026-05-15", status="done", started="2026-05-01T09:00:00-08:00", completed="2026-05-10T09:00:00-08:00"),
        ],
    }
    out = render.to_mermaid(data, TODAY, show_done=True)
    assert "T2[" in out


def test_mermaid_no_past_keeps_pending_overdue():
    data = {
        "project": "demo",
        "next_id": 4,
        "tasks": [
            _t("T1", due="2026-05-01"),  # past, open
            _t("T2", due="2026-05-01", status="done", started="2026-04-30T09:00:00-08:00", completed="2026-05-02T09:00:00-08:00"),  # past, done
            _t("T3", due="2026-05-15"),  # week
        ],
    }
    out = render.to_mermaid(data, TODAY, no_past=True, show_done=True)
    assert "T1[" in out  # overdue-open stays
    assert "T2[" not in out  # done past dropped
    assert "T3[" in out


def test_mermaid_status_classes_applied():
    data = {
        "project": "demo",
        "next_id": 4,
        "tasks": [
            _t("T1", due="2026-05-15", status="active", started="2026-05-12T09:00:00-08:00"),
            _t("T2", due="2026-05-15", status="delegated"),
            _t("T3", due="2026-05-15", big_ticket=True),
        ],
    }
    out = render.to_mermaid(data, TODAY)
    assert "class T1 active" in out
    assert "class T2 delegated" in out
    assert "class T3 open,big_ticket" in out


def test_mermaid_overdue_class_overrides_status():
    data = {
        "project": "demo",
        "next_id": 2,
        "tasks": [_t("T1", due="2026-05-01", status="active", started="2026-04-30T09:00:00-08:00")],
    }
    out = render.to_mermaid(data, TODAY)
    assert "class T1 overdue" in out
    assert "class T1 active" not in out


def test_mermaid_edges_drop_to_hidden_tasks():
    data = {
        "project": "demo",
        "next_id": 3,
        "tasks": [
            _t("T1", due="2026-05-15", status="cancelled", completed="2026-05-10T09:00:00-08:00"),
            _t("T2", due="2026-05-15", deps=["T1"]),
        ],
    }
    out = render.to_mermaid(data, TODAY)
    assert "T1 --> T2" not in out
    assert "T2[" in out


def test_mermaid_empty_buckets_omitted():
    data = {
        "project": "demo",
        "next_id": 2,
        "tasks": [_t("T1", due="2026-05-15")],
    }
    out = render.to_mermaid(data, TODAY)
    assert "Past due" not in out
    assert "2–4 weeks" not in out
    assert "This week" in out
