"""
Live integration test against the real Practice Hub API.

Skipped unless PRACTICE_API_TOKEN is set in the environment. It creates a
post, reads it, updates it, and deletes it again, so it leaves nothing behind.

    PRACTICE_API_TOKEN=... python -m pytest tests/test_live.py -v
"""

import asyncio
import json
import os

import pytest

import server

pytestmark = pytest.mark.skipif(
    not os.environ.get("PRACTICE_API_TOKEN"),
    reason="PRACTICE_API_TOKEN not set; skipping live API test",
)


def run(coro):
    return asyncio.run(coro)


def test_live_crud_round_trip():
    server._transport = None

    listed = run(server.list_posts(mine=True))
    assert not listed.startswith("Error"), listed
    assert isinstance(json.loads(listed), list)

    created = run(server.create_post("MP7 live test", "Temporary post from pytest", ["mp7", "test"]))
    assert not created.startswith("Error"), created
    post = json.loads(created)
    post_id = post["id"]

    try:
        fetched = json.loads(run(server.get_post(post_id)))
        assert fetched["title"] == "MP7 live test"

        updated = json.loads(run(server.update_post(post_id, title="MP7 live test (edited)")))
        assert updated["title"] == "MP7 live test (edited)"
        assert updated["body"] == "Temporary post from pytest"
    finally:
        deleted = run(server.delete_post(post_id))
        assert deleted == f"Post {post_id} deleted successfully.", deleted

    missing = run(server.get_post(post_id))
    assert missing.startswith("Error 404"), missing


def test_live_bad_token(monkeypatch):
    monkeypatch.setenv("PRACTICE_API_TOKEN", "definitely-not-valid")
    result = run(server.list_posts())
    assert result.startswith("Error 401"), result
