from typing import Protocol, TypedDict

import structlog
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, StateGraph

from app.engines.review.prompt import REVIEW_SYSTEM_PROMPT, build_review_prompt
from app.engines.review.retryability import classify_failures
from app.engines.understanding.providers.base import LLMProvider
from app.engines.understanding.structured_extraction import StructuredExtractor
from app.schemas.review import AgentDecision, ReviewDecision, ReviewOutcome
from app.schemas.validation import ValidationReport

log = structlog.get_logger()


class Reprocessor(Protocol):
    """Port: re-run extraction + confidence + validation with an optional hint."""

    def reprocess(self, *, hint: str | None) -> tuple[dict, dict, ValidationReport]: ...


class ReviewState(TypedDict, total=False):
    document_id: str
    data: dict
    confidence: dict
    validation: dict
    validation_obj: ValidationReport
    attempts: int
    max_attempts: int
    retryable: list[str]
    blocking: list[str]
    why: dict[str, str]
    decision: str
    reasoning: str
    suspicious_fields: list[str]
    retry_hint: str | None
    overridden: bool
    override_reason: str | None
    history: list[dict]


class ReviewAgent:
    """Agentic review as a bounded state machine.

    The LLM's decision is a PROPOSAL. Termination and safety are enforced by
    deterministic guardrails, never by asking the model to behave:
      - retry unreachable once attempts >= max_attempts   -> ESCALATE
      - retry unreachable when every failure is blocking  -> ESCALATE (0 LLM calls)
      - retry unreachable when no reprocessor is wired    -> ESCALATE
      - accept overridden whenever blocking failures exist -> ESCALATE
      - unparseable agent output                          -> ESCALATE

    TERMINATION INVARIANT: every path into the retry node increments `attempts`.
    An earlier version incremented it only inside the reprocessor branch, so a
    None reprocessor produced an unbounded assess->decide->retry loop. A
    termination guarantee must not depend on an optional collaborator.
    """

    def __init__(
        self,
        provider: LLMProvider,
        reprocessor: Reprocessor | None = None,
        max_attempts: int = 2,
    ) -> None:
        self._extractor = StructuredExtractor(provider, max_retries=1)
        self._reprocessor = reprocessor
        self._max_attempts = max_attempts
        self._graph = self._build()

    # ---------------- nodes ----------------

    def _assess(self, state: ReviewState) -> dict:
        retryable, blocking, why = classify_failures(
            state["validation_obj"], state["confidence"]
        )
        log.info(
            "review.assessed",
            document_id=state.get("document_id"),
            attempts=state.get("attempts", 1),
            retryable=retryable,
            blocking=blocking,
        )
        return {"retryable": retryable, "blocking": blocking, "why": why}

    def _decide(self, state: ReviewState) -> dict:
        prompt = build_review_prompt(
            data=state["data"],
            confidence=state["confidence"],
            validation=state["validation"],
            retryable=state["retryable"],
            blocking=state["blocking"],
            why=state["why"],
            attempts=state.get("attempts", 1),
            max_attempts=state["max_attempts"],
        )
        out = self._extractor.extract(
            document_text="",
            system_prompt=REVIEW_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema_model=AgentDecision,
        )

        try:
            proposal = AgentDecision.model_validate(out.data)
        except Exception:
            proposal = AgentDecision(
                decision=ReviewDecision.ESCALATE,
                reasoning=f"Review agent returned unusable output: {out.parse_error}",
            )

        decision, overridden, override_reason = self._apply_guardrails(state, proposal)

        entry = {
            "attempt": state.get("attempts", 1),
            "proposed": proposal.decision.value,
            "final": decision.value,
            "reasoning": proposal.reasoning,
            "overridden": overridden,
            "override_reason": override_reason,
        }
        log.info(
            "review.decided",
            document_id=state.get("document_id"),
            attempts=state.get("attempts", 1),
            proposed=proposal.decision.value,
            final=decision.value,
            overridden=overridden,
            override_reason=override_reason,
        )
        return {
            "decision": decision.value,
            "reasoning": proposal.reasoning,
            "suspicious_fields": proposal.suspicious_fields,
            "retry_hint": proposal.retry_hint,
            "overridden": overridden,
            "override_reason": override_reason,
            "history": [*state.get("history", []), entry],
        }

    def _apply_guardrails(
        self, state: ReviewState, proposal: AgentDecision
    ) -> tuple[ReviewDecision, bool, str | None]:
        attempts = state.get("attempts", 1)

        if proposal.decision is ReviewDecision.RETRY:
            if self._reprocessor is None:
                return (
                    ReviewDecision.ESCALATE,
                    True,
                    "retry requested but no reprocessor is configured; "
                    "retry is not available in this deployment",
                )
            if attempts >= state["max_attempts"]:
                return (
                    ReviewDecision.ESCALATE,
                    True,
                    f"retry budget exhausted ({attempts}/{state['max_attempts']})",
                )
            if not state["retryable"]:
                return (
                    ReviewDecision.ESCALATE,
                    True,
                    "agent asked to retry but every failure is blocking; "
                    "re-extraction cannot change the outcome",
                )

        if proposal.decision is ReviewDecision.ACCEPT and state["blocking"]:
            return (
                ReviewDecision.ESCALATE,
                True,
                f"agent accepted despite blocking failures: {', '.join(state['blocking'])}",
            )

        return proposal.decision, False, None

    def _retry(self, state: ReviewState) -> dict:
        """Re-run upstream processing.

        INVARIANT: this node ALWAYS increments `attempts`, on every path. That is
        the only thing standing between a retry-happy agent and an infinite loop.
        """
        attempts = state.get("attempts", 1) + 1

        # Unreachable in practice (_apply_guardrails blocks retry without a
        # reprocessor) but the increment must hold even if that changes.
        if self._reprocessor is None:
            return {"attempts": attempts}

        data, confidence, validation = self._reprocessor.reprocess(
            hint=state.get("retry_hint")
        )
        log.info(
            "review.reprocessed",
            document_id=state.get("document_id"),
            attempt=attempts,
            new_confidence=confidence.get("overall"),
            new_validation=validation.overall.value,
        )
        return {
            "data": data,
            "confidence": confidence,
            "validation": validation.model_dump(mode="json"),
            "validation_obj": validation,
            "attempts": attempts,
        }

    # ---------------- edges ----------------

    def _route(self, state: ReviewState) -> str:
        return "retry" if state["decision"] == ReviewDecision.RETRY.value else "end"

    def _build(self):
        b = StateGraph(ReviewState)
        b.add_node("assess", self._assess)
        b.add_node("decide", self._decide)
        b.add_node("retry", self._retry)
        b.set_entry_point("assess")
        b.add_edge("assess", "decide")
        b.add_conditional_edges("decide", self._route, {"retry": "retry", "end": END})
        b.add_edge("retry", "assess")  # the loop — bounded by _apply_guardrails
        return b.compile()

    # ---------------- api ----------------

    def review(
        self, *, document_id: str, data: dict, confidence: dict, validation: ValidationReport
    ) -> ReviewOutcome:
        initial: ReviewState = {
            "document_id": document_id,
            "data": data,
            "confidence": confidence,
            "validation": validation.model_dump(mode="json"),
            "validation_obj": validation,
            "attempts": 1,
            "max_attempts": self._max_attempts,
            "history": [],
        }
        try:
            final = self._graph.invoke(initial, {"recursion_limit": 25})
        except GraphRecursionError:
            # Last-resort net: the guardrails should make this unreachable, but a
            # runaway graph must degrade to a safe human handoff, not an exception
            # that leaves the document stuck mid-pipeline.
            log.error("review.recursion_limit", document_id=document_id)
            return ReviewOutcome(
                decision=ReviewDecision.ESCALATE,
                reasoning="Review loop failed to terminate; escalated for human review.",
                attempts=self._max_attempts,
                overridden=True,
                override_reason="graph recursion limit reached",
            )

        return ReviewOutcome(
            decision=ReviewDecision(final["decision"]),
            reasoning=final.get("reasoning", ""),
            attempts=final.get("attempts", 1),
            suspicious_fields=final.get("suspicious_fields", []),
            overridden=final.get("overridden", False),
            override_reason=final.get("override_reason"),
            history=final.get("history", []),
        )
