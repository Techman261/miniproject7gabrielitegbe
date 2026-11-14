# INF601
# Gabriel Itegbe
# Advanced Programming in Python
# Mini Project 7

"""
Practice Hub MCP server.

Exposes five tools (list_posts, get_post, create_post, update_post,
delete_post) that an AI agent such as Claude Code can call to manage posts on
the Practice Hub REST API. Configuration is read from environment variables:

    PRACTICE_API_URL      Base URL of the API (default: https://practice.fhsucyber.com)
    PRACTICE_API_TOKEN    Personal bearer token (required, never hardcoded)
    PRACTICE_API_TIMEOUT  Request timeout in seconds (optional, default: 15)

Run directly with:  python server.py   (speaks MCP over stdio)
"""

import json
import os
from typing import Any, Optional

import httpx
from mcp.server.mcpserver import MCPServer

# Load a local .env file if python-dotenv is installed. Values already set in
# the real environment (e.g. by `claude mcp add --env`) take precedence.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass

DEFAULT_API_URL = "https://practice.fhsucyber.com"
DEFAULT_TIMEOUT = 15.0  # seconds
POSTS_PATH = "/api/v1/posts"

mcp = MCPServer("practice-hub")

# Tests swap this for an httpx.MockTransport so no real network is used.
_transport: Optional[httpx.AsyncBaseTransport] = None


# --------------------------------------------------------------------------- #
# Configuration helpers
# --------------------------------------------------------------------------- #
def _base_url() -> str:
    """Return the API base URL from the environment, without a trailing slash."""
    return os.environ.get("PRACTICE_API_URL", "").strip().rstrip("/") or DEFAULT_API_URL


def _token() -> Optional[str]:
    """Return the API token from the environment, or None if it is unset/blank."""
    token = os.environ.get("PRACTICE_API_TOKEN", "").strip()
    return token or None


def _timeout_seconds() -> float:
    """Return the request timeout, falling back to the default on bad input."""
    raw = os.environ.get("PRACTICE_API_TIMEOUT", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _extract_detail(response: httpx.Response) -> str:
    """Pull a human-readable error detail out of an API error response."""
    try:
        data = response.json()
    except ValueError:
        return response.text.strip() or response.reason_phrase
    if isinstance(data, dict):
        for key in ("detail", "error", "message"):
            if data.get(key):
                value = data[key]
                return value if isinstance(value, str) else json.dumps(value)
    return json.dumps(data)


def _error_message(response: httpx.Response, post_id: Optional[int] = None) -> str:
    """Translate an HTTP error status into a clear message for the agent."""
    status = response.status_code
    detail = _extract_detail(response)
    target = f"post {post_id}" if post_id is not None else "this resource"

    if status == 401:
        return (
            "Error 401 Unauthorized: the API token is missing, invalid, or expired. "
            f"Check that PRACTICE_API_TOKEN is set correctly. (API said: {detail})"
        )
    if status == 403:
        return (
            f"Error 403 Forbidden: you are not allowed to modify {target}. "
            f"You can only edit or delete posts that you created. (API said: {detail})"
        )
    if status == 404:
        return (
            f"Error 404 Not Found: {target} does not exist. "
            f"Use list_posts to see valid post IDs. (API said: {detail})"
        )
    if status in (400, 422):
        return f"Error {status} Bad Request: the API rejected the input. (API said: {detail})"
    if status == 429:
        return f"Error 429 Too Many Requests: slow down and try again shortly. (API said: {detail})"
    if status >= 500:
        return f"Error {status}: the API server had a problem. Try again later. (API said: {detail})"
    return f"Error {status}: request failed. (API said: {detail})"


async def _request(
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    post_id: Optional[int] = None,
) -> str:
    """
    Send an authenticated request to the API and return a string result.

    On success the JSON body is returned pretty-printed. On any failure
    (missing token, HTTP error, timeout, network problem) a descriptive error
    string is returned instead of raising, so the MCP server never crashes.
    """
    token = _token()
    if token is None:
        return (
            "Error: PRACTICE_API_TOKEN is not set. Add it to your environment "
            "(or .env file / `claude mcp add --env`) and restart the server."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    url = f"{_base_url()}{path}"
    timeout = _timeout_seconds()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 5.0)),
            transport=_transport,
        ) as client:
            response = await client.request(
                method, url, headers=headers, params=params, json=payload
            )
    except httpx.TimeoutException:
        return f"Error: the request to {url} timed out after {timeout:g} seconds."
    except httpx.RequestError as exc:
        return f"Error: could not reach the API at {url} ({exc.__class__.__name__}: {exc})."

    if response.is_error:
        return _error_message(response, post_id)

    if response.status_code == 204 or not response.content:
        return "Success (no content returned)."

    try:
        return json.dumps(response.json(), indent=2)
    except ValueError:
        return response.text


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
@mcp.tool()
async def list_posts(mine: bool = False) -> str:
    """
    List posts on Practice Hub.

    Call this when the user wants to browse, search, or count posts, or when
    you need to find a post's ID before getting, updating, or deleting it.

    Args:
        mine: If True, return only posts owned by the authenticated user
              (the owner of PRACTICE_API_TOKEN). If False, return all posts.

    Returns:
        A JSON list of posts (id, title, body, tags, author_name, timestamps),
        or an error message string.
    """
    params = {"mine": "true"} if mine else None
    return await _request("GET", POSTS_PATH, params=params)


