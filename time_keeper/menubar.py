"""macOS menu bar app for time-keeper using rumps."""
from __future__ import annotations

import os
import subprocess

import rumps

from . import store, reports


class TimeKeeperApp(rumps.App):
    def __init__(self):
        super().__init__("TK", quit_button=None)
        self.icon = None
        self.conn = store.get_db()
        self.last_repo = None

        self.status_item = rumps.MenuItem("No active session")
        self.status_item.set_callback(None)

        self.menu = [
            self.status_item,
            None,  # separator
            rumps.MenuItem("Start Session", callback=self.start_session),
            rumps.MenuItem("Stop Session", callback=self.stop_session),
            None,
            rumps.MenuItem("Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("DB Status", callback=self.show_db_status),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self.timer = rumps.Timer(self.refresh, 30)
        self.timer.start()
        self.refresh(None)

    def _get_active(self) -> dict | None:
        return store.get_active_session(self.conn)

    def refresh(self, _):
        active = self._get_active()
        if active:
            hours = reports.session_duration_hours(active)
            label = f"TK: {reports.format_hours(hours)}"
            self.title = label
            self.status_item.title = f"{active['project_name']}: {reports.format_hours(hours)}"
            self.last_repo = active["repo_path"]
        else:
            self.title = "TK"
            self.status_item.title = "No active session"

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
        session_id = store.create_session(self.conn, repo)
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
