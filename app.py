from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timedelta
import re
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

DAY_MAP = {
    "su": 6, "sun": 6, "sunday": 6,
    "m": 0, "mon": 0, "monday": 0,
    "t": 1, "tu": 1, "tue": 1, "tuesday": 1,
    "w": 2, "wed": 2, "wednesday": 2,
    "th": 3, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "f": 4, "fri": 4, "friday": 4,
    "s": 5, "sat": 5, "saturday": 5,
}

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
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
    {"name": "Alex Morgan", "profile": "Mon Wed Fri 9-10am, Tue Thu 2-3:30pm", "reliability": 92, "max_hours": 12, "preferred_shift": "afternoon", "recent_callouts": 0},
    {"name": "Priya Shah", "profile": "Tue Thu 11-12:30pm, Final Exam Dec 16 1-3pm", "reliability": 95, "max_hours": 10, "preferred_shift": "morning", "recent_callouts": 0},
    {"name": "Jordan Lee", "profile": "Mon Wed 1-2pm, Fri 10-11am", "reliability": 84, "max_hours": 14, "preferred_shift": "evening", "recent_callouts": 1},
    {"name": "Camila Torres", "profile": "Tue Thu 9-10am, Quiz Nov 20 3-4pm", "reliability": 88, "max_hours": 12, "preferred_shift": "afternoon", "recent_callouts": 0},
]


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


TIME_RE = re.compile(r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)?", re.I)
RANGE_RE = re.compile(r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:-|to)\s*(?P<end>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", re.I)
DAY_TOKEN_RE = re.compile(r"(?:mon|monday|m|tue|tuesday|tu|t|wed|wednesday|w|thu|thursday|thurs|thur|th|fri|friday|f|sat|saturday|sat|s|sun|sunday|su)", re.I)
EXAM_DATE_RE = re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|[A-Za-z]+)\s+(\d{1,2})", re.I)
CLASS_LINE_RE = re.compile(r"^(?P<days>[A-Za-z/ ,]+?)\s+(?P<range>\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:-|to)\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$", re.I)


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
            if compact[i:i+2] == "th":
                ordered.append("th")
                i += 2
            elif compact[i:i+2] == "su":
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
            commitments.append(Commitment(type="exam", description=chunk, date=exam_date, start_minutes=start_minutes, end_minutes=end_minutes, priority="high" if "final" in lower else "medium"))
            continue

        class_match = CLASS_LINE_RE.match(chunk)
        if class_match and time_match:
            days = parse_day_tokens(class_match.group("days"))
            for day_value in days:
                commitments.append(Commitment(type="class", description=chunk, day_of_week=day_value, start_minutes=start_minutes, end_minutes=end_minutes))
            continue

        commitments.append(Commitment(type="other", description=chunk))
    return commitments


def parse_students(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    students = payload.get("students") or []
    parsed = []
    for idx, raw in enumerate(students, start=1):
        name = (raw.get("name") or f"Student {idx}").strip() or f"Student {idx}"
        profile_text = (raw.get("profile") or "").strip()
        commitments = parse_commitments(profile_text)
        reliability = max(50, min(100, int(raw.get("reliability") or 85)))
        max_hours = max(1, min(40, int(raw.get("max_hours") or 12)))
        preferred_shift = (raw.get("preferred_shift") or "any").strip().lower() or "any"
        recent_callouts = max(0, min(10, int(raw.get("recent_callouts") or 0)))
        parsed.append({
            "name": name,
            "profile": profile_text,
            "commitments": commitments,
            "reliability": reliability,
            "max_hours": max_hours,
            "preferred_shift": preferred_shift,
            "recent_callouts": recent_callouts,
            "academic_load": len([c for c in commitments if c.type in {"class", "exam"}]),
        })
    return parsed


def circle_pairs(student_count: int) -> List[List[List[int]]]:
    workers: List[Any] = list(range(student_count))
    odd = student_count % 2 == 1
    if odd:
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
    odd = student_count % 2 == 1
    if odd:
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


def conflicts_with_commitments(student: Dict[str, Any], shift_date: str, start_minutes: int, end_minutes: int) -> Optional[Commitment]:
    weekday = datetime.strptime(shift_date, "%Y-%m-%d").date().weekday()
    for commitment in student["commitments"]:
        day_match = commitment.date == shift_date if commitment.date else commitment.day_of_week == weekday
        if not day_match or commitment.start_minutes is None or commitment.end_minutes is None:
            continue
        if overlaps(start_minutes, end_minutes, commitment.start_minutes, commitment.end_minutes):
            return commitment
    return None


def overlaps_existing(student_name: str, shift_date: str, start_minutes: int, end_minutes: int, assignments: List[ShiftAssignment]) -> bool:
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


def build_score(student: Dict[str, Any], student_stats: Dict[str, Dict[str, Any]], shift_date: date, start_minutes: int, end_minutes: int, assignments: List[ShiftAssignment], for_backup: bool = False) -> Optional[tuple]:
    shift_iso = shift_date.isoformat()
    commitment = conflicts_with_commitments(student, shift_iso, start_minutes, end_minutes)
    if commitment:
        return None
    if overlaps_existing(student["name"], shift_iso, start_minutes, end_minutes, assignments):
        return None

    stat = student_stats[student["name"]]
    duration_hours = (end_minutes - start_minutes) / 60
    projected_hours = stat["hours_primary"] + (0 if for_backup else duration_hours)
    overtime_ratio = projected_hours / max(student["max_hours"], 1)
    pref = student["preferred_shift"]
    bucket = shift_bucket(start_minutes)
    preference_penalty = 0 if pref in {"any", bucket, ""} else 1
    reliability_bonus = (100 - student["reliability"]) / 100
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
        round(reliability_bonus + callout_penalty + academic_penalty + backup_penalty, 3),
        freshness,
        student["name"].lower(),
    )


