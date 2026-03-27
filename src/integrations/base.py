"""Shared types and abstract interface for all export integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExportResult:
    target: str
    dry_run: bool
    meeting_id: str
    created_ids: list[str] = field(default_factory=list)
    payload_preview: list[dict] = field(default_factory=list)
    message: str = ""


class BaseExporter(ABC):
    """Every integration must implement this interface."""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """True when all required credentials/config are present."""

    @abstractmethod
    async def export(
        self,
        meeting_id: str,
        meeting_title: str,
        action_items: list[dict],
        config: dict,
    ) -> ExportResult:
        """Export action items. Returns dry-run result if not configured."""
