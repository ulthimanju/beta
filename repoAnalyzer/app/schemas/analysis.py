import re
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


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
        clean_url = v.strip().rstrip("/")
        pattern = r"^https?://(www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$"
        match = re.match(pattern, clean_url)
        if not match:
            raise ValueError(
                "Invalid repository URL format. Must be a valid GitHub URL: https://github.com/owner/repository"
            )
        return clean_url


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


class CloneRepoResponse(BaseModel):
    """Schema for response when repository is cloned in Step 2."""
    session_id: str
    repo_url: str
    owner: str
    repo_name: str
    temp_dir: str
    commit_hash: str
    branch: str
    file_count: int
    size_bytes: int
    duration_ms: float
    step: int = 2
    step_title: str = "Clone Repository"
    status: str = "cloned"
    message: str
