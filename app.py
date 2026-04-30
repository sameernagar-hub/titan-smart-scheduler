from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, date, datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from flask import Flask, abort, g, jsonify, make_response, redirect, render_template, request, url_for

from outcome_builder import OUTCOME_GOALS, build_outcome_candidates
from pdf_reports import (
    RENDERER_OPTIONS,
    REPORT_OPTIONS,
    build_analytics_report_data,
    build_ethics_report_data,
    build_pdf_bytes,
)
import scheduler_engine
from scheduler_config import (
    ALGORITHM_META,
    AUTHOR_PROFILE,
    DATABASE_PATH,
    DEFAULT_CUSTOM_CONFIG,
    DEFAULT_SHIFT_TEMPLATES,
    DEFAULT_STUDENTS,
    ETHICS_THEORIES,
    FAQ_ITEMS,
    FOOTER_LINKS,
    PRELOADED_SCENARIOS,
    PROJECT_REPO_URL,
)
from scheduler_engine import (
    ShiftAssignment,
    algorithm_label,
    build_input_template,
    build_text_input_template,
    clamp_int,
    detect_conflicts,
    generate_schedule,
    mode_label,
    normalize_import_payload,
    parse_text_input_template,
    parse_students,
    serialize_assignments,
    serialize_students,
)
from scheduler_reporting import (
    build_algorithm_insights,
    build_ethics_analysis,
    build_ethics_suggestions,
    build_ethics_snapshot,
    build_service_analytics_snapshot,
    build_stats,
    compute_history_summary,
    summarize_services,
)

app = Flask(__name__)


def format_timestamp(value: str) -> str:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    return parsed.strftime("%b %d, %Y at %I:%M %p")


def canonical_algorithm(value: str) -> str:
    return "round_robin" if value == "standard" else value


def cleanup_transient_runs() -> None:
    db = get_db()
    transient_names = {
        "Ethics Suggestion Verification",
        "Polish Verification",
        "Refactor Verification",
        "Priority Suggestion Verification",
        "Smoke Test Plan",
        "Verification",
    }
    rows = db.execute(
        "SELECT id FROM schedule_runs WHERE name IN ({})".format(",".join("?" for _ in transient_names)),
        tuple(sorted(transient_names)),
    ).fetchall()
    if not rows:
        return
    run_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" for _ in run_ids)
    db.execute(f"DELETE FROM assignments WHERE run_id IN ({placeholders})", run_ids)
    db.execute(f"DELETE FROM schedule_runs WHERE id IN ({placeholders})", run_ids)
    db.commit()


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


