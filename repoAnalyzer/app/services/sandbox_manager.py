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
        self.active_processes: list[asyncio.subprocess.Process] = []

    def initialize(self) -> str:
        """Create the isolated sandbox directory on disk."""
        os.makedirs(self.root_dir, exist_ok=True)
        self.status = "active"
        logger.info("Sandbox initialized", session_id=self.session_id, path=self.root_dir)
        return self.root_dir

    def set_repo_dir(self, repo_dir_name: str = "repo") -> str:
        """Define and return the repository target path inside the sandbox."""
        self.repo_dir = os.path.join(self.root_dir, repo_dir_name)
        return self.repo_dir

    def get_working_directory(self) -> str:
        """Return the current working directory inside the sandbox."""
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
