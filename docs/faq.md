# FAQ

## Where is my data stored?

All data is in a single SQLite file at `~/.time-keeper/timekeeper.db`. The directory is created automatically on first use. No data is sent anywhere.

## Does time-keeper phone home or collect telemetry?

No. time-keeper is fully local. It makes no network requests, has no telemetry, and does not require any external accounts.

## Can I use time-keeper without Claude Code?

Yes. Claude conversation parsing is optional enrichment for the `tk detail` command. All core features (watching, tracking, reporting) work without Claude Code installed.

## What happens if I forget to stop a session?

If you're using `tk watch`, sessions auto-pause after the idle timeout (default 15 minutes of no file activity). If you started a session manually with `tk start` and forgot to stop it, you can stop it later with `tk stop`. The recorded time will include the full elapsed duration.

## Can I track multiple repos at once?

Currently, `tk watch` tracks one repo per invocation. You can run multiple `tk watch` processes in separate terminals for different repos. Each creates its own session in the database.

## How do I change the idle timeout?

Pass `--idle-timeout` to `tk watch`:

```bash
tk watch --idle-timeout 10    # 10 minutes
tk watch --idle-timeout 30    # 30 minutes
```

The default is 15 minutes.

## Can I query the database directly?

Yes. It's a standard SQLite file:

```bash
sqlite3 ~/.time-keeper/timekeeper.db
```

See [database-schema.md](database-schema.md) for the full schema.

## How do I clean up old data?

Use the export command to archive and remove old sessions:

```bash
tk db-export --before 2026-01-01
```

This exports matching sessions to a JSON file, deletes them from the database, and runs VACUUM.

## Does time-keeper work on Linux/Windows?

The core features (watching, tracking, reporting) should work on any platform with Python 3.9+. The `tk menubar` command requires macOS (it uses the `rumps` library). The dashboard and all other commands are cross-platform.

## What files does the watcher ignore?

By default: `.git/*`, `__pycache__/*`, `node_modules/*`, `*.pyc`, `.DS_Store`, `*.swp`, `*.swo`, `*~`.
