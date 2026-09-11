import asyncio
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.logging import get_logger

import re

logger = get_logger("sandbox_manager")

SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_session_id_security(session_id: str) -> str:
    """
    Strictly validates session_id to prevent directory traversal and injection.
    Only alphanumeric characters, dashes, and underscores up to 64 chars are permitted.
    """
    clean = (session_id or "").strip()
    if not clean or not SESSION_ID_REGEX.match(clean) or ".." in clean or "/" in clean or "\\" in clean:
        raise SandboxError(
            f"Security violation: Invalid session ID format '{session_id}'. Path traversal characters detected."
        )
    return clean


SKILL_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Sensitive environment variable name patterns that must never be exposed to subprocesses
SENSITIVE_ENV_PATTERNS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSWD",
    "AUTH",
    "CREDENTIAL",
    "DATABASE",
    "DB_",
    "MONGO",
    "POSTGRES",
    "REDIS",
    "AWS",
    "GCP",
    "AZURE",
    "PRIVATE",
    "BEARER",
    "JWT",
)

# Strictly allowlisted system environment variables needed for OS and CLI process execution
ALLOWED_SYSTEM_ENV_VARS = {
    # Windows system essentials (vital for Win32 API, DLL resolution, and socket layer)
    "SYSTEMROOT",
    "WINDIR",
    "SYSTEMDRIVE",
    "COMSPEC",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    # Execution & User essentials
    "PATH",
    "LOCALAPPDATA",
    "APPDATA",
    "USERPROFILE",
    # Unix/POSIX system essentials
    "HOME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TZ",
}


def is_sensitive_env_key(key: str) -> bool:
    """Check if an environment variable name matches any sensitive credential pattern."""
    key_upper = key.upper()
    return any(pattern in key_upper for pattern in SENSITIVE_ENV_PATTERNS)


def validate_skill_name_security(skill_name: str) -> str:
    """
    Strictly validates skill_name to prevent directory traversal and injection.
    Only alphanumeric characters, dashes, and underscores up to 64 chars are permitted.
    """
    clean = (skill_name or "").strip()
    if not clean or not SKILL_NAME_REGEX.match(clean) or ".." in clean or "/" in clean or "\\" in clean:
        raise SandboxError(
            f"Security violation: Invalid skill name format '{skill_name}'. Path traversal characters detected."
        )
    return clean


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class ProcessStreamConsumer:
    """
    Asynchronously consumes and buffers stdout and stderr for a subprocess in background daemon threads.
    Completely prevents OS pipe buffer exhaustion (typically 64KB on Linux/Windows) which would otherwise
    cause the child process to block indefinitely on sys.stdout.write() / sys.stderr.write().
    """

    def __init__(self, proc: Any, max_buffer_size: int = 10 * 1024 * 1024):
        self.proc = proc
        self.max_buffer_size = max_buffer_size
        self._stdout_chunks: list[str] = []
        self._stderr_chunks: list[str] = []
        self._stdout_len = 0
        self._stderr_len = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None

        self.start()

    def start(self) -> None:
        """Start background daemon reader threads for proc.stdout and proc.stderr."""
        if hasattr(self.proc, "stdout") and self.proc.stdout:
            self._stdout_thread = threading.Thread(
                target=self._reader,
                args=(self.proc.stdout, "stdout"),
                daemon=True,
                name=f"stdout-consumer-{getattr(self.proc, 'pid', 'unknown')}",
            )
            self._stdout_thread.start()

        if hasattr(self.proc, "stderr") and self.proc.stderr:
            self._stderr_thread = threading.Thread(
                target=self._reader,
                args=(self.proc.stderr, "stderr"),
                daemon=True,
                name=f"stderr-consumer-{getattr(self.proc, 'pid', 'unknown')}",
            )
            self._stderr_thread.start()

    def _reader(self, stream: Any, stream_type: str) -> None:
        """Continuously reads from stream in chunks until EOF or stop event."""
        try:
            while not self._stop_event.is_set():
                chunk = stream.read(4096)
                if not chunk:
                    break
                if isinstance(chunk, bytes):
                    chunk = chunk.decode("utf-8", errors="replace")
                with self._lock:
                    if stream_type == "stdout":
                        self._stdout_chunks.append(chunk)
                        self._stdout_len += len(chunk)
                        while self._stdout_chunks and self._stdout_len > self.max_buffer_size:
                            popped = self._stdout_chunks.pop(0)
                            self._stdout_len -= len(popped)
                    else:
                        self._stderr_chunks.append(chunk)
                        self._stderr_len += len(chunk)
                        while self._stderr_chunks and self._stderr_len > self.max_buffer_size:
                            popped = self._stderr_chunks.pop(0)
                            self._stderr_len -= len(popped)
        except Exception:
            pass

    def get_stdout(self) -> str:
        """Return all collected stdout so far as a string."""
        with self._lock:
            return "".join(self._stdout_chunks)

    def get_stderr(self) -> str:
        """Return all collected stderr so far as a string."""
        with self._lock:
            return "".join(self._stderr_chunks)

    def stop(self) -> None:
        """Signal reader threads to stop."""
        self._stop_event.set()


