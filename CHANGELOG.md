# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-13

### Added

- `tk watch` — file watcher daemon with auto-start, idle pause, and resume
- `tk start` / `tk stop` — manual session tracking
- `tk status` — show active session with elapsed time
- `tk summary` — hours-per-project report with date filtering
- `tk detail` — per-session breakdown with git commits and Claude conversation summaries
- `tk dashboard` — live terminal UI with sessions, projects, and activity feed
- `tk projects` — list all tracked projects
- `tk recap` — copy-paste-ready work summary
- `tk menubar` — macOS menu bar app
- `tk ingest` — JSON inbox for external time sources
- `tk db-status` / `tk db-export` — database maintenance utilities
- SQLite storage at `~/.time-keeper/timekeeper.db`
- Git commit enrichment for reports
- Claude Code conversation parsing for detailed reports

[0.1.0]: https://github.com/djzevenbergen/time-keeper/releases/tag/v0.1.0
