"""The MCP 201 server plus one skill. FastMCP 4.2.0a1 only; run from the second venv.

    .venv-skills/bin/python skills_server.py            (port 8201, in place of server.py)

A skill (SEP-2640) is a SKILL.md with supporting files that the server
publishes once, as skill://<name>/... resources and through skills/list, so
every agent reads the same playbook instead of each person pasting it into a
prompt. Claude Code has no skills/list support yet, but it attaches any MCP
resource with @server:uri, which is how the live demo uses it:

    @weather:skill://rain-outlook/SKILL.md  will it rain in Denver this weekend?

Everything else (auth, scopes, middleware, tasks, elicitation) is server.py,
imported unchanged. The stable 4.1.4 server never sees the alpha.
"""

import os
from pathlib import Path

from fastmcp.skills import Skill
from fastmcp.skills.provider import SkillCatalogProvider

from server import mcp

# Skill.from_directory reads SKILL.md (frontmatter: name, description; body:
# the instructions) plus any files beside it. SkillCatalogProvider serves the
# catalog. The skill text is written so the answer visibly changes shape:
# without it the agent answers however it likes.
# Gotcha: on 4.2.0a1 a search or code-mode transform empties skills/list, so
# the skill sits on the plain server; the skill:// resources read either way.
rain_outlook = Skill.from_directory(Path(__file__).parent / "skills" / "rain-outlook")
mcp.add_provider(SkillCatalogProvider([rain_outlook]))


if __name__ == "__main__":
    from lab import PORT

    mcp.run(transport="http", port=int(os.environ.get("PORT", PORT)), show_banner=False)
