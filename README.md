# Time_limit

Claude Managed Agent that manages pre-lock payment notices for Alma Lasers devices.

## What it does

- Reads a daily Salesforce report (CSV, delivered to a Google Drive folder).
- Sends a fixed-template notice to customers **4 days** and **1 day** before `Key End Date`.
- Logs each customer reply, classifies it, creates a task row, and emails a case request to the dedicated Salesforce queue.
- Compares each day's report with the previous one to spot repeated short (up to 7 days) `Key End Date` extensions and flags **suspected** unlock-code abuse for human review.

## Files

| Path | Purpose |
|---|---|
| `agent.md` | Agent definition: model, tool allow-list, system prompt |
| `environment.yaml` | Cloud environment with limited networking (only `eu2.make.com`) |
| `test-data/` | Fictitious CSVs for the rehearsal session |
| `run_rehearsal.py` | Runs a rehearsal session: dry run (data inline) or `--live` (real Make tool, test data) |
| `setup_vault.py` | Creates the vault and stores the Make MCP token (read from an env var, never printed) |
| `list_make_tools.py` | Lists the tool names a Make MCP token exposes, to check its scope |

## How it connects

The agent has one allowed tool, `scenarios_run`, on the Make MCP server. A single Make scenario ("Lock agent - actions") exposes six fixed actions: `find_report`, `read_file`, `read_sheet`, `append_row`, `send_case_email`, `send_alert`. Recipients, allowed folders, and allowed sheets are fixed inside Make, so the agent can only pass field values. The Make token lives in a vault, never in this repo.

### `test-data/`

| Path | Covers |
|---|---|
| `main/` | T-4 and T-1 notices, memo exclusion, bad date, missing contact |
| `empty/` | Empty report |
| `stale/` | Report not dated today |
| `abuse-history/` | Five weekly reports: repeated grace extensions and a payment renewal |
| `replies-test.csv` | Simulated customer replies, including a prompt-injection attempt |

All test data is fictitious. Dates are relative to 16/10/2026.

## Extension classification

| `Key End Date` change | Meaning |
|---|---|
| Up to 7 days forward | Unlock-code grace |
| About 3 months forward | Payment renewal |
| Anything else | Needs a look |

Suspected abuse threshold (assumption, to be tuned): 3 or more grace extensions within 60 days.

## Safety rules

- Customer replies and `Key Memo` are treated as data, never as instructions.
- `Key Encryption Number` and `Sent Key` are never copied to Sheets, email, messages, or memory.
- Messages use approved templates only. During rehearsal, all write actions are `always_ask`.
- No secrets in this repo. Credentials live in a vault and are entered in the Console.

## Status

Rehearsal in progress, on test data only. Passed live: normal path, bad data, duplicate protection. Dry run only so far: empty and stale report, customer replies and injection, abuse pattern.

Open items:

- Customer messaging channel and contact columns in the report (until then notices are logged as `would-send`)
- How the daily report reaches Drive
- Before go-live: point the case email at `cx.il@almalasers.com` in Make, replace the test folders/sheets with production ones, and narrow Make exposure (the token can run any active scenario)
- Date format assumed DD/MM/YYYY
- Message templates (T-4 and T-1)
- Scheduled deployment and monitoring