def fetch_schedule_run_rows() -> List[sqlite3.Row]:
    return get_db().execute(
        """
        SELECT id, name, created_at, mode, algorithm, assignment_count, backup_count, warning_count,
               conflict_count, fairness_spread, coverage_ready_percent, scheduled_days, ethics_json,
               source_run_id, outcome_goal, outcome_label, is_final
        FROM schedule_runs
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()


def service_analytics_snapshot() -> Dict[str, Any]:
    return build_service_analytics_snapshot(fetch_schedule_run_rows())


def ethics_snapshot() -> Dict[str, Any]:
    rows = get_db().execute(
        """
        SELECT id, name, created_at, ethics_json
        FROM schedule_runs
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return build_ethics_snapshot(rows)


def report_data_for(report_type: str) -> Dict[str, Any]:
    if report_type == "analytics":
        return build_analytics_report_data(service_analytics_snapshot())
    if report_type == "ethics":
        return build_ethics_report_data(ethics_snapshot(), ETHICS_THEORIES)
    raise ValueError(f"Unsupported report type: {report_type}")


def feedback_snapshot(limit: int = 5) -> List[Dict[str, Any]]:
    rows = get_db().execute(
        """
        SELECT id, name, role, rating, message, created_at
        FROM feedback_entries
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def save_feedback_entry(name: str, role: str, rating: int, message: str) -> None:
    get_db().execute(
        """
        INSERT INTO feedback_entries (name, role, rating, message, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, role, rating, message, datetime.now(UTC).isoformat(timespec="seconds")),
    )
    get_db().commit()


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

    run_dict = dict(run)
    students = json.loads(run["students_json"])
    payload = json.loads(run["payload_json"])
    warnings = json.loads(run["warnings_json"])
    conflicts = json.loads(run["conflicts_json"])
    stats = json.loads(run["stats_json"])
    algorithm = canonical_algorithm(run_dict.get("algorithm") or "round_robin")
    stats.setdefault("algorithm", algorithm)
    stats.setdefault("algorithm_label", algorithm_label(algorithm))
    stats.setdefault("conflict_count", len(conflicts))
    stats.setdefault(
        "conflict_free_percent",
        round(((stats.get("total_assignments", 0) - len(conflicts)) / stats.get("total_assignments", 1)) * 100)
        if stats.get("total_assignments")
        else 100,
    )
    run_dict["mode_label"] = mode_label(run_dict["mode"])
    run_dict["algorithm_label"] = algorithm_label(algorithm)
    run_dict["created_at_display"] = format_timestamp(run_dict["created_at"])
    typed_assignments = [
        ShiftAssignment(
            shift_instance_id=item["shift_instance_id"],
            date=item["date"],
            student=item["student"],
            time=item["time"],
            shift_name=item["shift_name"],
            start_minutes=item["start_minutes"],
            end_minutes=item["end_minutes"],
            round_label=item["round_label"],
            conflict=bool(item["conflict"]),
            conflict_reason=item["conflict_reason"],
            role=item["role"],
            ethics_flags=item["ethics_flags"],
        )
        for item in assignments
    ]
    ethics = json.loads(run["ethics_json"] or "{}")
    return {
        "run": run_dict,
        "payload": payload,
        "students": students,
        "assignments": assignments,
        "warnings": warnings,
        "conflicts": conflicts,
        "callout_plan": json.loads(run["callout_plan_json"]),
        "stats": stats,
        "algorithm_insights": build_algorithm_insights(algorithm, typed_assignments, students, warnings, conflicts, stats),
        "ethics": ethics,
        "ethics_suggestions": build_ethics_suggestions(typed_assignments, students, warnings, conflicts, stats, ethics),
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
    source_run_id: Optional[int] = None,
    outcome_goal: Optional[str] = None,
    outcome_label: Optional[str] = None,
    is_final: bool = False,
) -> int:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO schedule_runs (
            name, created_at, mode, algorithm, weeks, students_json, payload_json,
            stats_json, warnings_json, conflicts_json, callout_plan_json, ethics_json,
            assignment_count, backup_count, warning_count, conflict_count,
            fairness_spread, coverage_ready_percent, scheduled_days,
            source_run_id, outcome_goal, outcome_label, is_final
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            created_at or datetime.now(UTC).isoformat(timespec="seconds"),
            payload.get("mode", "round_robin"),
            payload.get("algorithm", "constraint_shield"),
            clamp_int(payload.get("weeks"), 4, 1, 12),
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
            source_run_id,
            outcome_goal,
            outcome_label,
            int(is_final),
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
    for scenario in PRELOADED_SCENARIOS:
        if db.execute("SELECT 1 FROM schedule_runs WHERE name = ?", (scenario["name"],)).fetchone():
            continue
        base_date = datetime.strptime(scenario["base_date"], "%Y-%m-%d").date()
        payload = {k: v for k, v in scenario.items() if k not in {"name", "base_date"}}
        students = parse_students(payload, base_date=base_date)
        assignments = generate_schedule(students, payload, base_date=base_date)
        conflicts = detect_conflicts(assignments, students)
        warnings = scheduler_engine.build_warnings(assignments, students)
        callout_plan = scheduler_engine.build_callout_plan(assignments)
        stats = build_stats(assignments, students, warnings, conflicts, payload.get("algorithm", "constraint_shield"))
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
        assignments = [
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
            for item in assignment_rows
        ]
        students = json.loads(row["students_json"])
        payload = json.loads(row["payload_json"])
        stats = json.loads(row["stats_json"])
        warnings = json.loads(row["warnings_json"])
        conflicts = json.loads(row["conflicts_json"])
        ethics = build_ethics_analysis(assignments, students, warnings, conflicts, stats, payload)
        db.execute("UPDATE schedule_runs SET ethics_json = ? WHERE id = ?", (json.dumps(ethics), row["id"]))
    db.commit()


def unique_recent_runs(runs: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    suppressed_names = {
        "custom service run",
        "test",
        "verification",
    }
    seen_names = set()
    items = []
    for allow_suppressed in (False, True):
        for run in runs:
            name_key = run["name"].strip().lower()
            if not allow_suppressed and name_key in suppressed_names:
                continue
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            items.append(run)
            if len(items) >= limit:
                return items
    return items


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
                ,
                source_run_id INTEGER,
                outcome_goal TEXT,
                outcome_label TEXT,
                is_final INTEGER NOT NULL DEFAULT 0
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
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                rating INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        db.commit()
        columns = {row[1] for row in db.execute("PRAGMA table_info(schedule_runs)").fetchall()}
        if "ethics_json" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN ethics_json TEXT NOT NULL DEFAULT '{}'")
            db.commit()
        if "source_run_id" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN source_run_id INTEGER")
            db.commit()
        if "outcome_goal" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN outcome_goal TEXT")
            db.commit()
        if "outcome_label" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN outcome_label TEXT")
            db.commit()
        if "is_final" not in columns:
            db.execute("ALTER TABLE schedule_runs ADD COLUMN is_final INTEGER NOT NULL DEFAULT 0")
            db.commit()

    with app.app_context():
        cleanup_transient_runs()
        seed_history_data()
        backfill_ethics_data()


@app.context_processor
def inject_global_template_data() -> Dict[str, Any]:
    return {
        "services_nav": summarize_services(),
        "footer_links": FOOTER_LINKS,
        "faq_items": FAQ_ITEMS,
        "project_repo_url": PROJECT_REPO_URL,
        "author_profile": AUTHOR_PROFILE,
    }


@app.route("/")
def home() -> str:
    analytics = service_analytics_snapshot()
    highlighted_runs = unique_recent_runs(analytics["recent_runs"])
    carousel_items = [
        {
            "eyebrow": "Recent Activity",
            "title": run["name"],
            "description": f"{run['assignment_count']} primary assignments, {run['backup_count']} backups, {run['coverage_ready_percent']}% coverage readiness using {run['algorithm_label']}. Logged {run['created_at_display']}.",
            "href": f"/history/{run['id']}",
            "cta": "Open run",
        }
        for run in highlighted_runs
    ] or [
        {
            "eyebrow": "Live Workspace",
            "title": "Weekly coverage planning",
            "description": "Build a staffing plan, review its impact, and keep a record that leaders can revisit later.",
            "href": "/scheduler",
            "cta": "Plan shifts",
        }
    ]
    return render_template(
        "home.html",
        page_name="home",
        analytics=analytics,
        service_cards=summarize_services(),
        featured_run=highlighted_runs[0] if highlighted_runs else None,
        algorithm_spotlight=analytics["algorithm_performance"][0] if analytics["algorithm_performance"] else None,
        carousel_items=carousel_items,
    )


@app.route("/services")
def services_page() -> str:
    return render_template("services.html", page_name="services", service_cards=summarize_services(), analytics=service_analytics_snapshot())


@app.route("/reports")
def reports_page() -> str:
    report_type = (request.args.get("type") or "analytics").strip().lower()
    if report_type not in REPORT_OPTIONS:
        report_type = "analytics"
    return render_template(
        "reports.html",
        page_name="reports",
        report_type=report_type,
        report_options=REPORT_OPTIONS,
        renderer_options=RENDERER_OPTIONS,
    )


@app.route("/scheduler")
def scheduler_page() -> str:
    return render_template(
        "scheduler.html",
        page_name="scheduler",
        default_templates=DEFAULT_SHIFT_TEMPLATES,
        default_config=DEFAULT_CUSTOM_CONFIG,
        default_students=DEFAULT_STUDENTS,
        algorithms=ALGORITHM_META,
    )


@app.route("/analytics")
def analytics_page() -> str:
    return render_template("analytics.html", page_name="analytics", analytics=service_analytics_snapshot())


@app.route("/ethics")
def ethics_page() -> str:
    return render_template("ethics.html", page_name="ethics", ethics=ethics_snapshot(), theories=ETHICS_THEORIES)


@app.route("/analytics/report.pdf")
def analytics_report_pdf():
    pdf_bytes = build_pdf_bytes("analytics", "reportlab", report_data_for("analytics"))
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=operations-analytics-report.pdf"
    return response


@app.route("/ethics/report.pdf")
def ethics_report_pdf():
    pdf_bytes = build_pdf_bytes("ethics", "reportlab", report_data_for("ethics"))
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=ethics-review-report.pdf"
    return response


@app.route("/reports/pdf/<report_type>/<renderer>")
def report_pdf(report_type: str, renderer: str):
    normalized_type = report_type.strip().lower()
    normalized_renderer = renderer.strip().lower()
    if normalized_type not in REPORT_OPTIONS or normalized_renderer not in RENDERER_OPTIONS:
        abort(404)
    disposition = "inline" if (request.args.get("disposition") or "attachment").strip().lower() == "inline" else "attachment"
    pdf_bytes = build_pdf_bytes(normalized_type, normalized_renderer, report_data_for(normalized_type))
    filename = f"{REPORT_OPTIONS[normalized_type]['filename']}-{normalized_renderer}.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"{disposition}; filename={filename}"
    return response


@app.route("/history")
def history_page() -> str:
    rows = fetch_schedule_run_rows()
    history_runs = []
    for row in rows:
        item = dict(row)
        ethics = json.loads(item["ethics_json"] or "{}")
        item["ethics_overall_status"] = ethics.get("overall_status", "Not rated")
        item["ethics_overall_score"] = ethics.get("overall_score", 0)
        item["mode_label"] = mode_label(item["mode"])
        item["algorithm_label"] = algorithm_label(canonical_algorithm(item["algorithm"]))
        item["created_at_display"] = format_timestamp(item["created_at"])
        item["outcome_goal_label"] = OUTCOME_GOALS.get(item.get("outcome_goal") or "", {}).get("label", "")
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
    source_run = None
    if detail["run"].get("source_run_id"):
        source_run = get_db().execute("SELECT id, name FROM schedule_runs WHERE id = ?", (detail["run"]["source_run_id"],)).fetchone()
    return render_template(
        "history_detail.html",
        page_name="history",
        detail=detail,
        outcome_goals=OUTCOME_GOALS,
        source_run=dict(source_run) if source_run else None,
    )


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
        "algorithm_insights": detail["algorithm_insights"],
        "ethics": detail["ethics"],
        "ethics_suggestions": detail["ethics_suggestions"],
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


@app.route("/history/<int:run_id>/outcomes", methods=["POST"])
def history_outcomes(run_id: int):
    detail = get_run_detail(run_id)
    if detail is None:
        abort(404)
    payload = request.get_json(force=True)
    goal = str(payload.get("goal") or "").strip().lower()
    try:
        candidates = build_outcome_candidates(detail, goal)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    preview_candidates = [
        {
            "key": item["key"],
            "title": item["title"],
            "subtitle": item["subtitle"],
            "goal": item["goal"],
            "goal_label": item["goal_label"],
            "algorithm": item["algorithm"],
            "algorithm_label": item["algorithm_label"],
            "mode_label": item["mode_label"],
            "score": item["score"],
            "summary": item["summary"],
            "deltas": item["deltas"],
            "narrative": item["narrative"],
            "rank": item["rank"],
            "recommended": item["recommended"],
        }
        for item in candidates
    ]
    return jsonify(
        {
            "goal": goal,
            "goal_label": OUTCOME_GOALS[goal]["label"],
            "baseline": {
                "conflicts": len(detail["conflicts"]),
                "warnings": len(detail["warnings"]),
                "coverage_ready_percent": detail["stats"].get("coverage_ready_percent", 0),
                "fairness_spread": detail["stats"].get("fairness_spread", 0),
                "ethics_score": detail["ethics"].get("overall_score", 0),
            },
            "candidates": preview_candidates,
        }
    )


@app.route("/history/<int:run_id>/outcomes/<candidate_key>/save", methods=["POST"])
def save_history_outcome(run_id: int, candidate_key: str):
    detail = get_run_detail(run_id)
    if detail is None:
        abort(404)
    payload = request.get_json(force=True)
    goal = str(payload.get("goal") or "").strip().lower()
    finalize = bool(payload.get("finalize"))
    try:
        candidates = build_outcome_candidates(detail, goal)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    candidate = next((item for item in candidates if item["key"] == candidate_key), None)
    if candidate is None:
        return jsonify({"error": "That outcome candidate is no longer available. Generate outcomes again."}), 404

    schedule_name = (
        f"{detail['run']['name']} - Final Outcome"
        if finalize
        else f"{detail['run']['name']} - {candidate['goal_label']} Revision"
    )
    run_id_new = save_schedule_run(
        schedule_name,
        candidate["payload"],
        candidate["students"],
        [
            ShiftAssignment(
                shift_instance_id=item["shift_instance_id"],
                date=item["date"],
                student=item["student"],
                time=item["time"],
                shift_name=item["shift_name"],
                start_minutes=item["start_minutes"],
                end_minutes=item["end_minutes"],
                round_label=item.get("round_label"),
                conflict=bool(item.get("conflict")),
                conflict_reason=item.get("conflict_reason"),
                role=item.get("role", "primary"),
                ethics_flags=item.get("ethics_flags") or [],
            )
            for item in candidate["assignments"]
        ],
        candidate["conflicts"],
        candidate["warnings"],
        candidate["stats"],
        candidate["callout_plan"],
        candidate["ethics"],
        source_run_id=run_id,
        outcome_goal=goal,
        outcome_label=candidate["title"],
        is_final=finalize,
    )
    return jsonify({"run_id": run_id_new, "history_url": f"/history/{run_id_new}"})


@app.route("/faq")
def faq_page() -> str:
    return render_template("faq.html", page_name="faq", faq_items=FAQ_ITEMS)


@app.route("/feedback", methods=["GET", "POST"])
def feedback_page() -> str:
    if request.method == "POST":
        name = (request.form.get("name") or "").strip() or "Anonymous visitor"
        role = (request.form.get("role") or "").strip() or "Scheduler reviewer"
        rating = clamp_int(request.form.get("rating"), 5, 1, 5)
        message = (request.form.get("message") or "").strip()
        if not message:
            return render_template(
                "feedback.html",
                page_name="feedback",
                feedback_items=feedback_snapshot(),
                success_message="",
                error_message="Share at least a short note so the feedback board stays useful.",
            )
        save_feedback_entry(name, role, rating, message)
        return redirect(url_for("feedback_page", submitted="1"))

    success_message = "Thanks for helping shape the product." if request.args.get("submitted") == "1" else ""
    return render_template(
        "feedback.html",
        page_name="feedback",
        feedback_items=feedback_snapshot(),
        success_message=success_message,
        error_message="",
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    payload = request.get_json(force=True)
    students = parse_students(payload, base_date=date.today())
    if len(students) < 2:
        return jsonify({"error": "Add at least 2 students to generate a schedule."}), 400

    algorithm = str(payload.get("algorithm") or "constraint_shield").strip().lower()
    if algorithm not in ALGORITHM_META:
        return jsonify({"error": "Choose a valid algorithm before generating a plan."}), 400
    schedule_name = (payload.get("schedule_name") or "").strip() or f"{algorithm_label(algorithm)} Coverage Run"
    try:
        assignments = generate_schedule(students, payload, base_date=date.today())
        conflicts = detect_conflicts(assignments, students)
        warnings = scheduler_engine.build_warnings(assignments, students)
        callout_plan = scheduler_engine.build_callout_plan(assignments)
        stats = build_stats(assignments, students, warnings, conflicts, algorithm)
        algorithm_insights = build_algorithm_insights(algorithm, assignments, students, warnings, conflicts, stats)
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
            "algorithm_insights": algorithm_insights,
            "ethics": ethics,
            "history_url": f"/history/{run_id}",
            "export_json_url": f"/history/{run_id}/download/json",
            "export_csv_url": f"/history/{run_id}/download/csv",
        }
    )


@app.route("/api/input-template")
def api_input_template():
    response = make_response(build_text_input_template())
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=planner-template.txt"
    return response


@app.route("/api/import-template", methods=["POST"])
def api_import_template():
    try:
        if request.is_json:
            payload = request.get_json(force=True)
        else:
            payload = parse_text_input_template(request.get_data(as_text=True))
        normalized = normalize_import_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"payload": normalized})


init_db()


if __name__ == "__main__":
    app.run(debug=True)
