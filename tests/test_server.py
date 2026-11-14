"""Unit tests for server.py using httpx.MockTransport (no network)."""

import asyncio
import json

import httpx
import pytest

import server

TOKEN = "test-token"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("PRACTICE_API_TOKEN", TOKEN)
    monkeypatch.setenv("PRACTICE_API_URL", "https://api.example.test/")
    monkeypatch.delenv("PRACTICE_API_TIMEOUT", raising=False)
    yield
    server._transport = None


def mock(handler):
    """Install a mock transport and record every request it receives."""
    seen = []

    def wrapper(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    server._transport = httpx.MockTransport(wrapper)
    return seen


def run(coro):
    return asyncio.run(coro)


POST = {"id": 7, "title": "Hello", "body": "World", "tags": ["a"]}


# --- configuration --------------------------------------------------------- #
def test_missing_token_returns_error_without_request(monkeypatch):
    monkeypatch.delenv("PRACTICE_API_TOKEN")
    seen = mock(lambda r: httpx.Response(200, json=[]))
    result = run(server.list_posts())
    assert "PRACTICE_API_TOKEN is not set" in result
    assert seen == []


def test_default_base_url(monkeypatch):
    monkeypatch.delenv("PRACTICE_API_URL")
    assert server._base_url() == "https://practice.fhsucyber.com"


def test_timeout_env(monkeypatch):
    monkeypatch.setenv("PRACTICE_API_TIMEOUT", "3")
    assert server._timeout_seconds() == 3.0
    monkeypatch.setenv("PRACTICE_API_TIMEOUT", "nope")
    assert server._timeout_seconds() == server.DEFAULT_TIMEOUT


# --- read tools ------------------------------------------------------------ #
def test_list_posts_sends_bearer_and_url():
    seen = mock(lambda r: httpx.Response(200, json=[POST]))
    result = run(server.list_posts())
    req = seen[0]
    assert req.method == "GET"
    assert str(req.url) == "https://api.example.test/api/v1/posts"
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"
    assert json.loads(result) == [POST]


def test_list_posts_mine_adds_query():
    seen = mock(lambda r: httpx.Response(200, json=[]))
    run(server.list_posts(mine=True))
    assert seen[0].url.params["mine"] == "true"


def test_get_post():
    seen = mock(lambda r: httpx.Response(200, json=POST))
    result = run(server.get_post(7))
    assert seen[0].url.path == "/api/v1/posts/7"
    assert json.loads(result)["title"] == "Hello"


# --- write tools ----------------------------------------------------------- #
def test_create_post_payload():
    seen = mock(lambda r: httpx.Response(201, json=POST))
    result = run(server.create_post("Hello", "World", ["a"]))
    req = seen[0]
    assert req.method == "POST"
    assert json.loads(req.content) == {"title": "Hello", "body": "World", "tags": ["a"]}
    assert json.loads(result)["id"] == 7


def test_create_post_rejects_blank_title():
    seen = mock(lambda r: httpx.Response(201, json=POST))
    assert "title cannot be empty" in run(server.create_post("  ", "x"))
    assert seen == []


def test_update_post_sends_only_given_fields():
    seen = mock(lambda r: httpx.Response(200, json=POST))
    run(server.update_post(7, title="New"))
    req = seen[0]
    assert req.method == "PATCH"
    assert req.url.path == "/api/v1/posts/7"
    assert json.loads(req.content) == {"title": "New"}


def test_update_post_with_nothing_makes_no_request():
    seen = mock(lambda r: httpx.Response(200, json=POST))
    assert "Nothing to update" in run(server.update_post(7))
    assert seen == []


def test_delete_post_204():
    seen = mock(lambda r: httpx.Response(204))
    result = run(server.delete_post(7))
    assert seen[0].method == "DELETE"
    assert result == "Post 7 deleted successfully."


# --- error handling -------------------------------------------------------- #
@pytest.mark.parametrize(
    "status, expected",
    [
        (401, "Error 401 Unauthorized"),
        (403, "Error 403 Forbidden: you are not allowed to modify post 7"),
        (404, "Error 404 Not Found: post 7 does not exist"),
        (422, "Error 422 Bad Request"),
        (500, "Error 500"),
    ],
)
def test_http_errors_become_messages(status, expected):
    mock(lambda r: httpx.Response(status, json={"detail": "nope"}))
    result = run(server.delete_post(7))
    assert result.startswith(expected)
    assert "(API said: nope)" in result


def test_timeout_is_reported():
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)

    mock(boom)
    assert "timed out" in run(server.get_post(1))


def test_connection_error_is_reported():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    mock(boom)
    assert "could not reach the API" in run(server.get_post(1))


def test_tools_registered():
    names = {t.name for t in run(server.mcp.list_tools())}
    assert names == {"list_posts", "get_post", "create_post", "update_post", "delete_post"}
