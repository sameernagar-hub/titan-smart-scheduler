from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
import re
from typing import Any, Dict, List, Optional

from scheduler_config import ALGORITHM_META, DEFAULT_CUSTOM_CONFIG, DEFAULT_SHIFT_TEMPLATES, DEFAULT_STUDENTS

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


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def algorithm_label(algorithm: str) -> str:
    return ALGORITHM_META.get(algorithm, ALGORITHM_META["round_robin"]).get("label", "Round Robin")


def algorithm_family(algorithm: str) -> str:
    return ALGORITHM_META.get(algorithm, ALGORITHM_META["round_robin"]).get("family", "Rotational")


def algorithm_summary(algorithm: str) -> str:
    return ALGORITHM_META.get(algorithm, ALGORITHM_META["round_robin"]).get("summary", "")


def mode_label(mode: str) -> str:
    return "Smart Custom" if mode == "custom" else "Signature Rotation"


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
        reliability = clamp_int(raw.get("reliability"), 85, 50, 100)
        max_hours = clamp_int(raw.get("max_hours"), 12, 1, 40)
        preferred_shift = (raw.get("preferred_shift") or "any").strip().lower() or "any"
        recent_callouts = clamp_int(raw.get("recent_callouts"), 0, 0, 10)
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
            round_pairs.append(pair)
        schedule.append([pair for pair in round_pairs if "BYE" not in pair])
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


def initialize_student_stats(students: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        student["name"]: {
            "primary_assignments": 0,
            "backup_assignments": 0,
            "hours_primary": 0.0,
            "last_assigned_ordinal": -10**9,
            "weekly_hours": defaultdict(float),
            "daily_primary": defaultdict(int),
        }
        for student in students
    }


def day_spacing_penalty(
    student_name: str, shift_iso: str, start_minutes: int, end_minutes: int, assignments: List[ShiftAssignment]
) -> float:
    penalty = 0.0
    for item in assignments:
        if item.student != student_name or item.date != shift_iso or item.role != "primary":
            continue
        if overlaps(start_minutes, end_minutes, item.start_minutes, item.end_minutes):
            return 99.0
        gap = min(abs(start_minutes - item.end_minutes), abs(item.start_minutes - end_minutes))
        if gap < 60:
            penalty += round((60 - max(gap, 0)) / 20, 2)
    return penalty


def build_score(
    student: Dict[str, Any],
    student_stats: Dict[str, Dict[str, Any]],
    shift_date: date,
    start_minutes: int,
    end_minutes: int,
    assignments: List[ShiftAssignment],
    for_backup: bool = False,
    strategy: str = "smart",
) -> Optional[tuple]:
    shift_iso = shift_date.isoformat()
    commitment = conflicts_with_commitments(student, shift_iso, start_minutes, end_minutes)
    if commitment or overlaps_existing(student["name"], shift_iso, start_minutes, end_minutes, assignments):
        return None

    stat = student_stats[student["name"]]
    duration_hours = (end_minutes - start_minutes) / 60
    projected_hours = stat["hours_primary"] + (0 if for_backup else duration_hours)
    week_key = start_of_week(shift_date).isoformat()
    projected_week_hours = stat["weekly_hours"].get(week_key, 0.0) + (0 if for_backup else duration_hours)
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
    spacing_penalty = day_spacing_penalty(student["name"], shift_iso, start_minutes, end_minutes, assignments)
    weekly_ratio = projected_week_hours / max(student["max_hours"], 1)

    if strategy == "priority":
        return (
            student["recent_callouts"],
            100 - student["reliability"],
            preference_penalty,
            round(weekly_ratio, 3),
            stat["primary_assignments"] + (0 if for_backup else 1),
            round(academic_penalty + backup_penalty + spacing_penalty, 3),
            freshness,
            student["name"].lower(),
        )

    if strategy == "constraint_shield":
        return (
            round(overload_penalty, 3),
            1 if weekly_ratio > 1 else 0,
            round(spacing_penalty, 3),
            preference_penalty,
            round(reliability_penalty + callout_penalty + academic_penalty + backup_penalty, 3),
            stat["primary_assignments"] + (0 if for_backup else 1),
            round(projected_week_hours, 2),
            freshness,
            student["name"].lower(),
        )

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
    strategy: str = "smart",
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
            strategy=strategy,
        )
        if score is not None:
            ranked.append((score, student["name"]))
    ranked.sort(key=lambda item: item[0])
    chosen = [name for _, name in ranked[:count]]
    duration_hours = (end_minutes - start_minutes) / 60
    week_key = start_of_week(shift_date).isoformat()
    shift_iso = shift_date.isoformat()
    for name in chosen:
        stat = student_stats[name]
        if for_backup:
            stat["backup_assignments"] += 1
        else:
            stat["primary_assignments"] += 1
            stat["hours_primary"] += duration_hours
            stat["last_assigned_ordinal"] = shift_date.toordinal()
            stat["weekly_hours"][week_key] += duration_hours
            stat["daily_primary"][shift_iso] += 1
    return chosen


