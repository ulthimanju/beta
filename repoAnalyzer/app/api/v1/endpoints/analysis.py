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
    SandboxCloseResponse,
    SandboxStatsResponse,
)
from app.services.git_cloner import clone_repository_into_sandbox, GitCloneError
from app.services.sandbox_manager import sandbox_manager, SandboxError


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
