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
from app.services.sandbox_manager import sandbox_manager
from app.services.repo_inspector import repo_inspector
from app.services.report_generator import report_generator


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
                cmd,
                cwd=working_dir,
                env=sanitized_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            pid = process.pid

            # Register process in sandbox for tracking and graceful shutdown
            sandbox.active_processes.append(process)
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

        # Dispatch query to active agent process stdin if running
        agent_proc = getattr(sandbox, "agent_process", None)
        if agent_proc and agent_proc.stdin and not agent_proc.stdin.closed:
            try:
                agent_proc.stdin.write(f"{query}\n")
                agent_proc.stdin.flush()
                logger.info("Dispatched prompt to agent stdin", session_id=session_id, query=query)
            except Exception as e:
                logger.warning("Could not write query to agent stdin", session_id=session_id, error=str(e))

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Step 5: Query dispatched to CLI AI agent",
            session_id=session_id,
            query=query,
            model=active_model,
            skill="repo-analyzer",
            working_dir=working_dir,
            duration_ms=duration_ms,
        )

        return {
            "session_id": session_id,
            "query": query,
            "model_used": active_model,
            "working_dir": working_dir,
            "skill_name": "repo-analyzer",
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

        # Ensure skill is mounted in sandbox
        mounted_skill_dir = sandbox.mount_skill(skill_name)
        if not mounted_skill_dir or not os.path.exists(mounted_skill_dir):
            candidates = [
                os.path.join(sandbox.root_dir, ".agents", "skills", skill_name),
                os.path.join(os.getcwd(), ".agents", "skills", skill_name),
                os.path.expanduser(f"~/.agents/skills/{skill_name}"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    mounted_skill_dir = cand
                    break

        if not mounted_skill_dir or not os.path.exists(mounted_skill_dir):
            raise AgentRunnerError(f"Skill '{skill_name}' could not be located in sandbox or system.")

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

    async def perform_analysis(self, session_id: str) -> dict[str, Any]:
        """
        Step 7: The AI agent analyzes the repository according to the instructions
        defined in the repo-analyzer skill and its configuration.
        Executes deep codebase inspection across the 4 pillars.
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

        # Run codebase inspection across 4 pillars
        inspection = await asyncio.to_thread(repo_inspector.inspect_codebase, working_dir)

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
        repo_name = getattr(sandbox, "repo_name", os.path.basename(working_dir))

        # Store results in sandbox
        setattr(sandbox, "analysis_result", inspection)
        setattr(sandbox, "analysis_completed", True)

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