def preview_candidates(
    students: List[Dict[str, Any]],
    student_stats: Dict[str, Dict[str, Any]],
    shift_date: date,
    start_minutes: int,
    end_minutes: int,
    assignments: List[ShiftAssignment],
    count: int,
    strategy: str,
) -> List[str]:
    ranked = []
    for student in students:
        score = build_score(
            student,
            student_stats,
            shift_date,
            start_minutes,
            end_minutes,
            assignments,
            strategy=strategy,
        )
        if score is not None:
            ranked.append((score, student["name"]))
    ranked.sort(key=lambda item: item[0])
    return [name for _, name in ranked[:count]]


def parse_custom_days(value: str) -> List[int]:
    chunks = [chunk for chunk in re.split(r"[,/]|\s+", value.strip()) if chunk]
    joined = " ".join(chunks)
    parsed = parse_day_tokens(joined)
    return parsed if parsed else parse_day_tokens(value.replace(" ", ""))


def build_shift_occurrences(payload: Dict[str, Any], base_date: Optional[date] = None) -> List[Dict[str, Any]]:
    use_custom = payload.get("mode") == "custom"
    shift_templates = payload.get("shift_templates") if use_custom else DEFAULT_SHIFT_TEMPLATES
    schedule_config = payload.get("schedule_config") if use_custom else DEFAULT_CUSTOM_CONFIG
    shift_templates = shift_templates or DEFAULT_SHIFT_TEMPLATES
    schedule_config = schedule_config or DEFAULT_CUSTOM_CONFIG
    weeks = clamp_int(payload.get("weeks"), 4, 1, 12)
    monday = start_of_week(base_date or date.today())
    occurrences: List[Dict[str, Any]] = []

    for week in range(weeks):
        base_week = monday + timedelta(days=7 * week)
        for template in shift_templates:
            config = schedule_config.get(f"shift_{template['id']}", {"days": "Mon Wed Fri", "count": 3})
            weekdays = parse_custom_days(config.get("days", ""))
            if not weekdays:
                continue
            weekly_count = clamp_int(config.get("count"), 1, 1, 7)
            shift_start = parse_time_to_minutes(template["start"])
            shift_end = parse_time_to_minutes(template["end"])
            if shift_end <= shift_start:
                raise ValueError(f"Shift end time must be after start time for {template['name']}")
            for i in range(weekly_count):
                weekday = weekdays[i % len(weekdays)]
                shift_date = base_week + timedelta(days=weekday)
                occurrences.append(
                    {
                        "shift_instance_id": f"s-{week + 1}-{template['id']}-{i + 1}",
                        "date": shift_date,
                        "shift_name": template["name"],
                        "start_minutes": shift_start,
                        "end_minutes": shift_end,
                        "time": f"{minutes_to_label(shift_start)} - {minutes_to_label(shift_end)}",
                        "students_needed": clamp_int(template.get("students_needed"), 1, 1, 12),
                        "week_label": f"Week {week + 1}",
                        "weekday_options": weekdays,
                        "preferred_weekday": weekday,
                    }
                )
    occurrences.sort(key=lambda item: (item["date"], item["start_minutes"], item["shift_name"]))
    return occurrences


def rotation_round_orders(student_count: int, algorithm: str) -> List[List[int]]:
    rounds = circle_pairs(student_count) if algorithm == "circle" else standard_pairs(student_count)
    orders: List[List[int]] = []
    for pairings in rounds:
        ordered: List[int] = []
        for pair in pairings:
            for index in pair:
                if index not in ordered:
                    ordered.append(index)
        for index in range(student_count):
            if index not in ordered:
                ordered.append(index)
        orders.append(ordered)
    return orders or [list(range(student_count))]


def available_rotation_candidates(
    order: List[int],
    students: List[Dict[str, Any]],
    shift_date: date,
    start_minutes: int,
    end_minutes: int,
    assignments: List[ShiftAssignment],
    exclude: Optional[set] = None,
) -> List[str]:
    exclude = exclude or set()
    names = []
    shift_iso = shift_date.isoformat()
    for index in order:
        student = students[index]
        if student["name"] in exclude:
            continue
        if overlaps_existing(student["name"], shift_iso, start_minutes, end_minutes, assignments):
            continue
        names.append(student["name"])
    return names


