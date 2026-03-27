"""Maps target names to exporter instances."""

from src.integrations.base import BaseExporter
from src.integrations.jira import JiraExporter
from src.integrations.linear import LinearExporter
from src.integrations.webhook import WebhookExporter

_REGISTRY: dict[str, BaseExporter] = {
    "jira": JiraExporter(),
    "linear": LinearExporter(),
    "webhook": WebhookExporter(),
}

SUPPORTED_TARGETS = list(_REGISTRY.keys())


def get_exporter(target: str) -> BaseExporter:
    exporter = _REGISTRY.get(target)
    if exporter is None:
        raise KeyError(f"Unknown export target '{target}'. Supported: {SUPPORTED_TARGETS}")
    return exporter
