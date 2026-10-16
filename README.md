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
| `agent.md` | Agent definition: model, tool policy, system prompt |
| `environment.yaml` | Cloud environment with limited networking |
| `test-data/` | Fictitious CSVs for the rehearsal session |

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

Rehearsal not yet run. Open items:

- Customer messaging channel and contact columns in the report
- How the daily report reaches Drive
- Wiring Google Drive, Sheets, and Gmail to the agent through MCP and a vault
- Date format assumed DD/MM/YYYY
- Message templates (T-4 and T-1)