class SessionSandbox:
    """
    Represents an isolated, ephemeral session sandbox.
    All operations (cloning, working directory, CLI AI agent commands)
    execute strictly within this isolated boundary.
    Closing the sandbox kills active processes and completely deletes all files.
    """

    def __init__(self, session_id: str, base_dir: Optional[str] = None):
        clean_id = validate_session_id_security(session_id)
        self.session_id = clean_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.closed_at: Optional[str] = None
        self.status: str = "created"  # created, active, closed

        # Base directory for sandboxes with strict canonical path resolution
        resolved_base = os.path.realpath(os.path.abspath(base_dir or os.path.join(tempfile.gettempdir(), "repo_sandboxes")))
        candidate_root = os.path.realpath(os.path.abspath(os.path.join(resolved_base, f"sandbox_{clean_id}")))

        # Enforce sandbox boundary verification (strictly prevents path traversal)
        try:
            common = os.path.commonpath([resolved_base, candidate_root])
            if common != resolved_base or candidate_root == resolved_base:
                raise SandboxError(
                    f"Security violation: Sandbox root '{candidate_root}' escapes boundary '{resolved_base}'."
                )
        except ValueError:
            raise SandboxError("Security violation: Invalid drive or path configuration.")

        self.root_dir = candidate_root
        self.repo_dir: Optional[str] = None
        self.working_dir: Optional[str] = None
        self.active_processes: list[Any] = []
        self.agent_process: Optional[Any] = None
        self.agent_pid: Optional[int] = None
        self._stream_consumers: dict[int, ProcessStreamConsumer] = {}

    def register_process(self, proc: Any) -> None:
        """
        Register a running process in this sandbox for lifecycle tracking and cleanup.
        Ensures active_processes tracks the process, agent_process is bound,
        and background stream consumers are started to prevent pipe buffer deadlocks.
        """
        if proc is not None:
            if proc not in self.active_processes:
                self.active_processes.append(proc)
            self.agent_process = proc
            pid = getattr(proc, "pid", None)
            if pid:
                self.agent_pid = pid
                if pid not in self._stream_consumers:
                    consumer = ProcessStreamConsumer(proc)
                    self._stream_consumers[pid] = consumer
                    logger.info(
                        "Started background stdout/stderr stream consumer for process",
                        session_id=self.session_id,
                        pid=pid,
                    )

    def get_process_stdout(self, pid: Optional[int] = None) -> str:
        """Retrieve accumulated stdout for a specific process or the current agent process."""
        target_pid = pid or self.agent_pid
        if target_pid and target_pid in self._stream_consumers:
            return self._stream_consumers[target_pid].get_stdout()
        return ""

    def get_process_stderr(self, pid: Optional[int] = None) -> str:
        """Retrieve accumulated stderr for a specific process or the current agent process."""
        target_pid = pid or self.agent_pid
        if target_pid and target_pid in self._stream_consumers:
            return self._stream_consumers[target_pid].get_stderr()
        return ""

    def get_agent_stdout(self) -> str:
        """Convenience method to retrieve stdout from the current agent process."""
        return self.get_process_stdout()

    def get_agent_stderr(self) -> str:
        """Convenience method to retrieve stderr from the current agent process."""
        return self.get_process_stderr()

    def initialize(self) -> str:
        """Create the isolated sandbox directory on disk."""
        os.makedirs(self.root_dir, exist_ok=True)
        self.status = "active"
        self.working_dir = self.root_dir
        logger.info("Sandbox initialized", session_id=self.session_id, path=self.root_dir)
        return self.root_dir

    def set_repo_dir(self, repo_dir_name: str = "repo") -> str:
        """Define and return the repository target path inside the sandbox."""
        self.repo_dir = os.path.join(self.root_dir, repo_dir_name)
        return self.repo_dir

    def mount_skill(self, skill_name: str = "repo-analyzer") -> Optional[str]:
        """Ensure skill is mounted/accessible inside the sandbox workspace for the CLI AI agent."""
        clean_skill = validate_skill_name_security(skill_name)
        real_root = os.path.realpath(self.root_dir)

        # Base directories for global and project skills
        allowed_skill_roots = [
            os.path.realpath(os.path.expanduser("~/.agents/skills")),
            os.path.realpath(os.path.join(os.getcwd(), ".agents", "skills")),
        ]

        src = None
        for root in allowed_skill_roots:
            candidate = os.path.realpath(os.path.join(root, clean_skill))
            try:
                if os.path.commonpath([root, candidate]) == root and os.path.exists(candidate):
                    src = candidate
                    break
            except ValueError:
                pass

        if src and os.path.exists(src):
            sandbox_skills_dir = os.path.join(real_root, ".agents", "skills")
            os.makedirs(sandbox_skills_dir, exist_ok=True)
            target_skill_dir = os.path.realpath(os.path.join(sandbox_skills_dir, clean_skill))

            # Enforce sandbox containment on destination
            if os.path.commonpath([real_root, target_skill_dir]) != real_root:
                raise SandboxError("Security violation: Skill target directory escapes sandbox root.")

            if not os.path.exists(target_skill_dir):
                try:
                    shutil.copytree(src, target_skill_dir, dirs_exist_ok=True)
                    logger.info("Mounted skill into sandbox", skill=clean_skill, target=target_skill_dir)
                except Exception as e:
                    logger.warning("Failed to copy skill to sandbox", error=str(e))

            # Also mount into repo working directory if cloned
            if self.repo_dir and os.path.exists(self.repo_dir):
                real_repo = os.path.realpath(self.repo_dir)
                if os.path.commonpath([real_root, real_repo]) == real_root:
                    repo_skills_dir = os.path.join(real_repo, ".agents", "skills")
                    os.makedirs(repo_skills_dir, exist_ok=True)
                    repo_skill_target = os.path.realpath(os.path.join(repo_skills_dir, clean_skill))
                    if os.path.commonpath([real_root, repo_skill_target]) == real_root and not os.path.exists(repo_skill_target):
                        try:
                            shutil.copytree(src, repo_skill_target, dirs_exist_ok=True)
                        except Exception:
                            pass

            return target_skill_dir
        return None


    def set_working_directory(self, target_path: Optional[str] = None) -> dict[str, Any]:
        """
        Step 3: Set and verify the working directory inside the sandbox.
        Ensures strict boundary security (no directory traversal or symlink escapes outside sandbox root).
        Inspects directory contents and detects ecosystem/project framework markers.
        """
        if target_path is None:
            if self.repo_dir and os.path.exists(self.repo_dir):
                target_path = self.repo_dir
            else:
                target_path = self.root_dir
        elif not os.path.isabs(target_path):
            base = self.repo_dir if (self.repo_dir and os.path.exists(self.repo_dir)) else self.root_dir
            target_path = os.path.join(base, target_path)

        lexical_target = os.path.abspath(target_path)
        lexical_root = os.path.abspath(self.root_dir)

        # Canonical path resolution (resolves symlinks and junctions)
        real_target = os.path.realpath(lexical_target)
        real_root = os.path.realpath(lexical_root)

        # 1. Existence and directory verification
        if not os.path.exists(real_target):
            raise SandboxError(f"Working directory does not exist: '{target_path}'")

        if not os.path.isdir(real_target):
            raise SandboxError(f"Target path is not a directory: '{target_path}'")

        # 2. Strict canonical containment check (prevents symlink escape attacks)
        try:
            common = os.path.commonpath([real_root, real_target])
            if common != real_root:
                raise SandboxError(
                    f"Security violation: Target directory '{target_path}' resolves outside sandbox boundary via symlink to '{real_target}'."
                )
        except ValueError:
            raise SandboxError(f"Security violation: Target directory '{target_path}' is on an invalid or unshared drive.")

        # 3. Intermediate path component symlink check
        curr = lexical_target
        while True:
            if os.path.islink(curr):
                link_dest = os.path.realpath(curr)
                try:
                    if os.path.commonpath([real_root, link_dest]) != real_root:
                        raise SandboxError(
                            f"Security violation: Symlink component '{curr}' points outside sandbox boundary to '{link_dest}'."
                        )
                except ValueError:
                    raise SandboxError(f"Security violation: Symlink component '{curr}' points across drives.")
            parent = os.path.dirname(curr)
            if parent == curr or len(curr) <= len(lexical_root):
                break
            curr = parent

        self.working_dir = real_target

        # Inspect entries
        try:
            entries = sorted(os.listdir(real_target))
        except OSError as e:
            raise SandboxError(f"Failed to read directory contents: {str(e)}")

        is_git_worktree = os.path.isdir(os.path.join(real_target, ".git"))
        readme_present = any(e.lower().startswith("readme") for e in entries)

        # Detect frameworks and project markers
        detected_frameworks: list[str] = []
        entry_set = set(entries)

        if "package.json" in entry_set:
            detected_frameworks.append("Node.js / TypeScript")
        if any(f in entry_set for f in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "poetry.lock")):
            detected_frameworks.append("Python")
        if "go.mod" in entry_set:
            detected_frameworks.append("Go")
        if "Cargo.toml" in entry_set:
            detected_frameworks.append("Rust")
        if any(f in entry_set for f in ("pom.xml", "build.gradle", "build.gradle.kts")):
            detected_frameworks.append("Java / Kotlin")
        if "composer.json" in entry_set:
            detected_frameworks.append("PHP")
        if "Gemfile" in entry_set:
            detected_frameworks.append("Ruby")
        if any(f in entry_set for f in ("Dockerfile", "docker-compose.yml", "compose.yaml", "Containerfile")):
            detected_frameworks.append("Docker / Container")
        if "Makefile" in entry_set:
            detected_frameworks.append("Make")

        relative_path = os.path.relpath(real_target, real_root)
        repo_name = os.path.basename(real_target)

        logger.info(
            "Working directory set inside Session Sandbox",
            session_id=self.session_id,
            working_dir=self.working_dir,
            relative_path=relative_path,
            frameworks=detected_frameworks,
            files_count=len(entries),
        )

        return {
            "session_id": self.session_id,
            "sandbox_root": self.root_dir,
            "working_dir": self.working_dir,
            "relative_working_dir": relative_path if relative_path != "." else "./",
            "repo_name": repo_name,
            "is_git_worktree": is_git_worktree,
            "readme_present": readme_present,
            "detected_frameworks": detected_frameworks,
            "top_level_entries": entries[:25],
        }

    def get_working_directory(self) -> str:
        """Return the current verified canonical working directory inside the sandbox."""
        real_root = os.path.realpath(self.root_dir)
        for candidate in (self.working_dir, self.repo_dir, self.root_dir):
            if candidate and os.path.exists(candidate):
                real_candidate = os.path.realpath(candidate)
                try:
                    if os.path.commonpath([real_root, real_candidate]) == real_root:
                        return real_candidate
                except ValueError:
                    pass
        return real_root

    def build_isolated_environment(
        self,
        working_dir: Optional[str] = None,
        extra_env: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """
        Construct a strictly isolated process environment for sandbox subprocesses.

        Security guarantees:
        1. Zero inheritance of arbitrary host environment variables (prevents leaking API keys,
           database credentials, cloud credentials, CI tokens, service secrets).
        2. Strict allowlist of core OS runtime variables required to boot and run executables (SYSTEMROOT, PATH, etc.).
        3. Defense-in-depth secret pattern scrubbing for both system and extra variables.
        4. Temporary directory redirection to an isolated sandbox-local directory (.tmp).
        5. Sandbox boundary context injection (ANTIGRAVITY_SANDBOX_DIR, ANTIGRAVITY_WORKING_DIR).
        """
        isolated_env: dict[str, str] = {}

        # 1. Populate only from strict system allowlist, scrubbing any sensitive patterns
        for var_name in ALLOWED_SYSTEM_ENV_VARS:
            if var_name in os.environ and not is_sensitive_env_key(var_name):
                isolated_env[var_name] = os.environ[var_name]

        # 2. Add extra variables if explicitly passed, validating against sensitive patterns
        if extra_env:
            for k, v in extra_env.items():
                if not is_sensitive_env_key(k):
                    isolated_env[k] = str(v)
                else:
                    logger.warning("Rejected sensitive variable from extra_env", key=k)

        # 3. Redirect temp directories inside the sandbox
        sandbox_tmp = os.path.join(self.root_dir, ".tmp")
        try:
            os.makedirs(sandbox_tmp, exist_ok=True)
        except OSError:
            pass
        isolated_env["TEMP"] = sandbox_tmp
        isolated_env["TMP"] = sandbox_tmp
        isolated_env["TMPDIR"] = sandbox_tmp

        # 4. Contextual sandbox metadata
        target_work_dir = working_dir or self.get_working_directory()
        isolated_env["ANTIGRAVITY_SANDBOX_DIR"] = self.root_dir
        isolated_env["ANTIGRAVITY_WORKING_DIR"] = target_work_dir

        # 5. Explicitly ensure prohibited agent recursion flag is purged
        isolated_env.pop("ANTIGRAVITY_AGENT", None)

        return isolated_env

    def get_stats(self) -> dict[str, Any]:
        """Compute disk usage and file count inside this sandbox."""
        total_files = 0
        total_size = 0
        if os.path.exists(self.root_dir):
            for root, _, files in os.walk(self.root_dir):
                for f in files:
                    total_files += 1
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass

        return {
            "session_id": self.session_id,
            "status": self.status,
            "root_dir": self.root_dir,
            "repo_dir": self.repo_dir,
            "working_dir": self.get_working_directory(),
            "total_files": total_files,
            "size_bytes": total_size,
            "stdout_bytes": len(self.get_agent_stdout()),
            "stderr_bytes": len(self.get_agent_stderr()),
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }

    async def close(self) -> dict[str, Any]:
        """
        Close and destroy the sandbox:
        1. Stop background stream consumers and terminate any active subprocesses.
        2. Completely remove sandbox directory and all files from disk.
        3. Mark status as closed.
        """
        logger.info("Closing and cleaning up sandbox", session_id=self.session_id, path=self.root_dir)

        # 0. Stop background stream consumers
        for pid, consumer in list(self._stream_consumers.items()):
            try:
                consumer.stop()
            except Exception:
                pass
        self._stream_consumers.clear()

        # 1. Terminate any active processes
        procs_to_terminate: list[Any] = list(self.active_processes)
        agent_proc = getattr(self, "agent_process", None)
        if agent_proc and agent_proc not in procs_to_terminate:
            procs_to_terminate.append(agent_proc)

        for proc in procs_to_terminate:
            try:
                pid = getattr(proc, "pid", None)
                # Check if process is still running
                is_running = False
                if hasattr(proc, "poll"):
                    is_running = (proc.poll() is None)
                elif hasattr(proc, "returncode"):
                    is_running = (proc.returncode is None)

                if is_running:
                    logger.info("Terminating sandbox process", session_id=self.session_id, pid=pid)

                    # 1. Attempt graceful termination first
                    try:
                        proc.terminate()
                    except (ProcessLookupError, OSError):
                        pass

                    # Allow brief grace period for exit
                    for _ in range(6):
                        await asyncio.sleep(0.05)
                        if hasattr(proc, "poll") and proc.poll() is not None:
                            break
                        if hasattr(proc, "returncode") and proc.returncode is not None:
                            break

                    # 2. Force kill if still running
                    still_alive = False
                    if hasattr(proc, "poll"):
                        still_alive = (proc.poll() is None)
                    elif hasattr(proc, "returncode"):
                        still_alive = (proc.returncode is None)

                    if still_alive:
                        try:
                            proc.kill()
                        except (ProcessLookupError, OSError):
                            pass

                    # 3. On Windows, force-kill full process tree by PID to eliminate stubborn child processes
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

                    # 4. Final poll to reap process
                    if hasattr(proc, "poll"):
                        proc.poll()

                    # 5. Now that process is terminated, safely close standard streams
                    for stream_name in ("stdin", "stdout", "stderr"):
                        stream = getattr(proc, stream_name, None)
                        if stream and hasattr(stream, "close") and not getattr(stream, "closed", True):
                            try:
                                stream.close()
                            except Exception:
                                pass
            except Exception as e:
                logger.warning("Error terminating sandbox process", session_id=self.session_id, error=str(e))

        self.active_processes.clear()
        self.agent_process = None
        self.agent_pid = None

        # 2. Delete the directory tree
        if os.path.exists(self.root_dir):
            try:
                # Windows read-only file handling during git object deletion
                def handle_remove_readonly(func: Any, path: str, exc: Any) -> None:
                    try:
                        import stat
                        os.chmod(path, stat.S_IWRITE)
                        func(path)
                    except Exception:
                        pass

                await asyncio.to_thread(shutil.rmtree, self.root_dir, False, handle_remove_readonly)
                logger.info("Sandbox directory wiped completely", path=self.root_dir)
            except Exception as e:
                logger.error("Failed to fully delete sandbox directory", error=str(e))
                # Fallback non-blocking
                shutil.rmtree(self.root_dir, ignore_errors=True)

        self.status = "closed"
        self.closed_at = datetime.now(timezone.utc).isoformat()

        return {
            "session_id": self.session_id,
            "status": "closed",
            "message": "Sandbox successfully destroyed and all temporary session files wiped.",
            "closed_at": self.closed_at,
        }


class SessionSandboxManager:
    """Manages active session sandboxes across their lifecycle."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, SessionSandbox] = {}

    def get_or_create_sandbox(self, session_id: str) -> SessionSandbox:
        """Get an existing sandbox or create and initialize a new one."""
        if session_id in self._sandboxes:
            sb = self._sandboxes[session_id]
            if sb.status != "closed":
                return sb

        sandbox = SessionSandbox(session_id=session_id)
        sandbox.initialize()
        self._sandboxes[session_id] = sandbox
        return sandbox

    def get_sandbox(self, session_id: str) -> Optional[SessionSandbox]:
        """Retrieve an active sandbox by session ID with path traversal protection."""
        clean = (session_id or "").strip()
        if not clean or not SESSION_ID_REGEX.match(clean) or ".." in clean:
            return None
        return self._sandboxes.get(clean)

    async def close_sandbox(self, session_id: str) -> Optional[dict[str, Any]]:
        """Close and delete a sandbox by session ID with path traversal protection."""
        clean = (session_id or "").strip()
        if not clean or not SESSION_ID_REGEX.match(clean) or ".." in clean:
            return None
        sandbox = self._sandboxes.pop(clean, None)
        if sandbox:
            return await sandbox.close()
        return None

    async def close_all(self) -> None:
        """Close all active sandboxes (used on application shutdown)."""
        logger.info("Closing all active session sandboxes", count=len(self._sandboxes))
        for session_id in list(self._sandboxes.keys()):
            await self.close_sandbox(session_id)


# Singleton manager instance
sandbox_manager = SessionSandboxManager()
