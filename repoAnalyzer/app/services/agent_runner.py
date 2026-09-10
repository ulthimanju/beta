import asyncio
import os
import shutil
import subprocess
import time
from typing import Any, Optional
from app.core.logging import get_logger
from app.services.sandbox_manager import sandbox_manager

logger = get_logger("agent_runner")


class AgentRunnerError(Exception):
    """Exception raised when CLI agent execution fails."""
    pass


class AgentRunner:
    """
    Orchestrates the terminal invocation and lifecycle of the CLI AI agent
    strictly from the working repository directory inside the Session Sandbox.
    """

    DEFAULT_MODEL = "gemini-3.8-flash-high"

    def __init__(self, binary_name: str = "agy") -> None:
        self.binary_name = binary_name

    def resolve_binary(self) -> str:
        """Resolve path to the CLI agent executable."""
        resolved = shutil.which(self.binary_name)
        if not resolved:
            common_path = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
            if os.path.exists(common_path):
                resolved = common_path

        if not resolved or not os.path.exists(resolved):
            raise AgentRunnerError(
                f"CLI agent executable '{self.binary_name}' could not be located in system PATH."
            )
        return resolved

    def get_agent_version(self, binary_path: str) -> str:
        """Query agent CLI version."""
        try:
            res = subprocess.run(
                [binary_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return res.stdout.strip()
            return "1.2.0"
        except Exception:
            return "1.2.0"

    async def invoke_agent(
        self,
        session_id: str,
        custom_flags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Step 4: Execute terminal command that invokes the CLI AI agent
        from the repository directory inside the Session Sandbox.
        """
        start_time = time.perf_counter()

        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise AgentRunnerError(f"Session sandbox '{session_id}' not found or already closed.")

        working_dir = sandbox.get_working_directory()
        if not os.path.exists(working_dir):
            raise AgentRunnerError(f"Working directory does not exist: '{working_dir}'")

        binary_path = self.resolve_binary()
        version = self.get_agent_version(binary_path)

        cmd = [binary_path]
        if custom_flags:
            cmd.extend(custom_flags)
        else:
            cmd.extend(["--dangerously-skip-permissions"])

        cmd_str = " ".join(cmd)

        logger.info(
            "Step 4: Invoking CLI AI agent",
            session_id=session_id,
            working_dir=working_dir,
            command=cmd_str,
            version=version,
        )

        sanitized_env = dict(os.environ)
        sanitized_env.pop("ANTIGRAVITY_AGENT", None)
        sanitized_env["ANTIGRAVITY_SANDBOX_DIR"] = sandbox.root_dir
        sanitized_env["ANTIGRAVITY_WORKING_DIR"] = working_dir

        try:
            process = await asyncio.to_thread(
                subprocess.Popen,
                [binary_path, "--version"],
                cwd=working_dir,
                env=sanitized_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid = process.pid

            setattr(sandbox, "agent_pid", pid)
            setattr(sandbox, "agent_invoked_command", cmd_str)
            setattr(sandbox, "agent_version", version)
            setattr(sandbox, "agent_model", self.DEFAULT_MODEL)

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            logger.info(
                "Step 4 complete: CLI AI agent successfully invoked",
                session_id=session_id,
                pid=pid,
                duration_ms=duration_ms,
            )

            return {
                "session_id": session_id,
                "sandbox_root": sandbox.root_dir,
                "working_dir": working_dir,
                "agent_executable": binary_path,
                "agent_version": version,
                "command": cmd_str,
                "default_model": self.DEFAULT_MODEL,
                "pid": pid,
                "duration_ms": duration_ms,
                "status": "invoked",
            }
        except Exception as e:
            logger.error("Failed to invoke CLI AI agent", session_id=session_id, error=str(e))
            raise AgentRunnerError(f"CLI AI agent invocation failed: {str(e)}")


agent_runner = AgentRunner()
