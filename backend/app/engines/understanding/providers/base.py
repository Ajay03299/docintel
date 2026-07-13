from abc import ABC, abstractmethod

from app.schemas.llm import LLMResponse


class LLMProvider(ABC):
    """Contract every LLM backend implements. Callers depend on THIS,
    never on a concrete provider — that's what makes providers swappable."""

    name: str

    @abstractmethod
    def complete(self, *, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
        """Run one completion. If json_schema is given, the provider should
        request structured output constrained to that schema when supported."""
        ...