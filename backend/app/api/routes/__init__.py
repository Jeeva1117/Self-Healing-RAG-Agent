"""Routes package."""

from app.api.routes.admin import router as admin_router
from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.data_sources import router as data_sources_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.retrieval import search_alias_router
from app.api.routes.stubs import (
    evaluation_router,
    observability_router,
)
from app.api.routes.system import router as system_router

__all__ = [
    "health_router",
    "system_router",
    "auth_router",
    "admin_router",
    "knowledge_bases_router",
    "documents_router",
    "retrieval_router",
    "search_alias_router",
    "chat_router",
    "agents_router",
    "data_sources_router",
    "evaluation_router",
    "observability_router",
]
