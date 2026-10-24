"""Focused API and extraction regressions. Run: python -m unittest discover -s backend/tests."""
from io import BytesIO
import unittest

from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter
from PyPDF2.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.main import MAX_PDF_BYTES, analyze, app, extract_projects, get_section


def pdf_bytes(lines=None):
    """Create a real text PDF without requiring a document-generation package."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    page = writer.pages[0]
    if lines:
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
        })
        stream = DecodedStreamObject()
        commands = ["BT /F1 12 Tf 50 740 Td 16 TL"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj T*")
        commands.append("ET")
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = stream
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class AnalysisRegressionTests(unittest.TestCase):
    def test_explicit_description_skills_take_priority_over_role_defaults(self):
        result = analyze("Jane Doe\nSkills\nReact JavaScript\n", "Frontend Developer using React and JavaScript")
        self.assertEqual(result.job_match.score, 100)
        self.assertEqual(result.job_match.missing_skills, [])
        # The supplied job asks for two skills; generic role coverage remains a
        # separate, broader comparison and must not imply full role coverage.
        self.assertEqual(result.recommendations[0].match, 29)
        self.assertIn("typescript", result.recommendations[0].missing_skills)

    def test_generic_role_uses_fallback_requirements(self):
        result = analyze("Jane Doe\nSkills\nReact JavaScript\n", "Frontend Developer")
        self.assertEqual(result.job_match.score, 29)
        self.assertIn("typescript", result.job_match.missing_skills)

    def test_description_without_known_skills_or_role(self):
        result = analyze("Jane Doe\nSkills\nPython", "Seeking a dependable colleague")
        self.assertEqual(result.job_match.score, 0)
        self.assertEqual(result.job_match.missing_skills, [])
        self.assertIn("couldn't calculate", result.summary)
        self.assertNotIn("0%", result.summary)
        self.assertEqual(len(result.job_match.suggestions), 1)
        self.assertIn("recognizable role", result.job_match.suggestions[0])

    def test_missing_required_skills_still_reports_zero_match(self):
        result = analyze("Jane Doe\nSkills\nPython", "React and JavaScript")
        self.assertEqual(result.job_match.score, 0)
        self.assertIn("keyword coverage is 0%", result.summary)

    def test_actual_experience_is_preferred_to_earlier_projects(self):
        result = analyze("Jane Doe\nProjects\nPortfolio Website\n- Built using React\nExperience\nSoftware Intern\n- Developed Python APIs")
        self.assertEqual(result.experience, ["Software Intern", "Developed Python APIs"])

    def test_ordinary_project_titles_and_shared_section_boundaries(self):
        for heading in ["Projects", "Personal Projects", "Academic Projects", "Project Experience"]:
            with self.subTest(heading=heading):
                resume = f"""Jane Doe
Academic Background
BSc Computer Science
{heading}:
Portfolio Website
- Built a responsive React interface with JavaScript.
Task Manager | Python, FastAPI
- Developed an API using Python.
Certificates
AWS Certificate
"""
                result = analyze(resume, "Frontend Developer using React and JavaScript")
                self.assertEqual([project.title for project in result.projects], ["Portfolio Website", "Task Manager"])
                self.assertEqual(result.projects[0].matched_keywords, ["javascript", "react"])
                self.assertEqual(result.projects[1].matched_keywords, [])
                self.assertEqual(len(result.related_projects), 1)
                self.assertNotIn("aws", result.projects[1].skills)
                self.assertEqual(result.education, ["BSc Computer Science"])
                self.assertEqual(result.certifications, ["AWS Certificate"])
                self.assertTrue(result.experience)

    def test_experience_stops_at_project_heading_variants(self):
        resume = "Experience\nSoftware Intern\nAcademic Projects\nPortfolio Website\n- Built with React."
        self.assertEqual(get_section(resume, ["experience"]), ["Software Intern"])

    def test_description_sentences_and_bullets_do_not_create_projects(self):
        projects = extract_projects("Projects\nPortfolio Website\nBuilt using React\n- Deployed on AWS\nSkills\nPython")
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].skills, ["react", "aws"])


class ApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_valid_pdf_analysis_and_job_description(self):
        response = self.client.post("/api/analyze", files={"file": ("resume.pdf", pdf_bytes([
            "Jane Doe", "Skills", "React JavaScript", "Education", "BSc Computer Science",
            "Projects", "Portfolio Website", "- Built a React website with JavaScript.",
        ]), "application/pdf")}, data={"job_description": "Frontend Developer using React and JavaScript"})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["candidate_name"], "Jane Doe")
        self.assertEqual(result["job_match"]["score"], 100)
        self.assertEqual(result["projects"][0]["title"], "Portfolio Website")

    def test_bad_extension_corrupt_pdf_and_scanned_pdf_are_rejected(self):
        for filename, content, status in [
            ("resume.txt", b"invalid", 400),
            ("resume.pdf", b"not a PDF", 400),
            ("resume.pdf", pdf_bytes(), 422),
        ]:
            with self.subTest(filename=filename, expected=status):
                response = self.client.post("/api/analyze", files={"file": (filename, content, "application/pdf")})
                self.assertEqual(response.status_code, status)

    def test_oversized_pdf_is_rejected_before_parsing(self):
        response = self.client.post("/api/analyze", files={"file": ("resume.pdf", b"0" * (MAX_PDF_BYTES + 1), "application/pdf")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("4 MB", response.json()["detail"])

    def test_oversized_job_description_is_rejected(self):
        response = self.client.post("/api/analyze", files={"file": (
            "resume.pdf", pdf_bytes(["Jane Doe", "Skills: React and JavaScript"]), "application/pdf"
        )}, data={"job_description": "a" * 20001})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "job_description"])

    def test_vercel_and_local_origins_allow_browser_preflight(self):
        for origin in ["https://resume-analyzer-abc123.vercel.app", "http://localhost:3001"]:
            with self.subTest(origin=origin):
                response = self.client.options("/api/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)

    def test_unrelated_origins_are_rejected(self):
        for origin in ["https://example.com", "https://foo.vercel.app.evil.com"]:
            response = self.client.options("/api/analyze", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
