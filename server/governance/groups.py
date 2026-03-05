"""Discover existing workspace groups for RBAC policy assignment."""

from databricks.sdk import WorkspaceClient


def list_workspace_groups(client: WorkspaceClient) -> list[dict]:
    """Return existing account-level and workspace-local groups.

    Each item: {"display_name": str, "id": str, "member_count": int}
    """
    groups = client.groups.list()
    results = []
    for g in groups:
        results.append({
            "display_name": g.display_name,
            "id": g.id,
            "member_count": len(g.members) if g.members else 0,
        })
    return sorted(results, key=lambda g: g["display_name"])


def get_group_members(client: WorkspaceClient, group_id: str) -> list[str]:
    """Return list of user display names / emails in a group."""
    group = client.groups.get(group_id)
    if not group.members:
        return []
    members = []
    for m in group.members:
        members.append(m.display or m.value or "unknown")
    return members
