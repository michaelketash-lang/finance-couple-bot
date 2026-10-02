# Backend

Flask API running on PythonAnywhere. Receives transactions from three sources (Gmail, card webhooks, Telegram), parses them with GPT-4o, persists them to SQLite, and serves the dashboard and BFF endpoints.

## Entry Point

```bash
python flask_app.py
```

`flask_app.py` creates the Flask app, registers the API and BFF blueprints, starts the Telegram bot polling thread, and initializes the database on startup.

## Module Overview

### API & Routing

| File | Responsibility |
|------|---------------|
| `flask_app.py` | App factory, blueprint registration, `/webhook` (card alerts), `/gmail-webhook` (Pub/Sub push), `/health` |
| `api_routes.py` | REST endpoints: expenses CRUD, budgets, investments, Gmail watch renewal, Sheets export, AI insights trigger |
| `bff_routes.py` | Backend-for-frontend aggregation — computes KPIs, payer settlement, and category actuals in one round-trip so the dashboard makes a single request per page load |

### Transaction Ingestion

| File | Responsibility |
|------|---------------|
| `telegram_bot.py` | Receives manual expense input, sends inline-keyboard confirmation UI, handles button callbacks; pending transactions are persisted to SQLite so restarts don't lose them |
| `gmail_processor.py` | Fetches the 5 most recent emails via Gmail API (proxied through PythonAnywhere's outbound proxy), extracts PDF attachments and plain-text receipt bodies, deduplicates by message ID |
| `gmail_setup.py` | One-time OAuth flow to generate `token_michael.json` and `token_ofri.json`; also registers the Gmail Pub/Sub watch |

### AI

| File | Responsibility |
|------|---------------|
| `ai_parser.py` | Sends raw email/webhook text to GPT-4o; returns structured JSON with merchant, amount, category, payer, and split |
| `ai_insights.py` | Queries recent spending data, sends a summary prompt to GPT-4o-mini every 3 days, and delivers the result to both users via Telegram |

### Database

| File | Responsibility |
|------|---------------|
| `database_manager.py` | SQLite setup, table creation, and shared helpers: `is_email_processed`, `mark_email_processed`, `save/load/delete_pending_txn`, `save_ai_insight`, `mark_insight_read`, `cleanup_pending_txns` |
| `db_expenses.py` | Expense read/write queries |
| `db_budgets.py` | Budget target read/write queries |
| `db_investments.py` | Investment snapshot read/write queries |
| `db_insights.py` | Fetches spending context for AI insight generation |

## Environment Variables

```
TELEGRAM_TOKEN=
MY_CHAT_ID=
OPENAI_API_KEY=
GOOGLE_PROJECT_ID=
SHEETS_SPREADSHEET_ID=
CRON_SECRET=
PAYER_1=YourName
PAYER_2=PartnerName
PAYER_1_EMAIL=your@gmail.com
PAYER_2_EMAIL=partner@gmail.com
```

## Key Files (not committed)

| File | Purpose |
|------|---------|
| `.env` | Environment variables |
| `token_michael.json` | OAuth token for PAYER_1's Gmail account |
| `token_ofri.json` | OAuth token for PAYER_2's Gmail account |
| `service_account.json` | Google service account for Sheets export and Pub/Sub |
| `finance_bot.db` | SQLite database |

## Scheduled Jobs (GitHub Actions)

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `renew-gmail-watch.yml` | Every 6 days | Gmail Pub/Sub watch expires every 7 days; this keeps it alive |
| `generate-insights.yml` | Every 3 days | Triggers AI spending insights delivery to Telegram |
