import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import traceback
import urllib.request
from typing import Any
from app.core.logging import get_logger
from app.services.sandbox_manager import sandbox_manager, SessionSandbox

logger = get_logger("git_cloner")

GIT_BIN: str = shutil.which("git") or "git"

# Configurable timeout thresholds for git network and local operations
DEFAULT_GIT_CLONE_TIMEOUT: float = float(os.environ.get("REPO_ANALYZER_GIT_CLONE_TIMEOUT", "60.0"))
DEFAULT_GIT_METADATA_TIMEOUT: float = float(os.environ.get("REPO_ANALYZER_GIT_METADATA_TIMEOUT", "10.0"))

# Dimension and resource limits to prevent disk exhaustion and denial of service
DEFAULT_MAX_REPO_SIZE_MB: float = float(os.environ.get("REPO_ANALYZER_MAX_REPO_SIZE_MB", "100.0"))
DEFAULT_MAX_REPO_SIZE_BYTES: int = int(DEFAULT_MAX_REPO_SIZE_MB * 1024 * 1024)
DEFAULT_MAX_REPO_FILES: int = int(os.environ.get("REPO_ANALYZER_MAX_REPO_FILES", "5000"))


class GitCloneError(Exception):
    """Raised when repository cloning fails."""
    pass


def _terminate_subprocess(proc: subprocess.Popen[str]) -> None:
    """Forcefully terminate a running subprocess and its process tree."""
    pid = getattr(proc, "pid", None)
    try:
        proc.terminate()
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.kill()
    except (ProcessLookupError, OSError):
        pass
    if os.name == "nt" and pid:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
    try:
        proc.wait(timeout=1.0)
    except Exception:
        pass


def _sync_count_files_and_size(directory: str) -> tuple[int, int]:
    """Synchronously count files and size in bytes."""
    total_files = 0
    total_size = 0
    if not os.path.exists(directory):
        return 0, 0
    for root, _, files in os.walk(directory):
        for f in files:
            total_files += 1
            fp = os.path.join(root, f)
            try:
                total_size += os.path.getsize(fp)
            except OSError:
                pass
    return total_files, total_size


# Hardened git configuration flags preventing arbitrary command execution, hooks, and SSRF
GIT_SANDBOX_SECURITY_FLAGS: list[str] = [
    "-c", "protocol.file.allow=never",
    "-c", "protocol.ext.allow=never",
    "-c", "core.hooksPath=" + ("NUL" if os.name == "nt" else "/dev/null"),
    "-c", "core.fsmonitor=false",
    "-c", "credential.helper=",
    "-c", "transfer.fsckObjects=true",
]


