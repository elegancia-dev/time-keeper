"""User configuration: the registry of repos the watcher tracks.

The registry is a small JSON file at ~/.time-keeper/config.json. `tk watch`
reads it to decide which repos to track in a single process, and the
`tk repos` commands manage it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".time-keeper"
CONFIG_PATH = CONFIG_DIR / "config.json"


def _default_config() -> dict:
    return {"repos": []}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return _default_config()
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _default_config()
    if not isinstance(data, dict):
        return _default_config()
    data.setdefault("repos", [])
    return data


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Write-then-rename so a crash mid-write can't corrupt the registry.
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp, CONFIG_PATH)


def _normalize(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def list_repos() -> list[dict]:
    """Registered repos as a list of {'path', 'project'} dicts."""
    return load_config().get("repos", [])


def add_repo(path: str, project: str | None = None) -> tuple[bool, str]:
    repo_path = _normalize(path)
    if not os.path.isdir(repo_path):
        return False, f"Not a directory: {repo_path}"
    config = load_config()
    for r in config["repos"]:
        if r["path"] == repo_path:
            return False, f"Already registered: {r['project']} ({repo_path})"
    entry = {"path": repo_path, "project": project or os.path.basename(repo_path)}
    config["repos"].append(entry)
    save_config(config)
    return True, f"Added {entry['project']} -> {repo_path}"


def remove_repo(path: str) -> tuple[bool, str]:
    repo_path = _normalize(path)
    config = load_config()
    kept = [r for r in config["repos"] if r["path"] != repo_path]
    if len(kept) == len(config["repos"]):
        return False, f"Not registered: {repo_path}"
    config["repos"] = kept
    save_config(config)
    return True, f"Removed {repo_path}"
