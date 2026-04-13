# Titan Smart Scheduler

Titan Smart Scheduler is a multi-page Flask platform for ethical student-worker scheduling.
It is designed to feel like a real campus operations product: planning shifts, reviewing staffing history, monitoring analytics, evaluating ethics, and exporting schedules in manager-friendly formats.

## Why This Project Stands Out
- Ethical scheduling is the core, not an afterthought
- Student commitments, fairness, backup coverage, and risk all influence planning
- Every saved plan carries an ethics analysis record
- Past plans are stored in a reviewable archive
- Supervisors can export plans as JSON or CSV
- Users can bulk-fill the planner with a downloadable/uploadable template
- The UI is multi-page, responsive, themed, and presentation-ready

## Service Areas

### 1. Shift Planning Desk
The main planning workspace where managers can:
- choose a planning mode
- define students and academic profiles
- configure shift templates
- generate staffing plans with backup support
- import a completed JSON planning template instead of filling every field manually

### 2. Operations Dashboard
The analytics workspace for:
- fairness spread
- alert and conflict trends
- coverage readiness
- planning mix
- assignment load across recent plans

### 3. Ethics Review Board
The ethics workspace where saved plans are evaluated against:
- Subjective Relativism
- Cultural Relativism
- Divine Command Theory
- Ethical Egoism
- Kantianism
- Act Utilitarianism
- Rule Utilitarianism
- Social Contract Theory
- Virtue Ethics

Each saved plan gets an ethics score, theory-by-theory status, and a narrative interpretation.

### 4. Coverage Archive
The history workspace where previous plans are stored with:
- staffing outputs
- warnings and conflicts
- callout recovery plans
- ethics analysis records
- export links for JSON and CSV

### 5. Manager Help Center
A built-in FAQ page that explains:
- what the services do
- how metrics should be interpreted
- what the ethical warnings mean
- how the ethics review should be read

## Key Features

### Ethical Planning Logic
- class conflict detection
- exam conflict detection
- weekly hour-limit protection
- shift preference awareness
- reliability-aware selection
- backup coverage planning
- overload and fatigue warnings

### History and Traceability
- every generated plan is saved automatically
- previous plans are reviewable in the archive
- preloaded example plans are inserted on first launch
- ethics records are stored with each plan

### Import / Export Workflow
- download a planning template from the Shift Planning Desk
- fill the template offline as JSON
- upload the file back into the scheduler to auto-populate the form
- export saved plans as JSON or CSV

### Experience and Presentation
- multi-page product layout
- animated landing page with a rotating activity board
- multiple visual themes
- responsive layouts for desktop and mobile
- hover feedback and motion for a more alive interface
- contextual `?` help affordances across the platform

## Tech Stack
- Python
- Flask
- SQLite
- HTML / Jinja templates
- CSS
- Vanilla JavaScript

## Project Structure
```text
.
├── app.py
├── requirements.txt
├── scheduler_service.db
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── services.html
│   ├── scheduler.html
│   ├── analytics.html
│   ├── ethics.html
│   ├── history.html
│   ├── history_detail.html
│   └── faq.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## API and Workflow Endpoints

### Scheduling
- `POST /api/generate`
  Generates a staffing plan, stores it in SQLite, creates ethics analysis, and returns results plus archive/export URLs.

### Bulk Input
- `GET /api/input-template`
  Downloads a fillable planner template in JSON format.
- `POST /api/import-template`
  Validates and normalizes an uploaded planning template so it can populate the scheduler form.

### Saved Plan Exports
- `GET /history/<run_id>/download/json`
  Downloads a saved plan as JSON.
- `GET /history/<run_id>/download/csv`
  Downloads a saved plan as CSV.

## How To Run

### From the repo root
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\app.py
```

Then open:
- `http://127.0.0.1:5000`

### If PowerShell blocks activation
You can skip activation entirely and call the venv Python directly:
```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\app.py
```

## Data Storage
- SQLite database file: `scheduler_service.db`
- Generated plans are stored automatically
- Ethics analysis records are stored with each plan
- Preloaded sample plans are inserted on first startup

## How To Use The Planner Template
1. Open the `Shift Planning Desk`
2. Click `Download Template`
3. Edit the JSON file with your plan name, students, mode, shifts, and schedule configuration
4. Click `Upload Filled Template`
5. The scheduler form will populate automatically
6. Generate the plan and review the results

## Why The Ethics Layer Matters
This project is not just about making schedules.
It is about showing that scheduling decisions can be:
- transparent
- reviewable
- explainable
- fairer to student workers
- aligned with ethical reasoning frameworks

The ethics page and ethics records in history make the platform stronger for:
- class projects
- presentations
- demos
- design reviews
- discussions about fairness in labor scheduling systems

## Author
**Sameer Nagar**

This project was authored by Sameer Nagar and presented as an ethics-focused scheduling platform that combines operational planning, reporting, and ethical analysis in one cohesive web application.

## Final Notes
Titan Smart Scheduler is designed to be both functional and presentable:
- strong enough to demo as a software product
- structured enough to discuss as a systems project
- ethical enough to support an academic ethics framing
- polished enough to serve as a strong GitHub portfolio piece
