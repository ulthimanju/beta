import asyncio
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from typing import Any
from app.core.logging import get_logger

logger = get_logger("git_cloner")

GIT_BIN: str = shutil.which("git") or "git"


class GitCloneError(Exception):
    """Raised when repository cloning fails."""
    pass


def _sync_count_files_and_size(directory: str) -> tuple[int, int]:
    """Synchronously count files and size in bytes."""
    total_files = 0
    total_size = 0
    for root, _, files in os.walk(directory):
        for f in files:
            total_files += 1
            fp = os.path.join(root, f)
            try:
                total_size += os.path.getsize(fp)
            except OSError:
                pass
    return total_files, total_size


def _sync_get_git_metadata(directory: str) -> tuple[str, str]:
    """Retrieve current commit hash and branch name via subprocess."""
    try:
        proc_commit = subprocess.run(
            [GIT_BIN, "rev-parse", "--short", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        commit_hash = proc_commit.stdout.strip() or "unknown"

        proc_branch = subprocess.run(
            [GIT_BIN, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
        )
        branch = proc_branch.stdout.strip() or "main"

        return commit_hash, branch
    except Exception as e:
        logger.warning("Could not retrieve git metadata", error=repr(e))
        return "unknown", "main"


def _sync_clone(repo_url: str, target_dir: str) -> subprocess.CompletedProcess[str]:
    """Execute git clone command synchronously inside a thread."""
    return subprocess.run(
        [GIT_BIN, "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        text=True,
        check=False,
    )


async def clone_repository(repo_url: str, session_id: str) -> dict[str, Any]:
    """
    Execute Step 2: Clone repository into an isolated temporary directory.
    Uses shallow clone (--depth 1) in a worker thread to ensure compatibility
    across Windows and POSIX event loops without blocking.
    """
    start_time = time.perf_counter()
    temp_dir = tempfile.mkdtemp(prefix=f"repo_analyzer_{session_id[:8]}_")
    logger.info("Step 2: Created temporary directory for cloning", temp_dir=temp_dir, repo_url=repo_url)

    try:
        # Run clone in worker thread
        proc = await asyncio.to_thread(_sync_clone, repo_url, temp_dir)

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Git clone command failed."
            logger.error("Git clone failed", returncode=proc.returncode, stderr=err_msg)
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise GitCloneError(f"Failed to clone repository: {err_msg}")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        commit_hash, branch = await asyncio.to_thread(_sync_get_git_metadata, temp_dir)
        file_count, size_bytes = await asyncio.to_thread(_sync_count_files_and_size, temp_dir)

        logger.info(
            "Step 2 completed: Repository cloned successfully",
            temp_dir=temp_dir,
            commit_hash=commit_hash,
            branch=branch,
            file_count=file_count,
            size_kb=round(size_bytes / 1024, 2),
            duration_ms=duration_ms,
        )

        return {
            "temp_dir": temp_dir,
            "commit_hash": commit_hash,
            "branch": branch,
            "file_count": file_count,
            "size_bytes": size_bytes,
            "duration_ms": duration_ms,
            "status": "cloned",
        }

    except GitCloneError:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        tb = traceback.format_exc()
        logger.error("Unexpected error during git clone", error=repr(e), traceback=tb)
        raise GitCloneError(f"Unexpected error while cloning: {repr(e)}")
