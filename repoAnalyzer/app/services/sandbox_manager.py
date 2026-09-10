import asyncio
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.logging import get_logger

logger = get_logger("sandbox_manager")


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class SessionSandbox:
    """
    Represents an isolated, ephemeral session sandbox.
    All operations (cloning, working directory, CLI AI agent commands)
    execute strictly within this isolated boundary.
    Closing the sandbox kills active processes and completely deletes all files.
    """

    def __init__(self, session_id: str, base_dir: Optional[str] = None):
        self.session_id = session_id
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.closed_at: Optional[str] = None
        self.status: str = "created"  # created, active, closed

        # Base directory for sandboxes
        if base_dir:
            self.root_dir = os.path.join(base_dir, f"sandbox_{session_id}")
        else:
            self.root_dir = os.path.join(tempfile.gettempdir(), "repo_sandboxes", f"sandbox_{session_id}")

        self.repo_dir: Optional[str] = None
        self.working_dir: Optional[str] = None
        self.active_processes: list[asyncio.subprocess.Process] = []

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
        global_skill_path = os.path.expanduser(f"~/.agents/skills/{skill_name}")
        local_skill_path = os.path.join(os.getcwd(), ".agents", "skills", skill_name)

        src = None
        if os.path.exists(global_skill_path):
            src = global_skill_path
        elif os.path.exists(local_skill_path):
            src = local_skill_path

        if src and os.path.exists(src):
            sandbox_skills_dir = os.path.join(self.root_dir, ".agents", "skills")
            os.makedirs(sandbox_skills_dir, exist_ok=True)
            target_skill_dir = os.path.join(sandbox_skills_dir, skill_name)
            if not os.path.exists(target_skill_dir):
                try:
                    shutil.copytree(src, target_skill_dir, dirs_exist_ok=True)
                    logger.info("Mounted skill into sandbox", skill=skill_name, target=target_skill_dir)
                except Exception as e:
                    logger.warning("Failed to copy skill to sandbox", error=str(e))
            return target_skill_dir
        return None


    def set_working_directory(self, target_path: Optional[str] = None) -> dict[str, Any]:
        """
        Step 3: Set and verify the working directory inside the sandbox.
        Ensures strict boundary security (no directory traversal outside sandbox root).
        Inspects directory contents and detects ecosystem/project framework markers.
        """
        if target_path is None:
            if self.repo_dir and os.path.exists(self.repo_dir):
                target_path = self.repo_dir
            else:
                target_path = self.root_dir

        resolved_target = os.path.abspath(target_path)
        resolved_root = os.path.abspath(self.root_dir)

        # Sandbox boundary security check
        try:
            common = os.path.commonpath([resolved_root, resolved_target])
            if common != resolved_root:
                raise SandboxError(f"Security violation: Target directory '{target_path}' lies outside sandbox boundary.")
        except ValueError:
            raise SandboxError(f"Security violation: Target directory '{target_path}' is on an invalid path.")

        if not os.path.exists(resolved_target):
            raise SandboxError(f"Working directory does not exist: '{resolved_target}'")

        if not os.path.isdir(resolved_target):
            raise SandboxError(f"Target path is not a directory: '{resolved_target}'")

        self.working_dir = resolved_target

        # Inspect entries
        try:
            entries = sorted(os.listdir(resolved_target))
        except OSError as e:
            raise SandboxError(f"Failed to read directory contents: {str(e)}")

        is_git_worktree = os.path.isdir(os.path.join(resolved_target, ".git"))
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

        relative_path = os.path.relpath(resolved_target, self.root_dir)
        repo_name = os.path.basename(resolved_target)

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
        """Return the current working directory inside the sandbox."""
        if self.working_dir and os.path.exists(self.working_dir):
            return self.working_dir
        if self.repo_dir and os.path.exists(self.repo_dir):
            return self.repo_dir
        return self.root_dir

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
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }

    async def close(self) -> dict[str, Any]:
        """
        Close and destroy the sandbox:
        1. Terminate any active subprocesses.
        2. Completely remove sandbox directory and all files from disk.
        3. Mark status as closed.
        """
        logger.info("Closing and cleaning up sandbox", session_id=self.session_id, path=self.root_dir)

        # 1. Kill any active processes
        for proc in self.active_processes:
            try:
                if proc.returncode is None:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.returncode is None:
                        proc.kill()
            except Exception as e:
                logger.warning("Error terminating sandbox process", error=str(e))
        self.active_processes.clear()

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
        """Retrieve an active sandbox by session ID."""
        return self._sandboxes.get(session_id)

    async def close_sandbox(self, session_id: str) -> Optional[dict[str, Any]]:
        """Close and delete a sandbox by session ID."""
        sandbox = self._sandboxes.pop(session_id, None)
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
