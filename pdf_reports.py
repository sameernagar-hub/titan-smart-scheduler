from __future__ import annotations

import os
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Sequence

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
FONTCONFIG_DIR = CACHE_DIR / "fontconfig"
FONTCONFIG_DIR.mkdir(exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("HOME", str(BASE_DIR))
os.environ.setdefault("USERPROFILE", str(BASE_DIR))
os.environ.setdefault("FONTCONFIG_CACHE", str(FONTCONFIG_DIR))

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from weasyprint import HTML


REPORT_OPTIONS = {
    "analytics": {
        "label": "Operations Analytics",
        "title": "Operations Analytics Report",
        "filename": "operations-analytics-report",
        "subtitle": "Operational readiness, workload distribution, alert pressure, and algorithm performance.",
    },
    "ethics": {
        "label": "Ethics Review",
        "title": "Ethics Review Report",
        "filename": "ethics-review-report",
        "subtitle": "Ethical posture, theory-by-theory scoring, and archived review evidence.",
    },
}

RENDERER_OPTIONS = {
    "reportlab": {"label": "ReportLab", "summary": "Backend-first layout with durable pagination and table handling."},
    "weasyprint": {"label": "WeasyPrint", "summary": "HTML/CSS-driven layout with stronger visual fidelity and brand styling."},
}


def _timestamp_label() -> str:
    return datetime.now(UTC).strftime("%b %d, %Y at %I:%M %p UTC")


def _report_title(report_type: str) -> str:
    return REPORT_OPTIONS[report_type]["title"]


def _styles():
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#0f2742"),
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#567086"),
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#123252"),
            spaceAfter=10,
            spaceBefore=8,
        ),
        "body": ParagraphStyle(
            "BodyCopy",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#25313d"),
            spaceAfter=8,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#6b7f91"),
            alignment=TA_LEFT,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#0f2742"),
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "SmallCopy",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            textColor=colors.HexColor("#536170"),
        ),
    }


def _metric_table(metrics: Sequence[tuple[str, str]]) -> Table:
    styles = _styles()
    cells = []
    for label, value in metrics:
        cells.append(
            [
                Paragraph(label, styles["metric_label"]),
                Paragraph(value, styles["metric_value"]),
            ]
        )
    rows = []
    for index in range(0, len(cells), 2):
        row = []
        for card in cells[index:index + 2]:
            row.append(card)
        while len(row) < 2:
            row.append(["", ""])
        rows.append(row)

    table_data = []
    for row in rows:
        table_row = []
        for label_cell, value_cell in row:
            inner = Table([[label_cell], [value_cell]], colWidths=[2.55 * inch])
            inner.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f8fb")),
                        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d6dee7")),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ]
                )
            )
            table_row.append(inner)
        table_data.append(table_row)
    table = Table(table_data, colWidths=[2.75 * inch, 2.75 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return table


def _data_table(headers: Sequence[str], rows: Sequence[Sequence[str]], col_widths: Sequence[float] | None = None) -> Table:
    styles = _styles()
    table_rows = [[Paragraph(f"<b>{header}</b>", styles["small"]) for header in headers]]
    for row in rows:
        table_rows.append([Paragraph(str(cell), styles["small"]) for cell in row])
    table = Table(table_rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f2742")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#d6dee7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _draw_report_header(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0f2742"))
    canvas.rect(0, 736, letter[0], 56, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(44, 764, getattr(doc, "report_title", "Titan Smart Scheduler Report"))
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#dbe7f2"))
    canvas.drawString(44, 748, getattr(doc, "report_subtitle", ""))
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(44, 24, "Titan Smart Scheduler")
    canvas.drawRightString(letter[0] - 44, 24, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _render_reportlab_pdf(report_type: str, report_data: Dict[str, Any]) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=44,
        rightMargin=44,
        topMargin=82,
        bottomMargin=40,
    )
    doc.report_title = report_data["title"]
    doc.report_subtitle = f"{report_data['subtitle']} Prepared {_timestamp_label()}."
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_draw_report_header)])

    story: List[Any] = [
        Paragraph(report_data["title"], styles["title"]),
        Paragraph(f"{report_data['subtitle']} Prepared {_timestamp_label()}.", styles["subtitle"]),
        Paragraph("Executive Summary", styles["section"]),
        Paragraph(report_data["overview"], styles["body"]),
        Spacer(1, 6),
        _metric_table(report_data["metrics"]),
        Spacer(1, 12),
    ]

    for section in report_data["sections"]:
        story.append(Paragraph(section["title"], styles["section"]))
        if section.get("body"):
            story.append(Paragraph(section["body"], styles["body"]))
        if section["type"] == "table":
            story.append(_data_table(section["headers"], section["rows"], section.get("col_widths")))
        else:
            story.append(_data_table(["Item", "Value"], section["rows"], [3.5 * inch, 2.2 * inch]))
        story.append(Spacer(1, 12))

    if report_type == "ethics":
        for run in report_data.get("run_details", []):
            story.append(PageBreak())
            story.append(Paragraph(f"Run Detail: {run['name']}", styles["section"]))
            story.append(Paragraph(run["summary"], styles["body"]))
            story.append(_data_table(["Theory", "Score", "Status", "Interpretation"], run["rows"], [1.6 * inch, 0.55 * inch, 1.3 * inch, 2.6 * inch]))
            story.append(Spacer(1, 12))

    doc.build(story)
    return buffer.getvalue()


