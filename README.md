# Mini Project 7 – Practice Hub MCP Server

**INF601 – Advanced Programming in Python** · Gabriel Itegbe

## Overview

`server.py` is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server. It wraps the
Practice Hub REST API (`https://practice.fhsucyber.com`) so an AI agent such as **Claude Code** can list, read,
create, edit, and delete posts through natural-language requests.

It is built with the official MCP Python SDK 2.x (`MCPServer`, formerly `FastMCP`) and uses `httpx.AsyncClient`
for non-blocking HTTP calls. Every request carries `Authorization: Bearer <PRACTICE_API_TOKEN>`.

| Tool | HTTP call | Purpose |
|------|-----------|---------|
| `list_posts(mine=False)` | `GET /api/v1/posts` (`?mine=true` when `mine` is true) | List all posts, or only your own |
| `get_post(id)` | `GET /api/v1/posts/{id}` | Fetch one post |
| `create_post(title, body, tags=[])` | `POST /api/v1/posts` | Create a new post |
| `update_post(id, title=None, body=None, tags=None)` | `PATCH /api/v1/posts/{id}` | Change only the fields you pass |
| `delete_post(id)` | `DELETE /api/v1/posts/{id}` | Delete one of your posts |

### Error handling

API and network failures never crash the server. Each tool returns a readable message string instead:

| Situation | Message starts with |
|-----------|---------------------|
| Missing `PRACTICE_API_TOKEN` (checked before any request) | `Error: PRACTICE_API_TOKEN is not set` |
| Invalid or expired token | `Error 401 Unauthorized` |
| Editing or deleting a post you don't own | `Error 403 Forbidden` |
| Post ID doesn't exist | `Error 404 Not Found` |
| Bad input (400/422), rate limit (429), server error (5xx) | `Error <status> …` |
| Timeout or unreachable host | `Error: the request … timed out` / `Error: could not reach the API` |

The API's own `detail` text is appended to each message, for example `(API said: Post not found.)`.

## Project files

```
mini-project-7/
├── server.py              # The MCP server
├── requirements.txt       # Runtime dependencies
├── requirements-dev.txt   # Adds pytest for running the tests
├── tests/
│   ├── conftest.py
│   ├── test_server.py     # Unit tests (mocked HTTP, no network)
│   └── test_live.py       # Live API round trip (runs only when a token is set)
├── .env.example           # Template for local environment variables
├── .gitignore
└── README.md
```

## Setup

Requires **Python 3.10+** (developed and tested on Python 3.13 on Windows 11).

### 1. Create a virtual environment and install dependencies

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

Use `requirements.txt` instead if you only need to run the server and not the tests.

### 2. Environment variables

The server reads its configuration only from environment variables. The token is never hardcoded.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PRACTICE_API_TOKEN` | Yes | – | Your personal Practice Hub API token |
| `PRACTICE_API_URL` | No | `https://practice.fhsucyber.com` | Base URL of the API |
| `PRACTICE_API_TIMEOUT` | No | `15` | Request timeout in seconds |

You can supply them through `claude mcp add --env` (recommended; see below), or by copying `.env.example` to
`.env` (loaded by `python-dotenv`). `.env` is git-ignored, so don't commit it.

## Connecting to Claude Code

Claude Code launches the server over **stdio**. Use absolute paths to the venv's Python and to `server.py` so the
server runs with the right interpreter no matter which directory Claude is started from. Replace the paths and
`your-token-here`:

```powershell
claude mcp add --transport stdio practice-hub --env PRACTICE_API_URL=https://practice.fhsucyber.com --env PRACTICE_API_TOKEN=your-token-here -- "C:\path\to\mini-project-7\venv\Scripts\python.exe" "C:\path\to\mini-project-7\server.py"
```

macOS / Linux:

```bash
claude mcp add --transport stdio practice-hub --env PRACTICE_API_URL=https://practice.fhsucyber.com --env PRACTICE_API_TOKEN=your-token-here -- /path/to/mini-project-7/venv/bin/python /path/to/mini-project-7/server.py
```

Then check it:

```bash
claude mcp list
```

`practice-hub` should show as **connected**, and `/mcp` inside Claude Code lists the five tools. To remove it, run
`claude mcp remove practice-hub`.

## Testing

Unit tests replace the network with `httpx.MockTransport`. They check URLs, the Bearer header, request payloads,
PATCH sending only the fields you pass, and every error path (401/403/404/422/5xx, timeout, connection error,
missing token):

```bash
python -m pytest -v
```

The live test (`tests/test_live.py`) runs only when `PRACTICE_API_TOKEN` is set. It creates a post, reads it,
updates it, deletes it, and confirms a 404 afterwards, so it leaves nothing behind. It also checks that a bad token
gets a 401:

```powershell
$env:PRACTICE_API_TOKEN = "your-token-here"
python -m pytest -v
```

Last run: **21 passed** (19 unit tests and 2 live tests against `https://practice.fhsucyber.com`). The server was
also tested end to end over stdio with an MCP client: all five tools were listed and `list_posts` returned
`200 OK`.

