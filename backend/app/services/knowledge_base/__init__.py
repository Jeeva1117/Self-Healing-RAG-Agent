"""Phase 12 Intelligent Knowledge Base Management and Quality Services."""

from app.services.knowledge_base.conflicts import KnowledgeBaseConflictEngine
from app.services.knowledge_base.coverage import KnowledgeBaseCoverageEngine
from app.services.knowledge_base.duplicates import KnowledgeBaseDuplicateEngine
from app.services.knowledge_base.health import KnowledgeBaseHealthEngine
from app.services.knowledge_base.repair import KnowledgeBaseRepairEngine
from app.services.knowledge_base.versioning import KnowledgeBaseVersioningEngine

__all__ = [
    "KnowledgeBaseHealthEngine",
    "KnowledgeBaseDuplicateEngine",
    "KnowledgeBaseVersioningEngine",
    "KnowledgeBaseRepairEngine",
    "KnowledgeBaseCoverageEngine",
    "KnowledgeBaseConflictEngine",
]
