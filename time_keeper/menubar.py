"""macOS menu bar app for time-keeper using rumps."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone

import rumps

from . import store, reports


class TimeKeeperApp(rumps.App):
    def __init__(self):
        super().__init__("⚪ TK", quit_button=None)
        self.icon = None
        self.conn = store.get_db()
        self.last_repo = None

        # --- Active sessions section ---
        self.active_section_items: list[rumps.MenuItem] = []
        self._no_active_item = rumps.MenuItem("No active sessions")
        self._no_active_item.set_callback(None)

        # --- Summary submenu ---
        self.summary_menu = rumps.MenuItem("Summary")

        periods = [
            ("Last 12 hours", 12),
            ("Last 24 hours", 24),
            ("Last 2 days", 48),
            ("Last 3 days", 72),
        ]
        for label, hours in periods:
            item = rumps.MenuItem(label, callback=self._make_period_callback(hours, label))
            self.summary_menu.add(item)
        self.summary_menu.add(None)  # separator
        self.summary_menu.add(rumps.MenuItem("Specific day…", callback=self.pick_specific_day))

        # --- Build initial menu ---
        self.menu = [
            self._no_active_item,
            None,  # separator
            rumps.MenuItem("Start Session", callback=self.start_session),
            rumps.MenuItem("Stop Session", callback=self.stop_session),
            None,
            self.summary_menu,
            None,
            rumps.MenuItem("Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("DB Status", callback=self.show_db_status),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self.timer = rumps.Timer(self.refresh, 30)
        self.timer.start()
        self.refresh(None)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _get_all_active(self) -> list[dict]:
        return store.list_sessions(self.conn, status="active")

    def _get_active(self) -> dict | None:
        return store.get_active_session(self.conn)

    def refresh(self, _):
        active_sessions = self._get_all_active()

        # --- Update title ---
        if active_sessions:
            # Show elapsed of the most recent active session in the title
            latest = active_sessions[0]
            hours = reports.session_duration_hours(latest)
            self.title = f"🟢 TK {reports.format_hours(hours)}"
            self.last_repo = latest["repo_path"]
        else:
            self.title = "⚪ TK"

        # --- Rebuild active sessions section ---
        # Remove old active session items
        for item in self.active_section_items:
            try:
                del self.menu[item.title]
            except KeyError:
                pass
        if self._no_active_item.title in self.menu:
            try:
                del self.menu[self._no_active_item.title]
            except KeyError:
                pass
        self.active_section_items.clear()

        if active_sessions:
            for s in active_sessions:
                hours = reports.session_duration_hours(s)
                label = f"{s['project_name']} — {reports.format_hours(hours)}"
                item = rumps.MenuItem(label)
                item.set_callback(None)
                self.active_section_items.append(item)
                self.menu.insert_before("Start Session", item)
        else:
            self._no_active_item.title = "No active sessions"
            self.menu.insert_before("Start Session", self._no_active_item)

    # ------------------------------------------------------------------
    # Session actions
    # ------------------------------------------------------------------

    @rumps.clicked("Start Session")
    def start_session(self, _):
        active = self._get_active()
        if active:
            rumps.notification(
                "Time Keeper", "Already active",
                f"Session running for {active['project_name']}"
            )
            return

        repo = self.last_repo or os.path.expanduser("~")
        store.create_session(self.conn, repo)
        project = os.path.basename(repo)
        rumps.notification("Time Keeper", "Session started", f"Tracking {project}")
        self.refresh(None)

    @rumps.clicked("Stop Session")
    def stop_session(self, _):
        active = self._get_active()
        if not active:
            rumps.notification("Time Keeper", "No session", "No active session to stop")
            return

        store.stop_session(self.conn, active["id"])
        hours = reports.session_duration_hours(active)
        rumps.notification(
            "Time Keeper", "Session stopped",
            f"{active['project_name']}: {reports.format_hours(hours)}"
        )
        self.refresh(None)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _make_period_callback(self, hours: int, label: str):
        def callback(_):
            since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
            self._show_summary_in_terminal(since_dt, label)
        return callback

    def pick_specific_day(self, _):
        response = rumps.Window(
            message="Enter date (YYYY-MM-DD):",
            title="Summary for specific day",
            default_text=datetime.now().strftime("%Y-%m-%d"),
            ok="Show",
            cancel="Cancel",
            dimensions=(200, 24),
        ).run()
        if not response.clicked:
            return
        date_str = response.text.strip()
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            rumps.alert("Invalid date format. Use YYYY-MM-DD.")
            return
        self._show_summary_in_terminal(day, date_str)

    def _show_summary_in_terminal(self, since_dt: datetime, period_label: str):
        since_str = since_dt.strftime("%Y-%m-%d")
        subprocess.Popen([
            "osascript", "-e",
            f'tell application "Terminal" to do script "tk recap --since {since_str}"'
        ])

    # ------------------------------------------------------------------
    # Other actions
    # ------------------------------------------------------------------

    @rumps.clicked("Dashboard")
    def open_dashboard(self, _):
        subprocess.Popen(
            ["osascript", "-e",
             'tell application "Terminal" to do script "tk dashboard"']
        )

    @rumps.clicked("DB Status")
    def show_db_status(self, _):
        size = store.db_size_mb()
        session_count = self.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        activity_count = self.conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        rumps.alert(
            title="DB Status",
            message=(
                f"Size: {size:.2f} MB\n"
                f"Sessions: {session_count}\n"
                f"Activity log: {activity_count}"
            ),
        )

    @rumps.clicked("Quit")
    def quit_app(self, _):
        self.conn.close()
        rumps.quit_application()


def run_menubar():
    TimeKeeperApp().run()
