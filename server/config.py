import os
from databricks.sdk import WorkspaceClient

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

_workspace_client: WorkspaceClient | None = None


def get_workspace_client() -> WorkspaceClient:
    global _workspace_client
    if _workspace_client is not None:
        return _workspace_client

    if IS_DATABRICKS_APP:
        _workspace_client = WorkspaceClient()
    else:
        host = os.environ.get("DATABRICKS_HOST", "")
        token = os.environ.get("DATABRICKS_TOKEN", "")
        profile = os.environ.get("DATABRICKS_PROFILE")
        if host and token:
            _workspace_client = WorkspaceClient(host=host, token=token)
        elif profile:
            _workspace_client = WorkspaceClient(profile=profile)
        else:
            _workspace_client = WorkspaceClient()
    return _workspace_client


def get_oauth_token() -> str:
    client = get_workspace_client()
    headers = client.config.authenticate()
    if headers and "Authorization" in headers:
        return headers["Authorization"].replace("Bearer ", "")
    raise RuntimeError("Failed to obtain OAuth token from Databricks SDK")


def get_workspace_host() -> str:
    if IS_DATABRICKS_APP:
        host = os.environ.get("DATABRICKS_HOST", "")
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host
    client = get_workspace_client()
    return client.config.host


def get_serving_endpoint() -> str:
    return os.environ.get("SERVING_ENDPOINT", "databricks-claude-sonnet-4-5")
