"""Domain flow regressions using synthetic resumes, never personal source data."""
import unittest

from fastapi.testclient import TestClient

from backend.main import analyze, app
from backend.roles import MODEL_PATH
from backend.tests.test_analysis import pdf_bytes


class DomainApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_catalog_has_domains_and_real_training_counts(self):
        response = self.client.get("/api/roles")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["roles"]), 20)
        self.assertTrue(all(role["domain"] for role in data["roles"]))
        self.assertEqual(data["training"]["source_count"], 12)
        self.assertEqual(data["training"]["unique_count"], 11)
        self.assertEqual(data["training"]["duplicate_count"], 1)
        self.assertEqual(len(data["training"]["trained_roles"]), 10)

    def test_role_selection_works_without_description_and_matches_project_aliases(self):
        response = self.client.post("/api/analyze", data={"target_role": "Frontend Developer"}, files={
            "file": ("sample.pdf", pdf_bytes([
                "Jane Doe", "Education", "BSc Computing", "Projects", "Task board",
                "React.js, JavaScript", "- Built an interface with React.js and JavaScript.",
            ]), "application/pdf"),
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["selected_role"], "Frontend Developer")
        self.assertEqual(result["role_source"], "selected")
        self.assertEqual(result["domain"], "Web development")
        self.assertIsNone(result["job_match"])
        self.assertIn("react", result["related_projects"][0]["matched_keywords"])
        self.assertTrue(result["recommended_projects"])
        self.assertNotEqual(result["projects"][0]["title"], result["recommended_projects"][0]["title"])

    def test_selected_goal_does_not_replace_job_description_requirements(self):
        result = analyze(
            "Jane Doe\nSkills\nFigma Prototyping\n", "UI/UX Designer: Figma and prototyping", "Data Analyst"
        )
        self.assertEqual(result.selected_role, "Data Analyst")
        self.assertEqual(result.role_source, "selected")
        self.assertEqual(result.job_match.target_role, "UI/UX Designer")
        self.assertEqual(result.job_match.score, 100)
        self.assertEqual(result.job_match.basis, "job_description")
        self.assertEqual(result.recommendations[0].title, "Data Analyst")
        self.assertEqual(result.recommendations[0].match, 0)
        self.assertTrue(all("sql" in idea.skills or "pandas" in idea.skills for idea in result.recommended_projects))

    def test_role_only_description_is_an_explicit_curated_fallback(self):
        result = analyze("Jane Doe\nSkills\nReact JavaScript\n", "Frontend Developer")
        self.assertEqual(result.job_match.basis, "role_requirements")
        self.assertEqual(result.job_match.score, 29)
        self.assertIn("Curated role requirement coverage", result.summary)
        self.assertNotIn("Job-description keyword coverage", result.summary)
        ai = analyze("Jane Doe\nSkills\nMachine learning and Python\n", "Machine Learning Engineer")
        self.assertEqual(ai.job_match.basis, "role_requirements")
        self.assertIn("pandas", ai.job_match.missing_skills)

    def test_zero_evidence_has_no_arbitrary_automatic_role(self):
        result = analyze("Jane Doe\nExperienced in flower arranging and floral bouquets.")
        self.assertEqual(result.recommendations, [])
        self.assertIsNone(result.selected_role)
        self.assertEqual(result.recommended_projects, [])

    def test_keyword_lists_do_not_inflate_section_completeness(self):
        result = analyze("Jane Doe\nSkills\nPython Java React SQL Figma Docker AWS Pandas Git NLP RAG")
        self.assertEqual(result.score_basis, "section_completeness")
        self.assertEqual(result.score, 20)
        self.assertFalse(result.structure_checks["education"])
        self.assertFalse(result.structure_checks["project_details"])

    def test_invalid_role_is_reported_instead_of_ignored(self):
        response = self.client.post("/api/analyze", data={"target_role": "Invented role"}, files={
            "file": ("sample.pdf", pdf_bytes(["Jane Doe", "Python and SQL programming experience"]), "application/pdf"),
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn("supported target role", response.json()["detail"])

    def test_regular_upload_does_not_modify_learned_profiles(self):
        before = MODEL_PATH.read_bytes()
        response = self.client.post("/api/analyze", files={
            "file": ("sample.pdf", pdf_bytes(["Jane Doe", "Python and SQL programming experience"]), "application/pdf"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MODEL_PATH.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
