# Finance Couple Bot

> A full-stack personal finance tracker for two — powered by Telegram, GPT-4o, Gmail, and a live web dashboard.

![CI](https://img.shields.io/badge/build-passing-brightgreen) ![Python](https://img.shields.io/badge/python-3.13-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## What It Does

Michael and Ori share expenses. This system automatically captures transactions from Gmail receipts, card alerts, and manual Telegram input — parses them with GPT-4o — and displays everything on a live dashboard with charts, budget tracking, and settlement calculations.

## Features

- **Automatic Gmail parsing** — detects financial emails and PDF receipts, extracts amounts and merchants using GPT-4o (supports Hebrew text)
- **Telegram bot** — manual expense entry and real-time AI-generated spending insights every 3 days
- **Card app integration** — receives live transaction webhooks from mobile card apps
- **Interactive dashboard** — filter by month, split type, and payer; view charts, edit transactions inline
- **Budget tracking** — set monthly targets per category, track pacing in real time
- **Settlement calculator** — automatically calculates who owes whom each month
- **Google Sheets export** — export any month's transactions to a Google Sheet with one click
- **AI insights** — GPT-4o-mini analyzes spending patterns and sends alerts via Telegram

## Architecture

```
Gmail / Card App / Telegram
         ↓
  Flask API (PythonAnywhere)
         ↓
  GPT-4o — parse merchant, amount, category
         ↓
  User confirms: Shared or Personal (Telegram inline keyboard)
         ↓
  SQLite Database
         ↓
  Dash Dashboard (Render) — charts, budgets, export
         ↓
  AI Insights (every 3 days) → Telegram notification
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot | pyTelegramBotAPI |
| API | Flask + SQLite |
| AI | GPT-4o, GPT-4o-mini (OpenAI) |
| Email | Gmail API + Google Pub/Sub |
| Dashboard | Dash + Plotly |
| Export | Google Sheets API + gspread |
| Deployment | PythonAnywhere (backend) + Render (frontend) |

## Screenshots

> Add screenshots here

## Setup

### Prerequisites
- Python 3.11+
- Telegram bot token (via BotFather)
- OpenAI API key
- Google Cloud project with Gmail API, Sheets API, and Pub/Sub enabled

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file with the following variables:

```
TELEGRAM_TOKEN=
MY_CHAT_ID=
OPENAI_API_KEY=
GOOGLE_PROJECT_ID=
SHEETS_SPREADSHEET_ID=
CRON_SECRET=
```

Run locally:
```bash
python flask_app.py
```

### Frontend

```bash
cd frontend
pip install -r requirements.txt
python app.py
```

## Live Demo

- **Dashboard:** https://finance-couple-bot.onrender.com
- **Backend API:** https://michaelketash.pythonanywhere.com/api
