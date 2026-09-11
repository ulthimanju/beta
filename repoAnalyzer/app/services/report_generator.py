import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional
from app.core.logging import get_logger
from app.services.sandbox_manager import sandbox_manager

logger = get_logger("report_generator")


class ReportGeneratorError(Exception):
    """Exception raised when report formatting or generation fails."""
    pass


class ReportGenerator:
    """
    Step 8: Generates formatted output strictly according to the format and
    requirements specified by the repo-analyzer skill and configuration.
    Produces:
    1. Schema-validated machine-readable JSON matching schemas/report_schema.json.
    2. Full human-readable raw Markdown synthesis without excluded appendices.
    3. Frontend dashboard payload for SPA visualization.
    """

    def generate_report(self, session_id: str) -> dict[str, Any]:
        start_time = time.perf_counter()

        sandbox = sandbox_manager.get_sandbox(session_id)
        if not sandbox:
            raise ReportGeneratorError(f"Session sandbox '{session_id}' not found or already closed.")

        analysis = getattr(sandbox, "analysis_result", None)
        if not analysis:
            raise ReportGeneratorError(
                f"Repository analysis (Step 7) has not been performed yet for session '{session_id}'."
            )

        repo_name = getattr(sandbox, "repo_name", os.path.basename(sandbox.get_working_directory()))
        repo_url = getattr(sandbox, "repo_url", f"https://github.com/owner/{repo_name}")
        commit_hash = getattr(sandbox, "commit_hash", "HEAD")
        branch = getattr(sandbox, "branch", "main")
        analyzed_at = datetime.now(timezone.utc).isoformat()

        exec_summary = analysis.get("executive_summary") or analysis.get("executiveSummary") or ""
        overall_score = analysis.get("overall_score")
        if overall_score is None and isinstance(analysis.get("metadata"), dict):
            overall_score = analysis["metadata"].get("overallScore")
        if overall_score is None:
            overall_score = analysis.get("overallScore", 0)

        grade = analysis.get("grade")
        if not grade and isinstance(analysis.get("metadata"), dict):
            grade = analysis["metadata"].get("grade")
        if not grade:
            grade = analysis.get("grade", "B")

        arch_pattern = analysis.get("primary_architecture_pattern")
        if not arch_pattern and isinstance(analysis.get("metadata"), dict):
            arch_pattern = analysis["metadata"].get("primaryArchitecturePattern")
        if not arch_pattern:
            arch_pattern = analysis.get("primaryArchitecturePattern", "Modular Architecture")

        primary_lang = analysis.get("primary_language")
        if not primary_lang and isinstance(analysis.get("metadata"), dict):
            primary_lang = analysis["metadata"].get("primaryLanguage")
        if not primary_lang:
            primary_lang = analysis.get("primaryLanguage", "Unknown")

        secondary_langs = analysis.get("secondary_languages")
        if secondary_langs is None and isinstance(analysis.get("metadata"), dict):
            secondary_langs = analysis["metadata"].get("secondaryLanguages")
        if secondary_langs is None:
            secondary_langs = analysis.get("secondaryLanguages", [])

        pillars = analysis.get("pillars", [])

        # 1. Build Raw Markdown Synthesis (prefer AI-generated rawMarkdown if present)
        raw_markdown = analysis.get("raw_markdown") or analysis.get("rawMarkdown")
        if not raw_markdown:
            raw_markdown = self._synthesize_markdown(
                repo_name=repo_name,
                overall_score=overall_score,
                grade=grade,
                arch_pattern=arch_pattern,
                primary_lang=primary_lang,
                secondary_langs=secondary_langs,
                exec_summary=exec_summary,
                pillars=pillars,
            )

        # 2. Build Schema-Compliant JSON matching schemas/report_schema.json
        schema_json: dict[str, Any] = {
            "executiveSummary": exec_summary,
            "metadata": {
                "overallScore": overall_score,
                "grade": grade,
                "primaryArchitecturePattern": arch_pattern,
                "primaryLanguage": primary_lang,
                "secondaryLanguages": secondary_langs,
            },
            "pillars": [
                {
                    "title": p["title"],
                    "score": p["score"],
                    "status": p["status"],
                    "summary": p["summary"],
                    "keyStrengths": p["keyStrengths"],
                    "antiPatterns": p["antiPatterns"],
                    "checklist": [
                        {
                            "label": c["label"],
                            "passed": c["passed"],
                            "note": c["note"],
                        }
                        for c in p["checklist"]
                    ],
                }
                for p in pillars
            ],
            "rawMarkdown": raw_markdown,
        }

        # Validate against report_schema.json if available
        schema_valid = self._validate_schema(schema_json, sandbox)

        # 3. Build Frontend-Compatible AnalysisReport structure
        pillar_map = {}
        for p in pillars:
            key = p["title"].lower().replace(" ", "_")
            if "software" in key or "principle" in key:
                key = "principles"
            pillar_map[key] = {
                "title": p["title"],
                "score": p["score"],
                "status": p["status"],
                "summary": p["summary"],
                "strengths": p["keyStrengths"],
                "antiPatterns": p["antiPatterns"],
                "checklist": p["checklist"],
            }

        frontend_report = {
            "repoUrl": repo_url,
            "repoName": repo_name,
            "analyzedAt": analyzed_at,
            "commitHash": commit_hash[:8] if len(commit_hash) >= 8 else commit_hash,
            "branch": branch,
            "primaryLanguage": primary_lang,
            "overallScore": overall_score,
            "grade": grade,
            "primaryArchitecture": arch_pattern,
            "executiveSummary": exec_summary,
            "pillars": {
                "architecture": pillar_map.get("architecture", {}),
                "ideology": pillar_map.get("ideology", {}),
                "methodology": pillar_map.get("methodology", {}),
                "principles": pillar_map.get("principles", {}),
            },
            "rawMarkdownOutput": raw_markdown,
        }

        # Store generated report on the sandbox
        setattr(sandbox, "generated_report", schema_json)
        setattr(sandbox, "frontend_report", frontend_report)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Step 8 complete: Report formatted and generated",
            session_id=session_id,
            repo_name=repo_name,
            schema_valid=schema_valid,
            overall_score=overall_score,
            duration_ms=duration_ms,
        )

        return {
            "session_id": session_id,
            "repo_name": repo_name,
            "schema_valid": schema_valid,
            "schema_json": schema_json,
            "frontend_report": frontend_report,
            "duration_ms": duration_ms,
            "status": "generated",
        }

    def _synthesize_markdown(
        self,
        repo_name: str,
        overall_score: int,
        grade: str,
        arch_pattern: str,
        primary_lang: str,
        secondary_langs: list[str],
        exec_summary: str,
        pillars: list[dict[str, Any]],
    ) -> str:
        """Synthesizes human-readable markdown strictly following SKILL.md Step 5."""
        lines: list[str] = []

        lines.append(f"# Codebase & Architecture Audit: {repo_name}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(exec_summary)
        lines.append("")
        lines.append("## Metadata")
        lines.append(f"- **Overall Score**: {overall_score}/100")
        lines.append(f"- **Grade**: {grade}")
        lines.append(f"- **Primary Architecture Pattern**: {arch_pattern}")
        lines.append(f"- **Primary Language**: {primary_lang}")
        if secondary_langs:
            lines.append(f"- **Secondary Languages**: {', '.join(secondary_langs)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for idx, pillar in enumerate(pillars, start=1):
            lines.append(f"## Pillar {idx}: {pillar['title']}")
            lines.append(f"- **Score**: {pillar['score']}/100 (`{pillar['status']}`)")
            lines.append(f"- **Summary**: {pillar['summary']}")
            lines.append("")

            lines.append("### Key Strengths")
            if pillar.get("keyStrengths"):
                for s in pillar["keyStrengths"]:
                    lines.append(f"- {s}")
            else:
                lines.append("- Baseline adherence observed across surveyed files.")
            lines.append("")

            lines.append("### Anti-Patterns / Violations Identified")
            if pillar.get("antiPatterns"):
                for a in pillar["antiPatterns"]:
                    lines.append(f"- {a}")
            else:
                lines.append("- None identified in standard audit scope.")
            lines.append("")

            lines.append("### Evaluation Checklist")
            for c in pillar["checklist"]:
                mark = "[x]" if c["passed"] else "[ ]"
                lines.append(f"- {mark} **{c['label']}**: {c['note']}")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines).strip()

    def _validate_schema(self, payload: dict[str, Any], sandbox: Any) -> bool:
        """Verifies output complies with report_schema.json requirements."""
        required_keys = {"executiveSummary", "metadata", "pillars", "rawMarkdown"}
        if not required_keys.issubset(payload.keys()):
            return False

        meta_keys = {"overallScore", "grade", "primaryArchitecturePattern", "primaryLanguage"}
        if not meta_keys.issubset(payload["metadata"].keys()):
            return False

        if len(payload["pillars"]) != 4:
            return False

        for p in payload["pillars"]:
            pillar_keys = {"title", "score", "status", "summary", "keyStrengths", "antiPatterns", "checklist"}
            if not pillar_keys.issubset(p.keys()):
                return False
            for item in p["checklist"]:
                item_keys = {"label", "passed", "note"}
                if not item_keys.issubset(item.keys()):
                    return False

        return True


report_generator = ReportGenerator()