def _sync_get_git_metadata(
    directory: str,
    sandbox: Optional[SessionSandbox] = None,
    timeout: float = DEFAULT_GIT_METADATA_TIMEOUT,
    env: Optional[dict[str, str]] = None,
) -> tuple[str, str]:
    """Retrieve current commit hash and branch name via subprocess with timeout and boundary protection."""
    commit_hash = "unknown"
    branch = "main"

    try:
        cmd_commit = [GIT_BIN] + GIT_SANDBOX_SECURITY_FLAGS + ["rev-parse", "--short", "HEAD"]
        proc_commit = subprocess.Popen(
            cmd_commit,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if sandbox:
            sandbox.register_process(proc_commit)
        try:
            proc_commit.wait(timeout=timeout)
            time.sleep(0.02)
            out = sandbox.get_process_stdout(proc_commit.pid) if sandbox else (proc_commit.stdout.read() if proc_commit.stdout else "")
            commit_hash = out.strip() or "unknown"
        except subprocess.TimeoutExpired:
            _terminate_subprocess(proc_commit)

        cmd_branch = [GIT_BIN] + GIT_SANDBOX_SECURITY_FLAGS + ["rev-parse", "--abbrev-ref", "HEAD"]
        proc_branch = subprocess.Popen(
            cmd_branch,
            cwd=directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if sandbox:
            sandbox.register_process(proc_branch)
        try:
            proc_branch.wait(timeout=timeout)
            time.sleep(0.02)
            out = sandbox.get_process_stdout(proc_branch.pid) if sandbox else (proc_branch.stdout.read() if proc_branch.stdout else "")
            branch = out.strip() or "main"
        except subprocess.TimeoutExpired:
            _terminate_subprocess(proc_branch)

        return commit_hash, branch
    except Exception as e:
        logger.warning("Could not retrieve git metadata", error=repr(e))
        return commit_hash, branch


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


def _check_github_repo_size_preflight(repo_url: str, max_size_bytes: int) -> None:
    """
    Query GitHub API pre-flight to check declared repository size before downloading any data.
    If the repository is known to exceed max_size_bytes, rejects it immediately before disk consumption.
    """
    clean_url = repo_url.rstrip("/")
    m = re.search(r"github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?$", clean_url)
    if not m:
        return

    owner, repo = m.group(1), m.group(2)
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "repoAnalyzer-SecurityScanner",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode("utf-8"))
                size_kb = payload.get("size", 0)
                size_bytes = size_kb * 1024
                if size_bytes > max_size_bytes:
                    limit_mb = max_size_bytes / (1024 * 1024)
                    repo_mb = size_bytes / (1024 * 1024)
                    logger.warning(
                        "Pre-flight rejection: Repository size exceeds allowed limit",
                        repo=f"{owner}/{repo}",
                        size_mb=repo_mb,
                        limit_mb=limit_mb,
                    )
                    raise GitCloneError(
                        f"Repository size limit exceeded: {owner}/{repo} is approximately {repo_mb:.1f} MB (maximum allowed: {limit_mb:.1f} MB). Clone aborted before downloading."
                    )
    except GitCloneError:
        raise
    except Exception as e:
        logger.debug("GitHub API pre-flight size check skipped or unavailable", error=str(e))


def _sync_clone(
    repo_url: str,
    target_dir: str,
    sandbox: SessionSandbox,
    timeout: float = DEFAULT_GIT_CLONE_TIMEOUT,
    max_size_bytes: int = DEFAULT_MAX_REPO_SIZE_BYTES,
    max_file_count: int = DEFAULT_MAX_REPO_FILES,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """
    Execute git clone command confined within the sandbox boundary:
    1. Working directory confined strictly to sandbox.root_dir.
    2. Process registered in sandbox.active_processes and bound to OS resource limits (Job Object).
    3. Real-time disk consumption watchdog (terminates immediately if downloaded size exceeds max_size_bytes).
    4. Real-time file count watchdog (terminates immediately if file count exceeds max_file_count).
    5. Git security flags (disables file:// SSRF, ext protocols, hooks, fsmonitor, and credential helpers).
    6. Strict timeout enforcement.
    """
    start_time = time.perf_counter()
    cmd = [GIT_BIN] + GIT_SANDBOX_SECURITY_FLAGS + ["clone", "--depth", "1", "--", repo_url, target_dir]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=sandbox.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except Exception as e:
        raise GitCloneError(f"Failed to spawn git clone process: {str(e)}")

    # Enforce sandbox process boundary & OS kernel resource limits
    sandbox.register_process(proc)

    poll_interval = 0.25
    timed_out = False
    size_exceeded = False
    files_exceeded = False
    observed_size = 0
    observed_files = 0

    while True:
        rc = proc.poll()
        if rc is not None:
            break

        elapsed = time.perf_counter() - start_time
        if elapsed > timeout:
            timed_out = True
            break

        # Check real-time directory consumption
        if os.path.exists(target_dir):
            observed_files, observed_size = _sync_count_files_and_size(target_dir)
            if observed_size > max_size_bytes:
                size_exceeded = True
                break
            if observed_files > max_file_count:
                files_exceeded = True
                break

        time.sleep(poll_interval)

    if timed_out:
        _terminate_subprocess(proc)
        logger.error("Git clone operation timed out", repo_url=repo_url, timeout=timeout)
        raise GitCloneError(
            f"Repository cloning timed out after {timeout:.1f} seconds. The connection to GitHub was unresponsive."
        )

    if size_exceeded:
        _terminate_subprocess(proc)
        mb_used = observed_size / (1024 * 1024)
        mb_limit = max_size_bytes / (1024 * 1024)
        logger.error("Repository exceeded maximum allowed disk size during clone", repo_url=repo_url, size_mb=mb_used, limit_mb=mb_limit)
        raise GitCloneError(
            f"Repository size limit exceeded during clone: data reached {mb_used:.1f} MB (maximum allowed: {mb_limit:.1f} MB). Clone aborted."
        )

    if files_exceeded:
        _terminate_subprocess(proc)
        logger.error("Repository exceeded maximum allowed file count during clone", repo_url=repo_url, files=observed_files, limit_files=max_file_count)
        raise GitCloneError(
            f"Repository file count limit exceeded during clone: reached {observed_files} files (maximum allowed: {max_file_count} files). Clone aborted."
        )

    proc.wait()
    time.sleep(0.02)
    stdout = sandbox.get_process_stdout(proc.pid) or (proc.stdout.read() if proc.stdout else "")
    stderr = sandbox.get_process_stderr(proc.pid) or (proc.stderr.read() if proc.stderr else "")
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
    )


async def clone_repository_into_sandbox(
    repo_url: str,
    session_id: str,
    timeout: float = DEFAULT_GIT_CLONE_TIMEOUT,
    max_size_bytes: int = DEFAULT_MAX_REPO_SIZE_BYTES,
    max_file_count: int = DEFAULT_MAX_REPO_FILES,
) -> dict[str, Any]:
    """
    Execute Step 2: Clone repository directly into the dedicated Session Sandbox.
    Enforces sandbox boundary confinement, pre-flight size check, real-time disk/file watchdog,
    OS process resource limits, timeout, and post-clone verification.
    """
    # Strict URL validation before any filesystem or process activity
    clean_repo_url = validate_repo_url_security(repo_url)

    # 1. Pre-flight GitHub API size check (aborts before downloading if declared size exceeds limit)
    await asyncio.to_thread(_check_github_repo_size_preflight, clean_repo_url, max_size_bytes)

    start_time = time.perf_counter()
    sandbox: SessionSandbox = sandbox_manager.get_or_create_sandbox(session_id)
    target_repo_dir = sandbox.set_repo_dir("repo")

    # Build isolated environment with git config lockdown and prompt suppression
    clone_env = sandbox.build_isolated_environment(
        working_dir=sandbox.root_dir,
        extra_env={
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_SSH_COMMAND": "",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "NUL" if os.name == "nt" else "/dev/null",
        },
    )

    logger.info(
        "Step 2: Cloning directly into Session Sandbox",
        session_id=session_id,
        sandbox_root=sandbox.root_dir,
        target_dir=target_repo_dir,
        repo_url=clean_repo_url,
        timeout=timeout,
        max_size_mb=round(max_size_bytes / (1024 * 1024), 2),
        max_files=max_file_count,
    )

    try:
        # 2. Run shallow clone confined inside sandbox boundary with active watchdog and OS resource limits
        proc = await asyncio.to_thread(
            _sync_clone,
            clean_repo_url,
            target_repo_dir,
            sandbox,
            timeout,
            max_size_bytes,
            max_file_count,
            clone_env,
        )

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Git clone command failed."
            logger.error("Git clone failed inside sandbox", returncode=proc.returncode, stderr=err_msg)
            await sandbox.close()
            raise GitCloneError(f"Failed to clone repository inside sandbox: {err_msg}")

        # 3. Post-clone exact count and dimension verification
        file_count, size_bytes = await asyncio.to_thread(_sync_count_files_and_size, target_repo_dir)

        if size_bytes > max_size_bytes:
            mb_used = size_bytes / (1024 * 1024)
            mb_limit = max_size_bytes / (1024 * 1024)
            await sandbox.close()
            raise GitCloneError(
                f"Repository size limit exceeded: unpacked repository is {mb_used:.2f} MB (maximum allowed: {mb_limit:.1f} MB)."
            )

        if file_count > max_file_count:
            await sandbox.close()
            raise GitCloneError(
                f"Repository file count limit exceeded: repository contains {file_count} files (maximum allowed: {max_file_count} files)."
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        commit_hash, branch = await asyncio.to_thread(
            _sync_get_git_metadata,
            target_repo_dir,
            sandbox,
            DEFAULT_GIT_METADATA_TIMEOUT,
            clone_env,
        )

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
