import re
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


def validate_github_repo_url(v: str) -> str:
    """Validate that the given URL is strictly a valid public GitHub URL."""
    clean_url = v.strip().rstrip("/")
    if clean_url.startswith("-"):
        raise ValueError("Invalid repository URL format. Parameter injection detected.")
    pattern = r"^https?://(www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(\.git)?$"
    match = re.match(pattern, clean_url)
    if not match:
        raise ValueError(
            "Invalid repository URL format. Must be a valid GitHub URL: https://github.com/owner/repository"
        )
    return clean_url


class RepoSubmitRequest(BaseModel):
    """Schema for submitting a GitHub repository URL."""
    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL (e.g. https://github.com/owner/repo)",
        examples=["https://github.com/fastapi/full-stack-fastapi-template"],
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        return validate_github_repo_url(v)


class RepoSubmitResponse(BaseModel):
    """Schema for response when repository URL is received and registered."""
    session_id: str
    repo_url: str
    owner: str
    repo_name: str
    step: int = 1
    step_title: str = "Receive Repository URL"
    status: str = "received"
    message: str
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CloneRepoRequest(BaseModel):
    """Schema for requesting repository clone in Step 2."""
    session_id: str = Field(..., description="Unique session ID from Step 1")
    repo_url: str = Field(..., description="Target repository URL verified in Step 1")

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        return validate_github_repo_url(v)


class CloneRepoResponse(BaseModel):
    """Schema for response when repository is cloned into the Session Sandbox."""
    session_id: str
    repo_url: str
    owner: str
    repo_name: str
    sandbox_root: str
    repo_dir: str
    working_dir: str
    commit_hash: str
    branch: str
    file_count: int
    size_bytes: int
    duration_ms: float
    step: int = 2
    step_title: str = "Clone Repository into Sandbox"
    status: str = "cloned"
    message: str


class SandboxCloseResponse(BaseModel):
    """Schema for response when a session sandbox is destroyed and cleaned up."""
    session_id: str
    status: str
    message: str
    closed_at: str


class SandboxStatsResponse(BaseModel):
    """Schema for inspecting session sandbox state."""
    session_id: str
    status: str
    root_dir: str
    repo_dir: Optional[str]
    working_dir: str
    total_files: int
    size_bytes: int
    created_at: str
    closed_at: Optional[str] = None


class SetWorkingDirRequest(BaseModel):
    """Schema for requesting to set the cloned repo as active working directory (Step 3)."""
    session_id: str = Field(..., description="Unique session ID from Step 1")
    target_subpath: Optional[str] = Field(
        None,
        description="Optional relative subpath inside the sandbox (defaults to cloned repo directory)",
    )


class SetWorkingDirResponse(BaseModel):
    """Schema for response when working directory is validated and set."""
    session_id: str
    sandbox_root: str
    working_dir: str
    relative_working_dir: str
    repo_name: str
    is_git_worktree: bool
    readme_present: bool
    detected_frameworks: list[str]
    top_level_entries: list[str]
    step: int = 3
    step_title: str = "Set Working Directory"
    status: str = "configured"
    message: str


class InvokeAgentRequest(BaseModel):
    """Schema for Step 4: Executing CLI AI agent terminal invocation from repo directory."""
    session_id: str = Field(..., description="Unique session ID from previous steps")
    custom_flags: Optional[list[str]] = Field(
        None,
        description="Optional custom terminal flags passed to the agent CLI invocation",
    )


class InvokeAgentResponse(BaseModel):
    """Schema for response when CLI AI agent is invoked from repository directory."""
    session_id: str
    sandbox_root: str
    working_dir: str
    agent_executable: str
    agent_version: str
    command: str
    default_model: str
    pid: Optional[int]
    status: str = "invoked"
    step: int = 4
    step_title: str = "Execute CLI AI Agent"
    duration_ms: float
    message: str


class DispatchQueryRequest(BaseModel):
    """Schema for Step 5: Dispatching analysis query to the CLI AI agent."""
    session_id: str = Field(..., description="Unique session ID from previous steps")
    query: str = Field(
        default="analyze this repo using repo-analyzer skill",
        description="Query sent to the AI agent using its default model",
    )
    model: Optional[str] = Field(
        None,
        description="Optional model override (defaults to agent's default model: gemini-3.8-flash-medium)",
    )


class DispatchQueryResponse(BaseModel):
    """Schema for response when analysis query is dispatched to the CLI AI agent."""
    session_id: str
    query: str
    model_used: str
    working_dir: str
    skill_name: str
    status: str = "dispatched"
    step: int = 5
    step_title: str = "Dispatch Query"
    timestamp: str
    duration_ms: float
    message: str
    communication_mode: Optional[str] = "stdin_stream"
    agent_pid: Optional[int] = None
    bytes_sent: Optional[int] = None


class PillarRuleInfo(BaseModel):
    """Information regarding an individual evaluation pillar loaded from the skill."""
    pillar: str = Field(..., description="Pillar name (e.g. Architecture, Ideology)")
    rules_count: int = Field(..., description="Number of evaluation checklist rules")
    focus: str = Field(..., description="Core focus areas evaluated")
    items: list[str] = Field(default_factory=list, description="List of checklist rule statements")


class LoadSkillRequest(BaseModel):
    """Schema for Step 6: AI agent loads and applies the repo-analyzer skill."""
    session_id: str = Field(..., description="Unique session ID from previous steps")
    skill_name: str = Field(
        default="repo-analyzer",
        description="Name of the skill to load and apply",
    )


class LoadSkillResponse(BaseModel):
    """Schema for response when AI agent loads and applies the repo-analyzer skill."""
    session_id: str
    skill_name: str
    skill_dir: str
    pillars_loaded: list[str]
    total_rules_count: int
    pillar_breakdowns: list[PillarRuleInfo]
    schema_valid: bool
    schema_title: str
    status: str = "loaded"
    step: int = 6
    step_title: str = "Load Skill"
    duration_ms: float
    message: str


class ChecklistItemResult(BaseModel):
    """Individual checklist item outcome from evaluation."""
    label: str
    passed: bool
    note: str


class PillarAnalysisData(BaseModel):
    """Full analysis outcome for a single pillar."""
    title: str
    score: int
    status: str
    summary: str
    keyStrengths: list[str]
    antiPatterns: list[str]
    checklist: list[ChecklistItemResult]


class PerformAnalysisRequest(BaseModel):
    """Schema for Step 7: Performing repository analysis using repo-analyzer skill."""
    session_id: str = Field(..., description="Unique session ID from previous steps")
    deep_scan: bool = Field(default=True, description="Execute full codebase inspection")


class PerformAnalysisResponse(BaseModel):
    """Schema for response when repository analysis is performed (Step 7)."""
    session_id: str
    repo_name: str
    working_dir: str
    primary_language: str
    secondary_languages: list[str]
    detected_architecture: str
    overall_score: int
    grade: str
    pillar_scores: dict[str, int]
    total_rules_evaluated: int
    passed_rules_count: int
    failed_rules_count: int
    executive_summary: str
    pillars: list[PillarAnalysisData]
    status: str = "analyzed"
    step: int = 7
    step_title: str = "Perform Repository Analysis"
    duration_ms: float
    message: str
    ai_agent_invoked: Optional[bool] = True
    ai_agent_model: Optional[str] = "gemini-3.8-flash-medium"
    ai_agent_evaluator: Optional[str] = "Antigravity CLI Agent (agy)"


class GenerateReportRequest(BaseModel):
    """Schema for Step 8: Generating formatted output per repo-analyzer specifications."""
    session_id: str = Field(..., description="Unique session ID from previous steps")


class GenerateReportResponse(BaseModel):
    """Schema for response when final formatted report is generated (Step 8)."""
    session_id: str
    repo_name: str
    schema_valid: bool
    report_schema: dict[str, Any]
    frontend_report: dict[str, Any]
    status: str = "generated"
    step: int = 8
    step_title: str = "Generate Formatted Output"
    duration_ms: float
    message: str




