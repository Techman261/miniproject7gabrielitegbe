---
name: post-summarizer
description: Summarize recent Practice Hub posts into a single study-note post using the mini-project-7 MCP tools.
---
# Steps
1. Call list_posts, then take the 25 newest posts.
2. Group by theme; write a short Markdown summary.
3. Call create_post with the title "Study Note — Practice Hub Digest", then confirm what was created and give its ID.