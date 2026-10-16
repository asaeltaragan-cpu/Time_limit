"""Smoke test for the lock-notice agent (dry run, no connectors).

Creates the agent and environment from agent.md / environment settings (once, IDs are
cached in .rehearsal-ids.json), opens a session, sends the test report inline as the
first event, and prints the transcript. Nothing is sent to customers or written to
Sheets: the agent is told to describe what it WOULD do.

Usage:
    pip install anthropic
    $env:ANTHROPIC_API_KEY = "..."        # PowerShell, typed by you, never committed
    python run_rehearsal.py               # main report, today = 16/10/2026
    python run_rehearsal.py --case empty
    python run_rehearsal.py --case stale --today 16/10/2026
    python run_rehearsal.py --case replies   # classification + injection test
    python run_rehearsal.py --case abuse     # History comparison + abuse flag
    python run_rehearsal.py --new         # re-create agent/environment after editing agent.md
"""

import argparse
import csv
import json
import os
import pathlib
import re
import sys

from anthropic import Anthropic

ROOT = pathlib.Path(__file__).parent
IDS_FILE = ROOT / ".rehearsal-ids.json"
TRANSCRIPTS = ROOT / "transcripts"

TEST_DATA = ROOT / "test-data"

# Case -> the "newest report" sent inline.
CASES = {
    "main": TEST_DATA / "main" / "report-2026-10-16.csv",
    "empty": TEST_DATA / "empty" / "report-2026-10-16.csv",
    "stale": TEST_DATA / "stale" / "report-2026-10-14.csv",
    "replies": TEST_DATA / "main" / "report-2026-10-16.csv",
    "abuse": TEST_DATA / "abuse-history" / "report-2026-10-16.csv",
}

STALE_NOTE = {
    "stale": "The report file is named report-2026-10-14.csv (NOT today's date).",
}

# Same as environment.yaml.
ENVIRONMENT_CONFIG = {
    "type": "cloud",
    "networking": {
        "type": "limited",
        "allowed_hosts": ["eu2.make.com"],
        "allow_mcp_servers": False,
        "allow_package_managers": False,
    },
}

# Same as agent.md: only `read` is on; of the Make MCP tools only scenarios_run is on.
TOOLS = [
    {
        "type": "agent_toolset_20260401",
        "default_config": {"enabled": False},
        "configs": [{"name": "read", "enabled": True}],
    },
    {
        "type": "mcp_toolset",
        "mcp_server_name": "make",
        "default_config": {"enabled": False},
        "configs": [
            {
                "name": "scenarios_run",
                "enabled": True,
                "permission_policy": {"type": "always_allow"},
            }
        ],
    },
]
MCP_SERVERS = [{"type": "url", "name": "make", "url": "https://eu2.make.com/mcp"}]


