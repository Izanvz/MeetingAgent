"""
Jira integration — exports action items as Tasks via Jira REST API v3.

Required env vars:
    JIRA_BASE_URL      e.g. https://yourcompany.atlassian.net
    JIRA_EMAIL         Atlassian account email
    JIRA_API_TOKEN     API token (id.atlassian.com → Security → API tokens)
    JIRA_PROJECT_KEY   e.g. MEET  (default: MEET)

If any required var is missing, runs in dry-run mode.
"""

import os
import httpx
from src.integrations.base import BaseExporter, ExportResult


def _build_issue_body(project_key: str, task: str, description: str, due_date: str | None) -> dict:
    body: dict = {
        "fields": {
            "project": {"key": project_key},
            "summary": task,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Task"},
        }
    }
    if due_date:
        body["fields"]["duedate"] = due_date
    # NOTE: mapping owner name → Atlassian accountId requires
    # GET /rest/api/3/user/search?query=<name>. Omitted until a real account is connected.
    return body


def _build_previews(action_items: list[dict], meeting_title: str, project_key: str) -> list[dict]:
    previews = []
    for item in action_items:
        description = f"From meeting: {meeting_title}"
        if item.get("owner"):
            description += f" | Owner: {item['owner']}"
        previews.append(_build_issue_body(project_key, item["task"], description, item.get("due_date")))
    return previews


class JiraExporter(BaseExporter):
    def __init__(self):
        self._base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
        self._email = os.getenv("JIRA_EMAIL", "")
        self._api_token = os.getenv("JIRA_API_TOKEN", "")
        self._project_key = os.getenv("JIRA_PROJECT_KEY", "MEET")

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._email and self._api_token)

    async def export(
        self,
        meeting_id: str,
        meeting_title: str,
        action_items: list[dict],
        config: dict,
    ) -> ExportResult:
        previews = _build_previews(action_items, meeting_title, self._project_key)

        if not self.configured:
            return ExportResult(
                target="jira",
                dry_run=True,
                meeting_id=meeting_id,
                payload_preview=previews,
                message=(
                    "Dry-run: Jira not configured. "
                    "Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env."
                ),
            )

        created_ids: list[str] = []
        async with httpx.AsyncClient(timeout=10) as client:
            for body in previews:
                res = await client.post(
                    f"{self._base_url}/rest/api/3/issue",
                    json=body,
                    auth=(self._email, self._api_token),
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                res.raise_for_status()
                created_ids.append(res.json()["key"])

        return ExportResult(
            target="jira",
            dry_run=False,
            meeting_id=meeting_id,
            created_ids=created_ids,
            payload_preview=previews,
            message=f"Created {len(created_ids)} issues in project {self._project_key}.",
        )