def _html_metric_cards(metrics: Sequence[tuple[str, str]]) -> str:
    return "".join(
        f"""
        <article class="metric-card">
          <span>{label}</span>
          <strong>{value}</strong>
        </article>
        """
        for label, value in metrics
    )


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    header_html = "".join(f"<th>{header}</th>" for header in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _render_weasyprint_pdf(report_type: str, report_data: Dict[str, Any]) -> bytes:
    sections_html = []
    for section in report_data["sections"]:
        headers = section["headers"] if section["type"] == "table" else ["Item", "Value"]
        table_rows = section["rows"]
        sections_html.append(
            f"""
            <section class="report-section">
              <h2>{section['title']}</h2>
              <p>{section.get('body', '')}</p>
              {_html_table(headers, table_rows)}
            </section>
            """
        )

    detail_html = ""
    if report_type == "ethics":
        detail_html = "".join(
            f"""
            <section class="report-section run-detail">
              <h2>Run Detail: {run['name']}</h2>
              <p>{run['summary']}</p>
              {_html_table(['Theory', 'Score', 'Status', 'Interpretation'], run['rows'])}
            </section>
            """
            for run in report_data.get("run_details", [])
        )

    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        @page {{
          size: letter;
          margin: 18mm;
          @top-center {{
            content: "{report_data['title']}";
            color: #0f2742;
            font-size: 10pt;
            font-weight: 700;
          }}
          @bottom-right {{
            content: "Page " counter(page);
            color: #64748b;
            font-size: 9pt;
          }}
        }}
        body {{
          font-family: "Segoe UI", Arial, sans-serif;
          color: #22303a;
          font-size: 10.5pt;
          line-height: 1.5;
        }}
        .hero {{
          background: linear-gradient(135deg, #0f2742, #1a5a63);
          color: white;
          border-radius: 18px;
          padding: 26px 28px;
          margin-bottom: 18px;
        }}
        .hero h1 {{
          margin: 0 0 8px;
          font-size: 24pt;
        }}
        .hero p {{
          margin: 0;
          color: #dce8f3;
        }}
        .metrics {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin: 18px 0 8px;
        }}
        .metric-card {{
          border: 1px solid #d7e1ea;
          background: #f6f8fb;
          border-radius: 14px;
          padding: 14px 16px;
        }}
        .metric-card span {{
          display: block;
          font-size: 8.5pt;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #64748b;
          margin-bottom: 8px;
        }}
        .metric-card strong {{
          font-size: 16pt;
          color: #0f2742;
        }}
        h2 {{
          color: #0f2742;
          font-size: 14pt;
          margin: 22px 0 8px;
        }}
        .report-section {{
          break-inside: avoid;
          margin-bottom: 18px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin-top: 10px;
          font-size: 9pt;
        }}
        thead th {{
          background: #0f2742;
          color: white;
          padding: 8px;
          text-align: left;
        }}
        tbody td {{
          border: 1px solid #d7e1ea;
          padding: 7px 8px;
          vertical-align: top;
        }}
        tbody tr:nth-child(even) {{
          background: #f6f8fb;
        }}
        .overview {{
          margin: 10px 0 0;
        }}
        .run-detail {{
          break-before: page;
        }}
      </style>
    </head>
    <body>
      <section class="hero">
        <h1>{report_data['title']}</h1>
        <p>{report_data['subtitle']}</p>
        <p class="overview">Prepared {_timestamp_label()}</p>
      </section>
      <section class="report-section">
        <h2>Executive Summary</h2>
        <p>{report_data['overview']}</p>
      </section>
      <section class="metrics">
        {_html_metric_cards(report_data['metrics'])}
      </section>
      {''.join(sections_html)}
      {detail_html}
    </body>
    </html>
    """
    return HTML(string=html).write_pdf()


def build_analytics_report_data(analytics: Dict[str, Any]) -> Dict[str, Any]:
    summary = analytics["summary"]
    performance = analytics["algorithm_performance"]
    strongest = performance[0]["label"] if performance else "No algorithm data"
    return {
        "title": REPORT_OPTIONS["analytics"]["title"],
        "subtitle": REPORT_OPTIONS["analytics"]["subtitle"],
        "overview": (
            "This report consolidates the operational dashboard into a portable briefing. "
            f"It captures staffing volume, backup readiness, alert pressure, algorithm usage, and the strongest current planning strategy: {strongest}."
        ),
        "metrics": [
            ("Plans Logged", str(summary["total_runs"])),
            ("Primary Shifts", str(summary["primary_assignments"])),
            ("Backup Slots", str(summary["backups"])),
            ("Average Readiness", f"{summary['avg_coverage']}%"),
        ],
        "sections": [
            {
                "title": "Alert Trend",
                "body": "Recent plans showing warning and conflict volume across the scheduling archive.",
                "type": "table",
                "headers": ["Plan", "Warnings", "Conflicts"],
                "rows": [[item["label"], str(item["warnings"]), str(item["conflicts"])] for item in analytics["warning_trend"]],
            },
            {
                "title": "Algorithm Mix",
                "body": "Distribution of scheduling strategies across all saved plans.",
                "type": "pairs",
                "headers": [],
                "rows": [[item["name"], f"{item['value']} plan{'s' if item['value'] != 1 else ''}"] for item in analytics["algorithm_mix"]],
            },
            {
                "title": "Algorithm Performance",
                "body": "Coverage, fairness, conflicts, warnings, and ethics rolled up by scheduling strategy.",
                "type": "table",
                "headers": ["Algorithm", "Family", "Runs", "Coverage", "Fairness", "Conflicts", "Warnings", "Ethics"],
                "rows": [
                    [
                        item["label"],
                        item["family"],
                        str(item["runs"]),
                        f"{item['avg_coverage']}%",
                        str(item["avg_fairness"]),
                        str(item["avg_conflicts"]),
                        str(item["avg_warnings"]),
                        str(item["avg_ethics"]),
                    ]
                    for item in analytics["algorithm_performance"]
                ],
                "col_widths": [1.3 * inch, 0.95 * inch, 0.45 * inch, 0.65 * inch, 0.6 * inch, 0.6 * inch, 0.65 * inch, 0.5 * inch],
            },
            {
                "title": "Recent Plans",
                "body": "Most recent plans with their operational footprint and readiness metrics.",
                "type": "table",
                "headers": ["Run", "Logged", "Algorithm", "Assignments", "Backups", "Warnings", "Coverage"],
                "rows": [
                    [
                        run["name"],
                        run.get("created_at_display", run["created_at"]),
                        run["algorithm_label"],
                        str(run["assignment_count"]),
                        str(run["backup_count"]),
                        str(run["warning_count"]),
                        f"{run['coverage_ready_percent']}%",
                    ]
                    for run in analytics["recent_runs"]
                ],
                "col_widths": [1.5 * inch, 1.2 * inch, 0.95 * inch, 0.55 * inch, 0.5 * inch, 0.5 * inch, 0.55 * inch],
            },
        ],
    }


def build_ethics_report_data(ethics: Dict[str, Any], theories: Sequence[str]) -> Dict[str, Any]:
    theory_summary = ethics["theory_summary"]
    highest = max(theory_summary, key=lambda item: item["average_score"], default={"theory": "None", "average_score": 0})
    lowest = min(theory_summary, key=lambda item: item["average_score"], default={"theory": "None", "average_score": 0})
    return {
        "title": REPORT_OPTIONS["ethics"]["title"],
        "subtitle": REPORT_OPTIONS["ethics"]["subtitle"],
        "overview": (
            "This report captures the ethics review posture of the scheduling archive. "
            f"It highlights the strongest theory trend ({highest['theory']} at {highest['average_score']}) and the most exposed area ({lowest['theory']} at {lowest['average_score']})."
        ),
        "metrics": [
            ("Average Ethics Score", str(ethics["overall_average"])),
            ("Overall Rating", ethics["overall_status"]),
            ("Plans Reviewed", str(len(ethics["runs"]))),
            ("Theories Tracked", str(len(theories))),
        ],
        "sections": [
            {
                "title": "Theory Snapshot",
                "body": "Average alignment score across the archive for each ethics framework.",
                "type": "table",
                "headers": ["Theory", "Average Score", "Status"],
                "rows": [[item["theory"], str(item["average_score"]), item["status"]] for item in ethics["theory_summary"]],
            },
            {
                "title": "Interpretation Guide",
                "body": "These ratings are advisory rather than absolute and should be read alongside the archived operational record.",
                "type": "pairs",
                "headers": [],
                "rows": [
                    ["Strong alignment", "Metrics and constraints strongly support that theory."],
                    ["Conditional alignment", "The case is generally supportable but still needs context or review."],
                    ["Needs review", "Conflicts, overload, weak coverage, or missing context weaken the ethical defense."],
                ],
            },
            {
                "title": "Reviewed Plans",
                "body": "Every archived plan retains an ethics score and status that can be revisited later.",
                "type": "table",
                "headers": ["Plan", "Logged", "Score", "Status"],
                "rows": [
                    [run["name"], run.get("created_at_display", run["created_at"]), str(run["overall_score"]), run["overall_status"]]
                    for run in ethics["runs"]
                ],
                "col_widths": [2.0 * inch, 1.45 * inch, 0.55 * inch, 2.0 * inch],
            },
        ],
        "run_details": [
            {
                "name": run["name"],
                "summary": f"Stored {run.get('created_at_display', run['created_at'])}. Overall score {run['overall_score']} with status {run['overall_status']}.",
                "rows": [[item["theory"], str(item["score"]), item["status"], item["summary"]] for item in run.get("theories", [])],
            }
            for run in ethics["runs"]
        ],
    }


def build_pdf_bytes(report_type: str, renderer: str, report_data: Dict[str, Any]) -> bytes:
    if renderer == "reportlab":
        return _render_reportlab_pdf(report_type, report_data)
    if renderer == "weasyprint":
        return _render_weasyprint_pdf(report_type, report_data)
    raise ValueError(f"Unsupported renderer: {renderer}")