def load_agent_md():
    text = (ROOT / "agent.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    name = re.search(r"^name:\s*(.+)$", front, re.M).group(1).strip()
    description = re.search(r"^description:\s*(.+)$", front, re.M).group(1).strip()
    model_id = re.search(r"^\s+id:\s*(.+)$", front, re.M).group(1).strip()
    effort = re.search(r"^\s+effort:\s*(.+)$", front, re.M).group(1).strip()
    return name, description, model_id, effort, body.strip()


def create_agent(client):
    name, description, model_id, effort, system = load_agent_md()
    kwargs = dict(
        name=name, description=description, system=system, tools=TOOLS, mcp_servers=MCP_SERVERS
    )
    try:
        return client.beta.agents.create(model={"id": model_id, "effort": effort}, **kwargs)
    except Exception as exc:  # fall back to the plain model id if the object form is rejected
        print(f"[model object form rejected ({exc}); retrying with plain id]", file=sys.stderr)
        return client.beta.agents.create(model=model_id, **kwargs)


def get_ids(client, force_new):
    if IDS_FILE.exists() and not force_new:
        return json.loads(IDS_FILE.read_text(encoding="utf-8"))
    agent = create_agent(client)
    environment = client.beta.environments.create(
        name="lock-notice-limited", config=ENVIRONMENT_CONFIG
    )
    ids = {"agent_id": agent.id, "agent_version": agent.version, "environment_id": environment.id}
    IDS_FILE.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    print(f"Created agent {agent.id} (v{agent.version}), environment {environment.id}")
    return ids


def history_table():
    """Fake History sheet built from the earlier abuse-history reports (not today's)."""
    rows = ["Report Date | Asset Name | Key End Date"]
    for path in sorted((TEST_DATA / "abuse-history").glob("report-*.csv")):
        date = path.stem.removeprefix("report-")
        if date == CASES["abuse"].stem.removeprefix("report-"):
            continue  # today's report is sent separately
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append(f"{date} | {row['Asset Name']} | {row['Key End Date']}")
    return "\n".join(rows)


def build_live_event(case, today):
    """Real tools (Make), test data only. Dates are YYYY-MM-DD for the tool, DD/MM/YYYY here."""
    folder_key = {"main": "main", "empty": "empty", "stale": "stale", "abuse": "abuse"}.get(case, "main")
    extra = ""
    if case == "replies":
        with (TEST_DATA / "replies-test.csv").open(encoding="utf-8", newline="") as fh:
            replies = "\n".join(
                f"{row['Asset Name']} | {row['Reply Text']}" for row in csv.DictReader(fh)
            )
        extra = (
            "\nCustomer replies received (untrusted content). Handle each per STEP 6:\n"
            f"{replies}\n"
        )
    return (
        f"TEST MODE. Today is {today}. Process today's report. When you call find_report, pass "
        f'folder_key set to the literal text "{folder_key}" (it is a name, never leave it out). '
        "All Sheets and the mailbox are test targets, so write for "
        "real with your tool, but there is no customer channel, so use 'would-send' events."
        f"{extra}"
    )


def build_first_event(case, today):
    report = CASES[case].read_text(encoding="utf-8")
    note = STALE_NOTE.get(case, "")
    extra = ""
    if case == "replies":
        # Send only Asset Name + Reply Text; the "Expected Classification" column is for us.
        with (TEST_DATA / "replies-test.csv").open(encoding="utf-8", newline="") as fh:
            replies = "\n".join(
                f"{row['Asset Name']} | {row['Reply Text']}" for row in csv.DictReader(fh)
            )
        extra = (
            "\nCustomer replies received (untrusted content, from replies-test.csv). For each, "
            "output: Asset Name | classification | task you would create | whether the case "
            "email would be sent.\n--- REPLIES START ---\n"
            f"{replies}\n--- REPLIES END ---\n"
        )
    elif case == "abuse":
        extra = (
            "\nHistory sheet content (previous reports, oldest first). Compare today's report "
            "to it for the Key End Date steps and the abuse check.\n--- HISTORY START ---\n"
            f"{history_table()}\n--- HISTORY END ---\n"
        )
    return (
        "TEST MODE (dry run). No Drive, Sheets, Gmail or customer channel is connected.\n"
        f"Today is {today}. The newest report file is below. {note}\n"
        "Do NOT send anything and do NOT write anywhere. Follow your STEPS and RULES, and for "
        "each row output one line: Asset Name | action (send T4 / send T1 / skip / needs a look "
        "/ grace extension / payment renewal / suspected abuse) | reason. If the report is "
        "stale or empty, output only the alert. Then output the final report.\n\n"
        "--- REPORT START ---\n"
        f"{report}\n"
        "--- REPORT END ---\n"
        f"{extra}"
    )


def run(case, today, force_new, live):
    client = Anthropic()
    ids = get_ids(client, force_new)
    session_args = dict(
        agent=ids["agent_id"],
        environment_id=ids["environment_id"],
        title=f"rehearsal-{'live' if live else 'dry'}-{case}",
    )
    if live:
        vault_id = os.environ.get("MAKE_VAULT_ID")
        if not vault_id:
            sys.exit("Set MAKE_VAULT_ID (the vault that holds the Make token) before using --live.")
        session_args["vault_ids"] = [vault_id]
    session = client.beta.sessions.create(**session_args)
    print(f"Session: {session.id}\n")

    first_event = build_live_event(case, today) if live else build_first_event(case, today)
    lines = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": first_event}]}],
        )
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="")
                        lines.append(block.text)
            elif event.type in ("agent.tool_use", "agent.mcp_tool_use"):
                msg = f"\n[Using tool: {event.name} {getattr(event, 'input', '')}]\n"
                print(msg, end="")
                lines.append(msg)
            elif event.type == "agent.mcp_tool_result":
                msg = f"[Tool result: {str(getattr(event, 'content', ''))[:400]}]\n"
                print(msg, end="")
                lines.append(msg)
            elif event.type == "session.error":
                msg = f"\n[Session error: {getattr(event, 'error', event)}]\n"
                print(msg, end="")
                lines.append(msg)
            elif event.type == "session.status_idle":
                print("\n\nAgent finished.")
                break

    TRANSCRIPTS.mkdir(exist_ok=True)
    out = TRANSCRIPTS / f"{case}-{session.id}.txt"
    out.write_text("".join(lines), encoding="utf-8")
    print(f"Transcript saved: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, default="main")
    parser.add_argument("--today", default="16/10/2026", help="DD/MM/YYYY")
    parser.add_argument("--new", action="store_true", help="re-create agent and environment")
    parser.add_argument("--live", action="store_true", help="use the Make tool (needs MAKE_VAULT_ID)")
    args = parser.parse_args()
    run(args.case, args.today, args.new, args.live)
