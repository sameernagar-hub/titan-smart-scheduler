from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

import scheduler_engine
from scheduler_config import ALGORITHM_META
from scheduler_engine import (
    algorithm_label,
    detect_conflicts,
    generate_schedule,
    mode_label,
    parse_students,
    serialize_assignments,
)
from scheduler_reporting import build_algorithm_insights, build_ethics_analysis, build_stats

OUTCOME_GOALS = {
    "conflict_free": {
        "label": "Conflict-Free First",
        "tagline": "Removes academic clashes and overload pressure before anything else.",
        "short_label": "Conflict-free",
    },
    "coverage_first": {
        "label": "Coverage First",
        "tagline": "Protects filled shifts and backup readiness while still respecting hard constraints.",
        "short_label": "Coverage",
    },
    "ethics_first": {
        "label": "Ethics First",
        "tagline": "Pushes the schedule toward stronger ethics alignment and lower risk signals.",
        "short_label": "Ethics",
    },
    "fairness_first": {
        "label": "Fairness First",
        "tagline": "Reduces workload spread, repeated pressure, and student imbalance.",
        "short_label": "Fairness",
    },
    "balanced": {
        "label": "Balanced Best Fit",
        "tagline": "Looks for the strongest all-around result across conflicts, coverage, fairness, and ethics.",
        "short_label": "Balanced",
    },
}


def _base_date_from_created_at(created_at: str) -> date:
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def _warning_counts(warnings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"overload": 0, "fatigue": 0, "coverage": 0}
    for item in warnings:
        kind = item.get("type")
        if kind in counts:
            counts[kind] += 1
    return counts


def _variant_algorithms(source_algorithm: str, goal: str) -> List[str]:
    priority_orders = {
        "conflict_free": ["constraint_shield", "priority", "round_robin", "circle"],
        "coverage_first": ["priority", "constraint_shield", "round_robin", "circle"],
        "ethics_first": ["constraint_shield", "priority", "circle", "round_robin"],
        "fairness_first": ["round_robin", "circle", "constraint_shield", "priority"],
        "balanced": ["constraint_shield", "priority", "round_robin", "circle"],
    }
    ordered = [item for item in priority_orders.get(goal, priority_orders["balanced"]) if item in ALGORITHM_META]
    return [item for item in ordered if item != source_algorithm]


def _score_candidate(goal: str, candidate: Dict[str, Any]) -> float:
    stats = candidate["stats"]
    ethics = candidate["ethics"]
    warnings = candidate["warnings"]
    conflicts = candidate["conflicts"]
    counts = _warning_counts(warnings)
    fairness = stats.get("fairness_spread", 0)
    coverage = stats.get("coverage_ready_percent", 0)
    ethics_score = ethics.get("overall_score", 0)
    preference_match = ethics.get("metrics", {}).get("preference_match_rate", 0)
    total_assignments = stats.get("total_assignments", 0)
    avg_risk = candidate["algorithm_insights"].get("average_risk", 0)

    if goal == "conflict_free":
        return (
            1200
            - len(conflicts) * 220
            - counts["overload"] * 80
            - counts["fatigue"] * 40
            + coverage * 2
            + ethics_score
            - fairness * 8
        )
    if goal == "coverage_first":
        return (
            400
            + coverage * 10
            + total_assignments * 6
            + ethics_score * 0.8
            - len(conflicts) * 120
            - counts["overload"] * 50
            - avg_risk * 1.2
        )
    if goal == "ethics_first":
        return (
            ethics_score * 11
            + preference_match * 3
            + coverage * 1.8
            - len(conflicts) * 130
            - counts["overload"] * 65
            - fairness * 10
        )
    if goal == "fairness_first":
        return (
            1000
            - fairness * 95
            - counts["overload"] * 70
            - len(conflicts) * 90
            + coverage * 2.4
            + preference_match * 1.8
            - avg_risk
        )
    return (
        1000
        + coverage * 3
        + ethics_score * 3
        + preference_match
        - len(conflicts) * 115
        - counts["overload"] * 65
        - counts["fatigue"] * 28
        - fairness * 20
        - avg_risk * 0.8
    )


def _candidate_narrative(goal: str, candidate: Dict[str, Any], baseline: Dict[str, Any]) -> str:
    metrics = candidate["summary"]
    delta_conflicts = baseline["conflicts"] - metrics["conflicts"]
    delta_ethics = metrics["ethics_score"] - baseline["ethics_score"]
    delta_coverage = metrics["coverage_ready_percent"] - baseline["coverage_ready_percent"]
    delta_fairness = baseline["fairness_spread"] - metrics["fairness_spread"]

    parts = []
    if delta_conflicts > 0:
        parts.append(f"removes {delta_conflicts} conflict{'s' if delta_conflicts != 1 else ''}")
    if delta_coverage > 0:
        parts.append(f"raises coverage by {delta_coverage} points")
    if delta_ethics > 0:
        parts.append(f"improves ethics by {delta_ethics}")
    if delta_fairness > 0:
        parts.append(f"tightens fairness spread by {delta_fairness}")
    if not parts:
        parts.append("offers the strongest available tradeoff for this goal")
    if len(parts) == 1:
        narrative = parts[0]
    else:
        narrative = ", ".join(parts[:-1]) + f", and {parts[-1]}"
    return f"Best when you want a plan that {narrative}."


