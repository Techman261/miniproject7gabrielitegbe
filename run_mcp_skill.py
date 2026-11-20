# INF601 Advanced Programming in Python
# Gabriel Itegbe
# Week 14 - Agent SDK + MCP

from pathlib import Path
import sys
import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)


async def main() -> None:
    project_dir = Path(__file__).resolve().parent

    options = ClaudeAgentOptions(
        cwd=str(project_dir),
        setting_sources=["project"],
        mcp_servers={
            "mini-project-7": {
                "command": sys.executable,
                "args": [str(project_dir / "server.py")],
            }
        },
        allowed_tools=["mcp_mini-project-7_*", "Skill"],
        max_turns=20,
    )

    prompt = (
        "Use the post-summarizer skill to fetch recent items, group them by "
        "theme into a Markdown summary, and save/publish the result."
    )

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        print(f"[Tool Call] {block.name} -> {block.input}")
            elif isinstance(message, ResultMessage):
                if message.result:
                    print("\n=== Final Result ===")
                    print(message.result)
    except ResultError as exc:
        print(f"\n[Agent stopped with ResultError]: {exc}")


if __name__ == "__main__":
    anyio.run(main)