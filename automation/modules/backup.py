"""Module 4a: daily SQL/media backups with optional remote upload via rclone."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from automation.core.config import AutomationConfig, require_env
from automation.core.logging_config import configure_logging

logger = configure_logging()


def run_command(command: list[str]) -> None:
    logger.info("Running backup command: %s", " ".join(command[:1] + ["***" if "password" in item.lower() else item for item in command[1:]]))
    subprocess.run(command, check=True)


def backup_database(config: AutomationConfig, stamp: str) -> Path:
    require_env(["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"])
    output = config.backup_dir / f"db_{stamp}.sql"
    command = [
        "mysqldump",
        f"--host={config.db.host}",
        f"--port={config.db.port}",
        f"--user={config.db.user}",
        f"--password={config.db.password}",
        "--single-transaction",
        "--quick",
        config.db.name,
    ]
    with output.open("wb") as handle:
        subprocess.run(command, stdout=handle, check=True)
    logger.info("Database backup created: %s", output)
    return output


def backup_media(config: AutomationConfig, stamp: str) -> Path | None:
    if not config.media_dir.exists():
        logger.warning("Media directory not found; skipping: %s", config.media_dir)
        return None
    archive = config.backup_dir / f"media_{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(config.media_dir, arcname=config.media_dir.name)
    logger.info("Media backup created: %s", archive)
    return archive


def upload_remote(paths: list[Path], config: AutomationConfig) -> None:
    if not config.remote_backup_target:
        logger.warning("REMOTE_BACKUP_TARGET not configured; backups remain local")
        return
    if not shutil.which("rclone"):
        logger.warning("rclone is not installed; cannot upload backups")
        return
    for path in paths:
        run_command(["rclone", "copy", str(path), config.remote_backup_target])
        logger.info("Uploaded backup to remote target: %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create database and media backups.")
    parser.add_argument("--skip-remote", action="store_true")
    args = parser.parse_args()
    config = AutomationConfig()
    config.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = [path for path in [backup_database(config, stamp), backup_media(config, stamp)] if path]
    if not args.skip_remote:
        upload_remote(paths, config)


if __name__ == "__main__":
    main()
