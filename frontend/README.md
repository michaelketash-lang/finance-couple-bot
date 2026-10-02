# Frontend

Dash application running on Render. Fetches aggregated data from the backend BFF layer and renders an interactive dashboard with three tabs: Expenses, Budget, and Investments. Fully responsive — desktop sidebar navigation, mobile bottom navigation with a Rise Up-inspired design.

## Entry Point

```bash
python app.py
```

`app.py` creates the Dash app, defines the sidebar and bottom navigation, mounts the three page layouts, and registers all tab callbacks.

## Environment Variables

```
API_BASE_URL=https://your-backend.pythonanywhere.com
PAYER_1=YourName
PAYER_2=PartnerName
```

## Module Overview

### Core

| File | Responsibility |
|------|---------------|
| `app.py` | Dash app factory, sidebar layout, mobile bottom nav, page-switching callback, PWA service worker route |
| `api_client.py` | All HTTP calls to the backend — fetches expenses, budgets, investments, BFF aggregations; triggers export and insights |

### layouts/

Each tab has a layout file (component tree) and a callbacks file (reactive logic). They share a frozen `_Ids` dataclass so component ID strings are never duplicated between the two files.

| File | Responsibility |
|------|---------------|
| `expenses_layout.py` | Full Expenses tab component tree: month tabs, year dropdown, KPI cards, charts, transactions table, payer summary, mobile category cards |
| `expenses_callbacks.py` | Master callback fetches all data in one BFF call and writes to `dcc.Store`; slave callbacks render table, charts, KPIs, payer summary, and mobile views from the store without additional HTTP requests |
| `budget_layout.py` | Budget tab component tree: year/payer controls, month tabs, budget goals table, category progress cards, yearly category chart |
| `investments_layout.py` | Investments tab component tree |
| `investments_callbacks.py` | Investments tab reactive callbacks |

### components/

Reusable UI primitives shared across tabs.

| File | Responsibility |
|------|---------------|
| `charts.py` | `category_pie_chart` (donut with horizontal legend), `monthly_trends_bar_chart` (12-month bar with average line) |
| `tables.py` | `expenses_datatable` (editable: merchant, amount, category, payer), `budgets_datatable` (editable: monthly target) |
| `cards.py` | `budget_progress_card` — category name, spend vs target, colored progress bar |

### assets/

| File | Responsibility |
|------|---------------|
| `custom.css` | Mobile-only styles inside `@media (max-width: 768px)` — Rise Up design tokens, bottom nav, card radii, typography; desktop is completely untouched |
| `manifest.json` | PWA manifest — enables "Add to Home Screen" on iOS and Android |
| `logo.png` | App icon used in the sidebar and as the PWA home screen icon |

## Architecture Pattern

The Expenses tab uses a **master/slave callback pattern** to minimize API calls:

1. **Master callback** — fires on year or month change, fetches all data in a single BFF request, writes to `dcc.Store`
2. **Slave callbacks** — read from the store and render the table, charts, KPIs, and payer summary without making additional HTTP requests
3. **Edit callback** — fires only on table cell edits, calls the update endpoint once for the changed row
4. **Export callback** — fires only on button click, triggers a Google Sheets export

This means navigating between split views (Shared / Michael / Ori) costs zero network requests.
