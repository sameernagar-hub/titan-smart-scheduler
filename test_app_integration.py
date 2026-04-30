import json
import unittest
from html import unescape

import app
from scheduler_config import FAQ_ITEMS
from scheduler_engine import build_input_template, build_text_input_template


class AppIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def _cleanup_run(self, run_id):
        with app.app.app_context():
            db = app.get_db()
            db.execute("DELETE FROM assignments WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM schedule_runs WHERE id = ?", (run_id,))
            db.commit()

    def test_reports_page_falls_back_for_unknown_type(self):
        response = self.client.get("/reports?type=unknown")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Operations Analytics", response.data)

    def test_invalid_report_route_returns_404(self):
        response = self.client.get("/reports/pdf/unknown/reportlab")
        self.assertEqual(response.status_code, 404)

    def test_faq_page_renders_all_configured_items(self):
        response = self.client.get("/faq")
        self.assertEqual(response.status_code, 200)
        page = unescape(response.get_data(as_text=True))
        for item in FAQ_ITEMS:
            self.assertIn(item["question"], page)
            self.assertIn(item["answer"], page)

    def test_feedback_submission_and_defaults_work(self):
        response = self.client.post(
            "/feedback",
            data={
                "name": "",
                "role": "",
                "rating": "4",
                "message": "The workflow feels much cleaner now.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Thanks for helping shape the product.", page)
        self.assertIn("Anonymous visitor", page)
        self.assertIn("Scheduler reviewer", page)
        self.assertIn("The workflow feels much cleaner now.", page)

        with app.app.app_context():
            db = app.get_db()
            db.execute(
                "DELETE FROM feedback_entries WHERE message = ?",
                ("The workflow feels much cleaner now.",),
            )
            db.commit()

    def test_feedback_requires_message(self):
        response = self.client.post(
            "/feedback",
            data={"name": "QA", "role": "Tester", "rating": "5", "message": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Share at least a short note", response.data)

    def test_input_template_endpoint_matches_builder(self):
        response = self.client.get("/api/input-template")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("planner-template.txt", response.headers["Content-Disposition"])
        self.assertEqual(response.get_data(as_text=True), build_text_input_template())

    def test_import_template_round_trip(self):
        template = build_text_input_template()
        template = template.replace("Plan name: Bookstore floor coverage week 4", "Plan name: Imported Plan")
        template = template.replace("Weeks: 4", "Weeks: 3")
        response = self.client.post("/api/import-template", data=template, content_type="text/plain")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["payload"]
        self.assertEqual(payload["schedule_name"], "Imported Plan")
        self.assertEqual(payload["weeks"], 3)
        self.assertGreaterEqual(len(payload["students"]), 2)

    def test_import_template_rejects_invalid_payload(self):
        response = self.client.post("/api/import-template", json={"students": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_generate_rejects_invalid_algorithm(self):
        payload = build_input_template()
        payload["algorithm"] = "not-real"
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose a valid algorithm", response.get_data(as_text=True))

    def test_generate_rejects_too_few_students(self):
        payload = build_input_template()
        payload["students"] = [payload["students"][0]]
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Add at least 2 students", response.get_data(as_text=True))

    def test_history_downloads_404_for_missing_run(self):
        self.assertEqual(self.client.get("/history/999999").status_code, 404)
        self.assertEqual(self.client.get("/history/999999/download/json").status_code, 404)
        self.assertEqual(self.client.get("/history/999999/download/csv").status_code, 404)

    def test_generated_run_json_contains_expected_sections(self):
        payload = build_input_template()
        payload["schedule_name"] = "Integration Verification Run"
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        run_id = response.get_json()["run_id"]

        try:
            export = self.client.get(f"/history/{run_id}/download/json")
            self.assertEqual(export.status_code, 200)
            data = json.loads(export.get_data(as_text=True))
            self.assertIn("run", data)
            self.assertIn("stats", data)
            self.assertIn("ethics", data)
            self.assertIn("assignments", data)
            self.assertEqual(data["run"]["name"], "Integration Verification Run")
        finally:
            self._cleanup_run(run_id)

    def test_outcome_builder_generates_and_saves_revision(self):
        payload = build_input_template()
        payload["schedule_name"] = "Outcome Builder Verification Run"
        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        source_run_id = response.get_json()["run_id"]
        derived_run_id = None

        try:
            outcomes = self.client.post(f"/history/{source_run_id}/outcomes", json={"goal": "balanced"})
            self.assertEqual(outcomes.status_code, 200)
            outcome_payload = outcomes.get_json()
            self.assertEqual(outcome_payload["goal"], "balanced")
            self.assertGreaterEqual(len(outcome_payload["candidates"]), 1)

            candidate_key = outcome_payload["candidates"][0]["key"]
            saved = self.client.post(
                f"/history/{source_run_id}/outcomes/{candidate_key}/save",
                json={"goal": "balanced", "finalize": False},
            )
            self.assertEqual(saved.status_code, 200)
            derived_run_id = saved.get_json()["run_id"]
            self.assertEqual(self.client.get(saved.get_json()["history_url"]).status_code, 200)

            with app.app.app_context():
                row = app.get_db().execute(
                    "SELECT source_run_id, outcome_goal, outcome_label, is_final FROM schedule_runs WHERE id = ?",
                    (derived_run_id,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["source_run_id"], source_run_id)
                self.assertEqual(row["outcome_goal"], "balanced")
                self.assertFalse(bool(row["is_final"]))
                self.assertTrue(row["outcome_label"])
        finally:
            if derived_run_id is not None:
                self._cleanup_run(derived_run_id)
            self._cleanup_run(source_run_id)


if __name__ == "__main__":
    unittest.main()
