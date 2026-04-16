from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "scheduler_service.db"
PROJECT_REPO_URL = "https://github.com/sameernagar-hub/titan-smart-scheduler.git"
AUTHOR_PROFILE = {
    "name": "Sameer Nagar",
    "title": "Builder of Titan Smart Scheduler",
    "bio": "Designed as an ethics-aware coverage desk that presents scheduling decisions with operational clarity, historical accountability, and academic safeguards.",
}
ALGORITHM_META = {
    "circle": {
        "label": "Circle Method",
        "family": "Rotational",
        "summary": "Balanced rotating coverage that cycles through the roster in a presentation-friendly way.",
        "tagline": "Classic fair rotation",
    },
    "round_robin": {
        "label": "Round Robin",
        "family": "Rotational",
        "summary": "Structured sequential rotation that keeps turns predictable and easy to explain.",
        "tagline": "Simple turn-taking logic",
    },
    "standard": {
        "label": "Round Robin",
        "family": "Rotational",
        "summary": "Legacy alias for the standard round robin rotation.",
        "tagline": "Compatible legacy mode",
    },
    "priority": {
        "label": "Priority Scheduling",
        "family": "Weighted",
        "summary": "Favors high-reliability, low-disruption staffing while still balancing workload and preferences.",
        "tagline": "Reliability-first coverage",
    },
    "constraint_shield": {
        "label": "Constraint Shield",
        "family": "Constraint-Aware",
        "summary": "Uses all known constraints and flexible day selection to reduce conflicts, overload, and fatigue.",
        "tagline": "Most conflict-resistant plan",
    },
}
FOOTER_LINKS = [
    {"title": "Planning Desk", "href": "/scheduler"},
    {"title": "Analytics", "href": "/analytics"},
    {"title": "Reports", "href": "/reports"},
    {"title": "Archive", "href": "/history"},
    {"title": "Ethics", "href": "/ethics"},
    {"title": "Feedback", "href": "/feedback"},
]

DEFAULT_SHIFT_TEMPLATES = [
    {"id": 1, "name": "Morning Concierge", "start": "09:00", "end": "13:00", "students_needed": 2},
    {"id": 2, "name": "Afternoon Studio", "start": "13:00", "end": "17:00", "students_needed": 2},
    {"id": 3, "name": "Evening Lounge", "start": "17:00", "end": "21:00", "students_needed": 2},
]

DEFAULT_CUSTOM_CONFIG = {
    "shift_1": {"days": "Mon Wed Fri", "count": 3},
    "shift_2": {"days": "Mon Tue Thu", "count": 3},
    "shift_3": {"days": "Tue Thu", "count": 2},
}

DEFAULT_STUDENTS = [
    {
        "name": "Alex Morgan",
        "profile": "Mon Wed Fri 9-10am, Tue Thu 2-3:30pm",
        "reliability": 92,
        "max_hours": 12,
        "preferred_shift": "afternoon",
        "recent_callouts": 0,
    },
    {
        "name": "Priya Shah",
        "profile": "Tue Thu 11-12:30pm, Final Exam Dec 16 1-3pm",
        "reliability": 95,
        "max_hours": 10,
        "preferred_shift": "morning",
        "recent_callouts": 0,
    },
    {
        "name": "Jordan Lee",
        "profile": "Mon Wed 1-2pm, Fri 10-11am",
        "reliability": 84,
        "max_hours": 14,
        "preferred_shift": "evening",
        "recent_callouts": 1,
    },
    {
        "name": "Camila Torres",
        "profile": "Tue Thu 9-10am, Quiz Nov 20 3-4pm",
        "reliability": 88,
        "max_hours": 12,
        "preferred_shift": "afternoon",
        "recent_callouts": 0,
    },
]

PRELOADED_SCENARIOS = [
    {
        "name": "Spring Concierge Coverage Sprint",
        "mode": "custom",
        "algorithm": "constraint_shield",
        "weeks": 3,
        "base_date": "2026-03-02",
        "students": DEFAULT_STUDENTS,
        "shift_templates": DEFAULT_SHIFT_TEMPLATES,
        "schedule_config": DEFAULT_CUSTOM_CONFIG,
    },
    {
        "name": "Round Robin Fairness Benchmark",
        "mode": "round_robin",
        "algorithm": "round_robin",
        "weeks": 2,
        "base_date": "2026-02-16",
        "students": DEFAULT_STUDENTS,
    },
    {
        "name": "Priority Coverage Showcase",
        "mode": "custom",
        "algorithm": "priority",
        "weeks": 2,
        "base_date": "2026-03-23",
        "students": DEFAULT_STUDENTS,
        "shift_templates": DEFAULT_SHIFT_TEMPLATES,
        "schedule_config": DEFAULT_CUSTOM_CONFIG,
    },
    {
        "name": "Circle Rotation Showcase",
        "mode": "round_robin",
        "algorithm": "circle",
        "weeks": 2,
        "base_date": "2026-04-06",
        "students": DEFAULT_STUDENTS,
    },
]

FAQ_ITEMS = [
    {
        "question": "What does this service do?",
        "answer": "It helps managers schedule student-heavy teams while protecting class time, keeping workloads balanced, and planning backup coverage for callouts.",
    },
    {
        "question": "What are ethical warnings?",
        "answer": "Warnings highlight staffing choices that may be operationally possible but risky, such as overloading a student, leaving weak backup coverage, or stacking shifts too tightly.",
    },
    {
        "question": "How does history work?",
        "answer": "Every generated schedule run is stored automatically so you can review prior assignments, compare analytics, and reuse seeded demo data.",
    },
    {
        "question": "What is Report Studio?",
        "answer": "Report Studio lets you preview the analytics or ethics report in both ReportLab and WeasyPrint, compare the outputs side by side, and download the version you want to share.",
    },
    {
        "question": "Why are there two PDF renderers?",
        "answer": "ReportLab is more backend-oriented and reliable for structured reporting, while WeasyPrint is stronger when you want HTML/CSS-driven visual fidelity. The compare view lets you choose which result fits the audience.",
    },
    {
        "question": "What do the question-mark hints mean?",
        "answer": "Each hint explains the feature, metric, or service nearby so users can understand what an option does before acting on it.",
    },
    {
        "question": "What is Constraint Shield?",
        "answer": "Constraint Shield is the most protective planning algorithm in the app. It uses class conflicts, weekly limits, fatigue spacing, preferences, reliability, and flexible day selection to reduce avoidable scheduling friction.",
    },
    {
        "question": "What is the difference between Circle, Round Robin, and Priority Scheduling?",
        "answer": "Circle and Round Robin are rotation-first strategies, while Priority Scheduling is a weighted assignment strategy that leans toward reliable, lower-risk coverage when multiple students are available.",
    },
    {
        "question": "What happens when a plan shows 'Needs review' in the ethics record?",
        "answer": "The archived run now includes a schedule suggestions section that uses the actual conflict, warning, workload, reliability, preference, and backup-coverage data from that plan to recommend the most useful adjustments first.",
    },
    {
        "question": "Are the schedule suggestions generic tips?",
        "answer": "No. Suggestions are built from the stored run itself, so they focus on the students, shifts, conflict patterns, overload risks, and coverage gaps that are actually driving the ethics score down.",
    },
]

ETHICS_THEORIES = [
    "Subjective Relativism",
    "Cultural Relativism",
    "Divine Command Theory",
    "Ethical Egoism",
    "Kantianism",
    "Act Utilitarianism",
    "Rule Utilitarianism",
    "Social Contract Theory",
    "Virtue Ethics",
]
