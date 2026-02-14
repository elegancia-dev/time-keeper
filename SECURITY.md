# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in time-keeper, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email: **djzevenbergen@gmail.com**

Include:

- A description of the vulnerability
- Steps to reproduce
- Any relevant logs or screenshots

You should receive a response within 72 hours. Once the issue is confirmed, a fix will be prioritized and released as soon as possible.

## Scope

time-keeper is a local-first tool. All data is stored in a local SQLite database (`~/.time-keeper/timekeeper.db`). It does not transmit data over the network, require external accounts, or include telemetry.

Security concerns most likely involve:

- Local file path handling
- SQLite injection via CLI inputs
- Unexpected behavior in the file watcher
