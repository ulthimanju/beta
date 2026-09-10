import asyncio
import os
import shutil
import subprocess
import time
import traceback
from typing import Any
from app.core.logging import get_logger
from app.services.sandbox_manager import sandbox_manager, SessionSandbox

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
    """Execute git clone command synchronously inside a worker thread."""
    return subprocess.run(
        [GIT_BIN, "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        text=True,
        check=False,
    )


async def clone_repository_into_sandbox(repo_url: str, session_id: str) -> dict[str, Any]:
    """
    Execute Step 2: Clone repository directly into the dedicated Session Sandbox.
    The sandbox boundary holds the repo and all session assets.
    """
    start_time = time.perf_counter()
    sandbox: SessionSandbox = sandbox_manager.get_or_create_sandbox(session_id)
    target_repo_dir = sandbox.set_repo_dir("repo")

    logger.info(
        "Step 2: Cloning directly into Session Sandbox",
        session_id=session_id,
        sandbox_root=sandbox.root_dir,
        target_dir=target_repo_dir,
        repo_url=repo_url,
    )

    try:
        # Run shallow clone directly into sandbox repository folder
        proc = await asyncio.to_thread(_sync_clone, repo_url, target_repo_dir)

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Git clone command failed."
            logger.error("Git clone failed inside sandbox", returncode=proc.returncode, stderr=err_msg)
            # Cleanup sandbox upon failure
            await sandbox.close()
            raise GitCloneError(f"Failed to clone repository inside sandbox: {err_msg}")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        commit_hash, branch = await asyncio.to_thread(_sync_get_git_metadata, target_repo_dir)
        file_count, size_bytes = await asyncio.to_thread(_sync_count_files_and_size, target_repo_dir)

        logger.info(
            "Step 2 completed: Repository cloned into Session Sandbox",
            session_id=session_id,
            sandbox_root=sandbox.root_dir,
            repo_dir=target_repo_dir,
            commit_hash=commit_hash,
            branch=branch,
            file_count=file_count,
            size_kb=round(size_bytes / 1024, 2),
            duration_ms=duration_ms,
        )

        return {
            "sandbox_root": sandbox.root_dir,
            "repo_dir": target_repo_dir,
            "working_dir": sandbox.get_working_directory(),
            "commit_hash": commit_hash,
            "branch": branch,
            "file_count": file_count,
            "size_bytes": size_bytes,
            "duration_ms": duration_ms,
            "status": "cloned",
        }

    except GitCloneError:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Unexpected error during git clone into sandbox", error=repr(e), traceback=tb)
        await sandbox.close()
        raise GitCloneError(f"Unexpected error while cloning into sandbox: {repr(e)}")