def choose_best_shift_date(
    students: List[Dict[str, Any]],
    student_stats: Dict[str, Dict[str, Any]],
    assignments: List[ShiftAssignment],
    base_week: date,
    preferred_weekday: int,
    weekday_options: List[int],
    start_minutes: int,
    end_minutes: int,
    needed: int,
    strategy: str,
) -> date:
    candidates = []
    for weekday in dict.fromkeys([preferred_weekday] + weekday_options):
        slot_date = base_week + timedelta(days=weekday)
        ranked = preview_candidates(
            students,
            student_stats,
            slot_date,
            start_minutes,
            end_minutes,
            assignments,
            needed,
            strategy,
        )
        score = (len(ranked) < needed, needed - len(ranked), abs(weekday - preferred_weekday), slot_date.isoformat())
        candidates.append((score, slot_date))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_rotation_schedule(
    students: List[Dict[str, Any]], payload: Dict[str, Any], algorithm: str, base_date: Optional[date] = None
) -> List[ShiftAssignment]:
    occurrences = build_shift_occurrences(payload, base_date=base_date)
    orders = rotation_round_orders(len(students), algorithm)
    assignments: List[ShiftAssignment] = []
    for slot_index, slot in enumerate(occurrences):
        order = orders[slot_index % len(orders)]
        shift_date = slot["date"]
        offset = (slot_index * max(1, slot["students_needed"])) % len(order)
        rotated = order[offset:] + order[:offset]
        primaries = available_rotation_candidates(
            rotated,
            students,
            shift_date,
            slot["start_minutes"],
            slot["end_minutes"],
            assignments,
        )[: slot["students_needed"]]
        backups = available_rotation_candidates(
            rotated,
            students,
            shift_date,
            slot["start_minutes"],
            slot["end_minutes"],
            assignments,
            exclude=set(primaries),
        )[: min(2, max(0, len(students) - len(primaries)))]
        for name in primaries:
            assignments.append(
                ShiftAssignment(
                    shift_instance_id=slot["shift_instance_id"],
                    date=shift_date.isoformat(),
                    student=name,
                    time=slot["time"],
                    shift_name=slot["shift_name"],
                    start_minutes=slot["start_minutes"],
                    end_minutes=slot["end_minutes"],
                    round_label=f"{algorithm_label(algorithm)} / Cycle {(slot_index % len(orders)) + 1}",
                )
            )
        for name in backups:
            assignments.append(
                ShiftAssignment(
                    shift_instance_id=slot["shift_instance_id"],
                    date=shift_date.isoformat(),
                    student=name,
                    time=slot["time"],
                    shift_name=slot["shift_name"],
                    start_minutes=slot["start_minutes"],
                    end_minutes=slot["end_minutes"],
                    round_label=f"{algorithm_label(algorithm)} / Cycle {(slot_index % len(orders)) + 1}",
                    role="backup",
                    ethics_flags=["backup coverage"],
                )
            )
    assignments.sort(key=lambda item: (item.date, item.start_minutes, item.shift_name, item.role, item.student))
    return assignments


def build_custom_schedule(
    students: List[Dict[str, Any]],
    payload: Dict[str, Any],
    base_date: Optional[date] = None,
    strategy: str = "smart",
    allow_day_flex: bool = False,
) -> List[ShiftAssignment]:
    occurrences = build_shift_occurrences(payload, base_date=base_date)
    assignments: List[ShiftAssignment] = []
    student_stats = initialize_student_stats(students)

    for slot in occurrences:
        shift_date = slot["date"]
        if allow_day_flex:
            week_start = start_of_week(shift_date)
            shift_date = choose_best_shift_date(
                students,
                student_stats,
                assignments,
                week_start,
                slot["preferred_weekday"],
                slot["weekday_options"],
                slot["start_minutes"],
                slot["end_minutes"],
                slot["students_needed"],
                strategy,
            )
        primaries = choose_candidates(
            students,
            student_stats,
            shift_date,
            slot["start_minutes"],
            slot["end_minutes"],
            assignments,
            slot["students_needed"],
            strategy=strategy,
        )
        backups = choose_candidates(
            students,
            student_stats,
            shift_date,
            slot["start_minutes"],
            slot["end_minutes"],
            assignments,
            min(2, max(0, len(students) - len(primaries))),
            for_backup=True,
            exclude=set(primaries),
            strategy=strategy,
        )
        for name in primaries:
            assignments.append(
                ShiftAssignment(
                    shift_instance_id=slot["shift_instance_id"],
                    date=shift_date.isoformat(),
                    student=name,
                    time=slot["time"],
                    shift_name=slot["shift_name"],
                    start_minutes=slot["start_minutes"],
                    end_minutes=slot["end_minutes"],
                    round_label=slot["week_label"],
                )
            )
        for name in backups:
            assignments.append(
                ShiftAssignment(
                    shift_instance_id=slot["shift_instance_id"],
                    date=shift_date.isoformat(),
                    student=name,
                    time=slot["time"],
                    shift_name=slot["shift_name"],
                    start_minutes=slot["start_minutes"],
                    end_minutes=slot["end_minutes"],
                    round_label=slot["week_label"],
                    role="backup",
                    ethics_flags=["backup coverage"],
                )
            )
    assignments.sort(key=lambda item: (item.date, item.start_minutes, item.shift_name, item.role, item.student))
    return assignments


