# Titan Smart Scheduler

Adaptive ethical scheduling platform for student-worker operations, featuring multi-page planning, archived run history, ethics evaluation, algorithm comparison, ethics-driven schedule suggestions, Outcome Builder revision flows, bulk template import, feedback capture, and downloadable schedule exports including dual-renderer PDF reports.

---

## Why This Project Pops

This is not just a shift generator.
It is a working service-style scheduling application that lets you:

- build staffing plans around student class and exam commitments
- balance workload, reliability, preferences, and backup coverage
- save and reopen completed plans in a dedicated archive
- review fairness, readiness, and alert trends in a separate analytics service
- evaluate saved plans against major ethical frameworks in a dedicated ethics service
- generate grounded improvement suggestions when an ethics review needs attention
- turn a reviewed run into revised or final candidate schedules with Outcome Builder
- import a prepared planning template instead of filling every field manually
- export completed plans as JSON or CSV for downstream use
- compare ReportLab and WeasyPrint output in a dedicated PDF preview studio before downloading reports

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

- multiple scheduling strategies: Constraint Shield, Priority Scheduling, Circle Method, and Round Robin
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
- ethics-driven schedule suggestions inside archived run reviews
- Outcome Builder modes for conflict-free, coverage-first, ethics-first, fairness-first, and balanced revisions
- save outcome-driven revisions or accept a generated schedule as the final result
- inline help markers across controls and metrics
- uploadable planner template for bulk input
- feedback lounge for product notes and contribution interest
- JSON and CSV exports for completed plans
- side-by-side PDF preview and download flow for analytics and ethics reporting

### Review And Reporting

- workload and risk summaries
- fairness and coverage metrics
- alert and conflict trend views
- algorithm-level analytics and performance comparisons
- ethics scoring and archived ethics records
- downloadable analytics and ethics PDF reports rendered through both ReportLab and WeasyPrint
- seeded example runs for a presentation-ready first launch

---

## App Services

The platform is organized as separate service areas so each workflow has its own space.

| Service | Purpose | Main Output |
|---|---|---|
| `Home` | Presents the platform, activity board, and service entry points | Overview + recent activity |
| `Shift Planning Desk` | Builds a new staffing plan | New saved plan |
| `Operations Dashboard` | Reviews operational metrics across saved plans | Coverage, fairness, and alert trends |
| `Report Studio` | Compares export renderers for printable reporting | Side-by-side PDF previews + downloads |
| `Ethics Review Board` | Reviews plans through ethical theory lenses | Ethics scores + theory-by-theory analysis |
| `Coverage Archive` | Lists previous saved plans | Plan history |
| `Plan Details` | Opens one archived plan | Staffing detail, exports, ethics record, grounded schedule suggestions, and Outcome Builder revisions |
| `Feedback Lounge` | Captures product feedback and contribution interest | Stored feedback notes |
| `Manager Help Center` | Explains services, metrics, and workflow | In-app documentation |

---

## Typical Workflow

1. Open `Shift Planning Desk` to define students, shift templates, and planning settings.
2. Generate a staffing plan with backup coverage and conflict-aware assignment logic.
3. Review the live results area for assignments, warnings, callout recovery, and workload balance.
4. Open the saved record in `Coverage Archive`.
5. Review the same plan in `Operations Dashboard` and `Ethics Review Board` for reporting.
6. If the ethics record shows `Needs review`, use the schedule suggestions block in the run detail page to see which adjustments should be made first.
7. Open `Outcome Builder` in the same run detail page, choose the goal you care about most, and generate revised schedule options.
8. Save the best candidate as a revision or accept it as the final schedule.
9. Open `Report Studio` when you want a printable analytics or ethics briefing and choose between the ReportLab and WeasyPrint PDF versions.
10. Download the plan as JSON or CSV when you need structured downstream data.

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
- schedule suggestions when conflicts, overload, weak coverage, or other risk signals need attention
- Outcome Builder lineage when a run is revised or promoted to a final outcome

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
- `PDF` for printable analytics and ethics briefings

Available endpoints:

- `GET /history/<run_id>/download/json`
- `GET /history/<run_id>/download/csv`
- `POST /history/<run_id>/outcomes`
- `POST /history/<run_id>/outcomes/<candidate_key>/save`
- `GET /analytics/report.pdf`
- `GET /ethics/report.pdf`
- `GET /reports/pdf/<report_type>/<renderer>`

Bulk-input template endpoints:

- `GET /api/input-template`
- `POST /api/import-template`

---

## Project Structure

```text
.
|-- scheduler_config.py
|-- scheduler_engine.py
|-- scheduler_reporting.py
|-- outcome_builder.py
|-- pdf_reports.py
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
|   |-- reports.html
|   |-- ethics.html
|   |-- history.html
|   |-- history_detail.html
|   |-- feedback.html
|   `-- faq.html
`-- static/
    |-- css/
    |   `-- style.css
    `-- js/
        `-- app.js
```

### Key Files

- `app.py` Flask entrypoint, database lifecycle, persistence helpers, route handlers, and report export routes
- `scheduler_config.py` app metadata, FAQ items, seeded scenarios, and algorithm definitions
- `scheduler_engine.py` parsing, scheduling algorithms, conflicts, warnings, and import/export helpers
- `scheduler_reporting.py` ethics scoring, analytics rollups, and schedule suggestion generation
- `outcome_builder.py` Outcome Builder goal definitions, candidate generation, and weighted revision scoring
- `pdf_reports.py` dual-renderer PDF report builders for ReportLab and WeasyPrint
- `templates/` multi-page HTML templates for each service area
- `static/css/style.css` design system, themes, responsiveness, motion, and Outcome Builder presentation
- `static/js/app.js` theme behavior, homepage activity carousel, scheduler interactions, template import flow, and Outcome Builder compare/save workflow

---

## Setup And Installation

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\app.py
```

### PDF Reporting Dependencies

The project now uses:

- `reportlab` for backend-oriented PDF reliability
- `weasyprint` for HTML/CSS-driven PDF fidelity

On Windows, WeasyPrint also needs the GTK runtime. If PDF previews or WeasyPrint exports fail, install the runtime with:

```powershell
winget install -e --id tschoonj.GTKForWindows --accept-package-agreements --accept-source-agreements
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
- Uses both ReportLab and WeasyPrint for comparative PDF reporting
- Includes seeded history so the app is not empty on first launch
- Keeps ethics evaluation tied directly to archived operational decisions
- Keeps schedule suggestions tied directly to the stored run data so recommendations are specific instead of generic
- Keeps derived revisions linked to their source runs so final outcomes remain traceable in the archive

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
- cohesive enough to serve as a strong GitHub portfolio piece
