from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.config import settings


def setup_metrics(app: FastAPI) -> None:
    """Initialize Prometheus metrics exporter and instrumentation."""
    if not settings.PROMETHEUS_METRICS_ENABLED:
        return

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
    )

    instrumentator.instrument(app).expose(app, endpoint="/metrics")