def _candidate_title(goal: str, algorithm: str) -> str:
    prefix = OUTCOME_GOALS[goal]["short_label"]
    return f"{prefix} via {algorithm_label(algorithm)}"


def _evaluate_payload(payload: Dict[str, Any], base_date: date) -> Dict[str, Any]:
    students = parse_students(payload, base_date=base_date)
    assignments = generate_schedule(students, payload, base_date=base_date)
    conflicts = detect_conflicts(assignments, students)
    warnings = scheduler_engine.build_warnings(assignments, students)
    callout_plan = scheduler_engine.build_callout_plan(assignments)
    algorithm = str(payload.get("algorithm") or "constraint_shield").strip().lower()
    stats = build_stats(assignments, students, warnings, conflicts, algorithm)
    algorithm_insights = build_algorithm_insights(algorithm, assignments, students, warnings, conflicts, stats)
    ethics = build_ethics_analysis(assignments, students, warnings, conflicts, stats, payload)
    return {
        "payload": payload,
        "students": students,
        "assignments": assignments,
        "conflicts": conflicts,
        "warnings": warnings,
        "callout_plan": callout_plan,
        "stats": stats,
        "algorithm_insights": algorithm_insights,
        "ethics": ethics,
    }


def build_outcome_candidates(detail: Dict[str, Any], goal: str, limit: int = 3) -> List[Dict[str, Any]]:
    if goal not in OUTCOME_GOALS:
        raise ValueError("Choose a valid Outcome Builder mode.")

    payload = dict(detail["payload"])
    source_algorithm = str(payload.get("algorithm") or detail["run"].get("algorithm") or "constraint_shield").strip().lower()
    base_date = _base_date_from_created_at(detail["run"]["created_at"])
    baseline = {
        "conflicts": len(detail["conflicts"]),
        "warnings": len(detail["warnings"]),
        "coverage_ready_percent": detail["stats"].get("coverage_ready_percent", 0),
        "fairness_spread": detail["stats"].get("fairness_spread", 0),
        "ethics_score": detail["ethics"].get("overall_score", 0),
    }

    candidates = []
    for algorithm in _variant_algorithms(source_algorithm, goal):
        variant_payload = dict(payload)
        variant_payload["algorithm"] = algorithm
        outcome = _evaluate_payload(variant_payload, base_date)
        summary = {
            "conflicts": len(outcome["conflicts"]),
            "warnings": len(outcome["warnings"]),
            "coverage_ready_percent": outcome["stats"].get("coverage_ready_percent", 0),
            "conflict_free_percent": outcome["stats"].get("conflict_free_percent", 0),
            "fairness_spread": outcome["stats"].get("fairness_spread", 0),
            "ethics_score": outcome["ethics"].get("overall_score", 0),
            "preference_match_rate": outcome["ethics"].get("metrics", {}).get("preference_match_rate", 0),
            "assignments": outcome["stats"].get("total_assignments", 0),
            "backups": outcome["stats"].get("total_backup_assignments", 0),
        }
        score = _score_candidate(goal, {**outcome, "summary": summary})
        key = f"{goal}-{algorithm}"
        candidates.append(
            {
                "key": key,
                "title": _candidate_title(goal, algorithm),
                "subtitle": f"{algorithm_label(algorithm)} in {mode_label(variant_payload.get('mode', 'round_robin'))}",
                "goal": goal,
                "goal_label": OUTCOME_GOALS[goal]["label"],
                "algorithm": algorithm,
                "algorithm_label": algorithm_label(algorithm),
                "mode_label": mode_label(variant_payload.get("mode", "round_robin")),
                "score": round(score, 1),
                "summary": summary,
                "deltas": {
                    "conflicts": summary["conflicts"] - baseline["conflicts"],
                    "warnings": summary["warnings"] - baseline["warnings"],
                    "coverage_ready_percent": summary["coverage_ready_percent"] - baseline["coverage_ready_percent"],
                    "fairness_spread": summary["fairness_spread"] - baseline["fairness_spread"],
                    "ethics_score": summary["ethics_score"] - baseline["ethics_score"],
                },
                "narrative": _candidate_narrative(goal, {**outcome, "summary": summary}, baseline),
                "payload": variant_payload,
                "students": outcome["students"],
                "assignments": serialize_assignments(outcome["assignments"]),
                "conflicts": outcome["conflicts"],
                "warnings": outcome["warnings"],
                "callout_plan": outcome["callout_plan"],
                "stats": outcome["stats"],
                "algorithm_insights": outcome["algorithm_insights"],
                "ethics": outcome["ethics"],
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["summary"]["conflicts"],
            -item["summary"]["coverage_ready_percent"],
            -item["summary"]["ethics_score"],
            item["summary"]["fairness_spread"],
        )
    )
    trimmed = candidates[:limit]
    for index, item in enumerate(trimmed, start=1):
        item["rank"] = index
        item["recommended"] = index == 1
    return trimmed
