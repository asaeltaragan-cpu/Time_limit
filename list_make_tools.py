"""List the tool names that the Make MCP server exposes for your token (names only).

Use it to check that the token is scoped to the one scenario "Lock agent - actions", and to
get the exact tool name for the allow-list in spec.md. The token is read from the
MAKE_MCP_TOKEN environment variable and never printed.

    $env:MAKE_MCP_TOKEN = "..."
    python list_make_tools.py
"""

import json
import os
import sys
import urllib.request

MCP_URL = "https://eu2.make.com/mcp"

token = os.environ.get("MAKE_MCP_TOKEN")
if not token:
    sys.exit("Set MAKE_MCP_TOKEN first (see the docstring).")

request = urllib.request.Request(
    MCP_URL,
    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        # urllib's default User-Agent is often blocked (403) by web firewalls.
        "User-Agent": "Mozilla/5.0 (compatible; lock-notice-setup/1.0)",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code} {exc.reason}")
    print(exc.read().decode("utf-8", "replace")[:400])  # server message only, never the token
    sys.exit(1)

# The reply is JSON or a single server-sent event ("data: {...}").
payload = next(
    (json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")),
    None,
) or json.loads(body)

tools = payload.get("result", {}).get("tools", [])
# Optional filter: python list_make_tools.py lock   (shows only names containing "lock")
needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
shown = [t for t in tools if needle in t["name"].lower()]
print(f"{len(tools)} tool(s) exposed, {len(shown)} shown:")
for tool in shown:
    print(f"- {tool['name']}")
