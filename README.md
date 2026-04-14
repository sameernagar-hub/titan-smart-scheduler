# Titan Smart Scheduler

Adaptive ethical scheduling platform for student-worker operations, featuring multi-page planning, archived run history, ethics evaluation, analytics, bulk template import, and downloadable schedule exports.

---

## Why This Project Pops

This is not just a shift generator.
It is a working service-style scheduling application that lets you:

- build staffing plans around student class and exam commitments
- balance workload, reliability, preferences, and backup coverage
- save and reopen completed plans in a dedicated archive
- review fairness, readiness, and alert trends in a separate analytics service
- evaluate saved plans against major ethical frameworks in a dedicated ethics service
- import a prepared planning template instead of filling every field manually
- export completed plans as JSON or CSV for downstream use

---

## Quick Start

### 1. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv .venv
```

#### macOS / Linux

```bash
python3 -m venv .venv
```

### 2. Install dependencies

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 3. Start the app

```powershell
.\.venv\Scripts\python .\app.py
```

### 4. Open the web app

```text
http://127.0.0.1:5000/
```

> Tip: the app opens into a multi-page product experience with separate spaces for planning, analytics, ethics, history, and help.

---

## Table Of Contents

- Features
- App Services
- Typical Workflow
- Ethics Layer
- Bulk Planning Template
- Exports
- Project Structure
- Setup And Installation
- Data Storage
- Author

---

## Features

### Scheduling Engine

- class conflict detection
- exam conflict detection
- weekly hour-limit protection
- reliability-aware staffing
- shift preference awareness
- backup coverage planning
- overload and fatigue warnings

### Product Workflow

- multi-page service layout
- saved plan archive
- dedicated run detail pages
- inline help markers across controls and metrics
- uploadable planner template for bulk input
- JSON and CSV exports for completed plans

### Review And Reporting

- workload and risk summaries
- fairness and coverage metrics
- alert and conflict trend views
- ethics scoring and archived ethics records
- seeded example runs for a presentation-ready first launch

---

## App Services

The platform is organized as separate service areas so each workflow has its own space.

| Service | Purpose | Main Output |
|---|---|---|
| `Home` | Presents the platform, activity board, and service entry points | Overview + recent activity |
| `Shift Planning Desk` | Builds a new staffing plan | New saved plan |
| `Operations Dashboard` | Reviews operational metrics across saved plans | Coverage, fairness, and alert trends |
| `Ethics Review Board` | Reviews plans through ethical theory lenses | Ethics scores + theory-by-theory analysis |
| `Coverage Archive` | Lists previous saved plans | Plan history |
| `Plan Details` | Opens one archived plan | Staffing detail, exports, ethics record |
| `Manager Help Center` | Explains services, metrics, and workflow | In-app documentation |

---

## Typical Workflow

1. Open `Shift Planning Desk` to define students, shift templates, and planning settings.
2. Generate a staffing plan with backup coverage and conflict-aware assignment logic.
3. Review the live results area for assignments, warnings, callout recovery, and workload balance.
4. Open the saved record in `Coverage Archive`.
5. Review the same plan in `Operations Dashboard` and `Ethics Review Board` for reporting.
6. Download the plan as JSON or CSV when you need to share or reuse it.

---

## Ethics Layer

This project is framed as an ethics-focused scheduling platform, so every saved plan can be evaluated against:

- Subjective Relativism
- Cultural Relativism
- Divine Command Theory
- Ethical Egoism
- Kantianism
- Act Utilitarianism
- Rule Utilitarianism
- Social Contract Theory
- Virtue Ethics

Each archived plan stores:

- an overall ethics score
- an overall ethics status
- theory-by-theory scores
- theory-by-theory interpretation notes
- an ethics narrative explaining what the system is checking

This makes the app stronger for:

- ethics coursework
- fairness discussions
- portfolio demonstrations
- judge presentations
- design reviews around responsible staffing systems

---

## Bulk Planning Template

The planner includes a bulk input workflow so users do not have to fill every field manually.

### Supported flow

1. Download a fillable planner template from the `Shift Planning Desk`
2. Edit the JSON file offline
3. Upload the completed file back into the app
4. Let the scheduler auto-populate the planning form
5. Generate and save the plan normally

### Template includes

- plan name
- planning mode
- algorithm
- week count
- student roster
- shift templates
- custom schedule configuration

---

## Exports

Saved plans can be exported as:

- `JSON` for structured downstream use
- `CSV` for spreadsheet or calendar-oriented workflows

Available endpoints:

- `GET /history/<run_id>/download/json`
- `GET /history/<run_id>/download/csv`

Bulk-input template endpoints:

- `GET /api/input-template`
- `POST /api/import-template`

---

## Project Structure

```text
.
|-- app.py
|-- README.md
|-- LICENSE
|-- requirements.txt
|-- templates/
|   |-- base.html
|   |-- home.html
|   |-- services.html
|   |-- scheduler.html
|   |-- analytics.html
|   |-- ethics.html
|   |-- history.html
|   |-- history_detail.html
|   `-- faq.html
`-- static/
    |-- css/
    |   `-- style.css
    `-- js/
        `-- app.js
```

### Key Files

- `app.py` Flask routes, scheduling logic, SQLite persistence, ethics analysis, exports, and template import/export APIs
- `templates/` multi-page HTML templates for each service area
- `static/css/style.css` design system, themes, responsiveness, and motion
- `static/js/app.js` theme behavior, homepage activity carousel, scheduler interactions, and template import flow

---

## Setup And Installation

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\app.py
```

### If PowerShell blocks activation scripts

You can skip activation entirely and run the virtual environment interpreter directly:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\app.py
```

---

## Data Storage

- SQLite database file: `scheduler_service.db`
- generated plans are stored automatically
- ethics records are stored with each plan
- preloaded sample plans are inserted on first startup

---

## Technical Notes

- Built with Flask and SQLite for a lightweight full-stack setup
- Designed as a service platform rather than a single one-page utility
- Uses Jinja templates plus vanilla JavaScript for the UI layer
- Includes seeded history so the app is not empty on first launch
- Keeps ethics evaluation tied directly to archived operational decisions

---

## Author

**Sameer Nagar**

Titan Smart Scheduler was authored by Sameer Nagar as an ethics-focused scheduling platform that combines operational planning, reporting, archival traceability, and theory-based ethical review in one cohesive web application.

---

## Final Notes

Titan Smart Scheduler is designed to be:

- strong enough to demo as a software product
- structured enough to present as a systems project
- thoughtful enough to support an ethics-centered academic framing
- polished enough to serve as a standout GitHub portfolio piece
