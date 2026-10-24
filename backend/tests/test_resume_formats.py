"""Synthetic layout regressions; no private resume content belongs in this file."""
import unittest

from backend.main import (
    CERTIFICATION_HEADINGS,
    EDUCATION_HEADINGS,
    EXPERIENCE_HEADINGS,
    PROJECT_HEADINGS,
    SKILL_HEADINGS,
    candidate_name,
    extract_projects,
    get_section,
    section_text,
)


class ResumeFormatTests(unittest.TestCase):
    def test_education_training_aliases_have_shared_boundaries(self):
        for heading in ("Education and Training", "Education & Training", "Academic Qualifications"):
            with self.subTest(heading=heading):
                text = f"{heading}\nExample Academy\nBSc Computing\nProfessional Summary\nA profile paragraph.\nCore Skills\nPython"
                self.assertEqual(get_section(text, EDUCATION_HEADINGS), ["Example Academy", "BSc Computing"])
                self.assertEqual(get_section(text, SKILL_HEADINGS), ["Python"])

    def test_summary_and_skill_variants_stop_projects(self):
        for boundary in ("Professional Summary", "Skills and Tools", "Technical Competencies", "Core Competencies"):
            with self.subTest(boundary=boundary):
                text = f"Selected Projects\nInventory Console | React\n- Built a booking interface.\n{boundary}\nUnrelated Profile Text\n- Used AWS."
                projects = extract_projects(text)
                self.assertEqual([project.title for project in projects], ["Inventory Console"])
                self.assertNotIn("aws", projects[0].skills)

    def test_hackathons_do_not_leak_into_projects_or_certifications(self):
        text = """Projects
Inventory Console | Python
- Built an inventory tool.
Certifications
Python Credential
Hackathons
Community Coding Event
- Used React and AWS.
"""
        self.assertEqual(get_section(text, CERTIFICATION_HEADINGS), ["Python Credential"])
        self.assertEqual(len(extract_projects(text)), 1)
        self.assertEqual(extract_projects(text)[0].skills, ["python"])

    def test_separate_stack_lines_remain_with_four_projects(self):
        text = """Projects
Inventory Console
React.js, FastAPI, Python, NLP
• Developed an inventory interface.
Routing Workspace
Python, FastAPI, NLP, OCR, RAG
• Implemented a document workflow.
Research Notebook
Next.js, React, RAG, Generative AI
• Built a research interface.
Garden Planner
Python, Flask, Scikit-learn
• Created a forecasting application.
Certifications
Example Credential
"""
        projects = extract_projects(text)
        self.assertEqual([project.title for project in projects], ["Inventory Console", "Routing Workspace", "Research Notebook", "Garden Planner"])
        self.assertIn("react", projects[0].skills)
        self.assertIn("flask", projects[-1].skills)

    def test_no_pipe_stack_suffix_is_removed_from_title(self):
        text = """Projects
Event Operations Console Elasticsearch, Kibana, ELK Stack
• Built an operational view.
Archive Browser Python, Streamlit, JSON
• Automated archive inspection.
Document Queue Python, FastAPI, JSON, ZIP/7Z
• Developed a queue interface.
Education
Example Academy
"""
        projects = extract_projects(text)
        self.assertEqual([project.title for project in projects], ["Event Operations Console", "Archive Browser", "Document Queue"])
        self.assertIn("python", projects[1].skills)
        self.assertIn("fastapi", projects[2].skills)

    def test_single_tool_suffix_is_metadata(self):
        projects = extract_projects("Projects\nAccount Flow Review Figma\n• Curated interface evidence.\nCustomer Journey Mapping Figma\n• Mapped a customer flow.")
        self.assertEqual([project.title for project in projects], ["Account Flow Review", "Customer Journey Mapping"])
        self.assertIn("figma", projects[0].skills)

    def test_sentence_case_titles_use_following_stack_or_bullet_context(self):
        projects = extract_projects("""Projects
Customer retention workspace
Python, SQL
• Built a customer activity view.
Order analytics console
• Created a reporting interface using React.
""")
        self.assertEqual([project.title for project in projects], ["Customer retention workspace", "Order analytics console"])
        self.assertIn("python", projects[0].skills)
        self.assertIn("react", projects[1].skills)

    def test_wrapped_bullet_sentences_do_not_become_titles(self):
        projects = extract_projects("""Projects
Document Queue | Python
• Developed a document processing workflow with
Python and FastAPI.
• Added filters to inspect records and
Validation Outcomes
using a visual summary.
Booking Workspace | React
• Built a scheduling interface.
""")
        self.assertEqual([project.title for project in projects], ["Document Queue", "Booking Workspace"])
        self.assertIn("fastapi", projects[0].skills)

    def test_wrapped_title_is_reassembled_before_first_bullet(self):
        projects = extract_projects("""Projects
Inventory and Warehouse
Management Workspace | Python, FastAPI
• Built a stock interface.
""")
        self.assertEqual([project.title for project in projects], ["Inventory and Warehouse Management Workspace"])
        self.assertIn("fastapi", projects[0].skills)

    def test_decorated_and_numbered_titles_with_dates(self):
        projects = extract_projects("""## Selected Projects:
• Inventory Console | React
• Built a stock interface.
2. Booking Workspace | Python
Jan 2024 – Jun 2024
• Created a booking workflow.
### Document Queue 2023 - 2024
• Developed a document API.
""")
        self.assertEqual([project.title for project in projects], ["Inventory Console", "Booking Workspace", "Document Queue"])

    def test_dates_and_page_numbers_are_metadata(self):
        projects = extract_projects("""Projects
Inventory Console
2024 - 2025
Jan 2024 – Mar 2025
Page 1 of 2
React, Python
• Built a stock interface.
2
""")
        self.assertEqual([project.title for project in projects], ["Inventory Console"])

    def test_repeated_sections_are_collected_without_cross_contamination(self):
        text = "Experience\nSupport Intern\nProjects\nInventory Console\n- Built with Python.\nWork Experience\nDevelopment Intern\nSkills\nReact"
        self.assertEqual(get_section(text, EXPERIENCE_HEADINGS), ["Support Intern", "Development Intern"])
        self.assertNotIn("React", section_text(text, PROJECT_HEADINGS))

    def test_name_after_document_heading_and_on_contact_row(self):
        self.assertEqual(candidate_name("RESUME\nÉLODIE MARTIN | example@example.test\nSkills\nPython"), "Élodie Martin")
        self.assertEqual(candidate_name("Name: Alex Example\nProfessional Summary\nA short profile."), "Alex Example")
        self.assertIsNone(candidate_name("Professional Summary\nA short profile.\nSkills\nPython"))

    def test_target_skills_can_match_projects_without_job_description(self):
        projects = extract_projects("Projects\nInventory Console | Python, FastAPI\n- Built a record API.", target_skills=["python", "react"])
        self.assertEqual(projects[0].matched_keywords, ["python"])

    def test_education_preserves_all_school_rows(self):
        lines = [f"Academic Record {number}" for number in range(1, 10)]
        text = "Education\n" + "\n".join(lines) + "\nProjects\nInventory Console"
        self.assertEqual(get_section(text, EDUCATION_HEADINGS), lines)

    def test_wrapped_section_bullets_join_and_skip_page_numbers(self):
        text = "Experience\nSupport Intern\n• Developed a workflow using\nPython and SQL.\nPage 1 of 2\n• Built a React interface.\nEducation\nExample Academy"
        self.assertEqual(get_section(text, EXPERIENCE_HEADINGS), ["Support Intern", "Developed a workflow using Python and SQL.", "Built a React interface."])

    def test_achievement_with_pipe_is_not_a_project(self):
        projects = extract_projects("Projects\nInventory Console | Python\nBuilt a summary | React\n- Deployed an interface.")
        self.assertEqual([project.title for project in projects], ["Inventory Console"])

    def test_inline_heading_content_is_a_boundary(self):
        text = "Projects: Inventory Console | Python\n- Built a stock interface.\nTechnical Skills: React, SQL\nProfessional Summary: A short profile."
        projects = extract_projects(text)
        self.assertEqual([project.title for project in projects], ["Inventory Console"])
        self.assertEqual(projects[0].skills, ["python"])
        self.assertEqual(get_section(text, SKILL_HEADINGS), ["React, SQL"])

    def test_new_employment_header_does_not_join_previous_bullet(self):
        text = "Experience\nSupport Intern\n• Built a support tool.\nDevelopment Intern\n• Created a workflow."
        self.assertEqual(get_section(text, EXPERIENCE_HEADINGS), ["Support Intern", "Built a support tool.", "Development Intern", "Created a workflow."])


if __name__ == "__main__":
    unittest.main()
