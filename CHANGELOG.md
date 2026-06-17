# Changelog

## DJ

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `tk repos add/remove/list` — registry of repos to watch (`~/.time-keeper/config.json`)
- `tk watch` with no `--repo` now watches **all registered repos** in one process, each as its own session
- `tk service install/uninstall/status` — launchd login agent (macOS) to auto-start the watcher
- Monthly, gzip-compressed rotation of the watcher log (`~/.time-keeper/logs/watch.log` → `logs/archive/watch-YYYY-MM.log.gz`)

### Changed

- File events are buffered and written in batches (≤1 commit/sec while active, none while idle) instead of one fsync per event
- SQLite now opens in WAL mode with `synchronous=NORMAL` and a busy timeout, so the dashboard, menu bar, and multiple watchers no longer collide with "database is locked"

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