def choose_candidates(students: List[Dict[str, Any]], student_stats: Dict[str, Dict[str, Any]], shift_date: date, start_minutes: int, end_minutes: int, assignments: List[ShiftAssignment], count: int, for_backup: bool = False, exclude: Optional[set] = None) -> List[str]:
    exclude = exclude or set()
    ranked = []
    for student in students:
        if student["name"] in exclude:
            continue
        score = build_score(student, student_stats, shift_date, start_minutes, end_minutes, assignments, for_backup=for_backup)
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


def expand_round_robin_schedule(students: List[Dict[str, Any]], algorithm: str) -> List[ShiftAssignment]:
    pair_rounds = circle_pairs(len(students)) if algorithm == "circle" else standard_pairs(len(students))
    shift_slots = [("Morning Concierge", 9 * 60, 13 * 60), ("Afternoon Studio", 13 * 60, 17 * 60), ("Evening Lounge", 17 * 60, 21 * 60)]
    monday = start_of_week(date.today())
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
                assignments.append(ShiftAssignment(shift_instance_id=shift_instance_id, date=shift_date, student=student["name"], time=f"{minutes_to_label(start_minutes)} - {minutes_to_label(end_minutes)}", shift_name=slot_name, start_minutes=start_minutes, end_minutes=end_minutes, round_label=f"Round {round_index} • Shift {pair_index}"))
            slot_index += 1
    return assignments


def parse_custom_days(value: str) -> List[int]:
    chunks = [chunk for chunk in re.split(r"[,/]|\s+", value.strip()) if chunk]
    joined = " ".join(chunks)
    parsed = parse_day_tokens(joined)
    return parsed if parsed else parse_day_tokens(value.replace(" ", ""))


def build_custom_schedule(students: List[Dict[str, Any]], payload: Dict[str, Any]) -> List[ShiftAssignment]:
    shift_templates = payload.get("shift_templates") or DEFAULT_SHIFT_TEMPLATES
    schedule_config = payload.get("schedule_config") or DEFAULT_CUSTOM_CONFIG
    weeks = int(payload.get("weeks") or 4)
    monday = start_of_week(date.today())
    assignments: List[ShiftAssignment] = []
    student_stats = {s["name"]: {"primary_assignments": 0, "backup_assignments": 0, "hours_primary": 0.0, "last_assigned_ordinal": -10**9} for s in students}

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
                shift_id = f"c-{week+1}-{template['id']}-{i+1}"
                primaries = choose_candidates(students, student_stats, shift_date, shift_start, shift_end, assignments, needed, for_backup=False)
                backups = choose_candidates(students, student_stats, shift_date, shift_start, shift_end, assignments, min(2, max(0, len(students) - len(primaries))), for_backup=True, exclude=set(primaries))
                for name in primaries:
                    assignments.append(ShiftAssignment(shift_instance_id=shift_id, date=shift_date.isoformat(), student=name, time=f"{minutes_to_label(shift_start)} - {minutes_to_label(shift_end)}", shift_name=template["name"], start_minutes=shift_start, end_minutes=shift_end, round_label=f"Week {week + 1}", role="primary"))
                for name in backups:
                    assignments.append(ShiftAssignment(shift_instance_id=shift_id, date=shift_date.isoformat(), student=name, time=f"{minutes_to_label(shift_start)} - {minutes_to_label(shift_end)}", shift_name=template["name"], start_minutes=shift_start, end_minutes=shift_end, round_label=f"Week {week + 1}", role="backup", ethics_flags=["backup coverage"] ))
    assignments.sort(key=lambda item: (item.date, item.start_minutes, item.shift_name, item.role, item.student))
    return assignments


