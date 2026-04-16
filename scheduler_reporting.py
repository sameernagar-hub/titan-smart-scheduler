from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from scheduler_config import ETHICS_THEORIES
from scheduler_engine import algorithm_family, algorithm_label, algorithm_summary, build_callout_plan, mode_label, shift_bucket, ShiftAssignment


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


def build_stats(
    assignments: List[ShiftAssignment],
    students: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    conflicts: Optional[List[Dict[str, Any]]] = None,
    algorithm: str = "constraint_shield",
) -> Dict[str, Any]:
    conflicts = conflicts or []
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
        "algorithm": algorithm,
        "algorithm_label": algorithm_label(algorithm),
        "algorithm_family": algorithm_family(algorithm),
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
        "conflict_count": len(conflicts),
        "conflict_free_percent": round(((len(primary) - len(conflicts)) / len(primary)) * 100) if primary else 100,
        "high_risk_count": sum(1 for score in risk_scores.values() if score >= 70),
    }


def build_algorithm_insights(
    algorithm: str,
    assignments: List[ShiftAssignment],
    students: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> Dict[str, Any]:
    primary = [item for item in assignments if item.role == "primary"]
    student_map = {student["name"]: student for student in students}
    preference_matches = 0
    for item in primary:
        preferred = student_map[item.student]["preferred_shift"]
        if preferred in {"any", "", shift_bucket(item.start_minutes)}:
            preference_matches += 1
    average_risk = round(sum(stats["risk_by_student"].values()) / max(len(stats["risk_by_student"]), 1), 1)
    preference_rate = round((preference_matches / len(primary)) * 100) if primary else 100
    if algorithm == "constraint_shield":
        headline = "Most protective fit"
    elif algorithm == "priority":
        headline = "Reliability-weighted plan"
    else:
        headline = "Rotation-first coverage"
    return {
        "algorithm": algorithm,
        "label": algorithm_label(algorithm),
        "family": algorithm_family(algorithm),
        "headline": headline,
        "summary": algorithm_summary(algorithm),
        "preference_match_rate": preference_rate,
        "average_risk": average_risk,
        "warning_pressure": len(warnings),
        "conflict_pressure": len(conflicts),
        "coverage_ready_percent": stats["coverage_ready_percent"],
        "conflict_free_percent": stats["conflict_free_percent"],
    }


def build_ethics_suggestions(
    assignments: List[ShiftAssignment],
    students: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    stats: Dict[str, Any],
    ethics: Dict[str, Any],
) -> Dict[str, Any]:
    suggestions: List[Dict[str, Any]] = []
    student_map = {student["name"]: student for student in students}
    hours_by_student = stats.get("hours_by_student", {})
    risk_by_student = stats.get("risk_by_student", {})
    backup_by_student = stats.get("backup_by_student", {})
    top_risk_students = sorted(risk_by_student.items(), key=lambda item: item[1], reverse=True)
    overloaded = [
        name
        for name, hours in hours_by_student.items()
        if hours > student_map.get(name, {}).get("max_hours", 0)
    ]

    if conflicts:
        grouped_conflicts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in conflicts:
            grouped_conflicts[item["student"]].append(item)
        worst_student, student_conflicts = max(grouped_conflicts.items(), key=lambda item: len(item[1]))
        suggestions.append(
            {
                "priority": 100,
                "impact": "High",
                "title": "Move conflict-heavy assignments first",
                "reason": f"{worst_student} is carrying {len(student_conflicts)} direct academic conflict flag(s), which is the fastest pressure point to remove from the run.",
                "action": f"Reassign {worst_student}'s clashing shifts to a student with open availability, then keep {worst_student} on non-overlapping slots closer to their preferred {student_map.get(worst_student, {}).get('preferred_shift', 'available')} window.",
            }
        )

    if overloaded:
        worst_overload = max(overloaded, key=lambda name: hours_by_student[name] - student_map[name]["max_hours"])
        overflow = round(hours_by_student[worst_overload] - student_map[worst_overload]["max_hours"], 1)
        suggestions.append(
            {
                "priority": 90,
                "impact": "High",
                "title": "Reduce overload before adding coverage complexity",
                "reason": f"{worst_overload} is scheduled {overflow}h over their weekly limit, which weakens both fairness and Kantian-style student protection.",
                "action": f"Pull one primary shift from {worst_overload} and move it to a lower-load student. If the shift is hard to cover, keep {worst_overload} as backup rather than primary so coverage stays intact without overcommitting them.",
            }
        )

    fatigue_warnings = [warning for warning in warnings if warning.get("type") == "fatigue"]
    if fatigue_warnings:
        item = fatigue_warnings[0]
        suggestions.append(
            {
                "priority": 75,
                "impact": "Medium",
                "title": "Add spacing between same-day assignments",
                "reason": f"{item['student']} has compressed same-day coverage, which increases fatigue pressure and makes callout recovery less stable.",
                "action": f"Shift one of {item['student']}'s same-day assignments to another qualified student or move that shift to a different day/time block so there is at least a one-hour buffer.",
            }
        )

    low_backup_students = [name for name, count in backup_by_student.items() if count == 0]
    if stats.get("coverage_ready_percent", 0) < 100:
        backup_candidate = low_backup_students[0] if low_backup_students else (top_risk_students[-1][0] if top_risk_students else "")
        suggestions.append(
            {
                "priority": 70,
                "impact": "Medium",
                "title": "Strengthen backup depth on exposed shifts",
                "reason": f"The run is only {stats.get('coverage_ready_percent', 0)}% backup ready, so some conflicts become harder to recover from once a callout hits.",
                "action": f"Assign backup coverage to uncovered shifts using {backup_candidate or 'the lowest-risk available student'} first, especially on shifts already carrying conflict or overload pressure.",
            }
        )

    low_preference_match = ethics.get("metrics", {}).get("preference_match_rate", 100) < 70
    if low_preference_match and top_risk_students:
        lowest_risk_name = sorted(risk_by_student.items(), key=lambda item: item[1])[0][0]
        pref = student_map.get(lowest_risk_name, {}).get("preferred_shift", "preferred")
        suggestions.append(
            {
                "priority": 55,
                "impact": "Medium",
                "title": "Use preference-aligned swaps to improve morale without harming coverage",
                "reason": "Preference match is low enough that some friction can be removed without sacrificing staffing integrity.",
                "action": f"Start swaps with {lowest_risk_name}, who has one of the lightest risk profiles, and move them toward {pref} coverage while moving less flexible students away from conflicting or disliked time buckets.",
            }
        )

    if not suggestions and top_risk_students:
        lead_name, lead_risk = top_risk_students[0]
        suggestions.append(
            {
                "priority": 40,
                "impact": "Low",
                "title": "Keep the strongest structure and trim the highest-risk edge",
                "reason": f"The run is mostly stable, but {lead_name} still carries the highest composite risk score at {lead_risk}.",
                "action": f"Keep the current algorithm profile, but reduce one high-pressure assignment from {lead_name} or convert one of their primaries into backup coverage to preserve efficiency while improving resilience.",
            }
        )

    suggestions.sort(key=lambda item: (-item["priority"], item["title"]))
    ordered = suggestions[:4]
    for index, item in enumerate(ordered, start=1):
        item["rank"] = index

    return {
        "headline": "To maximize efficiency and minimize conflicts, tighten these schedule decisions next.",
        "lead_action": ordered[0]["title"] if ordered else "No immediate correction needed",
        "suggestions": ordered,
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
        {
            "title": "Feedback Lounge",
            "summary": "Capture polished feedback, feature ideas, and contribution interest in a dedicated premium space.",
            "href": "/feedback",
            "help": "Use this page to collect reactions, feature requests, and contribution interest without leaving the product experience.",
        },
    ]


def compute_history_summary(rows: List[Any]) -> Dict[str, Any]:
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


def build_service_analytics_snapshot(rows: List[Any]) -> Dict[str, Any]:
    summary = compute_history_summary(rows)
    recent = []
    algorithm_rollup: Dict[str, Dict[str, Any]] = {}
    mode_mix = defaultdict(int)
    algorithm_mix = defaultdict(int)
    for row in rows:
        row_dict = dict(row)
        row_dict["mode_label"] = mode_label(row["mode"])
        row_dict["algorithm_label"] = algorithm_label(row["algorithm"])
        row_dict["algorithm_family"] = algorithm_family(row["algorithm"])
        ethics = json.loads(row["ethics_json"] or "{}")
        row_dict["ethics_score"] = ethics.get("overall_score", 0)
        recent.append(row_dict)
        key = row["algorithm"]
        bucket = algorithm_rollup.setdefault(
            key,
            {
                "algorithm": key,
                "label": algorithm_label(key),
                "family": algorithm_family(key),
                "runs": 0,
                "coverage_total": 0,
                "fairness_total": 0,
                "conflicts_total": 0,
                "warnings_total": 0,
                "ethics_total": 0,
            },
        )
        bucket["runs"] += 1
        bucket["coverage_total"] += row["coverage_ready_percent"]
        bucket["fairness_total"] += row["fairness_spread"]
        bucket["conflicts_total"] += row["conflict_count"]
        bucket["warnings_total"] += row["warning_count"]
        bucket["ethics_total"] += ethics.get("overall_score", 0)
        mode_mix[mode_label(row["mode"])] += 1
        algorithm_mix[algorithm_label(row["algorithm"])] += 1
    warning_trend = [
        {"label": row["name"], "warnings": row["warning_count"], "conflicts": row["conflict_count"]}
        for row in rows[:6]
    ][::-1]
    algorithm_performance = []
    for item in algorithm_rollup.values():
        runs = item["runs"] or 1
        algorithm_performance.append(
            {
                "label": item["label"],
                "family": item["family"],
                "runs": item["runs"],
                "avg_coverage": round(item["coverage_total"] / runs),
                "avg_fairness": round(item["fairness_total"] / runs, 1),
                "avg_conflicts": round(item["conflicts_total"] / runs, 1),
                "avg_warnings": round(item["warnings_total"] / runs, 1),
                "avg_ethics": round(item["ethics_total"] / runs),
            }
        )
    algorithm_performance.sort(key=lambda item: (-item["avg_coverage"], item["avg_conflicts"], item["label"]))
    return {
        "summary": summary,
        "recent_runs": recent[:5],
        "warning_trend": warning_trend,
        "mode_mix": [{"name": key, "value": value} for key, value in mode_mix.items()],
        "algorithm_mix": [{"name": key, "value": value} for key, value in algorithm_mix.items()],
        "algorithm_performance": algorithm_performance,
    }


def build_ethics_snapshot(rows: List[Any]) -> Dict[str, Any]:
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
