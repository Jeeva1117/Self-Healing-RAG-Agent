"""System information application service."""

import sys

from app.core.config import settings
from app.schemas.system import SystemInfoResponse


class SystemService:
    """Provides system diagnostics, runtime metrics, and module readiness status."""

    def get_info(self) -> SystemInfoResponse:
        return SystemInfoResponse(
            service=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            features={
                "hybrid_rag": False,  # Phase 5
                "reranker": False,  # Phase 5
                "langgraph_agents": False,  # Phase 7
                "self_healing": False,  # Phase 8
                "verification": False,  # Phase 9
                "evaluation": False,  # Phase 10
                "observability": False,  # Phase 11
                "mcp": False,  # Phase 12
            },
        )


system_service = SystemService()