def detect_conflicts(assignments: List[ShiftAssignment], students: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    student_map = {student["name"]: student for student in students}
    conflicts = []
    for assignment in assignments:
        if assignment.role != "primary":
            continue
        commitment = conflicts_with_commitments(student_map[assignment.student], assignment.date, assignment.start_minutes, assignment.end_minutes)
        if commitment:
            assignment.conflict = True
            assignment.conflict_reason = commitment.description
            assignment.ethics_flags.append("academic conflict")
            conflicts.append({"student": assignment.student, "date": assignment.date, "time": assignment.time, "shift_name": assignment.shift_name, "reason": f"{commitment.type.title()} conflict", "commitment": commitment.description, "priority": commitment.priority})
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
            warnings.append({"student": student_name, "date": week_start, "severity": "high", "reason": f"Scheduled {hours:.1f}h against {limit}h weekly limit", "type": "overload"})

    for key, day_items in grouped_by_student_day.items():
        day_items.sort(key=lambda item: item.start_minutes)
        for left, right in zip(day_items, day_items[1:]):
            gap = right.start_minutes - left.end_minutes
            if gap < 60:
                warnings.append({"student": key[0], "date": key[1], "severity": "medium", "reason": f"Back-to-back shifts with only {max(gap,0)} minutes between them", "type": "fatigue"})
        reliability = student_map[key[0]]["reliability"]
        if reliability < 75 and len(day_items) > 0:
            warnings.append({"student": key[0], "date": key[1], "severity": "medium", "reason": f"Lower reliability score ({reliability}%) suggests keeping backup coverage active", "type": "coverage"})

    return warnings


def build_callout_plan(assignments: List[ShiftAssignment]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in assignments:
        row = grouped.setdefault(item.shift_instance_id, {"shift_instance_id": item.shift_instance_id, "date": item.date, "time": item.time, "shift_name": item.shift_name, "primaries": [], "backups": []})
        row["primaries" if item.role == "primary" else "backups"].append(item.student)
    plans = list(grouped.values())
    plans.sort(key=lambda row: (row["date"], row["time"], row["shift_name"]))
    return plans


def serialize_assignments(assignments: List[ShiftAssignment]) -> List[Dict[str, Any]]:
    return [asdict(item) for item in assignments]


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
        warnings_count = sum(1 for w in warnings if w["student"] == name)
        risk = min(100, round((student["academic_load"] * 4) + (100 - student["reliability"]) * 0.8 + overload * 6 + warnings_count * 8))
        risk_scores[name] = risk

    counts = list(by_student.values()) or [0]
    avg = sum(counts) / len(counts) if counts else 0
    spread = max(counts) - min(counts) if counts else 0
    coverage_ready = sum(1 for plan in build_callout_plan(assignments) if len(plan["backups"]) > 0)
    total_shifts = len({a.shift_instance_id for a in primary})

    return {
        "total_students": len(students),
        "total_assignments": len(primary),
        "total_backup_assignments": len(backups),
        "scheduled_days": len(dates),
        "average_assignments": round(avg, 2),
        "fairness_spread": spread,
        "assignments_by_student": by_student,
        "hours_by_student": {k: round(v, 1) for k, v in hours_by_student.items()},
        "backup_by_student": backup_by_student,
        "reliability_by_student": reliability_map,
        "risk_by_student": risk_scores,
        "coverage_ready_percent": round((coverage_ready / total_shifts) * 100) if total_shifts else 0,
        "warning_count": len(warnings),
    }


@app.route("/")
def index() -> str:
    return render_template("index.html", default_templates=DEFAULT_SHIFT_TEMPLATES, default_config=DEFAULT_CUSTOM_CONFIG, default_students=DEFAULT_STUDENTS)


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True)
    students = parse_students(payload)
    if len(students) < 2:
        return jsonify({"error": "Add at least 2 students to generate a schedule."}), 400
    mode = payload.get("mode", "round_robin")
    algorithm = payload.get("algorithm", "circle")
    try:
        assignments = build_custom_schedule(students, payload) if mode == "custom" else expand_round_robin_schedule(students, algorithm)
        conflicts = detect_conflicts(assignments, students)
        warnings = build_warnings(assignments, students)
        stats = build_stats(assignments, students, warnings)
        callout_plan = build_callout_plan(assignments)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"assignments": serialize_assignments(assignments), "conflicts": conflicts, "warnings": warnings, "stats": stats, "callout_plan": callout_plan})


if __name__ == "__main__":
    app.run(debug=True)