### Manual acceptance prompts in Claude Code

1. *"List all posts on Practice Hub."* → `list_posts`
2. *"Show only my posts."* → `list_posts(mine=true)`
3. *"Create a post titled 'Hello from MCP' with body 'Testing MP7' and tags python, mcp."* → `create_post`; note the ID
4. *"Get post &lt;ID&gt;."* → `get_post`
5. *"Change the title of post &lt;ID&gt; to 'Updated from MCP'."* → `update_post` sends only `title`
6. *"Delete a post that someone else wrote."* → clear `Error 403 Forbidden` message; the server keeps running
7. *"Get post 99999999."* → `Error 404 Not Found`
8. *"Delete post &lt;ID&gt;."* → success; a later `get_post` returns 404

## What I Did & Key Decisions

### Windows environment troubleshooting

The first attempt to run Python failed: `python` and `py` resolved to the Windows Store **App Execution Alias**
stubs in `%LOCALAPPDATA%\Microsoft\WindowsApps`, which returned "Permission denied" instead of starting an
interpreter. I fixed this by disabling the broken `python.exe` / `py.exe` aliases in Windows Settings
(*Apps → Advanced app settings → App execution aliases*), installing a working Python 3.13, and creating a clean
project-local `venv`. All dependencies are installed into that venv, and Claude Code is pointed at
`venv\Scripts\python.exe` directly so it never depends on what `python` resolves to on `PATH`.

### Dependency and SDK versioning

The assignment referenced `from mcp.server.fastmcp import FastMCP`. The venv installed **mcp 2.3.0**, where FastMCP
was renamed to **`MCPServer`** (`from mcp.server.mcpserver import MCPServer`), so the old import raises
`ModuleNotFoundError`. I had two options:

- pin `mcp<2` and keep the FastMCP import, or
- move to the current 2.x API.

I chose the current SDK (`mcp>=2.3,<3`), because the decorator-based tool API is the same and it avoids building on
a deprecated module. `httpx` is pinned to `>=0.28,<1`, and `pytest` lives in `requirements-dev.txt` so the runtime
install stays small.

### Environment injection and stdio transport

Claude Code starts local MCP servers as a child process over stdio, so the server can't rely on the shell it was
started from. The `claude mcp add` command injects `PRACTICE_API_URL` and `PRACTICE_API_TOKEN` with `--env` and uses
absolute paths for both the interpreter and the script. `python-dotenv` is optional and never overrides variables
that are already set. The token lives only in the environment or in a git-ignored `.env`.

### Code changes to `server.py`

- **Async HTTP:** switched from a blocking `httpx.Client` to `httpx.AsyncClient`, and made all five tools
  `async def`, so a slow API call doesn't block the server's event loop.
- **Endpoints and headers:** centralized the `/api/v1/posts` path, sent `Authorization: Bearer …` and
  `Accept: application/json` on every request, and normalized `PRACTICE_API_URL` (trailing slash, blank value).
- **Timeouts:** a configurable `PRACTICE_API_TIMEOUT` (default 15 s) with a shorter connect timeout, falling back
  safely if the value is invalid.
- **Error handling:** status-specific messages for 401/403/404/400/422/429/5xx that include the API's `detail`
  text, separate handling for timeouts and connection errors, and a token check before any request is sent.
- **Input checks:** `update_post` refuses to send an empty PATCH, `create_post` rejects a blank title, and `tags`
  defaults to an empty list.
- **Docstrings:** each tool's docstring says *when* to call it (for example "only when the user clearly asks to
  delete") so the agent picks the right tool.
- **Security cleanup:** removed a pasted `claude mcp add …` line that had a live token in it and was also a syntax
  error.
- **Testability:** a module-level `_transport` hook lets the tests swap in `httpx.MockTransport` without patching
  internals.

## AI Usage

I used **Claude Code** (Anthropic, Claude Opus 5.5) as an assistant on this project.

### Where AI helped

- Drafting the first MCP tool boilerplate in `server.py` (the five tools, the shared request helper, and error
  mapping).
- Scaffolding the test suite (mocked unit tests and the live round-trip test).
- Diagnosing the Windows Store stub errors (`python` / `py` returning "Permission denied") and explaining the MCP
  SDK 2.x rename from `FastMCP` to `MCPServer`.

### Where I worked and decided

- Debugging my local Windows settings: disabling the broken App Execution Aliases, installing Python 3.13, and
  building the venv.
- Choosing the dependency and SDK strategy (moving to `mcp` 2.x and `MCPServer` instead of pinning to the old
  FastMCP).
- Managing my API credentials: keeping the token out of source code and git, and injecting it through
  environment variables.
- Checking that the server actually runs: registering it with Claude Code and running the tools against the live
  API.
- Reviewing and changing `server.py`: endpoint paths and headers, timeout and error-handling behavior, and tool
  docstrings.

*AI was also used to help optimize and format this README.md documentation.*
