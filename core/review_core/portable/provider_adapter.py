from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional

class LLMAdapter(ABC):
    """Vendor-neutral boundary. Content rules MUST NOT live here."""

    @abstractmethod
    def generate(self, messages: list[dict[str, str]], response_schema: Optional[dict[str, Any]] = None) -> str:
        """Return model text. Adapter may use native structured output when available."""
        raise NotImplementedError

class SearchAdapter(ABC):
    """Optional fact-verification boundary."""

    @abstractmethod
    def verify(self, claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError
