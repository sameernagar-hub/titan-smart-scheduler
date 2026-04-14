from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

from flask import Flask, abort, g, jsonify, make_response, render_template, request

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "scheduler_service.db"

DAY_MAP = {
    "su": 6,
    "sun": 6,
    "sunday": 6,
    "m": 0,
    "mon": 0,
    "monday": 0,
    "t": 1,
    "tu": 1,
    "tue": 1,
    "tuesday": 1,
    "w": 2,
    "wed": 2,
    "wednesday": 2,
    "th": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "f": 4,
    "fri": 4,
    "friday": 4,
    "s": 5,
    "sat": 5,
    "saturday": 5,
}

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

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
        "algorithm": "circle",
        "weeks": 3,
        "base_date": "2026-03-02",
        "students": DEFAULT_STUDENTS,
        "shift_templates": DEFAULT_SHIFT_TEMPLATES,
        "schedule_config": DEFAULT_CUSTOM_CONFIG,
    },
    {
        "name": "Round Robin Fairness Benchmark",
        "mode": "round_robin",
        "algorithm": "standard",
        "weeks": 2,
        "base_date": "2026-02-16",
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
        "question": "What do the question-mark hints mean?",
        "answer": "Each hint explains the feature, metric, or service nearby so users can understand what an option does before acting on it.",
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

TIME_RE = re.compile(r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)?", re.I)
RANGE_RE = re.compile(
    r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to)\s*(?P<end>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
    re.I,
)
DAY_TOKEN_RE = re.compile(
    r"(?:mon|monday|m|tue|tuesday|tu|t|wed|wednesday|w|thu|thursday|thurs|thur|th|fri|friday|f|sat|saturday|sat|s|sun|sunday|su)",
    re.I,
)
EXAM_DATE_RE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|[A-Za-z]+)\s+(\d{1,2})", re.I)
CLASS_LINE_RE = re.compile(
    r"^(?P<days>[A-Za-z/ ,]+?)\s+(?P<range>\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:-|to)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$",
    re.I,
)


@dataclass
class Commitment:
    type: str
    description: str
    date: Optional[str] = None
    day_of_week: Optional[int] = None
    start_minutes: Optional[int] = None
    end_minutes: Optional[int] = None
    priority: str = "medium"


@dataclass
class ShiftAssignment:
    shift_instance_id: str
    date: str
    student: str
    time: str
    shift_name: str
    start_minutes: int
    end_minutes: int
    round_label: Optional[str] = None
    conflict: bool = False
    conflict_reason: Optional[str] = None
    role: str = "primary"
    ethics_flags: List[str] = field(default_factory=list)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        g.db = connection
    return g.db


@app.teardown_appcontext
def close_db(_: Optional[BaseException]) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def minutes_to_label(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix}"


def parse_time_to_minutes(value: str) -> int:
    cleaned = value.strip().lower()
    match = TIME_RE.fullmatch(cleaned)
    if not match:
        raise ValueError(f"Invalid time: {value}")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    period = match.group("period")
    if period:
        if hour == 12:
            hour = 0
        if period == "pm":
            hour += 12
    return hour * 60 + minute


def parse_time_range(expr: str) -> tuple[int, int]:
    match = RANGE_RE.search(expr.strip())
    if not match:
        raise ValueError(f"Invalid time range: {expr}")
    start = parse_time_to_minutes(match.group("start"))
    end = parse_time_to_minutes(match.group("end"))
    if end <= start:
        end += 12 * 60 if end < start else 24 * 60
    return start, end


def parse_day_tokens(day_expr: str) -> List[int]:
    expr = day_expr.strip().lower().replace("/", " ").replace(",", " ")
    expr = re.sub(r"\band\b", " ", expr)
    if expr in {"daily", "everyday", "every day"}:
        return list(range(7))
    if expr in {"weekdays", "weekday"}:
        return [0, 1, 2, 3, 4]
    if expr in {"weekends", "weekend"}:
        return [5, 6]

    tokens = DAY_TOKEN_RE.findall(expr)
    compact = expr.replace(" ", "")
    if not tokens and re.fullmatch(r"[mtwfsuh]+", compact):
        ordered = []
        i = 0
        while i < len(compact):
            if compact[i : i + 2] == "th":
                ordered.append("th")
                i += 2
            elif compact[i : i + 2] == "su":
                ordered.append("su")
                i += 2
            elif compact[i] == "s":
                ordered.append("s")
                i += 1
            else:
                ordered.append(compact[i])
                i += 1
        tokens = ordered

    result: List[int] = []
    for token in tokens:
        key = token.lower()
        if key in DAY_MAP and DAY_MAP[key] not in result:
            result.append(DAY_MAP[key])
    return result


def start_of_week(target: date) -> date:
    return target - timedelta(days=target.weekday())


def parse_commitments(text: str, base_date: Optional[date] = None) -> List[Commitment]:
    base = base_date or date.today()
    commitments: List[Commitment] = []
    chunks = [chunk.strip() for chunk in re.split(r"\n|;|,(?=\s*[A-Za-z])", text or "") if chunk.strip()]
    for chunk in chunks:
        lower = chunk.lower()
        is_exam = any(word in lower for word in ["exam", "midterm", "final", "quiz", "test"])
        time_match = RANGE_RE.search(chunk)
        start_minutes = end_minutes = None
        if time_match:
            start_minutes, end_minutes = parse_time_range(time_match.group(0))

        if is_exam:
            exam_date = None
            date_match = EXAM_DATE_RE.search(chunk)
            if date_match:
                month_name = date_match.group(1).lower()
                day_num = int(date_match.group(2))
                month = MONTH_MAP.get(month_name[:3], MONTH_MAP.get(month_name))
                if month:
                    year = base.year
                    candidate = date(year, month, day_num)
                    if candidate < base - timedelta(days=30):
                        candidate = date(year + 1, month, day_num)
                    exam_date = candidate.isoformat()
            commitments.append(
                Commitment(
                    type="exam",
                    description=chunk,
                    date=exam_date,
                    start_minutes=start_minutes,
                    end_minutes=end_minutes,
                    priority="high" if "final" in lower else "medium",
                )
            )
            continue

        class_match = CLASS_LINE_RE.match(chunk)
        if class_match and time_match:
            days = parse_day_tokens(class_match.group("days"))
            for day_value in days:
                commitments.append(
                    Commitment(
                        type="class",
                        description=chunk,
                        day_of_week=day_value,
                        start_minutes=start_minutes,
                        end_minutes=end_minutes,
                    )
                )
            continue

        commitments.append(Commitment(type="other", description=chunk))
    return commitments


def parse_students(payload: Dict[str, Any], base_date: Optional[date] = None) -> List[Dict[str, Any]]:
    students = payload.get("students") or []
    parsed = []
    for idx, raw in enumerate(students, start=1):
        name = (raw.get("name") or f"Student {idx}").strip() or f"Student {idx}"
        profile_text = (raw.get("profile") or "").strip()
        commitments = parse_commitments(profile_text, base_date=base_date)
        reliability = max(50, min(100, int(raw.get("reliability") or 85)))
        max_hours = max(1, min(40, int(raw.get("max_hours") or 12)))
        preferred_shift = (raw.get("preferred_shift") or "any").strip().lower() or "any"
        recent_callouts = max(0, min(10, int(raw.get("recent_callouts") or 0)))
        parsed.append(
            {
                "name": name,
                "profile": profile_text,
                "commitments": commitments,
                "reliability": reliability,
                "max_hours": max_hours,
                "preferred_shift": preferred_shift,
                "recent_callouts": recent_callouts,
                "academic_load": len([c for c in commitments if c.type in {"class", "exam"}]),
            }
        )
    return parsed


def circle_pairs(student_count: int) -> List[List[List[int]]]:
    workers: List[Any] = list(range(student_count))
    if student_count % 2 == 1:
        workers.append("BYE")
    total = len(workers)
    rounds: List[List[List[int]]] = []
    for _ in range(total - 1):
        round_pairs = []
        for i in range(total // 2):
            left = workers[i]
            right = workers[total - 1 - i]
            if "BYE" not in (left, right):
                round_pairs.append([left, right])
        rounds.append(round_pairs)
        workers = [workers[0]] + [workers[-1]] + workers[1:-1]
    return rounds


def standard_pairs(student_count: int) -> List[List[List[int]]]:
    workers: List[Any] = list(range(student_count))
    if student_count % 2 == 1:
        workers.append("BYE")
    total = len(workers)
    total_rounds = total - 1
    pairs_per_round = total // 2
    schedule = []
    for round_index in range(total_rounds):
        round_pairs = [[workers[0], workers[-1]]]
        for i in range(1, pairs_per_round):
            first_index = 1 + ((round_index + i - 1) % (total - 1))
            second_index = 1 + ((round_index + total - 2 - i) % (total - 1))
            pair = [workers[first_index], workers[second_index]]
            if "BYE" not in pair:
                round_pairs.append(pair)
        schedule.append(round_pairs)
    return schedule


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and a_end > b_start


def conflicts_with_commitments(
    student: Dict[str, Any], shift_date: str, start_minutes: int, end_minutes: int
) -> Optional[Commitment]:
    weekday = datetime.strptime(shift_date, "%Y-%m-%d").date().weekday()
    for commitment in student["commitments"]:
        day_match = commitment.date == shift_date if commitment.date else commitment.day_of_week == weekday
        if not day_match or commitment.start_minutes is None or commitment.end_minutes is None:
            continue
        if overlaps(start_minutes, end_minutes, commitment.start_minutes, commitment.end_minutes):
            return commitment
    return None


def overlaps_existing(
    student_name: str, shift_date: str, start_minutes: int, end_minutes: int, assignments: List[ShiftAssignment]
) -> bool:
    for item in assignments:
        if item.student == student_name and item.date == shift_date and item.role == "primary":
            if overlaps(start_minutes, end_minutes, item.start_minutes, item.end_minutes):
                return True
    return False


def shift_bucket(start_minutes: int) -> str:
    if start_minutes < 12 * 60:
        return "morning"
    if start_minutes < 17 * 60:
        return "afternoon"
    return "evening"


def build_score(
    student: Dict[str, Any],
    student_stats: Dict[str, Dict[str, Any]],
    shift_date: date,
    start_minutes: int,
    end_minutes: int,
    assignments: List[ShiftAssignment],
    for_backup: bool = False,
) -> Optional[tuple]:
    shift_iso = shift_date.isoformat()
    commitment = conflicts_with_commitments(student, shift_iso, start_minutes, end_minutes)
    if commitment or overlaps_existing(student["name"], shift_iso, start_minutes, end_minutes, assignments):
        return None

    stat = student_stats[student["name"]]
    duration_hours = (end_minutes - start_minutes) / 60
    projected_hours = stat["hours_primary"] + (0 if for_backup else duration_hours)
    overtime_ratio = projected_hours / max(student["max_hours"], 1)
    pref = student["preferred_shift"]
    bucket = shift_bucket(start_minutes)
    preference_penalty = 0 if pref in {"any", bucket, ""} else 1
    reliability_penalty = (100 - student["reliability"]) / 100
    callout_penalty = student["recent_callouts"] * 0.35
    academic_penalty = student["academic_load"] * 0.08
    overload_penalty = max(0, overtime_ratio - 1) * 8
    backup_penalty = stat["backup_assignments"] * 0.35 if for_backup else 0
    freshness = stat["last_assigned_ordinal"]

    return (
        overload_penalty,
        stat["primary_assignments"] + (0 if for_backup else 1),
        round(projected_hours, 2),
        preference_penalty,
        round(reliability_penalty + callout_penalty + academic_penalty + backup_penalty, 3),
        freshness,
        student["name"].lower(),
    )


def choose_candidates(
    students: List[Dict[str, Any]],
    student_stats: Dict[str, Dict[str, Any]],
    shift_date: date,
    start_minutes: int,
    end_minutes: int,
    assignments: List[ShiftAssignment],
    count: int,
    for_backup: bool = False,
    exclude: Optional[set] = None,
) -> List[str]:
    exclude = exclude or set()
    ranked = []
    for student in students:
        if student["name"] in exclude:
            continue
        score = build_score(
            student,
            student_stats,
            shift_date,
            start_minutes,
            end_minutes,
            assignments,
            for_backup=for_backup,
        )
        if score is not None:
            ranked.append((score, student["name"]))
    ranked.sort(key=lambda item: item[0])
    chosen = [name for _, name in ranked[:count]]
    duration_hours = (end_minutes - start_minutes) / 60
    for name in chosen:
        stat = student_stats[name]
        if for_backup:
            stat["backup_assignments"] += 1
        else:
            stat["primary_assignments"] += 1
            stat["hours_primary"] += duration_hours
            stat["last_assigned_ordinal"] = shift_date.toordinal()
    return chosen


def expand_round_robin_schedule(
    students: List[Dict[str, Any]], algorithm: str, base_date: Optional[date] = None
) -> List[ShiftAssignment]:
    pair_rounds = circle_pairs(len(students)) if algorithm == "circle" else standard_pairs(len(students))
    shift_slots = [
        ("Morning Concierge", 9 * 60, 13 * 60),
        ("Afternoon Studio", 13 * 60, 17 * 60),
        ("Evening Lounge", 17 * 60, 21 * 60),
    ]
    monday = start_of_week(base_date or date.today())
    assignments: List[ShiftAssignment] = []
    slot_index = 0
    for round_index, pairings in enumerate(pair_rounds, start=1):
        for pair_index, pair in enumerate(pairings, start=1):
            slot_name, start_minutes, end_minutes = shift_slots[slot_index % len(shift_slots)]
            day_offset = slot_index // len(shift_slots)
            shift_date = (monday + timedelta(days=day_offset)).isoformat()
            shift_instance_id = f"rr-{round_index}-{pair_index}"
            for student_index in pair:
                student = students[student_index]
                assignments.append(
                    ShiftAssignment(
                        shift_instance_id=shift_instance_id,
                        date=shift_date,
                        student=student["name"],
                        time=f"{minutes_to_label(start_minutes)} - {minutes_to_label(end_minutes)}",
                        shift_name=slot_name,
                        start_minutes=start_minutes,
                        end_minutes=end_minutes,
                        round_label=f"Round {round_index} / Shift {pair_index}",
                    )
                )
            slot_index += 1
    return assignments


def parse_custom_days(value: str) -> List[int]:
    chunks = [chunk for chunk in re.split(r"[,/]|\s+", value.strip()) if chunk]
    joined = " ".join(chunks)
    parsed = parse_day_tokens(joined)
    return parsed if parsed else parse_day_tokens(value.replace(" ", ""))


def build_custom_schedule(
    students: List[Dict[str, Any]], payload: Dict[str, Any], base_date: Optional[date] = None
) -> List[ShiftAssignment]:
    shift_templates = payload.get("shift_templates") or DEFAULT_SHIFT_TEMPLATES
    schedule_config = payload.get("schedule_config") or DEFAULT_CUSTOM_CONFIG
    weeks = int(payload.get("weeks") or 4)
    monday = start_of_week(base_date or date.today())
    assignments: List[ShiftAssignment] = []
    student_stats = {
        s["name"]: {
            "primary_assignments": 0,
            "backup_assignments": 0,
            "hours_primary": 0.0,
            "last_assigned_ordinal": -10**9,
        }
        for s in students
    }

    for week in range(weeks):
        base_week = monday + timedelta(days=7 * week)
        for template in shift_templates:
            config = schedule_config.get(f"shift_{template['id']}", {"days": "Mon Wed Fri", "count": 3})
            weekdays = parse_custom_days(config.get("days", ""))
            if not weekdays:
                continue
            weekly_count = max(1, int(config.get("count", 1)))
            shift_start = parse_time_to_minutes(template["start"])
            shift_end = parse_time_to_minutes(template["end"])
            if shift_end <= shift_start:
                raise ValueError(f"Shift end time must be after start time for {template['name']}")
            needed = max(1, int(template["students_needed"]))
            for i in range(weekly_count):
                weekday = weekdays[i % len(weekdays)]
                shift_date = base_week + timedelta(days=weekday)
                shift_id = f"c-{week + 1}-{template['id']}-{i + 1}"
                primaries = choose_candidates(
                    students, student_stats, shift_date, shift_start, shift_end, assignments, needed
                )
                backups = choose_candidates(
                    students,
                    student_stats,
                    shift_date,
                    shift_start,
                    shift_end,
                    assignments,
                    min(2, max(0, len(students) - len(primaries))),
                    for_backup=True,
                    exclude=set(primaries),
                )
                for name in primaries:
                    assignments.append(
                        ShiftAssignment(
                            shift_instance_id=shift_id,
                            date=shift_date.isoformat(),
                            student=name,
                            time=f"{minutes_to_label(shift_start)} - {minutes_to_label(shift_end)}",
                            shift_name=template["name"],
                            start_minutes=shift_start,
                            end_minutes=shift_end,
                            round_label=f"Week {week + 1}",
                        )
                    )
                for name in backups:
                    assignments.append(
                        ShiftAssignment(
                            shift_instance_id=shift_id,
                            date=shift_date.isoformat(),
                            student=name,
                            time=f"{minutes_to_label(shift_start)} - {minutes_to_label(shift_end)}",
                            shift_name=template["name"],
                            start_minutes=shift_start,
                            end_minutes=shift_end,
                            round_label=f"Week {week + 1}",
                            role="backup",
                            ethics_flags=["backup coverage"],
                        )
                    )
    assignments.sort(key=lambda item: (item.date, item.start_minutes, item.shift_name, item.role, item.student))
    return assignments


def detect_conflicts(assignments: List[ShiftAssignment], students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    student_map = {student["name"]: student for student in students}
    conflicts = []
    for assignment in assignments:
        if assignment.role != "primary":
            continue
        commitment = conflicts_with_commitments(
            student_map[assignment.student], assignment.date, assignment.start_minutes, assignment.end_minutes
        )
        if commitment:
            assignment.conflict = True
            assignment.conflict_reason = commitment.description
            assignment.ethics_flags.append("academic conflict")
            conflicts.append(
                {
                    "student": assignment.student,
                    "date": assignment.date,
                    "time": assignment.time,
                    "shift_name": assignment.shift_name,
                    "reason": f"{commitment.type.title()} conflict",
                    "commitment": commitment.description,
                    "priority": commitment.priority,
                }
            )
    return conflicts


def build_warnings(assignments: List[ShiftAssignment], students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    student_map = {s["name"]: s for s in students}
    warnings = []
    weekly_hours: Dict[tuple, float] = defaultdict(float)
    primary = [a for a in assignments if a.role == "primary"]
    grouped_by_student_day: Dict[tuple, List[ShiftAssignment]] = defaultdict(list)
    for item in primary:
        week_start = start_of_week(datetime.strptime(item.date, "%Y-%m-%d").date()).isoformat()
        weekly_hours[(item.student, week_start)] += (item.end_minutes - item.start_minutes) / 60
        grouped_by_student_day[(item.student, item.date)].append(item)

    for (student_name, week_start), hours in weekly_hours.items():
        limit = student_map[student_name]["max_hours"]
        if hours > limit:
            warnings.append(
                {
                    "student": student_name,
                    "date": week_start,
                    "severity": "high",
                    "reason": f"Scheduled {hours:.1f}h against {limit}h weekly limit",
                    "type": "overload",
                }
            )

    for key, day_items in grouped_by_student_day.items():
        day_items.sort(key=lambda item: item.start_minutes)
        for left, right in zip(day_items, day_items[1:]):
            gap = right.start_minutes - left.end_minutes
            if gap < 60:
                warnings.append(
                    {
                        "student": key[0],
                        "date": key[1],
                        "severity": "medium",
                        "reason": f"Back-to-back shifts with only {max(gap, 0)} minutes between them",
                        "type": "fatigue",
                    }
                )
        reliability = student_map[key[0]]["reliability"]
        if reliability < 75 and day_items:
            warnings.append(
                {
                    "student": key[0],
                    "date": key[1],
                    "severity": "medium",
                    "reason": f"Lower reliability score ({reliability}%) suggests keeping backup coverage active",
                    "type": "coverage",
                }
            )

    return warnings


def build_callout_plan(assignments: List[ShiftAssignment]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in assignments:
        row = grouped.setdefault(
            item.shift_instance_id,
            {
                "shift_instance_id": item.shift_instance_id,
                "date": item.date,
                "time": item.time,
                "shift_name": item.shift_name,
                "primaries": [],
                "backups": [],
            },
        )
        row["primaries" if item.role == "primary" else "backups"].append(item.student)
    plans = list(grouped.values())
    plans.sort(key=lambda row: (row["date"], row["time"], row["shift_name"]))
    return plans


def serialize_assignments(assignments: List[ShiftAssignment]) -> List[Dict[str, Any]]:
    return [asdict(item) for item in assignments]


def serialize_students(students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized = []
    for student in students:
        item = dict(student)
        item["commitments"] = [asdict(commitment) for commitment in student.get("commitments", [])]
        serialized.append(item)
    return serialized


def build_input_template() -> Dict[str, Any]:
    return {
        "schedule_name": "Bookstore floor coverage week 4",
        "mode": "custom",
        "algorithm": "circle",
        "weeks": 4,
        "students": DEFAULT_STUDENTS,
        "shift_templates": DEFAULT_SHIFT_TEMPLATES,
        "schedule_config": DEFAULT_CUSTOM_CONFIG,
        "notes": [
            "Download this template, update the values, then upload it back into the Shift Planning Desk.",
            "Use mode round_robin or custom.",
            "Keep student fields aligned with the planner form: name, profile, reliability, max_hours, preferred_shift, recent_callouts.",
            "Shift templates and schedule_config are used when mode is custom.",
        ],
    }


def normalize_import_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Imported file must contain a JSON object.")

    students = payload.get("students")
    if not isinstance(students, list) or len(students) < 2:
        raise ValueError("Imported file must contain at least 2 students.")

    normalized_students = []
    for index, raw in enumerate(students, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Student entry {index} must be an object.")
        normalized_students.append(
            {
                "name": str(raw.get("name") or f"Student {index}").strip(),
                "profile": str(raw.get("profile") or "").strip(),
                "reliability": int(raw.get("reliability") or 85),
                "max_hours": int(raw.get("max_hours") or 12),
                "preferred_shift": str(raw.get("preferred_shift") or "any").strip().lower(),
                "recent_callouts": int(raw.get("recent_callouts") or 0),
            }
        )

    mode = str(payload.get("mode") or "round_robin").strip().lower()
    if mode not in {"round_robin", "custom"}:
        raise ValueError("Mode must be either round_robin or custom.")

    algorithm = str(payload.get("algorithm") or "circle").strip().lower()
    if algorithm not in {"circle", "standard"}:
        raise ValueError("Algorithm must be either circle or standard.")

    normalized = {
        "schedule_name": str(payload.get("schedule_name") or "").strip(),
        "mode": mode,
        "algorithm": algorithm,
        "weeks": max(1, min(12, int(payload.get("weeks") or 4))),
        "students": normalized_students,
    }

    if mode == "custom":
        shift_templates = payload.get("shift_templates")
        schedule_config = payload.get("schedule_config")
        if not isinstance(shift_templates, list) or not shift_templates:
            raise ValueError("Custom mode imports must include at least one shift template.")
        if not isinstance(schedule_config, dict):
            raise ValueError("Custom mode imports must include schedule_config.")

        normalized_templates = []
        normalized_config: Dict[str, Dict[str, Any]] = {}
        for index, template in enumerate(shift_templates, start=1):
            if not isinstance(template, dict):
                raise ValueError(f"Shift template {index} must be an object.")
            template_id = int(template.get("id") or index)
            normalized_templates.append(
                {
                    "id": template_id,
                    "name": str(template.get("name") or f"Shift {index}").strip(),
                    "start": str(template.get("start") or "09:00").strip(),
                    "end": str(template.get("end") or "13:00").strip(),
                    "students_needed": max(1, int(template.get("students_needed") or 1)),
                }
            )
            config_key = f"shift_{template_id}"
            config_value = schedule_config.get(config_key) or {}
            normalized_config[config_key] = {
                "days": str(config_value.get("days") or "Mon Wed Fri").strip(),
                "count": max(1, int(config_value.get("count") or 1)),
            }

        normalized["shift_templates"] = normalized_templates
        normalized["schedule_config"] = normalized_config

    return normalized


def theory_status(score: int) -> str:
    if score >= 80:
        return "Strong alignment"
    if score >= 60:
        return "Conditional alignment"
    return "Needs review"


def build_ethics_analysis(
    assignments: List[ShiftAssignment],
    students: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    stats: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    primary = [item for item in assignments if item.role == "primary"]
    preferred_matches = 0
    overloaded_students = set()
    backup_ready_shifts = 0
    student_map = {student["name"]: student for student in students}
    hours_by_student = stats.get("hours_by_student", {})

    for item in primary:
        preferred = student_map[item.student]["preferred_shift"]
        if preferred in {"any", "", shift_bucket(item.start_minutes)}:
            preferred_matches += 1

    for student in students:
        if hours_by_student.get(student["name"], 0) > student["max_hours"]:
            overloaded_students.add(student["name"])

    for plan in build_callout_plan(assignments):
        if plan["backups"]:
            backup_ready_shifts += 1

    total_primary = len(primary) or 1
    total_plans = max(1, len({item.shift_instance_id for item in primary}))
    preference_rate = round((preferred_matches / total_primary) * 100)
    conflict_penalty = min(45, len(conflicts) * 18)
    warning_penalty = min(30, len(warnings) * 5)
    overload_penalty = min(25, len(overloaded_students) * 12)
    fairness_penalty = min(20, int(stats.get("fairness_spread", 0) * 4))
    coverage_bonus = round((backup_ready_shifts / total_plans) * 20)
    policy_bonus = 10 if payload.get("mode") == "custom" else 6

    theory_scores = {
        "Subjective Relativism": min(100, max(20, 45 + preference_rate // 2 + coverage_bonus // 3 - conflict_penalty // 3)),
        "Cultural Relativism": min(100, max(20, 68 + coverage_bonus - warning_penalty - conflict_penalty)),
        "Divine Command Theory": min(100, max(20, 58 + coverage_bonus // 2 - conflict_penalty // 2)),
        "Ethical Egoism": min(100, max(20, 55 + coverage_bonus + policy_bonus - overload_penalty - conflict_penalty // 2)),
        "Kantianism": min(100, max(20, 82 - conflict_penalty - overload_penalty - fairness_penalty // 2)),
        "Act Utilitarianism": min(100, max(20, 74 + coverage_bonus - warning_penalty - conflict_penalty)),
        "Rule Utilitarianism": min(100, max(20, 76 + policy_bonus + coverage_bonus - warning_penalty - conflict_penalty // 2)),
        "Social Contract Theory": min(100, max(20, 78 + coverage_bonus - fairness_penalty - overload_penalty - conflict_penalty // 2)),
        "Virtue Ethics": min(100, max(20, 75 + preference_rate // 4 - warning_penalty - fairness_penalty - conflict_penalty // 2)),
    }

    explanations = {
        "Subjective Relativism": "The plan partially reflects individual preferences by considering preferred shift times and personal academic commitments.",
        "Cultural Relativism": "The plan is judged against campus workplace norms such as protecting class time, spreading hours, and maintaining backup coverage.",
        "Divine Command Theory": "This framework remains context-dependent because religious obligations are not inferred automatically and must be supplied as explicit commitments or local rules.",
        "Ethical Egoism": "Operational continuity is supported through backups and coverage planning, but the system does not let institutional self-interest completely override student protections.",
        "Kantianism": "The strongest Kantian signal comes from treating students as ends in themselves through class protection, hour limits, and avoiding purely convenience-driven assignments.",
        "Act Utilitarianism": "The plan aims for the best near-term outcome by balancing staffing continuity with reduced conflicts, overload, and risk.",
        "Rule Utilitarianism": "The service follows repeatable rules such as class protection, weekly limits, fairness checks, and backup planning to improve outcomes over time.",
        "Social Contract Theory": "The plan reflects shared expectations between students and managers by pairing obligations with protections and keeping a reviewable record.",
        "Virtue Ethics": "The strongest virtues on display are fairness, prudence, reliability, and restraint when workload or academic pressure grows too high.",
    }

    theory_results = []
    for theory in ETHICS_THEORIES:
        score = theory_scores[theory]
        theory_results.append(
            {
                "theory": theory,
                "score": score,
                "status": theory_status(score),
                "summary": explanations[theory],
            }
        )

    overall_score = round(sum(item["score"] for item in theory_results) / len(theory_results))
    strong_count = sum(1 for item in theory_results if item["status"] == "Strong alignment")
    needs_review_count = sum(1 for item in theory_results if item["status"] == "Needs review")

    return {
        "overall_score": overall_score,
        "overall_status": theory_status(overall_score),
        "strong_count": strong_count,
        "needs_review_count": needs_review_count,
        "metrics": {
            "preference_match_rate": preference_rate,
            "overloaded_students": len(overloaded_students),
            "backup_ready_shifts": backup_ready_shifts,
            "total_planned_shifts": total_plans,
            "conflict_count": len(conflicts),
            "warning_count": len(warnings),
        },
        "theories": theory_results,
        "narrative": "This ethics review checks whether the scheduling process protects student commitments, shares workload responsibly, and preserves enough operational resilience to avoid avoidable harm.",
    }


def build_stats(assignments: List[ShiftAssignment], students: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
    primary = [a for a in assignments if a.role == "primary"]
    backups = [a for a in assignments if a.role == "backup"]
    by_student: Dict[str, int] = {student["name"]: 0 for student in students}
    hours_by_student: Dict[str, float] = {student["name"]: 0.0 for student in students}
    backup_by_student: Dict[str, int] = {student["name"]: 0 for student in students}
    reliability_map = {student["name"]: student["reliability"] for student in students}
    risk_scores = {}
    dates = set()

    for item in primary:
        by_student[item.student] += 1
        hours_by_student[item.student] += (item.end_minutes - item.start_minutes) / 60
        dates.add(item.date)
    for item in backups:
        backup_by_student[item.student] += 1

    for student in students:
        name = student["name"]
        overload = max(0, hours_by_student[name] - student["max_hours"])
        warnings_count = sum(1 for warning in warnings if warning["student"] == name)
        risk_scores[name] = min(
            100,
            round(
                (student["academic_load"] * 4)
                + (100 - student["reliability"]) * 0.8
                + overload * 6
                + warnings_count * 8
            ),
        )

    counts = list(by_student.values()) or [0]
    average = sum(counts) / len(counts) if counts else 0
    spread = max(counts) - min(counts) if counts else 0
    coverage_ready = sum(1 for plan in build_callout_plan(assignments) if plan["backups"])
    total_shifts = len({a.shift_instance_id for a in primary})

    return {
        "total_students": len(students),
        "total_assignments": len(primary),
        "total_backup_assignments": len(backups),
        "scheduled_days": len(dates),
        "average_assignments": round(average, 2),
        "fairness_spread": spread,
        "assignments_by_student": by_student,
        "hours_by_student": {k: round(v, 1) for k, v in hours_by_student.items()},
        "backup_by_student": backup_by_student,
        "reliability_by_student": reliability_map,
        "risk_by_student": risk_scores,
        "coverage_ready_percent": round((coverage_ready / total_shifts) * 100) if total_shifts else 0,
        "warning_count": len(warnings),
        "high_risk_count": sum(1 for score in risk_scores.values() if score >= 70),
    }


def summarize_services() -> List[Dict[str, str]]:
    return [
        {
            "title": "Shift Planning Desk",
            "summary": "Build weekly staffing plans around class schedules, preferred shift windows, and fair distribution of hours.",
            "href": "/scheduler",
            "help": "Use this workspace to create a new staffing plan for the week, including class-aware assignments and backup coverage.",
        },
        {
            "title": "Coverage Archive",
            "summary": "Review past staffing plans, compare coverage decisions, and revisit earlier assignments without rebuilding them.",
            "href": "/history",
            "help": "Every run is stored automatically so managers can trace what was assigned, when it was created, and how coverage was handled.",
        },
        {
            "title": "Operations Dashboard",
            "summary": "Track fairness, warning volume, coverage readiness, and workload pressure across recent scheduling activity.",
            "href": "/analytics",
            "help": "This page turns schedule output into manager-facing reporting so trends and staffing pressure are easier to explain.",
        },
        {
            "title": "Ethics Review Board",
            "summary": "Review every saved plan against major ethical frameworks to show whether scheduling choices stay fair, explainable, and protective.",
            "href": "/ethics",
            "help": "This page compares each saved plan against the ethics theories listed in your project brief and keeps that record in history.",
        },
        {
            "title": "Manager Help Center",
            "summary": "Get plain-language answers about each workflow, metric, and staffing policy used throughout the platform.",
            "href": "/faq",
            "help": "This page is the quick onboarding layer for managers, reviewers, and anyone learning how the platform works.",
        },
    ]


def compute_history_summary(rows: List[sqlite3.Row]) -> Dict[str, Any]:
    if not rows:
        return {
            "total_runs": 0,
            "primary_assignments": 0,
            "backups": 0,
            "avg_coverage": 0,
            "avg_fairness": 0,
            "warning_total": 0,
        }
    total_runs = len(rows)
    return {
        "total_runs": total_runs,
        "primary_assignments": sum(row["assignment_count"] for row in rows),
        "backups": sum(row["backup_count"] for row in rows),
        "avg_coverage": round(sum(row["coverage_ready_percent"] for row in rows) / total_runs),
        "avg_fairness": round(sum(row["fairness_spread"] for row in rows) / total_runs, 1),
        "warning_total": sum(row["warning_count"] for row in rows),
    }


def service_analytics_snapshot() -> Dict[str, Any]:
    db = get_db()
    rows = db.execute(
        """
        SELECT id, name, created_at, mode, assignment_count, backup_count, warning_count,
               conflict_count, fairness_spread, coverage_ready_percent, scheduled_days
        FROM schedule_runs
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    summary = compute_history_summary(rows)
    recent = [dict(row) for row in rows[:5]]
    warning_trend = [
        {"label": row["name"], "warnings": row["warning_count"], "conflicts": row["conflict_count"]}
        for row in rows[:6]
    ][::-1]
    mix = defaultdict(int)
    for row in rows:
        mix["Smart Custom" if row["mode"] == "custom" else "Round Robin"] += 1
    return {
        "summary": summary,
        "recent_runs": recent,
        "warning_trend": warning_trend,
        "service_mix": [{"name": key, "value": value} for key, value in mix.items()],
    }


def ethics_snapshot() -> Dict[str, Any]:
    rows = get_db().execute(
        """
        SELECT id, name, created_at, ethics_json
        FROM schedule_runs
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    parsed_runs = []
    theory_accumulator = {theory: [] for theory in ETHICS_THEORIES}
    for row in rows:
        ethics = json.loads(row["ethics_json"] or "{}")
        parsed_runs.append(
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "overall_score": ethics.get("overall_score", 0),
                "overall_status": ethics.get("overall_status", "Not rated"),
                "theories": ethics.get("theories", []),
            }
        )
        for theory in ethics.get("theories", []):
            theory_accumulator[theory["theory"]].append(theory["score"])

    theory_summary = []
    for theory in ETHICS_THEORIES:
        scores = theory_accumulator[theory]
        average = round(sum(scores) / len(scores)) if scores else 0
        theory_summary.append(
            {
                "theory": theory,
                "average_score": average,
                "status": theory_status(average) if scores else "Not rated",
            }
        )

    overall_average = round(sum(item["overall_score"] for item in parsed_runs) / len(parsed_runs)) if parsed_runs else 0
    return {
        "overall_average": overall_average,
        "overall_status": theory_status(overall_average) if parsed_runs else "Not rated",
        "runs": parsed_runs,
        "theory_summary": theory_summary,
    }


def get_run_detail(run_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    run = db.execute("SELECT * FROM schedule_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        return None
    assignments = [
        dict(row)
        for row in db.execute(
            """
            SELECT shift_instance_id, assignment_date AS date, student, time_label AS time,
                   shift_name, start_minutes, end_minutes, round_label, role, conflict,
                   conflict_reason, ethics_flags
            FROM assignments
            WHERE run_id = ?
            ORDER BY assignment_date, start_minutes, shift_name, role, student
            """,
            (run_id,),
        ).fetchall()
    ]
    for item in assignments:
        item["conflict"] = bool(item["conflict"])
        item["ethics_flags"] = json.loads(item["ethics_flags"] or "[]")
    return {
        "run": dict(run),
        "students": json.loads(run["students_json"]),
        "assignments": assignments,
        "warnings": json.loads(run["warnings_json"]),
        "conflicts": json.loads(run["conflicts_json"]),
        "callout_plan": json.loads(run["callout_plan_json"]),
        "stats": json.loads(run["stats_json"]),
        "ethics": json.loads(run["ethics_json"] or "{}"),
    }


def save_schedule_run(
    name: str,
    payload: Dict[str, Any],
    students: List[Dict[str, Any]],
    assignments: List[ShiftAssignment],
    conflicts: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    stats: Dict[str, Any],
    callout_plan: List[Dict[str, Any]],
    ethics: Dict[str, Any],
    created_at: Optional[str] = None,
) -> int:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO schedule_runs (
            name, created_at, mode, algorithm, weeks, students_json, payload_json,
            stats_json, warnings_json, conflicts_json, callout_plan_json, ethics_json,
            assignment_count, backup_count, warning_count, conflict_count,
            fairness_spread, coverage_ready_percent, scheduled_days
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            created_at or datetime.utcnow().isoformat(timespec="seconds"),
            payload.get("mode", "round_robin"),
            payload.get("algorithm", "circle"),
            int(payload.get("weeks") or 4),
            json.dumps(serialize_students(students)),
            json.dumps(payload),
            json.dumps(stats),
            json.dumps(warnings),
            json.dumps(conflicts),
            json.dumps(callout_plan),
            json.dumps(ethics),
            stats["total_assignments"],
            stats["total_backup_assignments"],
            stats["warning_count"],
            len(conflicts),
            stats["fairness_spread"],
            stats["coverage_ready_percent"],
            stats["scheduled_days"],
        ),
    )
    run_id = cursor.lastrowid
    db.executemany(
        """
        INSERT INTO assignments (
            run_id, shift_instance_id, assignment_date, student, time_label, shift_name,
            start_minutes, end_minutes, round_label, role, conflict, conflict_reason, ethics_flags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                item.shift_instance_id,
                item.date,
                item.student,
                item.time,
                item.shift_name,
                item.start_minutes,
                item.end_minutes,
                item.round_label,
                item.role,
                int(item.conflict),
                item.conflict_reason,
                json.dumps(item.ethics_flags),
            )
            for item in assignments
        ],
    )
    db.commit()
    return run_id


def seed_history_data() -> None:
    db = get_db()
    existing_count = db.execute("SELECT COUNT(*) AS count FROM schedule_runs").fetchone()["count"]
    if existing_count:
        return

    for scenario in PRELOADED_SCENARIOS:
        base_date = datetime.strptime(scenario["base_date"], "%Y-%m-%d").date()
        payload = {k: v for k, v in scenario.items() if k not in {"name", "base_date"}}
        students = parse_students(payload, base_date=base_date)
        assignments = (
            build_custom_schedule(students, payload, base_date=base_date)
            if payload["mode"] == "custom"
            else expand_round_robin_schedule(students, payload.get("algorithm", "circle"), base_date=base_date)
        )
        conflicts = detect_conflicts(assignments, students)
        warnings = build_warnings(assignments, students)
        stats = build_stats(assignments, students, warnings)
        callout_plan = build_callout_plan(assignments)
        ethics = build_ethics_analysis(assignments, students, warnings, conflicts, stats, payload)
        save_schedule_run(
            scenario["name"],
            payload,
            students,
            assignments,
            conflicts,
            warnings,
            stats,
            callout_plan,
            ethics,
            created_at=f"{scenario['base_date']}T09:00:00",
        )


def backfill_ethics_data() -> None:
    db = get_db()
    rows = db.execute(
        """
        SELECT id, payload_json, students_json, stats_json, warnings_json, conflicts_json, ethics_json
        FROM schedule_runs
        """
    ).fetchall()
    for row in rows:
        if row["ethics_json"] and row["ethics_json"] != "{}":
            continue
        assignment_rows = db.execute(
            """
            SELECT shift_instance_id, assignment_date, student, time_label, shift_name,
                   start_minutes, end_minutes, round_label, role, conflict, conflict_reason, ethics_flags
            FROM assignments
            WHERE run_id = ?
            ORDER BY assignment_date, start_minutes, shift_name, role, student
            """,
            (row["id"],),
        ).fetchall()
        assignments = []
        for item in assignment_rows:
            assignments.append(
                ShiftAssignment(
                    shift_instance_id=item["shift_instance_id"],
                    date=item["assignment_date"],
                    student=item["student"],
                    time=item["time_label"],
                    shift_name=item["shift_name"],
                    start_minutes=item["start_minutes"],
                    end_minutes=item["end_minutes"],
                    round_label=item["round_label"],
                    conflict=bool(item["conflict"]),
                    conflict_reason=item["conflict_reason"],
                    role=item["role"],
                    ethics_flags=json.loads(item["ethics_flags"] or "[]"),
                )
            )
        students = json.loads(row["students_json"])
        payload = json.loads(row["payload_json"])
        stats = json.loads(row["stats_json"])
        warnings = json.loads(row["warnings_json"])
        conflicts = json.loads(row["conflicts_json"])
        ethics = build_ethics_analysis(assignments, students, warnings, conflicts, stats, payload)
        db.execute("UPDATE schedule_runs SET ethics_json = ? WHERE id = ?", (json.dumps(ethics), row["id"]))
    db.commit()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                weeks INTEGER NOT NULL,
                students_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                conflicts_json TEXT NOT NULL,
                callout_plan_json TEXT NOT NULL,
                ethics_json TEXT NOT NULL DEFAULT '{}',
                assignment_count INTEGER NOT NULL,
                backup_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                conflict_count INTEGER NOT NULL,
                fairness_spread REAL NOT NULL,
                coverage_ready_percent REAL NOT NULL,
                scheduled_days INTEGER NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                shift_instance_id TEXT NOT NULL,
                assignment_date TEXT NOT NULL,
                student TEXT NOT NULL,
                time_label TEXT NOT NULL,
                shift_name TEXT NOT NULL,
                start_minutes INTEGER NOT NULL,
                end_minutes INTEGER NOT NULL,
                round_label TEXT,
                role TEXT NOT NULL,
                conflict INTEGER NOT NULL DEFAULT 0,
                conflict_reason TEXT,
                ethics_flags TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (run_id) REFERENCES schedule_runs (id)
            )
            """
        )
        db.commit()
        columns = {row[1] for row in db.execute("PRAGMA table_info(schedule_runs)").fetchall()}
        if "ethics_json" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN ethics_json TEXT NOT NULL DEFAULT '{}'")
            db.commit()

    with app.app_context():
        seed_history_data()
        backfill_ethics_data()


@app.context_processor
def inject_global_template_data() -> Dict[str, Any]:
    return {"services_nav": summarize_services(), "faq_items": FAQ_ITEMS}


@app.route("/")
def home() -> str:
    analytics = service_analytics_snapshot()
    carousel_items = []
    for run in analytics["recent_runs"][:4]:
        carousel_items.append(
            {
                "eyebrow": "Recent Activity",
                "title": run["name"],
                "description": f"{run['assignment_count']} primary assignments, {run['backup_count']} backups, {run['coverage_ready_percent']}% coverage ready.",
                "href": f"/history/{run['id']}",
                "cta": "Open run",
            }
        )
    if not carousel_items:
        carousel_items = [
            {
                "eyebrow": "Live Workspace",
                "title": "Weekly floor coverage planning",
                "description": "Create manager-ready schedules with backup coverage and a clean approval trail.",
                "href": "/scheduler",
                "cta": "Plan shifts",
            }
        ]
    return render_template(
        "home.html",
        page_name="home",
        analytics=analytics,
        service_cards=summarize_services(),
        featured_run=analytics["recent_runs"][0] if analytics["recent_runs"] else None,
        carousel_items=carousel_items,
    )


@app.route("/services")
def services_page() -> str:
    analytics = service_analytics_snapshot()
    return render_template(
        "services.html",
        page_name="services",
        service_cards=summarize_services(),
        analytics=analytics,
    )


@app.route("/scheduler")
def scheduler_page() -> str:
    return render_template(
        "scheduler.html",
        page_name="scheduler",
        default_templates=DEFAULT_SHIFT_TEMPLATES,
        default_config=DEFAULT_CUSTOM_CONFIG,
        default_students=DEFAULT_STUDENTS,
    )


@app.route("/analytics")
def analytics_page() -> str:
    return render_template("analytics.html", page_name="analytics", analytics=service_analytics_snapshot())


@app.route("/ethics")
def ethics_page() -> str:
    return render_template("ethics.html", page_name="ethics", ethics=ethics_snapshot(), theories=ETHICS_THEORIES)


@app.route("/history")
def history_page() -> str:
    rows = get_db().execute(
        """
        SELECT id, name, created_at, mode, assignment_count, backup_count, warning_count,
               conflict_count, fairness_spread, coverage_ready_percent, scheduled_days, ethics_json
        FROM schedule_runs
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    history_runs = []
    for row in rows:
        item = dict(row)
        ethics = json.loads(item["ethics_json"] or "{}")
        item["ethics_overall_status"] = ethics.get("overall_status", "Not rated")
        item["ethics_overall_score"] = ethics.get("overall_score", 0)
        history_runs.append(item)
    return render_template(
        "history.html",
        page_name="history",
        history_runs=history_runs,
        history_summary=compute_history_summary(rows),
    )


@app.route("/history/<int:run_id>")
def history_detail_page(run_id: int) -> str:
    detail = get_run_detail(run_id)
    if detail is None:
        abort(404)
    return render_template("history_detail.html", page_name="history", detail=detail)


@app.route("/history/<int:run_id>/download/json")
def download_run_json(run_id: int):
    detail = get_run_detail(run_id)
    if detail is None:
        abort(404)
    payload = {
        "run": {
            "id": detail["run"]["id"],
            "name": detail["run"]["name"],
            "created_at": detail["run"]["created_at"],
            "mode": detail["run"]["mode"],
            "algorithm": detail["run"]["algorithm"],
            "weeks": detail["run"]["weeks"],
        },
        "stats": detail["stats"],
        "ethics": detail["ethics"],
        "warnings": detail["warnings"],
        "conflicts": detail["conflicts"],
        "callout_plan": detail["callout_plan"],
        "assignments": detail["assignments"],
    }
    response = make_response(json.dumps(payload, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f"attachment; filename=run-{run_id}.json"
    return response


@app.route("/history/<int:run_id>/download/csv")
def download_run_csv(run_id: int):
    detail = get_run_detail(run_id)
    if detail is None:
        abort(404)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "shift_name", "student", "role", "time", "status", "round_label"])
    for item in detail["assignments"]:
        writer.writerow(
            [
                item["date"],
                item["shift_name"],
                item["student"],
                item["role"],
                item["time"],
                item["conflict_reason"] if item["conflict"] else "Clear",
                item["round_label"] or "",
            ]
        )
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename=run-{run_id}.csv"
    return response


@app.route("/faq")
def faq_page() -> str:
    return render_template("faq.html", page_name="faq", faq_items=FAQ_ITEMS)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True)
    students = parse_students(payload, base_date=date.today())
    if len(students) < 2:
        return jsonify({"error": "Add at least 2 students to generate a schedule."}), 400

    mode = payload.get("mode", "round_robin")
    algorithm = payload.get("algorithm", "circle")
    schedule_name = (payload.get("schedule_name") or "").strip() or f"{'Custom' if mode == 'custom' else 'Round Robin'} Service Run"
    try:
        assignments = (
            build_custom_schedule(students, payload, base_date=date.today())
            if mode == "custom"
            else expand_round_robin_schedule(students, algorithm, base_date=date.today())
        )
        conflicts = detect_conflicts(assignments, students)
        warnings = build_warnings(assignments, students)
        stats = build_stats(assignments, students, warnings)
        callout_plan = build_callout_plan(assignments)
        ethics = build_ethics_analysis(assignments, students, warnings, conflicts, stats, payload)
        run_id = save_schedule_run(schedule_name, payload, students, assignments, conflicts, warnings, stats, callout_plan, ethics)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "run_id": run_id,
            "assignments": serialize_assignments(assignments),
            "conflicts": conflicts,
            "warnings": warnings,
            "stats": stats,
            "callout_plan": callout_plan,
            "ethics": ethics,
            "history_url": f"/history/{run_id}",
            "export_json_url": f"/history/{run_id}/download/json",
            "export_csv_url": f"/history/{run_id}/download/csv",
        }
    )


@app.route("/api/input-template")
def api_input_template():
    response = make_response(json.dumps(build_input_template(), indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = "attachment; filename=planner-template.json"
    return response


@app.route("/api/import-template", methods=["POST"])
def api_import_template():
    payload = request.get_json(force=True)
    try:
        normalized = normalize_import_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"payload": normalized})


init_db()


if __name__ == "__main__":
    app.run(debug=True)
