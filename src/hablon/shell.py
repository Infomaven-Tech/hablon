from __future__ import annotations

import argparse
import cmd
from datetime import date, datetime

from . import model, parsing, render, store
from .buckets import assign_buckets

BASE_PROMPT = "hablon"


class Shell(cmd.Cmd):
    intro = (
        "hablon — weave your tasks together.\n"
        "Type `help` for commands, `mkproject <name>` or `use <name>` to "
        "select a project, `exit` to quit."
    )
    prompt = f"{BASE_PROMPT}> "

    def __init__(self) -> None:
        super().__init__()
        self.project: str | None = None
        self.data: dict | None = None
        self._render_opts = {"no_past": False, "show_done": False}

    # ---------- prompt / state helpers ----------

    def _refresh_prompt(self) -> None:
        if not self.project:
            self.prompt = f"{BASE_PROMPT}> "
            return
        data = self.data or {}
        tasks = data.get("tasks") or []
        open_active = sum(
            1 for t in tasks if t["status"] in ("open", "active")
        )
        today = date.today()
        buckets_map = assign_buckets(
            [t for t in tasks if t["status"] != "cancelled"], today
        )
        overdue = sum(
            1 for t in tasks
            if t["status"] in ("open", "active", "delegated")
            and buckets_map.get(t["id"]) == "past"
        )
        self.prompt = f"{self.project} ({open_active} open, {overdue} overdue)> "

    def _require_project(self) -> bool:
        if not self.project or self.data is None:
            print("No project selected. Run `use <name>` first.")
            return False
        return True

    def _save_and_render(self) -> None:
        assert self.project is not None and self.data is not None
        store.save(self.project, self.data)
        path = render.write_md(self.project, self.data, date.today(), **self._render_opts)
        self._refresh_prompt()
        print(f"Saved. Re-rendered {path}.")

    def _find(self, tid: str) -> dict | None:
        assert self.data is not None
        for t in self.data["tasks"]:
            if t["id"] == tid:
                return t
        print(f"Task {tid} not found.")
        return None

    # ---------- generic argparse runner ----------

    def _run(self, parser: argparse.ArgumentParser, raw: str):
        try:
            tokens = parsing.split_args(raw)
            return parser.parse_args(tokens)
        except parsing.ParseError as e:
            print(f"error: {e}")
            return None
        except SystemExit:
            return None

    # ---------- project commands ----------

    def do_use(self, arg: str):
        """use <project>  — switch active project (creates if missing)."""
        name = arg.strip()
        if not name:
            print("Usage: use <project>")
            return
        if not store.project_exists(name):
            ans = input(f"Project {name!r} does not exist. Create it? [y/N] ")
            if ans.strip().lower() not in ("y", "yes"):
                print("Cancelled.")
                return
        self.project = name
        self.data = store.load(name)
        store.save(name, self.data)
        self._refresh_prompt()
        print(f"Switched to project: {name}")

    def do_mkproject(self, arg: str):
        """mkproject <name>  — create a new project and switch to it."""
        name = arg.strip()
        if not name:
            print("Usage: mkproject <name>")
            return
        if any(ch in name for ch in r'\/:*?"<>|'):
            print("error: project name contains invalid path characters")
            return
        if store.project_exists(name):
            print(f"error: project {name!r} already exists")
            return
        self.project = name
        self.data = store.empty_project(name)
        store.save(name, self.data)
        self._refresh_prompt()
        print(f"Created project: {name}")

    def do_projects(self, _arg: str):
        """projects  — list all tracked projects."""
        names = store.list_projects()
        if not names:
            print("(no projects yet — `mkproject <name>` to create one)")
            return
        for n in names:
            data = store.load(n)
            count = sum(
                1 for t in data["tasks"] if t["status"] in ("open", "active")
            )
            marker = "*" if n == self.project else " "
            print(f"{marker} {n}  ({count} open/active)")

    # ---------- task commands ----------

    def do_add(self, arg: str):
        """add "<title>" [--due YYYY-MM-DD] [--depends T1,T2] [--notes "..."] [--big-ticket]"""
        if not self._require_project():
            return
        p = parsing.make_parser("add")
        p.add_argument("title")
        p.add_argument("--due")
        p.add_argument("--depends", default="")
        p.add_argument("--notes", default="")
        p.add_argument("--big-ticket", dest="big_ticket", action="store_true")
        ns = self._run(p, arg)
        if ns is None:
            return
        if ns.due:
            try:
                date.fromisoformat(ns.due)
            except ValueError:
                print(f"error: --due must be YYYY-MM-DD (got {ns.due!r})")
                return
        deps = [d.strip() for d in ns.depends.split(",") if d.strip()] if ns.depends else []
        for d in deps:
            if not any(t["id"] == d for t in self.data["tasks"]):
                print(f"error: depends-on {d!r} does not exist")
                return
        tid, next_n = store.next_task_id(self.data)
        task = model.new_task(
            tid,
            ns.title,
            created=model.now_iso_offset(),
            due=ns.due,
            depends_on=deps,
            notes=parsing.decode_nl(ns.notes),
            big_ticket=ns.big_ticket,
        )
        self.data["tasks"].append(task)
        self.data["next_id"] = next_n
        try:
            self._save_and_render()
        except model.ValidationError as e:
            self.data["tasks"].pop()
            self.data["next_id"] -= 1
            print(f"error: {e}")
            return
        print(f"Added {tid}.")

    def do_list(self, arg: str):
        """list [open|active|delegated|done|all] [--bucket past|week|month|future] [--big-ticket]"""
        if not self._require_project():
            return
        p = parsing.make_parser("list")
        p.add_argument(
            "status",
            nargs="?",
            default="visible",
            choices=["open", "active", "delegated", "done", "all", "visible"],
        )
        p.add_argument("--bucket", choices=["past", "week", "month", "future"])
        p.add_argument("--big-ticket", dest="big_ticket", action="store_true")
        ns = self._run(p, arg)
        if ns is None:
            return
        today = date.today()
        buckets_map = assign_buckets(
            [t for t in self.data["tasks"] if t["status"] != "cancelled"], today
        )
        rows = []
        for t in self.data["tasks"]:
            if t["status"] == "cancelled":
                continue
            if ns.status == "visible" and t["status"] in ("done",):
                continue
            if ns.status not in ("all", "visible") and t["status"] != ns.status:
                continue
            if ns.bucket and buckets_map.get(t["id"]) != ns.bucket:
                continue
            if ns.big_ticket and not t.get("big_ticket"):
                continue
            rows.append((t, buckets_map.get(t["id"], "future")))
        if not rows:
            print("(no tasks match)")
            return
        print(f"{'ID':<5} {'Status':<10} {'Bucket':<7} {'Due':<12} Title")
        print("-" * 60)
        for t, b in rows:
            tag = "*" if t.get("big_ticket") else " "
            title = t["title"]
            if len(title) > 40:
                title = title[:37] + "..."
            print(f"{t['id']:<5} {t['status']:<10} {b:<7} {(t.get('due') or '-'):<12}{tag}{title}")

    def do_show(self, arg: str):
        """show <id>"""
        if not self._require_project():
            return
        tid = arg.strip()
        if not tid:
            print("Usage: show <id>")
            return
        t = self._find(tid)
        if not t:
            return
        print(f"{t['id']}  {t['title']}")
        print(f"  status:   {t['status']}{'  [big-ticket]' if t.get('big_ticket') else ''}")
        print(f"  due:      {t.get('due') or '-'}")
        print(f"  depends:  {', '.join(t.get('depends_on') or []) or '-'}")
        print(f"  created:  {t.get('created') or '-'}")
        print(f"  started:  {t.get('started') or '-'}")
        print(f"  completed:{t.get('completed') or '-'}")
        notes = t.get("notes") or ""
        if notes:
            print("  notes:")
            for line in notes.split("\n"):
                print(f"    {line}")

    def do_edit(self, arg: str):
        """edit <id> [--title "..."] [--due YYYY-MM-DD] [--clear-due] [--notes "..."]"""
        if not self._require_project():
            return
        p = parsing.make_parser("edit")
        p.add_argument("id")
        p.add_argument("--title")
        p.add_argument("--due")
        p.add_argument("--clear-due", dest="clear_due", action="store_true")
        p.add_argument("--notes")
        ns = self._run(p, arg)
        if ns is None:
            return
        t = self._find(ns.id)
        if not t:
            return
        if ns.title is not None:
            t["title"] = ns.title
        if ns.clear_due:
            t["due"] = None
        if ns.due:
            try:
                date.fromisoformat(ns.due)
            except ValueError:
                print(f"error: --due must be YYYY-MM-DD")
                return
            t["due"] = ns.due
        if ns.notes is not None:
            t["notes"] = parsing.decode_nl(ns.notes)
        self._save_and_render()

    def do_notes(self, arg: str):
        """notes <id>  — enter multi-line notes; end with a single `.` line or Ctrl+D."""
        if not self._require_project():
            return
        tid = arg.strip()
        if not tid:
            print("Usage: notes <id>")
            return
        t = self._find(tid)
        if not t:
            return
        print(f"Enter notes for {tid}. End with a single '.' on its own line.")
        lines: list[str] = []
        while True:
            try:
                line = input("... ")
            except EOFError:
                print()
                break
            if line.strip() == ".":
                break
            lines.append(line)
        t["notes"] = "\n".join(lines)
        self._save_and_render()

    def _transition(self, arg: str, new_status: model.Status):
        if not self._require_project():
            return
        tid = arg.strip()
        if not tid:
            print(f"Usage: {new_status} <id>")
            return
        t = self._find(tid)
        if not t:
            return
        model.transition(t, new_status, model.now_iso_offset())
        self._save_and_render()

    def do_start(self, arg: str):
        """start <id>  — mark task as active."""
        self._transition(arg, "active")

    def do_delegate(self, arg: str):
        """delegate <id>  — mark task as delegated."""
        self._transition(arg, "delegated")

    def do_done(self, arg: str):
        """done <id>  — mark task as done."""
        self._transition(arg, "done")

    def do_cancel(self, arg: str):
        """cancel <id>  — mark task as cancelled."""
        self._transition(arg, "cancelled")

    def do_reopen(self, arg: str):
        """reopen <id>  — move task back to open."""
        self._transition(arg, "open")

    def do_tag(self, arg: str):
        """tag <id> --big-ticket"""
        self._set_flag(arg, True)

    def do_untag(self, arg: str):
        """untag <id> --big-ticket"""
        self._set_flag(arg, False)

    def _set_flag(self, arg: str, value: bool):
        if not self._require_project():
            return
        p = parsing.make_parser("tag" if value else "untag")
        p.add_argument("id")
        p.add_argument("--big-ticket", dest="big_ticket", action="store_true")
        ns = self._run(p, arg)
        if ns is None:
            return
        if not ns.big_ticket:
            print("error: only --big-ticket is supported")
            return
        t = self._find(ns.id)
        if not t:
            return
        t["big_ticket"] = value
        self._save_and_render()

    def do_depend(self, arg: str):
        """depend <id> on <other-id>"""
        if not self._require_project():
            return
        tokens = parsing.split_args(arg)
        if len(tokens) != 3 or tokens[1] != "on":
            print("Usage: depend <id> on <other-id>")
            return
        a, _, b = tokens
        ta = self._find(a)
        tb = self._find(b)
        if not ta or not tb:
            return
        if b in (ta.get("depends_on") or []):
            print(f"{a} already depends on {b}.")
            return
        ta.setdefault("depends_on", []).append(b)
        try:
            self._save_and_render()
        except model.ValidationError as e:
            ta["depends_on"].remove(b)
            print(f"error: {e}")

    def do_undepend(self, arg: str):
        """undepend <id> on <other-id>"""
        if not self._require_project():
            return
        tokens = parsing.split_args(arg)
        if len(tokens) != 3 or tokens[1] != "on":
            print("Usage: undepend <id> on <other-id>")
            return
        a, _, b = tokens
        ta = self._find(a)
        if not ta:
            return
        deps = ta.get("depends_on") or []
        if b not in deps:
            print(f"{a} does not depend on {b}.")
            return
        deps.remove(b)
        self._save_and_render()

    def do_rm(self, arg: str):
        """rm <id> [--force]"""
        if not self._require_project():
            return
        p = parsing.make_parser("rm")
        p.add_argument("id")
        p.add_argument("--force", action="store_true")
        ns = self._run(p, arg)
        if ns is None:
            return
        t = self._find(ns.id)
        if not t:
            return
        dependents = [o["id"] for o in self.data["tasks"] if ns.id in (o.get("depends_on") or [])]
        if dependents and not ns.force:
            print(f"error: {dependents} depend on {ns.id}. Use --force to remove anyway.")
            return
        self.data["tasks"] = [x for x in self.data["tasks"] if x["id"] != ns.id]
        if ns.force:
            for o in self.data["tasks"]:
                if ns.id in (o.get("depends_on") or []):
                    o["depends_on"].remove(ns.id)
        self._save_and_render()

    # ---------- rendering commands ----------

    def do_render(self, arg: str):
        """render [--no-past] [--show-done]"""
        if not self._require_project():
            return
        p = parsing.make_parser("render")
        p.add_argument("--no-past", dest="no_past", action="store_true")
        p.add_argument("--show-done", dest="show_done", action="store_true")
        p.add_argument("--today", help="(testing) override today's date as YYYY-MM-DD")
        ns = self._run(p, arg)
        if ns is None:
            return
        today = date.fromisoformat(ns.today) if ns.today else date.today()
        path = render.write_md(
            self.project, self.data, today,
            no_past=ns.no_past, show_done=ns.show_done,
        )
        print(f"Rendered {path}.")

    def do_future(self, arg: str):
        """future  — alias for `render --no-past`."""
        self.do_render(arg + " --no-past")

    def do_reorganize(self, arg: str):
        """reorganize  — alias for `render` against today's date."""
        self.do_render(arg)

    # ---------- exit ----------

    def do_exit(self, _arg: str):
        """exit  — leave the shell."""
        print("Goodbye.")
        return True

    def do_quit(self, _arg: str):
        """quit  — alias for exit."""
        return self.do_exit(_arg)

    def do_EOF(self, _arg: str):
        print()
        return self.do_exit(_arg)

    # ---------- ergonomics ----------

    def emptyline(self):
        pass

    def default(self, line: str):
        print(f"Unknown command: {line.split()[0]}. Type `help`.")


def main() -> None:
    Shell().cmdloop()
