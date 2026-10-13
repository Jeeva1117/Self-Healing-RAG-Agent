"""Central API v1 router aggregator."""

from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.agents import router as agents_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.data_sources import router as data_sources_router
from app.api.routes.documents import router as documents_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.observability import router as observability_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.retrieval import search_alias_router
from app.api.routes.system import router as system_router

api_v1_router = APIRouter()

# Core Foundation Routes
api_v1_router.include_router(health_router)
api_v1_router.include_router(system_router)

# Authentication & Admin (Phase 3)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)

# Knowledge Base & Documents (Phase 4)
api_v1_router.include_router(knowledge_bases_router)
api_v1_router.include_router(documents_router)

# Data Sources & External Connectors
api_v1_router.include_router(data_sources_router)

# Retrieval Engine (Phase 5)
api_v1_router.include_router(retrieval_router)
api_v1_router.include_router(search_alias_router)

# Future Phases (Stubs)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(agents_router)
api_v1_router.include_router(evaluation_router)
api_v1_router.include_router(observability_router)