def expand_round_robin_schedule(
    students: List[Dict[str, Any]], algorithm: str, base_date: Optional[date] = None, payload: Optional[Dict[str, Any]] = None
) -> List[ShiftAssignment]:
    actual_algorithm = "circle" if algorithm == "circle" else "round_robin"
    return build_rotation_schedule(students, payload or {"mode": "round_robin", "weeks": 2}, actual_algorithm, base_date=base_date)


def generate_schedule(
    students: List[Dict[str, Any]], payload: Dict[str, Any], base_date: Optional[date] = None
) -> List[ShiftAssignment]:
    algorithm = str(payload.get("algorithm") or "constraint_shield").strip().lower()
    if algorithm in {"circle", "round_robin", "standard"}:
        normalized = "circle" if algorithm == "circle" else "round_robin"
        return build_rotation_schedule(students, payload, normalized, base_date=base_date)
    if algorithm == "priority":
        return build_custom_schedule(students, payload, base_date=base_date, strategy="priority", allow_day_flex=False)
    return build_custom_schedule(
        students,
        payload,
        base_date=base_date,
        strategy="constraint_shield",
        allow_day_flex=True,
    )


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
        "algorithm": "constraint_shield",
        "weeks": 4,
        "students": DEFAULT_STUDENTS,
        "shift_templates": DEFAULT_SHIFT_TEMPLATES,
        "schedule_config": DEFAULT_CUSTOM_CONFIG,
        "notes": [
            "Download this template, update the values, then upload it back into the Shift Planning Desk.",
            "Use mode round_robin or custom.",
            "Algorithms available: round_robin, circle, priority, constraint_shield.",
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
                "reliability": clamp_int(raw.get("reliability"), 85, 50, 100),
                "max_hours": clamp_int(raw.get("max_hours"), 12, 1, 40),
                "preferred_shift": str(raw.get("preferred_shift") or "any").strip().lower(),
                "recent_callouts": clamp_int(raw.get("recent_callouts"), 0, 0, 10),
            }
        )

    mode = str(payload.get("mode") or "round_robin").strip().lower()
    if mode not in {"round_robin", "custom"}:
        raise ValueError("Mode must be either round_robin or custom.")

    algorithm = str(payload.get("algorithm") or "constraint_shield").strip().lower()
    if algorithm not in ALGORITHM_META:
        raise ValueError("Algorithm must be one of: round_robin, circle, priority, constraint_shield.")

    normalized = {
        "schedule_name": str(payload.get("schedule_name") or "").strip(),
        "mode": mode,
        "algorithm": algorithm,
        "weeks": clamp_int(payload.get("weeks"), 4, 1, 12),
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
            template_id = clamp_int(template.get("id"), index, 1, 9999)
            normalized_templates.append(
                {
                    "id": template_id,
                    "name": str(template.get("name") or f"Shift {index}").strip(),
                    "start": str(template.get("start") or "09:00").strip(),
                    "end": str(template.get("end") or "13:00").strip(),
                    "students_needed": clamp_int(template.get("students_needed"), 1, 1, 12),
                }
            )
            config_key = f"shift_{template_id}"
            config_value = schedule_config.get(config_key) or {}
            normalized_config[config_key] = {
                "days": str(config_value.get("days") or "Mon Wed Fri").strip(),
                "count": clamp_int(config_value.get("count"), 1, 1, 7),
            }

        normalized["shift_templates"] = normalized_templates
        normalized["schedule_config"] = normalized_config

    return normalized
