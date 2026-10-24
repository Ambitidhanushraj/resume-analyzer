import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import roles
from backend.training import train_profiles


class RoleCatalogTests(unittest.TestCase):
    def test_twenty_domains_have_canonical_requirements_and_project_ideas(self):
        catalog = roles.get_role_catalog()
        self.assertEqual(len(catalog), 20)
        for item in catalog:
            with self.subTest(role=item["title"]):
                requirements = roles.ROLE_REQUIREMENTS[item["title"]]
                self.assertTrue(requirements)
                self.assertEqual(len(requirements), len(set(requirements)))
                self.assertTrue(set(requirements).issubset(roles.SKILLS))
                self.assertTrue(item["domain"])
                self.assertIsInstance(item["profile_examples"], int)
                ideas = roles.suggest_projects(item["title"], [])
                self.assertGreaterEqual(len(ideas), 2)
                for idea in ideas:
                    self.assertTrue(idea["description"].startswith("Suggested learning project:"))
                    self.assertEqual(idea["skills"], idea["missing_skills"])
                    self.assertTrue(set(idea["skills"]).issubset(roles.SKILLS))

    def test_original_frontend_coverage_stays_twenty_nine(self):
        with patch.object(roles, "_load_profiles", return_value=None):
            frontend = next(item for item in roles.rank_role_matches(["react", "javascript"], limit=20) if item["title"] == "Frontend Developer")
        self.assertEqual(frontend["match"], 29)
        self.assertEqual(frontend["profile_examples"], 0)

    def test_aliases_include_actual_resume_spellings(self):
        skills = roles.extract_skills("C++11/14/17, React.js, NextJS, REST APIs, GenerativeAI, Retrieval-Augmented Generation, OOP, DSA, PowerBI, ELK")
        for canonical in ["c++", "react", "next.js", "rest api", "generative ai", "rag", "object-oriented programming", "data structures", "algorithms", "power bi", "elk stack"]:
            self.assertIn(canonical, skills)
        self.assertNotIn("c", skills)
        self.assertNotIn("javascript", roles.extract_skills("Next.js"))

    def test_short_aliases_do_not_match_inside_words(self):
        skills = roles.extract_skills("a diagram of fragments on a tablet; big examples; javascript; next.js; model creation")
        self.assertNotIn("rag", skills)
        self.assertNotIn("bi", skills)
        self.assertNotIn("business intelligence", skills)
        self.assertNotIn("ml", skills)
        self.assertNotIn("machine learning", skills)
        self.assertNotIn("java", skills)
        self.assertNotIn("c", skills)
        self.assertIn("javascript", skills)
        self.assertIn("machine learning", roles.extract_skills("ML engineer"))

    def test_explicit_summary_intent_beats_prior_job_title_and_project_title(self):
        text = """Example Candidate
Professional Summary
Former Software Developer Intern. Seeking the Trainee Security Analyst role.
Projects
Cloud Engineer Platform
AI Engineer Toolkit
"""
        self.assertEqual(roles.detect_role(text), "Security Analyst")
        self.assertIsNone(roles.detect_role("Example Candidate\nProjects\nAI Engineer Toolkit\nSoftware Engineer Platform"))
        self.assertIsNone(roles.detect_role("Frontended fragments and big analyst work"))

    def test_summary_aliases_cover_distinct_domains(self):
        for summary, expected in [
            ("Targeting C++ software and embedded developer roles.", "C++ / Embedded Developer"),
            ("Content Analyst candidate with Figma practice.", "Content Analyst"),
            ("Interested in Data Analytics roles.", "Data Analyst"),
            ("Seeking an entry-level Software Engineer role.", "Software Engineer"),
            ("Seeking a UI/UX Designer role.", "UI/UX Designer"),
            ("Seeking an SRE role.", "DevOps Engineer"),
        ]:
            with self.subTest(summary=summary):
                self.assertEqual(roles.detect_role("Professional Summary\n" + summary + "\nSkills\nPython"), expected)

    def test_shared_python_does_not_swamp_domain_evidence(self):
        cases = [
            (["python", "figma", "user research", "user flows", "wireframing", "prototyping", "accessibility"], "UI/UX Designer"),
            (["python", "elasticsearch", "kibana", "elk stack", "log analysis", "monitoring", "alerting"], "Observability Engineer"),
            (["python", "c++", "stl", "object-oriented programming", "data structures", "multithreading", "memory management", "linux", "rtos"], "C++ / Embedded Developer"),
            (["python", "content analysis", "screenshot curation", "ui pattern tagging", "user flows", "figma", "data validation", "quality assurance"], "Content Analyst"),
        ]
        for skills, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(roles.rank_role_matches(skills)[0]["title"], expected)

    def test_learning_changes_order_but_not_requirement_coverage(self):
        skills = ["python", "sql"]
        with patch.object(roles, "_load_profiles", return_value=None):
            baseline = roles.rank_role_matches(skills, limit=20)
        learned = train_profiles([{"text": "Python SQL", "roles": ["Data Engineer"]}])
        with patch.object(roles, "_load_profiles", return_value=learned):
            trained = roles.rank_role_matches(skills, limit=20)
        baseline_positions = {item["title"]: index for index, item in enumerate(baseline)}
        trained_positions = {item["title"]: index for index, item in enumerate(trained)}
        self.assertLess(trained_positions["Data Engineer"], baseline_positions["Data Engineer"])
        self.assertEqual(trained[0]["title"], "Data Engineer")
        self.assertEqual({item["title"]: item["match"] for item in baseline}, {item["title"]: item["match"] for item in trained})
        data_engineer = next(item for item in trained if item["title"] == "Data Engineer")
        self.assertEqual(data_engineer["profile_examples"], 1)
        self.assertIn("frequencies", data_engineer["explanation"])

    def test_missing_and_malformed_profiles_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.json"
            with patch.object(roles, "MODEL_PATH", model_path):
                for data in [None, "broken json", json.dumps({"schema_version": 2}), json.dumps({"schema_version": 1, "source_count": 1, "unique_count": 1, "duplicate_count": 0, "roles": {"AI Engineer": {"example_count": 1, "skill_counts": {"private unknown": 1}}}})]:
                    with self.subTest(data=data):
                        if data is not None:
                            model_path.write_text(data)
                        self.assertEqual(roles.training_metadata()["trained_roles"], [])
                        self.assertTrue(all(item["profile_examples"] == 0 for item in roles.get_role_catalog()))
                        self.assertEqual(roles.rank_role_matches(["figma", "user research", "user flows", "wireframing", "prototyping"])[0]["title"], "UI/UX Designer")

    def test_untrained_roles_do_not_claim_training(self):
        item = next(item for item in roles.get_role_catalog() if item["title"] == "UI/UX Designer")
        self.assertEqual(item["profile_examples"], 0)
        self.assertNotIn("UI/UX Designer", roles.training_metadata()["trained_roles"])

    def test_unknown_skills_do_not_return_meaningless_zero_matches(self):
        self.assertEqual(roles.rank_role_matches([]), [])
        self.assertEqual(roles.rank_role_matches(["unknown skill"]), [])
        self.assertTrue(all(item["match"] > 0 for item in roles.rank_role_matches(["python"], limit=20)))


if __name__ == "__main__":
    unittest.main()
