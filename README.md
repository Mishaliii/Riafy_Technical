# Smart Personal Finance Dashboard

Track expenses, understand spending habits, and get practical monthly insights in Indian Rupees (₹).

## Overview

This project is a local personal finance dashboard built with FastAPI, Jinja2, HTMX, and SQLite. It focuses on quick expense entry, flexible filtering, visual spending analysis, and lightweight rule-based insights without requiring a frontend build step.

The app starts with seeded sample data on first run, so the dashboard and charts are immediately usable.

## What You Can Do

- Add, edit, delete, restore, and permanently remove expenses
- Filter expenses by category, date range, month, year, amount range, and text search
- Export the current expense view to CSV
- View dashboard totals, category breakdowns, and daily spending trends
- Read monthly spending insights generated from the current data
- Manage deleted expenses from a recycle bin with automatic retention cleanup

## Main Screens

- Dashboard: summary cards, charts, insights, monthly summary, and recent transactions
- Expenses: searchable and filterable expense list with add/edit flows
- Recycle Bin: restored or permanently deleted expenses kept for a limited retention period

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI |
| Templates | Jinja2 |
| Interactivity | HTMX |
| Charts | Chart.js |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Database | SQLite |
| Styling | Vanilla CSS |

## Project Structure

```text
finance_dashboard/
├── main.py            # FastAPI app, routes, HTMX endpoints, CSV export
├── database.py        # SQLite setup, migrations, and sample data seeding
├── models.py          # SQLAlchemy models and indexes
├── schemas.py         # Pydantic models and INR formatting helpers
├── crud.py            # Database access layer
├── services.py        # Business logic and aggregation helpers
├── insights.py        # Monthly insight generation
├── static/
│   ├── css/main.css
│   └── js/app.js
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── expenses.html
│   ├── recycle.html
│   └── partials/
├── requirements.txt
└── README.md
```

## Setup

1. Open a terminal in the project folder.
2. Install the dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python main.py
```

4. Open the app at:

```text
http://localhost:8000
```

You can also run it directly with Uvicorn:

```bash
uvicorn main:app --reload
```

## Data Model

The app stores expenses in a single SQLite table named `expenses`.

- Categories: Food, Transport, Shopping, Bills, Entertainment, Health, Education, Other
- Fields: title, amount, category, date, note, created_at, updated_at, deleted_at
- Indexes: `date`, `category`, `(date, category)`, and `deleted_at`
- Recycle bin retention: 30 days

## Implementation Notes

- `main.py` handles page routes, HTMX partials, and API endpoints
- `services.py` coordinates dashboard data, summary data, CSV export, and recycle-bin behavior
- `insights.py` generates up to 8 monthly spending insights from actual expense data
- `static/js/app.js` manages modal behavior, toast notifications, and chart rendering
- `database.py` seeds sample expenses only when the database is empty

## Current Limitations

- Single-user, local-first setup
- No authentication
- No pagination yet for large datasets
- No CSV import or backup flow yet

## Future Ideas

- Budget tracking by category
- Recurring expense detection
- CSV import
- Pagination
- Spending heatmap calendar
- Mobile-friendly sidebar refinements
