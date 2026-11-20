# Mini Project 7 – Practice Hub MCP Server

*INF601 – Advanced Programming in Python* · Gabriel Itegbe

## Overview

server.py is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server. It wraps the
Practice Hub REST API (https://practice.fhsucyber.com) so an AI agent such as *Claude Code* can list, read,
create, edit, and delete posts through natural-language requests.

It is built with the official MCP Python SDK 2.x (MCPServer, formerly FastMCP) and uses httpx.AsyncClient
for non-blocking HTTP calls. Every request carries Authorization: Bearer <PRACTICE_API_TOKEN>.

| Tool | HTTP call | Purpose |
|------|-----------|---------|
| list_posts(mine=False) | GET /api/v1/posts (?mine=true when mine is true) | List all posts, or only your own |
| get_post(id) | GET /api/v1/posts/{id} | Fetch one post |
| create_post(title, body, tags=[]) | POST /api/v1/posts | Create a new post |
| update_post(id, title=None, body=None, tags=None) | PATCH /api/v1/posts/{id} | Change only the fields you pass |
| delete_post(id) | DELETE /api/v1/posts/{id} | Delete one of your posts |

### Error handling

API and network failures never crash the server. Each tool returns a readable message string instead:

| Situation | Message starts with |
|-----------|---------------------|
| Missing PRACTICE_API_TOKEN (checked before any request) | Error: PRACTICE_API_TOKEN is not set |
| Invalid or expired token | Error 401 Unauthorized |
| Editing or deleting a post you don't own | Error 403 Forbidden |
| Post ID doesn't exist | Error 404 Not Found |
| Bad input (400/422), rate limit (429), server error (5xx) | Error <status> … |
| Timeout or unreachable host | Error: the request … timed out / Error: could not reach the API |

The API's own detail text is appended to each message, for example (API said: Post not found.).

## Project files


mini-project-7/
├── server.py              # The MCP server
├── run_mcp_skill.py       # Week 14: drives the agent from Python with the Claude Agent SDK
├── run_log.txt            # Week 14: console output of the successful agent run
├── .mcp.json              # Week 14: project-level MCP server config for Claude Code
├── .claude/
│   ├── settings.json      # Week 14: tool permissions (allow list)
│   └── skills/
│       └── post-summarizer/
│           └── SKILL.md   # Week 14: the Agent Skill
├── requirements.txt       # Runtime dependencies
├── requirements-dev.txt   # Adds pytest for running the tests
├── tests/
│   ├── conftest.py
│   ├── test_server.py     # Unit tests (mocked HTTP, no network)
│   └── test_live.py       # Live API round trip (runs only when a token is set)
├── .env.example           # Template for local environment variables
├── .gitignore
└── README.md


## Setup

Requires *Python 3.10+* (developed and tested on Python 3.13 on Windows 11).

### 1. Create a virtual environment and install dependencies

Windows (PowerShell):

powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt


macOS / Linux:

bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt


Use requirements.txt instead if you only need to run the server and not the tests.

### 2. Environment variables

The server reads its configuration only from environment variables. The token is never hardcoded.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PRACTICE_API_TOKEN | Yes | – | Your personal Practice Hub API token |
| PRACTICE_API_URL | No | https://practice.fhsucyber.com | Base URL of the API |
| PRACTICE_API_TIMEOUT | No | 15 | Request timeout in seconds |

You can supply them through claude mcp add --env (recommended; see below), or by copying .env.example to
.env (loaded by python-dotenv). .env is git-ignored, so don't commit it.

## Connecting to Claude Code

Claude Code launches the server over *stdio*. Use absolute paths to the venv's Python and to server.py so the
server runs with the right interpreter no matter which directory Claude is started from. Replace the paths and
your-token-here:

powershell
claude mcp add --transport stdio practice-hub --env PRACTICE_API_URL=https://practice.fhsucyber.com --env PRACTICE_API_TOKEN=your-token-here -- "C:\path\to\mini-project-7\venv\Scripts\python.exe" "C:\path\to\mini-project-7\server.py"


macOS / Linux:

bash
claude mcp add --transport stdio practice-hub --env PRACTICE_API_URL=https://practice.fhsucyber.com --env PRACTICE_API_TOKEN=your-token-here -- /path/to/mini-project-7/venv/bin/python /path/to/mini-project-7/server.py


Then check it:

bash
claude mcp list


practice-hub should show as *connected*, and /mcp inside Claude Code lists the five tools. To remove it, run
claude mcp remove practice-hub.

## Testing

Unit tests replace the network with httpx.MockTransport. They check URLs, the Bearer header, request payloads,
PATCH sending only the fields you pass, and every error path (401/403/404/422/5xx, timeout, connection error,
missing token):

bash
python -m pytest -v


The live test (tests/test_live.py) runs only when PRACTICE_API_TOKEN is set. It creates a post, reads it,
updates it, deletes it, and confirms a 404 afterwards, so it leaves nothing behind. It also checks that a bad token
gets a 401:

powershell
$env:PRACTICE_API_TOKEN = "your-token-here"
python -m pytest -v


Last run: *21 passed* (19 unit tests and 2 live tests against https://practice.fhsucyber.com). The server was
also tested end to end over stdio with an MCP client: all five tools were listed and list_posts returned
200 OK.

### Manual acceptance prompts in Claude Code

1. "List all posts on Practice Hub." → list_posts
2. "Show only my posts." → list_posts(mine=true)
3. "Create a post titled 'Hello from MCP' with body 'Testing MP7' and tags python, mcp." → create_post; note the ID
4. "Get post &lt;ID&gt;." → get_post
5. "Change the title of post &lt;ID&gt; to 'Updated from MCP'." → update_post sends only title
6. "Delete a post that someone else wrote." → clear Error 403 Forbidden message; the server keeps running
7. "Get post 99999999." → Error 404 Not Found
8. "Delete post &lt;ID&gt;." → success; a later get_post returns 404

## What I Did & Key Decisions

### Windows environment troubleshooting

The first attempt to run Python failed: python and py resolved to the Windows Store *App Execution Alias*
stubs in %LOCALAPPDATA%\Microsoft\WindowsApps, which returned "Permission denied" instead of starting an
interpreter. I fixed this by disabling the broken python.exe / py.exe aliases in Windows Settings
(Apps → Advanced app settings → App execution aliases), installing a working Python 3.13, and creating a clean
project-local venv. All dependencies are installed into that venv, and Claude Code is pointed at
venv\Scripts\python.exe directly so it never depends on what python resolves to on PATH.

### Dependency and SDK versioning

The assignment referenced from mcp.server.fastmcp import FastMCP. The venv installed *mcp 2.3.0*, where FastMCP
was renamed to *MCPServer* (from mcp.server.mcpserver import MCPServer), so the old import raises
ModuleNotFoundError. I had two options:

- pin mcp<2 and keep the FastMCP import, or
- move to the current 2.x API.

I chose the current SDK (mcp>=2.3,<3), because the decorator-based tool API is the same and it avoids building on
a deprecated module. httpx is pinned to >=0.28,<1, and pytest lives in requirements-dev.txt so the runtime
install stays small.

### Environment injection and stdio transport

Claude Code starts local MCP servers as a child process over stdio, so the server can't rely on the shell it was
started from. The claude mcp add command injects PRACTICE_API_URL and PRACTICE_API_TOKEN with --env and uses
absolute paths for both the interpreter and the script. python-dotenv is optional and never overrides variables
that are already set. The token lives only in the environment or in a git-ignored .env.

### Code changes to server.py

- *Async HTTP:* switched from a blocking httpx.Client to httpx.AsyncClient, and made all five tools
  async def, so a slow API call doesn't block the server's event loop.
- *Endpoints and headers:* centralized the /api/v1/posts path, sent Authorization: Bearer … and
  Accept: application/json on every request, and normalized PRACTICE_API_URL (trailing slash, blank value).
- *Timeouts:* a configurable PRACTICE_API_TIMEOUT (default 15 s) with a shorter connect timeout, falling back
  safely if the value is invalid.
- *Error handling:* status-specific messages for 401/403/404/400/422/429/5xx that include the API's detail
  text, separate handling for timeouts and connection errors, and a token check before any request is sent.
- *Input checks:* update_post refuses to send an empty PATCH, create_post rejects a blank title, and tags
  defaults to an empty list.
- *Docstrings:* each tool's docstring says when to call it (for example "only when the user clearly asks to
  delete") so the agent picks the right tool.
- *Security cleanup:* removed a pasted claude mcp add … line that had a live token in it and was also a syntax
  error.
- *Testability:* a module-level _transport hook lets the tests swap in httpx.MockTransport without patching
  internals.

## Week 14 Extension: Agent Skill + Claude Agent SDK

Week 14 builds on the MCP server above. The goal is to package a repeatable workflow as an *Agent Skill*, then
drive an agent that uses the server and the skill *from Python* with the Claude Agent SDK, instead of chatting
with it. The SDK runs Claude Code under the hood, so it authenticates through the Claude Code subscription and
needs no separate API key.

### Step 1: Install Claude Code on Windows

Installed the Claude Code CLI from PowerShell:

powershell
irm https://claude.ai/install.ps1 | iex


My first attempt failed because a Markdown link got pasted into the command instead of the plain URL. After
fixing that and making sure the install folder was on PATH, claude ran from any PowerShell window. Inside
Claude Code I used /mcp (server status), /skills and /reload-skills (skill discovery), and /doctor
(diagnostics).

### Step 2: Point Claude Code at the server with .mcp.json

I added a project-level .mcp.json that launches server.py with the venv's interpreter. Absolute paths to both
python.exe and server.py keep the server on the right interpreter, as in the stdio section above:

json
{
  "mcpServers": {
    "mini-project-7": {
      "command": "C:\\path\\to\\mini-project-7\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\mini-project-7\\server.py"]
    }
  }
}


The first version of this file raised a JSONDecodeError. I regenerated it with Python's json.dumps and UTF-8
encoding, which fixed the encoding problem. Note that the tools registered through this file are named
mcp__mini-project-7__<tool>, while the earlier claude mcp add example registers the same server as
practice-hub. The paths are specific to my machine, so anyone else running this must edit them.

### Step 3: Write the Agent Skill

A skill is a folder containing a SKILL.md: YAML front-matter (name, description) plus Markdown instructions
the model follows when the skill is relevant. Mine lives at .claude/skills/post-summarizer/SKILL.md:

markdown
---
name: post-summarizer
description: Summarize recent Practice Hub posts into a single study-note post using the mini-project-7 MCP tools.
---
# Steps
1. Call list_posts, then take the 25 newest posts.
2. Group by theme; write a short Markdown summary.
3. Call create_post with the title "Study Note — Practice Hub Digest", then confirm what was created and give its ID.


My first draft used vague wording such as "the MCP read/list tool", which made the agent guess. I replaced it with
the real tool names from server.py. I also found that list_posts has no limit parameter (it only has mine),
so the original "limit 25" step didn't match the server. The skill now says to fetch the posts and take the 25
newest.

### Step 4: Drive the agent from Python with the Agent SDK

run_mcp_skill.py uses the Claude Agent SDK to start an agent, load the project's skill and MCP server, send one
prompt, and print every tool call plus the final result:

powershell
.\venv\Scripts\python.exe -m pip install claude-agent-sdk anyio
$env:PRACTICE_API_TOKEN = "your-token-here"
.\venv\Scripts\python.exe run_mcp_skill.py


Key settings in ClaudeAgentOptions:

| Option | Value | Why |
|--------|-------|-----|
| cwd | project folder | Lets the SDK find .claude/ and the server |
| setting_sources | ["project"] | Loads the project's skill and settings.json |
| mcp_servers | mini-project-7 (venv Python + server.py) | Starts the server with the token passed in env |
| allowed_tools | list_posts, create_post, Skill (exact names) | Only what the workflow needs |
| max_turns | 20 | The default run hit a 6-turn limit |

The script prints each ToolUseBlock as [Tool Call] <name> -> <input> and reports the ResultMessage subtype
and number of turns. It catches ClaudeSDKError for SDK failures.

Problems I hit and how I fixed them:

- *ModuleNotFoundError: No module named 'claude_agent_sdk':* the SDK was missing from the venv. Installing
  claude-agent-sdk and anyio with the venv's own python.exe -m pip fixed it.
- *Turn limit:* the first run stopped at 6 turns, so I raised max_turns to 20 and made the skill steps
  explicit.
- *ResultError import:* this class doesn't exist in the SDK. Failures such as the turn limit show up on the
  ResultMessage, and SDK exceptions derive from ClaudeSDKError, so I switched to that.

### Step 5: Permissions blocked the first run (harness customization)

The first complete run ended with the agent saying it could not use mcp__mini-project-7__list_posts because
Claude Code needed my permission and the session could not ask. A script has no terminal to approve a prompt, so
the harness refused the tool call and nothing was fetched or published. This is the Week 14 point about
permissions: they are part of the harness, and they decide what the agent may do without asking.

I fixed it in two places. First, I replaced the wildcard in allowed_tools with the exact tool names. Second, I
added a project permissions file, which setting_sources=["project"] loads:

json
{
  "permissions": {
    "allow": [
      "mcp__mini-project-7__list_posts",
      "mcp__mini-project-7__create_post"
    ]
  }
}


update_post and delete_post are deliberately *not* in the allow list, so the harness still asks before
anything that edits or removes data.

### Step 6: Successful run

With permissions fixed, the run showed [Tool Call] lines for the skill, then list_posts, then create_post. The
list tool returned all posts, and the agent summarized the 25 newest (#42–#68, Sept 23 – Nov 19) into four themes:

| Theme | Posts | Notes |
|-------|-------|-------|
| Mini Project 7 acceptance tests | 13 | Students creating a post through their own server, then editing it |
| Showcase of all five tools | 1 | Post #58, written in Claude's voice, using list, create, update, delete and get |
| Duplicate test posts | 6 | #50–#55, all titled "Test Post" with body "test" |
| Instructor daily check-ins | 5 | #42–#46, Sept 23–27, for the Scheduled Bot lab |

It published the result as *"Study Note — Practice Hub Digest"* (post #70, tagged study-note, digest, mcp,
inf601) with a short takeaways section. The full console output is saved in run_log.txt.

### Step 7: Clean up the test post

Every run of the script publishes a new post, so I deleted post #70 once the run was documented. The server
returned 204 No Content for the delete and 404 Not Found when I fetched the post again, which confirms it is
gone. I made that call directly through server.py with the project venv, because the mini-project-7 MCP server
was not connected in Claude Code at that moment. Because the call bypassed the MCP tool layer, the permission gate
did not apply to it. Permissions control the tools the harness exposes to the agent, not every way a process can
reach the API.

### What I learned

- *Skills vs. prompts:* a skill packages a repeatable multi-step workflow so I don't retype it, but it only works
  well when it names real tools and matches what the server actually does.
- *Harness vs. model:* the model proposes tool calls, but the harness decides whether they run. Permissions are a
  design choice, and a tight allowed_tools list plus an allow file is a safer default than bypassing prompts.
- *Agent as a library:* the same agent I normally chat with can be started, configured, and logged from Python,
  which makes the workflow repeatable and easy to capture as evidence.

## AI Usage

I used *Claude Code* (Anthropic, Claude Opus 5.5) as an assistant on this project, and for the Week 14
extension I also used *Claude* in a chat conversation for guidance and debugging help.

### Where AI helped

- Drafting the first MCP tool boilerplate in server.py (the five tools, the shared request helper, and error
  mapping).
- Scaffolding the test suite (mocked unit tests and the live round-trip test).
- Diagnosing the Windows Store stub errors (python / py returning "Permission denied") and explaining the MCP
  SDK 2.x rename from FastMCP to MCPServer.
- *Week 14:* drafting the first version of SKILL.md and run_mcp_skill.py, and suggesting fixes for the
  problems above (missing SDK package, the nonexistent ResultError import, the .mcp.json encoding error, the
  turn limit, and the permission block).
- *Week 14:* the agent itself, run through the Agent SDK, fetched the posts, grouped them by theme, and wrote and
  published the summary post (#70).

### Where I worked and decided

- Debugging my local Windows settings: disabling the broken App Execution Aliases, installing Python 3.13, and
  building the venv.
- Choosing the dependency and SDK strategy (moving to mcp 2.x and MCPServer instead of pinning to the old
  FastMCP).
- Managing my API credentials: keeping the token out of source code and git, and injecting it through
  environment variables.
- Checking that the server actually runs: registering it with Claude Code and running the tools against the live
  API.
- Reviewing and changing server.py: endpoint paths and headers, timeout and error-handling behavior, and tool
  docstrings.
- *Week 14:* installing Claude Code and the SDK in my own venv, setting the token in my shell, and running and
  re-running the script until it worked.
- *Week 14:* deciding which tools to allow and which to leave gated (update_post and delete_post stay out of
  the allow list), and matching SKILL.md to what list_posts actually supports.
- *Week 14:* verifying the result, then deleting the test post and confirming the 204 and 404 responses.

AI was also used to help optimize and format this README.md documentation.