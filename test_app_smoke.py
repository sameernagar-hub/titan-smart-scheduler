import unittest

import app


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_core_pages_render(self):
        for route in ["/", "/services", "/scheduler", "/analytics", "/ethics", "/history", "/faq", "/feedback"]:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    def test_generate_and_download_flow(self):
        run_id = None
        payload = {
            "schedule_name": "Smoke Test Plan",
            "mode": "custom",
            "algorithm": "constraint_shield",
            "weeks": 2,
            "students": [
                {
                    "name": "Alex",
                    "profile": "Mon Wed 9-10am",
                    "reliability": 90,
                    "max_hours": 10,
                    "preferred_shift": "afternoon",
                    "recent_callouts": 0,
                },
                {
                    "name": "Priya",
                    "profile": "Tue Thu 1-2pm",
                    "reliability": 95,
                    "max_hours": 10,
                    "preferred_shift": "morning",
                    "recent_callouts": 0,
                },
                {
                    "name": "Jordan",
                    "profile": "Fri 10-11am",
                    "reliability": 80,
                    "max_hours": 12,
                    "preferred_shift": "evening",
                    "recent_callouts": 1,
                },
            ],
            "shift_templates": [
                {"id": 1, "name": "Morning", "start": "09:00", "end": "13:00", "students_needed": 1},
                {"id": 2, "name": "Afternoon", "start": "13:00", "end": "17:00", "students_needed": 1},
            ],
            "schedule_config": {
                "shift_1": {"days": "Mon Wed", "count": 2},
                "shift_2": {"days": "Tue Thu", "count": 2},
            },
        }

        response = self.client.post("/api/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsNotNone(data)

        run_id = data["run_id"]
        self.assertEqual(self.client.get(f"/history/{run_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/history/{run_id}/download/json").status_code, 200)
        self.assertEqual(self.client.get(f"/history/{run_id}/download/csv").status_code, 200)
        with app.app.app_context():
            db = app.get_db()
            db.execute("DELETE FROM assignments WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM schedule_runs WHERE id = ?", (run_id,))
            db.commit()


if __name__ == "__main__":
    unittest.main()
