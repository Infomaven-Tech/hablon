from datetime import date

from hablon.buckets import assign_buckets, bucket_for


TODAY = date(2026, 5, 13)


def test_bucket_boundaries():
    assert bucket_for(date(2026, 5, 12), TODAY) == "past"
    assert bucket_for(TODAY, TODAY) == "week"
    assert bucket_for(date(2026, 5, 20), TODAY) == "week"
    assert bucket_for(date(2026, 5, 21), TODAY) == "month"
    assert bucket_for(date(2026, 6, 10), TODAY) == "month"
    assert bucket_for(date(2026, 6, 11), TODAY) == "future"


def _task(tid, due=None, depends_on=None):
    return {
        "id": tid,
        "due": due,
        "depends_on": depends_on or [],
        "status": "open",
    }


def test_no_due_inherits_leaf_bucket():
    # T1 (future) <- T2 (no due, depends on T1) — T2 should be in future.
    tasks = [
        _task("T1", "2026-12-01"),
        _task("T2", None, ["T1"]),
    ]
    result = assign_buckets(tasks, TODAY)
    assert result == {"T1": "future", "T2": "future"}


def test_no_due_picks_latest_in_component():
    # T1 (week) — T2 (month) — T3 (no due, depends on T2) → T3 should be month.
    tasks = [
        _task("T1", "2026-05-15"),
        _task("T2", "2026-05-25", ["T1"]),
        _task("T3", None, ["T2"]),
    ]
    result = assign_buckets(tasks, TODAY)
    assert result["T3"] == "month"


def test_isolated_no_due_goes_future():
    tasks = [_task("T1", None)]
    assert assign_buckets(tasks, TODAY) == {"T1": "future"}


def test_all_no_due_component_goes_future():
    tasks = [
        _task("T1", None),
        _task("T2", None, ["T1"]),
    ]
    result = assign_buckets(tasks, TODAY)
    assert result == {"T1": "future", "T2": "future"}


def test_undirected_component_walk():
    # T1 (week) depends on T2 (no due). T2 should inherit T1's bucket.
    tasks = [
        _task("T1", "2026-05-15", ["T2"]),
        _task("T2", None),
    ]
    result = assign_buckets(tasks, TODAY)
    assert result["T2"] == "week"
