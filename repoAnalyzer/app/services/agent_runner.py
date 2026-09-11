import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.services.sandbox_manager import sandbox_manager, validate_skill_name_security, SandboxError
from app.services.report_generator import report_generator
from app.services.repo_inspector import repo_inspector
from app.schemas.analysis import validate_safe_custom_flags


logger = get_logger("agent_runner")


class AgentRunnerError(Exception):
    """Exception raised when CLI agent execution fails."""
    pass


class AgentRunner:
    """
    Orchestrates the terminal invocation and lifecycle of the CLI AI agent
    strictly from the working repository directory inside the Session Sandbox.
    """

    DEFAULT_MODEL = settings.DEFAULT_MODEL

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

        # Strictly validate custom_flags against security allowlist
        try:
            safe_flags = validate_safe_custom_flags(custom_flags)
        except ValueError as e:
            raise AgentRunnerError(str(e))

        cmd = [binary_path]
        if not safe_flags or "--dangerously-skip-permissions" not in safe_flags:
            cmd.append("--dangerously-skip-permissions")
        if safe_flags:
            for flag in safe_flags:
                if flag not in cmd:
                    cmd.append(flag)

        cmd_str = " ".join(cmd)

        logger.info(
            "Step 4: Invoking CLI AI agent",
            session_id=session_id,
            working_dir=working_dir,
            command=cmd_str,
            version=version,
        )

        isolated_env = sandbox.build_isolated_environment(working_dir)

        try:
            process = await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                cwd=working_dir,
                env=isolated_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid = process.pid

            # Register process in sandbox for tracking and graceful shutdown
            sandbox.register_process(process)
            setattr(sandbox, "agent_process", process)
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

    async def dispatch_query(
        self,
        session_id: str,
        query: str = "analyze this repo using repo-analyzer skill",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Step 5: Send query "analyze this repo using repo-analyzer skill"
        to the AI agent using its default model.
        """
        start_time = time.perf_counter()

        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise AgentRunnerError(f"Session sandbox '{session_id}' not found or already closed.")

        working_dir = sandbox.get_working_directory()
        if not os.path.exists(working_dir):
            raise AgentRunnerError(f"Working directory does not exist: '{working_dir}'")

        # Mount/verify repo-analyzer skill is inside the sandbox workspace
        mounted_skill_dir = sandbox.mount_skill("repo-analyzer")

        active_model = model or self.DEFAULT_MODEL
        setattr(sandbox, "active_query", query)
        setattr(sandbox, "active_model", active_model)
        setattr(sandbox, "mounted_skill_dir", mounted_skill_dir)

        # Active process communication: send query to CLI AI agent stdin
        agent_proc = getattr(sandbox, "agent_process", None)
        communication_mode = "stdin_stream"
        bytes_sent = len(query.encode("utf-8"))
        agent_pid = getattr(sandbox, "agent_pid", None)

        # Check if existing agent process has already terminated
        if agent_proc and agent_proc.poll() is not None:
            rc = agent_proc.returncode
            err = sandbox.get_agent_stderr() or ""
            logger.error("AI agent process died before Step 5 query dispatch", session_id=session_id, pid=agent_proc.pid, exit_code=rc)
            raise AgentRunnerError(f"AI agent process (PID: {agent_proc.pid}) died with exit code {rc} before query could be dispatched. Stderr: {err[:300].strip() or 'None'}")

        if agent_proc and agent_proc.poll() is None:
            if not agent_proc.stdin or agent_proc.stdin.closed:
                raise AgentRunnerError(f"AI agent process (PID: {agent_proc.pid}) stdin is closed or unavailable.")
            try:
                agent_proc.stdin.write(f"{query}\n")
                agent_proc.stdin.flush()
                agent_pid = agent_proc.pid
                logger.info(
                    "Actively dispatched query to running AI agent process stdin",
                    session_id=session_id,
                    pid=agent_pid,
                    query=query,
                    bytes_sent=bytes_sent,
                )
            except Exception as e:
                logger.error("Failed writing query to agent stdin", session_id=session_id, error=str(e))
                raise AgentRunnerError(f"Failed to transmit query to AI agent stdin: {str(e)}")
        else:
            # If no active agent process is running, spawn dedicated CLI agent subprocess for query dispatch
            logger.info(
                "No persistent agent process running; spawning dedicated agent CLI subprocess for query dispatch",
                session_id=session_id,
                working_dir=working_dir,
            )
            binary_path = self.resolve_binary()
            cmd = [binary_path, "--dangerously-skip-permissions", "--model", active_model]
            isolated_env = sandbox.build_isolated_environment(working_dir)

            try:
                agent_proc = await asyncio.to_thread(
                    subprocess.Popen,
                    cmd,
                    cwd=working_dir,
                    env=isolated_env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except Exception as e:
                logger.error("Failed to spawn CLI AI agent process for query dispatch", session_id=session_id, error=str(e))
                raise AgentRunnerError(f"Failed to spawn CLI AI agent process: {str(e)}")

            sandbox.register_process(agent_proc)
            setattr(sandbox, "agent_process", agent_proc)
            setattr(sandbox, "agent_pid", agent_proc.pid)
            agent_pid = agent_proc.pid
            communication_mode = "subprocess_invocation"

            await asyncio.sleep(0.05)
            if agent_proc.poll() is not None:
                rc = agent_proc.returncode
                err = sandbox.get_agent_stderr() or ""
                raise AgentRunnerError(f"Spawned AI agent process (PID: {agent_pid}) died immediately on launch with exit code {rc}. Stderr: {err[:300].strip() or 'None'}")

            if not agent_proc.stdin or agent_proc.stdin.closed:
                raise AgentRunnerError(f"Spawned AI agent process (PID: {agent_pid}) stdin is closed.")
            try:
                agent_proc.stdin.write(f"{query}\n")
                agent_proc.stdin.flush()
                logger.info(
                    "Spawned agent subprocess and piped query to stdin",
                    session_id=session_id,
                    pid=agent_pid,
                    query=query,
                    bytes_sent=bytes_sent,
                )
            except Exception as e:
                logger.error("Failed writing query to spawned agent stdin", session_id=session_id, error=str(e))
                raise AgentRunnerError(f"Failed to transmit query to spawned AI agent stdin: {str(e)}")

        setattr(sandbox, "query_dispatched", True)
        setattr(sandbox, "communication_mode", communication_mode)
        setattr(sandbox, "bytes_sent", bytes_sent)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Step 5: Query dispatched to CLI AI agent",
            session_id=session_id,
            query=query,
            model=active_model,
            skill="repo-analyzer",
            working_dir=working_dir,
            communication_mode=communication_mode,
            pid=agent_pid,
            duration_ms=duration_ms,
        )

        return {
            "session_id": session_id,
            "query": query,
            "model_used": active_model,
            "working_dir": working_dir,
            "skill_name": "repo-analyzer",
            "communication_mode": communication_mode,
            "agent_pid": agent_pid,
            "bytes_sent": bytes_sent,
            "timestamp": timestamp,
            "duration_ms": duration_ms,
            "status": "dispatched",
        }

    async def load_skill(
        self,
        session_id: str,
        skill_name: str = "repo-analyzer",
    ) -> dict[str, Any]:
        """
        Step 6: The AI agent loads and applies the repo-analyzer skill.
        Validates skill files, extracts checklist rules across the 4 evaluation pillars
        (Architecture, Ideology, Methodology, Software Principles),
        and verifies the report output JSON schema.
        """
        start_time = time.perf_counter()

        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise AgentRunnerError(f"Session sandbox '{session_id}' not found or already closed.")

        try:
            clean_skill = validate_skill_name_security(skill_name)
        except SandboxError as e:
            raise AgentRunnerError(str(e))

        # Ensure skill is mounted in sandbox
        mounted_skill_dir = sandbox.mount_skill(clean_skill)
        if not mounted_skill_dir or not os.path.exists(mounted_skill_dir):
            real_root = os.path.realpath(sandbox.root_dir)
            allowed_candidate_roots = [
                os.path.realpath(os.path.join(real_root, ".agents", "skills")),
                os.path.realpath(os.path.join(os.getcwd(), ".agents", "skills")),
                os.path.realpath(os.path.expanduser("~/.agents/skills")),
            ]
            for cand_root in allowed_candidate_roots:
                candidate = os.path.realpath(os.path.join(cand_root, clean_skill))
                try:
                    if os.path.commonpath([cand_root, candidate]) == cand_root and os.path.exists(candidate):
                        mounted_skill_dir = candidate
                        break
                except ValueError:
                    pass

        if not mounted_skill_dir or not os.path.exists(mounted_skill_dir):
            raise AgentRunnerError(f"Skill '{clean_skill}' could not be located in sandbox or system.")

        skill_md_path = os.path.join(mounted_skill_dir, "SKILL.md")
        if not os.path.exists(skill_md_path):
            raise AgentRunnerError(f"Skill '{skill_name}' is missing required SKILL.md entrypoint.")

        # Parse 4 evaluation pillars from references/
        references_dir = os.path.join(mounted_skill_dir, "references")
        if not os.path.exists(references_dir):
            raise AgentRunnerError(f"Skill '{skill_name}' is missing 'references' directory.")

        pillar_files = {
            "Architecture": "architecture.md",
            "Ideology": "ideology.md",
            "Methodology": "methodology.md",
            "Software Principles": "principles.md",
        }

        pillar_breakdowns = []
        total_rules = 0

        for pillar_name, file_name in pillar_files.items():
            ref_path = os.path.join(references_dir, file_name)
            if not os.path.exists(ref_path):
                raise AgentRunnerError(f"Skill '{skill_name}' is missing pillar reference file: {file_name}")

            with open(ref_path, "r", encoding="utf-8") as f:
                content = f.read()

            focus_match = re.search(r"^Focus:\s*(.+)$", content, re.MULTILINE)
            focus = focus_match.group(1).strip() if focus_match else "Architectural analysis"

            checklist_match = re.search(r"##\s+Evaluation checklist[^\n]*\n([\s\S]*?)(?=\n##|\Z)", content)
            items = []
            if checklist_match:
                items = re.findall(r"^\s*\d+\.\s+(.+)$", checklist_match.group(1), re.MULTILINE)

            total_rules += len(items)
            pillar_breakdowns.append({
                "pillar": pillar_name,
                "rules_count": len(items),
                "focus": focus,
                "items": items,
            })

        # Parse & verify schemas/report_schema.json
        schema_path = os.path.join(mounted_skill_dir, "schemas", "report_schema.json")
        schema_valid = False
        schema_title = "Unknown"
        if os.path.exists(schema_path):
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_json = json.load(f)
                schema_title = schema_json.get("title", "RepoAnalyzerReport")
                schema_valid = True
            except Exception as e:
                logger.warning("Report schema validation failed", error=str(e))

        # Store loaded skill state on the session sandbox
        setattr(sandbox, "skill_loaded", True)
        setattr(sandbox, "active_skill", skill_name)
        setattr(sandbox, "loaded_skill_dir", mounted_skill_dir)
        setattr(sandbox, "skill_pillars", [p["pillar"] for p in pillar_breakdowns])
        setattr(sandbox, "skill_rules_count", total_rules)
        setattr(sandbox, "skill_breakdowns", pillar_breakdowns)
        setattr(sandbox, "schema_valid", schema_valid)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Step 6: Skill loaded and applied",
            session_id=session_id,
            skill=skill_name,
            pillars=len(pillar_breakdowns),
            total_rules=total_rules,
            duration_ms=duration_ms,
        )

        return {
            "session_id": session_id,
            "skill_name": skill_name,
            "skill_dir": mounted_skill_dir,
            "pillars_loaded": [p["pillar"] for p in pillar_breakdowns],
            "total_rules_count": total_rules,
            "pillar_breakdowns": pillar_breakdowns,
            "schema_valid": schema_valid,
            "schema_title": schema_title,
            "duration_ms": duration_ms,
            "status": "loaded",
        }

    async def _wait_for_agent_output(self, sandbox: Any, timeout: float = 120.0, pid: Optional[int] = None) -> str:
        """
        Polls the background stream consumer for accumulated stdout until either
        the agent process finishes execution or timeout expires. Returns all collected stdout.
        """
        if not sandbox:
            return ""

        start = time.perf_counter()
        target_pid = pid or getattr(sandbox, "agent_pid", None)
        proc = getattr(sandbox, "agent_process", None)

        while time.perf_counter() - start < timeout:
            if proc and proc.poll() is not None:
                # Agent process completed execution, give brief moment for background stream reader to flush final chunk
                await asyncio.sleep(0.3)
                return sandbox.get_process_stdout(target_pid) if target_pid else sandbox.get_agent_stdout()

            # Early exit ONLY if full output is already completely received and validly parseable
            buffered = sandbox.get_process_stdout(target_pid) if target_pid else sandbox.get_agent_stdout()
            if buffered and ('"status":"SUCCESS"' in buffered or '"status": "SUCCESS"' in buffered) and '"pillars"' in buffered:
                try:
                    envelope = json.loads(buffered.strip())
                    if isinstance(envelope, dict) and envelope.get("status") == "SUCCESS":
                        if "structured_output" in envelope and isinstance(envelope["structured_output"], dict):
                            return buffered
                        resp = envelope.get("response", "")
                        if isinstance(resp, str) and resp.strip():
                            json.loads(resp.strip())
                            return buffered
                except Exception:
                    # Still receiving stream chunks, continue loop
                    pass

            await asyncio.sleep(0.2)

        # Timeout reached: terminate process if still running
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            await asyncio.sleep(0.1)

        return sandbox.get_process_stdout(target_pid) if target_pid else sandbox.get_agent_stdout()

    def _read_process_stdout(self, proc: Any, timeout: float = 3.0, sandbox: Optional[Any] = None) -> str:
        """
        Safely retrieve available stdout from a running subprocess.
        Checks sandbox background stream consumer first, otherwise non-blocking pipe read.
        """
        if sandbox and hasattr(sandbox, "get_process_stdout"):
            pid = getattr(proc, "pid", None)
            buffered = sandbox.get_process_stdout(pid)
            if buffered:
                return buffered

        if not proc or not hasattr(proc, "stdout") or not proc.stdout:
            return ""

        collected: list[str] = []
        start = time.perf_counter()

        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            import msvcrt

            try:
                handle = msvcrt.get_osfhandle(proc.stdout.fileno())
            except Exception:
                return ""

            while time.perf_counter() - start < timeout:
                avail = wintypes.DWORD()
                success = ctypes.windll.kernel32.PeekNamedPipe(
                    handle, None, 0, None, ctypes.byref(avail), None
                )
                if success and avail.value > 0:
                    chunk = proc.stdout.read(avail.value)
                    if chunk:
                        collected.append(chunk)
                elif proc.poll() is not None:
                    try:
                        remaining = proc.stdout.read()
                        if remaining:
                            collected.append(remaining)
                    except Exception:
                        pass
                    break
                else:
                    time.sleep(0.05)
        else:
            import select
            while time.perf_counter() - start < timeout:
                r, _, _ = select.select([proc.stdout], [], [], 0.05)
                if r:
                    line = proc.stdout.readline()
                    if not line:
                        break
                    collected.append(line)
                elif proc.poll() is not None:
                    break

        return "".join(collected)

    def _detect_agent_rejection(self, stdout: str, stderr: str) -> Optional[str]:
        """
        Detect if the CLI AI agent explicitly rejected the command, directive, or arguments.
        """
        combined = f"{stderr}\n{stdout}".lower()
        rejection_indicators = [
            "flag provided but not defined",
            "unknown flag",
            "unknown command",
            "command not found",
            "unrecognized command",
            "command rejected",
            "directive rejected",
            "permission denied",
            "access denied",
            "invalid argument",
            "invalid option",
            "usage: agy",
            "unknown shorthand flag",
        ]
        for pattern in rejection_indicators:
            if pattern in combined:
                for line in f"{stderr}\n{stdout}".splitlines():
                    if pattern in line.lower():
                        return line.strip()
                return f"Rejection pattern detected: {pattern}"
        return None

    def _detect_model_unavailability(self, stdout: str, stderr: str) -> Optional[str]:
        """
        Detect if the requested AI model is unavailable, quota is exhausted, or authentication failed.
        """
        combined = f"{stderr}\n{stdout}".lower()
        model_error_indicators = [
            "not logged into antigravity",
            "you are not logged into",
            "auth mode is unspecified",
            "error getting token source",
            "token source",
            "failed to get load code assist response",
            "model unavailable",
            "model is unavailable",
            "model not found",
            "does not exist",
            "quota exceeded",
            "resource_exhausted",
            "rate limit",
            "insufficient_quota",
            "unauthenticated",
            "unauthorized",
            "api key not set",
            "invalid api key",
            "authentication failed",
            "service unavailable",
            "model_not_found",
            "overloaded",
            "no capacity available",
        ]
        for pattern in model_error_indicators:
            if pattern in combined:
                for line in f"{stderr}\n{stdout}".splitlines():
                    if pattern in line.lower():
                        return line.strip()
                return f"Model/Auth error detected: {pattern}"
        return None

    def _parse_and_validate_ai_output(
        self,
        raw_text: str,
        repo_name: str,
        working_dir: str,
        active_model: str,
        ai_evaluator: str,
    ) -> Optional[dict[str, Any]]:
        """
        Parses and validates the AI agent's raw stdout output against schemas/report_schema.json.
        Extracts structured JSON payload from raw text, code fences, or agy response wrapper.
        """
        if not raw_text or not raw_text.strip():
            return None

        candidate_str = raw_text.strip()

        parsed: Optional[dict[str, Any]] = None

        # Handle agy JSON output envelope {"response": "...", "status": "SUCCESS", "structured_output": {...}}
        try:
            envelope = json.loads(candidate_str)
            if isinstance(envelope, dict):
                if "structured_output" in envelope and isinstance(envelope["structured_output"], dict):
                    parsed = envelope["structured_output"]
                elif "response" in envelope and isinstance(envelope["response"], str):
                    inner = envelope["response"].strip()
                    if inner:
                        candidate_str = inner
        except Exception:
            pass

        if parsed is None:
            # Extract markdown code fence if present ```json ... ```
            code_fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", candidate_str)
            if code_fence_match:
                candidate_str = code_fence_match.group(1).strip()
            else:
                json_obj_match = re.search(r"(\{[\s\S]*\})", candidate_str)
                if json_obj_match:
                    candidate_str = json_obj_match.group(1).strip()

            try:
                parsed = json.loads(candidate_str)
            except Exception:
                return None

        if not isinstance(parsed, dict):
            return None

        metadata = parsed.get("metadata", {}) if isinstance(parsed.get("metadata"), dict) else {}
        exec_summary = parsed.get("executiveSummary") or parsed.get("executive_summary") or ""
        overall_score = metadata.get("overallScore") or parsed.get("overallScore") or parsed.get("overall_score") or 0
        grade = metadata.get("grade") or parsed.get("grade") or "B"
        arch_pattern = (
            metadata.get("primaryArchitecturePattern")
            or parsed.get("primaryArchitecturePattern")
            or parsed.get("primary_architecture_pattern")
            or "Modular Architecture"
        )
        primary_lang = metadata.get("primaryLanguage") or parsed.get("primaryLanguage") or parsed.get("primary_language") or "Unknown"
        secondary_langs = metadata.get("secondaryLanguages") or parsed.get("secondaryLanguages") or parsed.get("secondary_languages") or []
        pillars_raw = parsed.get("pillars", [])

        if not isinstance(pillars_raw, list) or len(pillars_raw) == 0:
            return None

        pillars = []
        for p in pillars_raw:
            if not isinstance(p, dict):
                continue
            title = p.get("title", "Unknown")
            score = int(p.get("score", 75))
            status = p.get("status", "good")
            summary = p.get("summary", "")
            key_strengths = p.get("keyStrengths") or p.get("strengths") or []
            anti_patterns = p.get("antiPatterns") or p.get("anti_patterns") or []
            checklist_raw = p.get("checklist", [])
            checklist = []
            for c in checklist_raw:
                if isinstance(c, dict):
                    checklist.append({
                        "label": str(c.get("label", "")),
                        "passed": bool(c.get("passed", False)),
                        "note": str(c.get("note", "")),
                    })
            pillars.append({
                "title": title,
                "score": score,
                "status": status,
                "summary": summary,
                "keyStrengths": key_strengths,
                "antiPatterns": anti_patterns,
                "checklist": checklist,
            })

        if len(pillars) < 4:
            return None

        return {
            "repo_name": repo_name,
            "working_dir": working_dir,
            "primary_language": primary_lang,
            "secondary_languages": secondary_langs,
            "primary_architecture_pattern": arch_pattern,
            "overall_score": int(overall_score),
            "grade": str(grade),
            "executive_summary": exec_summary,
            "pillars": pillars,
            "ai_agent_invoked": True,
            "ai_analysis_used": True,
            "ai_analysis_source": "agy_stdout",
            "ai_agent_model": active_model,
            "ai_agent_evaluator": ai_evaluator,
            "raw_markdown": parsed.get("rawMarkdown") or parsed.get("raw_markdown") or "",
        }

    async def perform_analysis(self, session_id: str) -> dict[str, Any]:
        """
        Step 7: The AI agent analyzes the repository according to the instructions
        defined in the repo-analyzer skill and its configuration.
        Actively dispatches the instruction, reads stdout from the agent, parses,
        validates against schemas/report_schema.json, and builds the report from the AI output.
        """
        start_time = time.perf_counter()

        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise AgentRunnerError(f"Session sandbox '{session_id}' not found or already closed.")

        working_dir = sandbox.get_working_directory()
        if not os.path.exists(working_dir):
            raise AgentRunnerError(f"Working directory does not exist: '{working_dir}'")

        # Ensure skill is loaded
        if not getattr(sandbox, "skill_loaded", False):
            await self.load_skill(session_id, "repo-analyzer")

        repo_name = getattr(sandbox, "repo_name", os.path.basename(working_dir))
        active_model = getattr(sandbox, "active_model", self.DEFAULT_MODEL)
        binary_path = self.resolve_binary()
        version = self.get_agent_version(binary_path)
        ai_evaluator = f"Antigravity CLI Agent ({version}) [{active_model}]"

        # Terminate any previous idle process from Step 4 if still running
        old_proc = getattr(sandbox, "agent_process", None)
        if old_proc and old_proc.poll() is None:
            try:
                old_proc.terminate()
                try:
                    await asyncio.to_thread(old_proc.wait, timeout=1.0)
                except Exception:
                    old_proc.kill()
                    await asyncio.to_thread(old_proc.wait, timeout=1.0)
            except Exception:
                pass

        # Locate report schema path
        loaded_skill_dir = getattr(sandbox, "loaded_skill_dir", None)
        schema_path = None
        if loaded_skill_dir:
            cand = os.path.join(loaded_skill_dir, "schemas", "report_schema.json")
            if os.path.exists(cand):
                schema_path = cand
        if not schema_path:
            cand = os.path.realpath(os.path.expanduser("~/.agents/skills/repo-analyzer/schemas/report_schema.json"))
            if os.path.exists(cand):
                schema_path = cand

        # Collect codebase structural metrics and evidence to ground the AI evaluation
        evidence_lines = []
        try:
            inspection_evidence = await asyncio.to_thread(repo_inspector.inspect_codebase, working_dir)
            if inspection_evidence:
                top_langs = [f"{k} ({v} files)" for k, v in inspection_evidence.get("file_counts", {}).items()][:4]
                if top_langs:
                    evidence_lines.append(f"Languages: {', '.join(top_langs)}")
                top_entries = inspection_evidence.get("top_level_entries", [])[:15]
                if top_entries:
                    evidence_lines.append(f"Top-level entries: {', '.join(top_entries)}")
                frameworks = inspection_evidence.get("frameworks", [])
                if frameworks:
                    evidence_lines.append(f"Detected stacks/frameworks: {', '.join(frameworks)}")
                ci_configs = inspection_evidence.get("ci_cd_configs", [])
                if ci_configs:
                    evidence_lines.append(f"CI/CD configs: {', '.join(ci_configs)}")
        except Exception:
            pass

        codebase_context = ""
        if evidence_lines:
            codebase_context = "Codebase context:\n" + "\n".join(f"- {line}" for line in evidence_lines) + "\n\n"

        # Extract checklist guidance from loaded skill if available
        skill_breakdowns = getattr(sandbox, "skill_breakdowns", [])
        pillar_hints = ""
        if skill_breakdowns:
            pillar_hints = "Audit criteria by pillar:\n"
            for pb in skill_breakdowns:
                pillar_hints += f"- {pb['pillar']} ({pb.get('focus', '')}): " + ", ".join(pb.get("items", [])[:5]) + "\n"

        analysis_instruction = (
            f"Analyze the repository '{repo_name}' located at '{working_dir}' using the repo-analyzer skill.\n\n"
            f"{codebase_context}"
            f"Audit the codebase across all 4 pillars: Architecture, Ideology, Methodology, and Software Principles.\n\n"
            f"{pillar_hints}\n"
            "Conclude your evaluation and output strictly as a JSON object adhering to schemas/report_schema.json with "
            "executiveSummary, metadata (overallScore, grade, primaryArchitecturePattern, primaryLanguage, secondaryLanguages), and pillars."
        )

        analysis_timeout = float(os.getenv("REPO_ANALYZER_ANALYSIS_TIMEOUT", "120.0"))

        cmd = [
            binary_path,
            "--dangerously-skip-permissions",
            "--model", active_model,
            "--output-format", "json",
            "--print-timeout", f"{int(analysis_timeout)}s",
        ]
        if schema_path and os.path.exists(schema_path):
            cmd.extend(["--json-schema", schema_path])
        cmd.extend(["--print", analysis_instruction])

        isolated_env = sandbox.build_isolated_environment(working_dir)

        logger.info(
            "Step 7: Launching non-interactive AI agent analysis via print mode",
            session_id=session_id,
            repo_name=repo_name,
            model=active_model,
            timeout=analysis_timeout,
            schema_enforced=bool(schema_path),
        )

        try:
            agent_proc = await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                cwd=working_dir,
                env=isolated_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception as e:
            logger.error("Failed to spawn CLI AI agent process for Step 7", session_id=session_id, error=str(e))
            raise AgentRunnerError(f"Failed to spawn CLI AI agent process: {str(e)}")

        sandbox.register_process(agent_proc)
        setattr(sandbox, "agent_process", agent_proc)
        setattr(sandbox, "agent_pid", agent_proc.pid)

        # Await AI agent completion or timeout from background stream consumer
        raw_stdout = await self._wait_for_agent_output(sandbox, timeout=analysis_timeout, pid=agent_proc.pid)
        raw_stderr = sandbox.get_process_stderr(agent_proc.pid) or sandbox.get_agent_stderr()

        # 5. Check if AI process died during execution
        if agent_proc.poll() is not None and agent_proc.returncode != 0:
            err_msg = (
                sandbox.get_process_stderr(agent_proc.pid).strip()
                or sandbox.get_process_stdout(agent_proc.pid).strip()
                or raw_stderr[:300].strip()
                or (raw_stdout[:300].strip() if raw_stdout else "None")
            )
            logger.error(
                "AI agent process died during analysis execution",
                session_id=session_id,
                pid=agent_proc.pid,
                exit_code=agent_proc.returncode,
                error=err_msg,
            )
            raise AgentRunnerError(
                f"AI agent process (PID: {agent_proc.pid}) died during analysis execution with exit code {agent_proc.returncode}. Error: {err_msg}"
            )

        # 6. Check if agent rejected the command
        rejection_reason = self._detect_agent_rejection(raw_stdout, raw_stderr)
        if rejection_reason:
            logger.error("AI agent rejected the analysis command", session_id=session_id, reason=rejection_reason)
            raise AgentRunnerError(f"AI agent rejected analysis directive: {rejection_reason}")

        # 7. Check if model is unavailable
        model_error = self._detect_model_unavailability(raw_stdout, raw_stderr)
        if model_error:
            logger.error("AI agent model is unavailable", session_id=session_id, model=active_model, error=model_error)
            raise AgentRunnerError(f"AI agent model '{active_model}' is unavailable: {model_error}")

        # 8. Attempt to parse and validate AI analysis output from stdout
        ai_inspection = self._parse_and_validate_ai_output(
            raw_stdout, repo_name, working_dir, active_model, ai_evaluator
        )

        if not ai_inspection:
            sample_err = raw_stderr[:300].strip() if raw_stderr else (raw_stdout[:300].strip() if raw_stdout else "No output received from agent")
            logger.error(
                "AI agent failed to generate valid repository analysis JSON output",
                session_id=session_id,
                stdout_len=len(raw_stdout),
                sample=sample_err,
            )
            raise AgentRunnerError(
                f"AI agent failed to produce valid repository analysis output adhering to schemas/report_schema.json. Agent output: {sample_err}"
            )

        inspection = ai_inspection
        logger.info(
            "Step 7: AI agent analysis output successfully read from stdout, parsed, and validated",
            session_id=session_id,
            overall_score=inspection["overall_score"],
            grade=inspection["grade"],
            source=inspection["ai_analysis_source"],
        )

        # Compute rules summary
        total_rules = 0
        passed_rules = 0
        pillar_scores: dict[str, int] = {}

        for p in inspection["pillars"]:
            pillar_scores[p["title"]] = p["score"]
            for item in p["checklist"]:
                total_rules += 1
                if item["passed"]:
                    passed_rules += 1

        failed_rules = total_rules - passed_rules

        # Store results in sandbox
        setattr(sandbox, "analysis_result", inspection)
        setattr(sandbox, "analysis_completed", True)
        if raw_stdout:
            setattr(sandbox, "ai_raw_stdout", raw_stdout)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Step 7: Repository analysis complete",
            session_id=session_id,
            repo_name=repo_name,
            overall_score=inspection["overall_score"],
            grade=inspection["grade"],
            total_rules=total_rules,
            passed_rules=passed_rules,
            duration_ms=duration_ms,
        )

        return {
            "session_id": session_id,
            "repo_name": repo_name,
            "working_dir": working_dir,
            "primary_language": inspection["primary_language"],
            "secondary_languages": inspection["secondary_languages"],
            "detected_architecture": inspection["primary_architecture_pattern"],
            "overall_score": inspection["overall_score"],
            "grade": inspection["grade"],
            "pillar_scores": pillar_scores,
            "total_rules_evaluated": total_rules,
            "passed_rules_count": passed_rules,
            "failed_rules_count": failed_rules,
            "executive_summary": inspection["executive_summary"],
            "pillars": inspection["pillars"],
            "ai_agent_invoked": True,
            "ai_analysis_used": True,
            "ai_analysis_source": inspection.get("ai_analysis_source", "agy_stdout"),
            "ai_agent_model": active_model,
            "ai_agent_evaluator": ai_evaluator,
            "status": "analyzed",
            "duration_ms": duration_ms,
        }

    async def generate_report(self, session_id: str) -> dict[str, Any]:
        """
        Step 8: Generate formatted output strictly according to the format
        and requirements specified by the repo-analyzer skill.
        Produces schema-compliant JSON and human-readable raw markdown synthesis.
        """
        # Ensure analysis was executed
        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise AgentRunnerError(f"Session sandbox '{session_id}' not found or already closed.")

        if not getattr(sandbox, "analysis_completed", False):
            await self.perform_analysis(session_id)

        return await asyncio.to_thread(report_generator.generate_report, session_id)


agent_runner = AgentRunner()

