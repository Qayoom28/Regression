# CRM Web App (Runnable MVP)

A runnable CRM MVP inspired by the requested system, built with **Python standard library + SQLite** so it works without external package installation.

## Features

- Dashboard summary cards (Leads, Customers, Open Tasks, Pipeline Value)
- Create and list Leads
- Create Customers
- Create Opportunities
- Create Tasks
- Persistent local storage using `crm.db`

## Run

```bash
python crm_server.py
```

Then open:

- `http://127.0.0.1:8000`

## API Endpoints

- `GET /health`
- `GET /api/summary`
- `GET /api/leads` / `POST /api/leads`
- `GET /api/customers` / `POST /api/customers`
- `GET /api/opportunities` / `POST /api/opportunities`
- `GET /api/tasks` / `POST /api/tasks`

## Notes

- Data is stored in local SQLite file: `crm.db`.
- This version intentionally avoids external dependencies to ensure it runs in constrained environments.