@mcp.tool()
async def get_post(id: int) -> str:
    """
    Get a single Practice Hub post by its numeric ID.

    Call this when the user asks for the full details (title, body, tags,
    author) of a specific post, or to confirm a post's current contents
    before changing it.

    Args:
        id: The numeric ID of the post.

    Returns:
        The post as JSON, or an error message (e.g. 404 if it doesn't exist).
    """
    return await _request("GET", f"{POSTS_PATH}/{id}", post_id=id)


# --------------------------------------------------------------------------- #
# Write tools
# --------------------------------------------------------------------------- #
@mcp.tool()
async def create_post(title: str, body: str, tags: Optional[list[str]] = None) -> str:
    """
    Create a new Practice Hub post owned by the authenticated user.

    Call this when the user asks to write, publish, add, or create a post.

    Args:
        title: The post title.
        body: The post content (plain text or Markdown).
        tags: A list of tag strings, e.g. ["python", "mcp"]. Omit or use [] for none.

    Returns:
        The newly created post as JSON (including its new ID), or an error message.
    """
    if not title.strip():
        return "Error: title cannot be empty."
    payload = {"title": title, "body": body, "tags": tags or []}
    return await _request("POST", POSTS_PATH, payload=payload)


@mcp.tool()
async def update_post(
    id: int,
    title: Optional[str] = None,
    body: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> str:
    """
    Partially update one of YOUR existing Practice Hub posts.

    Call this when the user asks to edit, rename, retitle, change, or retag a
    post. Only the fields you pass are changed; omitted fields are left as-is.
    You can only update posts you own; others return a 403 error.

    Args:
        id: The numeric ID of the post to update.
        title: New title (optional).
        body: New body text (optional).
        tags: New full list of tags, replacing the old list (optional).

    Returns:
        The updated post as JSON, or an error message (401/403/404).
    """
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if tags is not None:
        payload["tags"] = tags

    if not payload:
        return "Nothing to update: provide at least one of title, body, or tags."

    return await _request("PATCH", f"{POSTS_PATH}/{id}", payload=payload, post_id=id)


@mcp.tool()
async def delete_post(id: int) -> str:
    """
    Permanently delete one of YOUR Practice Hub posts by ID.

    Call this only when the user clearly asks to delete or remove a post.
    You can only delete posts you own; others return a 403 error.

    Args:
        id: The numeric ID of the post to delete.

    Returns:
        A success message, or an error message (401/403/404).
    """
    result = await _request("DELETE", f"{POSTS_PATH}/{id}", post_id=id)
    if result.startswith("Error"):
        return result
    return f"Post {id} deleted successfully."


if __name__ == "__main__":
    # stdio transport is what Claude Code uses for local MCP servers.
    mcp.run()
