"""
Linear integration — exports action items as Issues via Linear GraphQL API.

Required env vars:
    LINEAR_API_KEY     Personal API key (linear.app → Settings → API → Personal keys)
    LINEAR_TEAM_ID     Team ID where issues will be created

If any required var is missing, runs in dry-run mode.
"""

import os
import httpx
from src.integrations.base import BaseExporter, ExportResult

_LINEAR_ENDPOINT = "https://api.linear.app/graphql"

_CREATE_ISSUE_MUTATION = """
mutation CreateIssue($title: String!, $description: String!, $teamId: String!, $dueDate: TimelessDate) {
  issueCreate(input: {
    title: $title
    description: $description
    teamId: $teamId
    dueDate: $dueDate
  }) {
    success
    issue { id identifier url }
  }
}
"""


def _build_preview(task: str, meeting_title: str, owner: str | None, due_date: str | None, team_id: str) -> dict:
    description = f"Action item from meeting: **{meeting_title}**"
    if owner:
        description += f"\nOwner: {owner}"
    return {
        "title": task,
        "description": description,
        "teamId": team_id,
        "dueDate": due_date,
    }


class LinearExporter(BaseExporter):
    def __init__(self):
        self._api_key = os.getenv("LINEAR_API_KEY", "")
        self._team_id = os.getenv("LINEAR_TEAM_ID", "")

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._team_id)

    async def export(
        self,
        meeting_id: str,
        meeting_title: str,
        action_items: list[dict],
        config: dict,
    ) -> ExportResult:
        previews = [
            _build_preview(
                item["task"], meeting_title, item.get("owner"), item.get("due_date"), self._team_id
            )
            for item in action_items
        ]

        if not self.configured:
            return ExportResult(
                target="linear",
                dry_run=True,
                meeting_id=meeting_id,
                payload_preview=previews,
                message="Dry-run: Linear not configured. Set LINEAR_API_KEY and LINEAR_TEAM_ID in .env.",
            )

        created_ids: list[str] = []
        headers = {"Authorization": self._api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=10) as client:
            for variables in previews:
                res = await client.post(
                    _LINEAR_ENDPOINT,
                    json={"query": _CREATE_ISSUE_MUTATION, "variables": variables},
                    headers=headers,
                )
                res.raise_for_status()
                data = res.json()
                if errors := data.get("errors"):
                    raise RuntimeError(f"Linear API error: {errors}")
                issue = data["data"]["issueCreate"]["issue"]
                created_ids.append(issue["url"])

        return ExportResult(
            target="linear",
            dry_run=False,
            meeting_id=meeting_id,
            created_ids=created_ids,
            payload_preview=previews,
            message=f"Created {len(created_ids)} Linear issues.",
        )
