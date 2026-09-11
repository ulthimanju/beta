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

# Configurable timeout thresholds for git network and local operations
DEFAULT_GIT_CLONE_TIMEOUT: float = float(os.environ.get("REPO_ANALYZER_GIT_CLONE_TIMEOUT", "60.0"))
DEFAULT_GIT_METADATA_TIMEOUT: float = float(os.environ.get("REPO_ANALYZER_GIT_METADATA_TIMEOUT", "10.0"))


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


def _sync_get_git_metadata(
    directory: str,
    timeout: float = DEFAULT_GIT_METADATA_TIMEOUT,
    env: Optional[dict[str, str]] = None,
) -> tuple[str, str]:
    """Retrieve current commit hash and branch name via subprocess with timeout protection."""
    try:
        proc_commit = subprocess.run(
            [GIT_BIN, "rev-parse", "--short", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
        commit_hash = proc_commit.stdout.strip() or "unknown"

        proc_branch = subprocess.run(
            [GIT_BIN, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
        branch = proc_branch.stdout.strip() or "main"

        return commit_hash, branch
    except subprocess.TimeoutExpired:
        logger.warning("Git metadata retrieval timed out", directory=directory, timeout=timeout)
        return "unknown", "main"
    except Exception as e:
        logger.warning("Could not retrieve git metadata", error=repr(e))
        return "unknown", "main"


import re

def validate_repo_url_security(url: str) -> str:
    """
    Strictly validates repository URL to prevent SSRF, local file disclosure,
    and Git argument injection attacks.
    """
    clean_url = (url or "").strip().rstrip("/")
    if not clean_url or clean_url.startswith("-"):
        raise GitCloneError("Security violation: Invalid repository URL format or option injection attempt.")

    pattern = r"^https?://(www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(\.git)?$"
    if not re.match(pattern, clean_url):
        raise GitCloneError(
            "Security violation: Only public GitHub repositories over HTTP(S) are permitted (e.g. https://github.com/owner/repo)."
        )

    return clean_url


def _sync_clone(
    repo_url: str,
    target_dir: str,
    timeout: float = DEFAULT_GIT_CLONE_TIMEOUT,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Execute git clone command synchronously inside a worker thread with timeout and option injection protection."""
    try:
        return subprocess.run(
            [GIT_BIN, "clone", "--depth", "1", "--", repo_url, target_dir],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "Git clone operation timed out",
            repo_url=repo_url,
            target_dir=target_dir,
            timeout=timeout,
        )
        raise GitCloneError(
            f"Repository cloning timed out after {timeout:.1f} seconds. The connection to GitHub was unresponsive."
        ) from exc


async def clone_repository_into_sandbox(
    repo_url: str,
    session_id: str,
    timeout: float = DEFAULT_GIT_CLONE_TIMEOUT,
) -> dict[str, Any]:
    """
    Execute Step 2: Clone repository directly into the dedicated Session Sandbox.
    The sandbox boundary holds the repo and all session assets.
    """
    # Strict URL validation before any filesystem or process activity
    clean_repo_url = validate_repo_url_security(repo_url)

    start_time = time.perf_counter()
    sandbox: SessionSandbox = sandbox_manager.get_or_create_sandbox(session_id)
    target_repo_dir = sandbox.set_repo_dir("repo")

    # Build isolated environment with terminal prompts disabled to prevent hanging on auth
    clone_env = sandbox.build_isolated_environment(
        extra_env={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
        }
    )

    logger.info(
        "Step 2: Cloning directly into Session Sandbox",
        session_id=session_id,
        sandbox_root=sandbox.root_dir,
        target_dir=target_repo_dir,
        repo_url=clean_repo_url,
        timeout=timeout,
    )

    try:
        # Run shallow clone directly into sandbox repository folder with strict timeout
        proc = await asyncio.to_thread(_sync_clone, clean_repo_url, target_repo_dir, timeout, clone_env)

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Git clone command failed."
            logger.error("Git clone failed inside sandbox", returncode=proc.returncode, stderr=err_msg)
            # Cleanup sandbox upon failure
            await sandbox.close()
            raise GitCloneError(f"Failed to clone repository inside sandbox: {err_msg}")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        commit_hash, branch = await asyncio.to_thread(_sync_get_git_metadata, target_repo_dir, DEFAULT_GIT_METADATA_TIMEOUT, clone_env)
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
        await sandbox.close()
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Unexpected error during git clone into sandbox", error=repr(e), traceback=tb)
        await sandbox.close()
        raise GitCloneError(f"Unexpected error while cloning into sandbox: {repr(e)}")
