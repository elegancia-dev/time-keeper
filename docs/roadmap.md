# Roadmap

## v0.1.0 — Initial Release (current)

- File watcher with idle detection and auto-pause/resume
- Manual session start/stop
- SQLite storage (local, single file)
- Summary and detailed reports with date filtering
- Git commit enrichment
- Claude Code conversation parsing
- Live terminal dashboard
- macOS menu bar app
- JSON inbox ingestion for external sources
- Database export and cleanup utilities

## v0.2.0 — Planned Improvements

- Configurable ignore patterns for `tk watch` (currently hardcoded)
- Multi-repo watching (watch several repos simultaneously)
- CSV/JSON export for reports
- Improved session overlap detection and merging
- Project aliases and grouping
- Shell completions for bash/zsh/fish

## Future Directions

The following features are under consideration for future versions. Some may be offered as part of an enterprise edition, separate from the open-source core.

- **Team dashboards** — aggregate hours across team members
- **Invoice generation** — produce PDF invoices from tracked hours
- **Calendar integration** — sync sessions with Google Calendar or Outlook
- **Web UI** — browser-based dashboard as an alternative to the terminal
- **API server** — REST API for integrations and custom tooling
- **Multi-machine sync** — replicate the SQLite database across devices
- **Role-based access** — permissions for viewing/editing team data
- **Audit trail** — immutable log of all changes for compliance

The open-source core will always remain local-first, privacy-respecting, and fully functional as a standalone tool.
