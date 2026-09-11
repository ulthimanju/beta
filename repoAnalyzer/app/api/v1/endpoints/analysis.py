import uuid
import urllib.request
import urllib.error
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, status
from app.core.logging import get_logger
from app.schemas.analysis import (
    RepoSubmitRequest,
    RepoSubmitResponse,
    CloneRepoRequest,
    CloneRepoResponse,
    SetWorkingDirRequest,
    SetWorkingDirResponse,
    InvokeAgentRequest,
    InvokeAgentResponse,
    DispatchQueryRequest,
    DispatchQueryResponse,
    LoadSkillRequest,
    LoadSkillResponse,
    PerformAnalysisRequest,
    PerformAnalysisResponse,
    SandboxCloseResponse,
    SandboxStatsResponse,
)
from app.services.git_cloner import clone_repository_into_sandbox, GitCloneError
from app.services.sandbox_manager import sandbox_manager, SandboxError

from app.services.agent_runner import agent_runner, AgentRunnerError



logger = get_logger("analysis_endpoint")
router = APIRouter()


def check_github_repo_exists(repo_url: str) -> bool:
    """Check if the public GitHub repository exists and is accessible."""
    req = urllib.request.Request(
        repo_url,
        headers={"User-Agent": "repoAnalyzer/0.1.0"},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status in (200, 301, 302)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        # If GitHub rate limits or returns 403 for HEAD, fallback to allowing format validation
        return True
    except Exception:
        # Network fallback: if offline or timed out, do not block local/mock prototyping
        return True


@router.post(
    "/analyze",
    response_model=RepoSubmitResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 1: Receive repository URL and initialize Session Sandbox",
    description="Validates repository URL, verifies accessibility, and creates an isolated session sandbox.",
)
async def submit_repository(payload: RepoSubmitRequest) -> RepoSubmitResponse:
    """Execute Step 1 of the analysis pipeline."""
    session_id = str(uuid.uuid4())
    repo_url = payload.repo_url

    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid repository URL. Could not determine owner and repository name.",
        )

    owner, repo_name = parts[0], parts[1]

    # Initialize Session Sandbox
    sandbox = sandbox_manager.get_or_create_sandbox(session_id)

    logger.info(
        "Step 1: Repository URL received & Session Sandbox initialized",
        session_id=session_id,
        sandbox_dir=sandbox.root_dir,
        repo_url=repo_url,
        owner=owner,
        repo_name=repo_name,
    )

    # Check remote repository existence
    exists = check_github_repo_exists(repo_url)
    if not exists:
        logger.warning("Repository not found or private; wiping sandbox", repo_url=repo_url)
        await sandbox.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GitHub repository '{owner}/{repo_name}' was not found. Please ensure it is public and correctly spelled.",
        )

    logger.info(
        "Step 1 completed: Repository validated",
        session_id=session_id,
        repo_name=repo_name,
    )

    return RepoSubmitResponse(
        session_id=session_id,
        repo_url=repo_url,
        owner=owner,
        repo_name=repo_name,
        step=1,
        step_title="Receive Repository URL",
        status="received",
        message=f"Step 1 Successful: Repository '{owner}/{repo_name}' verified. Session sandbox initialized.",
    )


@router.post(
    "/clone",
    response_model=CloneRepoResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 2: Clone repository into Session Sandbox",
    description="Clones the target repository directly into the session's isolated sandbox workspace.",
)
async def clone_repository_endpoint(payload: CloneRepoRequest) -> CloneRepoResponse:
    """Execute Step 2 of the analysis pipeline."""
    session_id = payload.session_id
    repo_url = payload.repo_url

    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    owner = parts[0] if len(parts) > 0 else "unknown"
    repo_name = parts[1] if len(parts) > 1 else "unknown"

    logger.info("Step 2: Cloning repository into Session Sandbox", session_id=session_id, repo_url=repo_url)

    try:
        clone_result = await clone_repository_into_sandbox(repo_url=repo_url, session_id=session_id)
    except GitCloneError as e:
        logger.error("Step 2 failed during sandbox clone", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 2 Sandbox Clone Failure: {str(e)}",
        )

    return CloneRepoResponse(
        session_id=session_id,
        repo_url=repo_url,
        owner=owner,
        repo_name=repo_name,
        sandbox_root=clone_result["sandbox_root"],
        repo_dir=clone_result["repo_dir"],
        working_dir=clone_result["working_dir"],
        commit_hash=clone_result["commit_hash"],
        branch=clone_result["branch"],
        file_count=clone_result["file_count"],
        size_bytes=clone_result["size_bytes"],
        duration_ms=clone_result["duration_ms"],
        step=2,
        step_title="Clone Repository into Sandbox",
        status="cloned",
        message=f"Step 2 Successful: Repository cloned directly into Session Sandbox '{clone_result['sandbox_root']}' ({clone_result['file_count']} files, branch: {clone_result['branch']}) in {clone_result['duration_ms']}ms.",
    )


