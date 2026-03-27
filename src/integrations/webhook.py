"""
Webhook integration — POSTs a standardized payload to any URL.

Enables connection to Zapier, Make.com, n8n, Slack, or any internal system
without implementing each one individually.

Config (passed per-request, not via env vars):
    url        Required. Target webhook URL.
    secret     Optional. Sent as X-Webhook-Secret header for verification.

Payload shape posted to the webhook:
    {
        "source": "meeting-agent",
        "meeting_id": "...",
        "meeting_title": "...",
        "action_items": [
            {"task": "...", "owner": "...", "due_date": "...", "status": "..."}
        ]
    }
"""

import httpx
from src.integrations.base import BaseExporter, ExportResult


def _build_payload(meeting_id: str, meeting_title: str, action_items: list[dict]) -> dict:
    return {
        "source": "meeting-agent",
        "meeting_id": meeting_id,
        "meeting_title": meeting_title,
        "action_items": [
            {
                "task": item["task"],
                "owner": item.get("owner"),
                "due_date": item.get("due_date"),
                "status": item.get("status", "pending"),
            }
            for item in action_items
        ],
    }


class WebhookExporter(BaseExporter):
    @property
    def configured(self) -> bool:
        # Webhook is always "configured" — the URL is passed per-request.
        # Returns False only when called without config (used in dry-run).
        return True

    async def export(
        self,
        meeting_id: str,
        meeting_title: str,
        action_items: list[dict],
        config: dict,
    ) -> ExportResult:
        url = config.get("url", "")
        payload = _build_payload(meeting_id, meeting_title, action_items)

        if not url:
            return ExportResult(
                target="webhook",
                dry_run=True,
                meeting_id=meeting_id,
                payload_preview=[payload],
                message="Dry-run: no webhook URL provided. Pass {\"config\": {\"url\": \"https://...\"}} in the request body.",
            )

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if secret := config.get("secret"):
            headers["X-Webhook-Secret"] = secret

        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()

        return ExportResult(
            target="webhook",
            dry_run=False,
            meeting_id=meeting_id,
            created_ids=[url],
            payload_preview=[payload],
            message=f"Payload delivered to {url} — HTTP {res.status_code}.",
        )
