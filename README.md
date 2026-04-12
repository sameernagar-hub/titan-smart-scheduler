# Titan Smart Scheduler V2

A Flask app for ethical student-worker scheduling.

## What V2 adds
- Reliability-aware smart assignment
- Backup coverage for callouts
- Weekly hour-limit protection
- Academic conflict detection for classes and exams
- Ethical warnings for overload, fatigue, and weak coverage
- Student preference support for morning, afternoon, or evening shifts
- Manager-facing list view, calendar view, workload risk view, and callout recovery plan

## Run locally on Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
python app.py
```

Then open:
- http://127.0.0.1:5000

## Input model
Each student can include:
- name
- academic profile
- reliability score
- max hours per week
- preferred shift type
- recent callouts

## Why this fits Titan Shops problem #3
Titan Shops depends heavily on student employees. V2 helps balance:
- operational continuity
- fairness in workload distribution
- academic protection
- backup planning when callouts happen

## Core files
- `app.py` - scheduling engine and Flask routes
- `templates/index.html` - UI
- `static/css/style.css` - luxe styling
- `static/js/app.js` - interaction layer