@router.post(
    "/set-working-dir",
    response_model=SetWorkingDirResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 3: Set cloned repository directory as working directory",
    description="Validates and sets the cloned repository directory within the Session Sandbox as the execution working directory for AI agent commands.",
)
async def set_working_directory_endpoint(payload: SetWorkingDirRequest) -> SetWorkingDirResponse:
    """Execute Step 3 of the analysis pipeline."""
    session_id = payload.session_id
    sandbox = sandbox_manager.get_sandbox(session_id)
    if not sandbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for session '{session_id}' not found or already closed.",
        )

    logger.info("Step 3: Setting working directory inside Session Sandbox", session_id=session_id)

    try:
        result = sandbox.set_working_directory(payload.target_subpath)
    except SandboxError as e:
        logger.error("Step 3 failed to set working directory", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Step 3 Failed: {str(e)}",
        )

    frameworks_str = ", ".join(result["detected_frameworks"]) if result["detected_frameworks"] else "General/Plain"

    return SetWorkingDirResponse(
        session_id=session_id,
        sandbox_root=result["sandbox_root"],
        working_dir=result["working_dir"],
        relative_working_dir=result["relative_working_dir"],
        repo_name=result["repo_name"],
        is_git_worktree=result["is_git_worktree"],
        readme_present=result["readme_present"],
        detected_frameworks=result["detected_frameworks"],
        top_level_entries=result["top_level_entries"],
        step=3,
        step_title="Set Working Directory",
        status="configured",
        message=f"Step 3 Successful: Active working directory locked to '{result['relative_working_dir']}' inside sandbox. Git worktree verified: {result['is_git_worktree']}. Detected stacks: {frameworks_str}.",
    )


@router.post(
    "/invoke-agent",
    response_model=InvokeAgentResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 4: Execute CLI AI Agent terminal invocation",
    description="From the repository working directory within the Session Sandbox, executes the terminal command that invokes the CLI AI agent.",
)
async def invoke_agent_endpoint(payload: InvokeAgentRequest) -> InvokeAgentResponse:
    """Execute Step 4 of the analysis pipeline."""
    session_id = payload.session_id
    logger.info("Step 4: Invoking CLI AI Agent from repo directory", session_id=session_id)

    try:
        result = await agent_runner.invoke_agent(
            session_id=session_id,
            custom_flags=payload.custom_flags,
        )
    except AgentRunnerError as e:
        logger.error("Step 4 failed to invoke CLI AI agent", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 4 Failed: {str(e)}",
        )

    return InvokeAgentResponse(
        session_id=session_id,
        sandbox_root=result["sandbox_root"],
        working_dir=result["working_dir"],
        agent_executable=result["agent_executable"],
        agent_version=result["agent_version"],
        command=result["command"],
        default_model=result["default_model"],
        pid=result["pid"],
        status="invoked",
        step=4,
        step_title="Execute CLI AI Agent",
        duration_ms=result["duration_ms"],
        message=f"Step 4 Successful: CLI AI agent ({result['agent_version']}) successfully invoked from '{result['working_dir']}'. Runtime initialized and ready for query dispatch (PID: {result['pid']}).",
    )


@router.post(
    "/dispatch-query",
    response_model=DispatchQueryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 5: Send analysis query to CLI AI Agent",
    description="Sends the query 'analyze this repo using repo-analyzer skill' to the CLI AI agent using its default model.",
)
async def dispatch_query_endpoint(payload: DispatchQueryRequest) -> DispatchQueryResponse:
    """Execute Step 5 of the analysis pipeline."""
    session_id = payload.session_id
    logger.info("Step 5: Dispatching query to CLI AI agent", session_id=session_id, query=payload.query)

    try:
        result = await agent_runner.dispatch_query(
            session_id=session_id,
            query=payload.query,
            model=payload.model,
        )
    except AgentRunnerError as e:
        logger.error("Step 5 failed to dispatch query", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 5 Failed: {str(e)}",
        )

    return DispatchQueryResponse(
        session_id=session_id,
        query=result["query"],
        model_used=result["model_used"],
        working_dir=result["working_dir"],
        skill_name=result["skill_name"],
        status="dispatched",
        step=5,
        step_title="Dispatch Query",
        timestamp=result["timestamp"],
        duration_ms=result["duration_ms"],
        message=f"Step 5 Successful: Query '{result['query']}' dispatched to CLI AI agent using default model '{result['model_used']}' with '{result['skill_name']}' skill mounted in sandbox.",
    )


