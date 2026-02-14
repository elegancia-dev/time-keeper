# Contributing to time-keeper

Thanks for your interest in contributing! Here's how to get started.

## Setup

1. Fork the repo and clone your fork:

   ```bash
   git clone https://github.com/<your-username>/time-keeper.git
   cd time-keeper
   ```

2. Create a virtual environment and install in editable mode:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. Verify the install:

   ```bash
   tk --help
   ```

## Making Changes

1. Create a branch for your work:

   ```bash
   git checkout -b my-feature
   ```

2. Make your changes and test locally by running `tk` commands.

3. Commit your changes with a clear message describing what and why.

4. Push to your fork and open a pull request against `main`.

## Code Style

- Follow existing patterns in the codebase.
- Use type hints where the surrounding code already uses them.
- Keep commits focused -- one logical change per commit.

## Principles

- **Local-first** — all data stays on the user's machine. No network calls, no telemetry, no external accounts.
- **Minimal dependencies** — prefer the standard library. Only add a dependency if it provides significant value over a simple implementation (e.g., `watchdog` for cross-platform file watching, `click` for CLI, `rich` for terminal formatting).
- **Privacy by default** — never transmit, collect, or store user data outside `~/.time-keeper/`.

## Reporting Issues

Found a bug or have a feature request? [Open an issue](https://github.com/djzevenbergen/time-keeper/issues).
