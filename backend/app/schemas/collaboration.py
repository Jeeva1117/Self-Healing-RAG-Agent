"""Schemas and data models for Phase 16 Multi-Agent Collaboration."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SubtaskStatus(StrEnum):
    """Execution status for an individual planning research subtask."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ResearchSubtask(BaseModel):
    """Discrete research task planned by the Planning Agent."""

    task_id: str = Field(..., description="Stable task identifier e.g. task-1")
    title: str = Field(..., description="Short summary of the subtask")
    query: str = Field(..., description="Targeted retrieval search query")
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of tasks that must execute before this task"
    )
    status: SubtaskStatus = Field(default=SubtaskStatus.PENDING, description="Execution status")
    retrieved_chunk_ids: list[UUID] = Field(
        default_factory=list, description="IDs of chunks retrieved for this subtask"
    )
    findings: list[str] = Field(
        default_factory=list, description="Key extracted facts relevant to this subtask"
    )


class TaskPlan(BaseModel):
    """Structured plan produced by the Planning Agent."""

    plan_id: str = Field(..., description="Unique plan identifier")
    is_complex: bool = Field(default=False, description="Whether query required multi-task decomposition")
    reasoning: str = Field(default="", description="Planner decomposition strategy and rationale")
    subtasks: list[ResearchSubtask] = Field(
        default_factory=list, description="Ordered research subtasks to execute"
    )
    max_execution_steps: int = Field(default=6, description="Execution ceiling for this plan")


class AgentFinding(BaseModel):
    """Fact-checked finding produced by the Research and Evidence Analysis Agent."""

    finding_id: str = Field(..., description="Finding identifier e.g. find-1")
    claim: str = Field(..., description="Specific factual claim supported by retrieved evidence")
    evidence_chunk_ids: list[UUID] = Field(
        default_factory=list, description="IDs of chunks supporting this claim"
    )
    source_titles: list[str] = Field(
        default_factory=list, description="Titles of documents containing the evidence"
    )
    confidence: float = Field(default=1.0, description="Confidence in claim grounding (0.0 to 1.0)")
    is_contradiction: bool = Field(default=False, description="True if evidence contains conflicting claims")


class VerificationAudit(BaseModel):
    """Audit report produced by the Verification Agent."""

    is_verified: bool = Field(default=True, description="Whether findings satisfy query requirements")
    supported_claims: list[str] = Field(
        default_factory=list, description="Claims substantiated by retrieved evidence"
    )
    unsupported_claims: list[str] = Field(
        default_factory=list, description="Claims lacking retrieved evidence"
    )
    citation_validity_ratio: float = Field(default=1.0, description="Ratio of valid citation tags")
    missing_evidence: list[str] = Field(
        default_factory=list, description="Information gaps identified"
    )
    recommendation: str = Field(
        default="proceed", description="Recommended action: proceed, retry_retrieval, or abstain"
    )


class CollaborationMeta(BaseModel):
    """Summary of multi-agent collaboration across all specialized roles."""

    mode: str = Field(default="multi_agent_collaborative", description="Architecture mode")
    participating_agents: list[str] = Field(
        default_factory=lambda: [
            "Query Understanding Agent",
            "Planning Agent",
            "Retrieval Agent",
            "Evidence Analysis Agent",
            "Verification Agent",
            "Response Generation Agent",
            "Workflow Supervisor",
        ],
        description="Names of collaborating specialized agents",
    )
    plan: TaskPlan | None = Field(default=None, description="Plan produced by Planning Agent")
    findings: list[AgentFinding] = Field(
        default_factory=list, description="Findings produced by Evidence Analysis Agent"
    )
    verification: VerificationAudit | None = Field(
        default=None, description="Verification report produced by Verification Agent"
    )
    supervisor_decision: str = Field(
        default="approved", description="Final supervisor resolution: approved, recovered, or terminated_insufficient"
    )
