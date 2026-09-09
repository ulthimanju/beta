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
)
from app.services.git_cloner import clone_repository, GitCloneError

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
    summary="Step 1: Receive and validate repository URL",
    description="Validates the submitted repository URL, verifies public accessibility, and generates an analysis session.",
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

    logger.info(
        "Step 1: Repository URL received",
        session_id=session_id,
        repo_url=repo_url,
        owner=owner,
        repo_name=repo_name,
    )

    # Check remote repository existence
    exists = check_github_repo_exists(repo_url)
    if not exists:
        logger.warning("Repository not found or private", repo_url=repo_url)
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
        message=f"Step 1 Successful: Repository '{owner}/{repo_name}' received and verified.",
    )


@router.post(
    "/clone",
    response_model=CloneRepoResponse,
    status_code=status.HTTP_200_OK,
    tags=["Analysis Pipeline"],
    summary="Step 2: Clone repository into temporary directory",
    description="Clones the target repository into an isolated temporary directory via shallow clone.",
)
async def clone_repository_endpoint(payload: CloneRepoRequest) -> CloneRepoResponse:
    """Execute Step 2 of the analysis pipeline."""
    session_id = payload.session_id
    repo_url = payload.repo_url

    parsed = urlparse(repo_url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    owner = parts[0] if len(parts) > 0 else "unknown"
    repo_name = parts[1] if len(parts) > 1 else "unknown"

    logger.info("Step 2: Cloning repository", session_id=session_id, repo_url=repo_url)

    try:
        clone_result = await clone_repository(repo_url=repo_url, session_id=session_id)
    except GitCloneError as e:
        logger.error("Step 2 failed during clone", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Step 2 Clone Failure: {str(e)}",
        )

    logger.info(
        "Step 2 completed",
        session_id=session_id,
        temp_dir=clone_result["temp_dir"],
        commit=clone_result["commit_hash"],
        files=clone_result["file_count"],
    )

    return CloneRepoResponse(
        session_id=session_id,
        repo_url=repo_url,
        owner=owner,
        repo_name=repo_name,
        temp_dir=clone_result["temp_dir"],
        commit_hash=clone_result["commit_hash"],
        branch=clone_result["branch"],
        file_count=clone_result["file_count"],
        size_bytes=clone_result["size_bytes"],
        duration_ms=clone_result["duration_ms"],
        step=2,
        step_title="Clone Repository",
        status="cloned",
        message=f"Step 2 Successful: Cloned into temporary directory '{clone_result['temp_dir']}' ({clone_result['file_count']} files, branch: {clone_result['branch']}, HEAD: {clone_result['commit_hash']}) in {clone_result['duration_ms']}ms.",
    )
