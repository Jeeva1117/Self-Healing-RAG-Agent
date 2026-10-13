"""Future API module routers prepared for upcoming development phases."""

from fastapi import APIRouter

from app.api.routes.agents import router as agents_router  # noqa: F401
from app.api.routes.evaluation import router as evaluation_router  # noqa: F401

search_router = APIRouter(prefix="/search", tags=["Search"])
observability_router = APIRouter(prefix="/observability", tags=["Observability"])