@router.post(
    "/load-skill",
    response_model=LoadSkillResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 6: AI agent loads and applies repo-analyzer skill",
    description="Loads and parses repo-analyzer skill instructions, the 4 evaluation pillars checklists, and report output schema.",
)
async def load_skill_endpoint(payload: LoadSkillRequest) -> LoadSkillResponse:
    """Execute Step 6 of the analysis pipeline."""
    session_id = payload.session_id
    logger.info("Step 6: Loading and applying skill", session_id=session_id, skill_name=payload.skill_name)

    try:
        result = await agent_runner.load_skill(
            session_id=session_id,
            skill_name=payload.skill_name,
        )
    except AgentRunnerError as e:
        logger.error("Step 6 failed to load skill", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 6 Failed: {str(e)}",
        )

    return LoadSkillResponse(
        session_id=session_id,
        skill_name=result["skill_name"],
        skill_dir=result["skill_dir"],
        pillars_loaded=result["pillars_loaded"],
        total_rules_count=result["total_rules_count"],
        pillar_breakdowns=result["pillar_breakdowns"],
        schema_valid=result["schema_valid"],
        schema_title=result["schema_title"],
        status="loaded",
        step=6,
        step_title="Load Skill",
        duration_ms=result["duration_ms"],
        message=f"Step 6 Successful: AI agent loaded '{result['skill_name']}' skill ({len(result['pillars_loaded'])} pillars, {result['total_rules_count']} rules). Output schema verified.",
    )


@router.post(
    "/perform-analysis",
    response_model=PerformAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 7: Perform deep repository analysis",
    description="The AI agent audits the repository across the 4 pillars (Architecture, Ideology, Methodology, Software Principles) per repo-analyzer specifications.",
)
async def perform_analysis_endpoint(payload: PerformAnalysisRequest) -> PerformAnalysisResponse:
    """Execute Step 7 of the analysis pipeline."""
    session_id = payload.session_id
    logger.info("Step 7: Performing repository analysis", session_id=session_id)

    try:
        result = await agent_runner.perform_analysis(session_id=session_id)
    except AgentRunnerError as e:
        logger.error("Step 7 failed during repository analysis", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 7 Failed: {str(e)}",
        )

    return PerformAnalysisResponse(
        session_id=session_id,
        repo_name=result["repo_name"],
        working_dir=result["working_dir"],
        primary_language=result["primary_language"],
        secondary_languages=result["secondary_languages"],
        detected_architecture=result["detected_architecture"],
        overall_score=result["overall_score"],
        grade=result["grade"],
        pillar_scores=result["pillar_scores"],
        total_rules_evaluated=result["total_rules_evaluated"],
        passed_rules_count=result["passed_rules_count"],
        failed_rules_count=result["failed_rules_count"],
        executive_summary=result["executive_summary"],
        pillars=result["pillars"],
        status="analyzed",
        step=7,
        step_title="Perform Repository Analysis",
        duration_ms=result["duration_ms"],
        message=f"Step 7 Successful: Codebase analysis complete. Overall Score: {result['overall_score']}/100 (Grade: {result['grade']}). 34 checklist rules evaluated across 4 pillars.",
    )


@router.get(
    "/sandbox/{session_id}",
    response_model=SandboxStatsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Session Sandbox"],
    summary="Inspect Session Sandbox status",
    description="Returns current storage, file count, and working directory of the active session sandbox.",
)
async def get_sandbox_stats(session_id: str) -> SandboxStatsResponse:
    """Retrieve stats for an active session sandbox."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if not sandbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sandbox for session '{session_id}' not found or already closed.",
        )
    stats = sandbox.get_stats()
    return SandboxStatsResponse(**stats)


@router.post(
    "/sandbox/{session_id}/close",
    response_model=SandboxCloseResponse,
    status_code=status.HTTP_200_OK,
    tags=["Session Sandbox"],
    summary="Close and destroy Session Sandbox",
    description="Terminates all active processes, deletes all cloned repository files, and wipes the sandbox from disk.",
)
async def close_sandbox_endpoint(session_id: str) -> SandboxCloseResponse:
    """Explicitly destroy and wipe a session sandbox."""
    result = await sandbox_manager.close_sandbox(session_id)
    if not result:
        return SandboxCloseResponse(
            session_id=session_id,
            status="closed",
            message="Sandbox was already closed or does not exist.",
            closed_at="",
        )

    logger.info("Session sandbox destroyed via API", session_id=session_id)
    return SandboxCloseResponse(
        session_id=result["session_id"],
        status=result["status"],
        message=result["message"],
        closed_at=result["closed_at"],
    )
