from enum import Enum

from pydantic import BaseModel, Field


class ReviewDecision(str, Enum):
    ACCEPT = "accept"      # good enough -> proceed to output
    RETRY = "retry"        # extraction problem -> re-run with a hint
    ESCALATE = "escalate"  # a human must look at this
    REJECT = "reject"      # not a processable document of this type


class AgentDecision(BaseModel):
    """What the LLM returns. Its choice is a PROPOSAL, not the final word —
    deterministic guardrails may override it."""

    decision: ReviewDecision
    reasoning: str = Field(description="Why this decision, citing specific evidence.")
    suspicious_fields: list[str] = Field(default_factory=list)
    retry_hint: str | None = Field(
        default=None, description="Instruction for the next extraction attempt."
    )


class ReviewOutcome(BaseModel):
    decision: ReviewDecision
    reasoning: str
    attempts: int
    suspicious_fields: list[str] = Field(default_factory=list)
    overridden: bool = False           # did a guardrail overrule the model?
    override_reason: str | None = None
    history: list[dict] = Field(default_factory=list)
