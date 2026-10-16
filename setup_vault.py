"""Create the Managed Agents vault and store the Make MCP token in it.

The token is read from the MAKE_MCP_TOKEN environment variable and is never printed or
written to a file. Run once, then keep the printed vault ID (it is not a secret).

    $env:ANTHROPIC_API_KEY = "..."        # typed by you in the terminal
    $env:MAKE_MCP_TOKEN = "..."           # created in your Make profile (MCP token)
    python setup_vault.py
    $env:MAKE_VAULT_ID = "vlt_..."        # paste the printed ID, then run_rehearsal.py --live
"""

import json
import os
import sys
import urllib.error
import urllib.request

from anthropic import Anthropic

MCP_URL = "https://eu2.make.com/mcp"

token = (os.environ.get("MAKE_MCP_TOKEN") or "").strip()
if not token:
    sys.exit("Set MAKE_MCP_TOKEN first (see the docstring).")

# Check the token against Make BEFORE storing it, so a bad token never reaches the vault.
probe = urllib.request.Request(
    MCP_URL,
    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (compatible; lock-notice-setup/1.0)",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(probe, timeout=30):
        pass
except urllib.error.HTTPError as exc:
    sys.exit(f"Make rejected the token (HTTP {exc.code}). Fix MAKE_MCP_TOKEN, then rerun.")
print(f"Token accepted by Make (length {len(token)}).")

client = Anthropic()
vault = client.beta.vaults.create(
    display_name="Alma Lasers - lock notice",
    metadata={"client": "alma-lasers", "project": "Time_limit"},
)
client.beta.vaults.credentials.create(
    vault_id=vault.id,
    display_name="Make MCP token",
    auth={"type": "static_bearer", "mcp_server_url": MCP_URL, "token": token},
)
print(f"Vault created: {vault.id}")
