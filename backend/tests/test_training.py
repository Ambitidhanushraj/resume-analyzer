import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import roles
from backend.training import main, train_from_manifest, train_profiles


class TrainingTests(unittest.TestCase):
    def test_global_normalized_dedup_and_requirement_only_counts(self):
        examples = [
            {"text": "Private Person\nPython SQL Kibana React", "roles": ["Data Engineer"]},
            {"text": "private  PERSON python\nSQL kibana react", "roles": ["Data Engineer", "Observability Engineer"]},
            {"text": "Another private person\nSQL ETL", "roles": ["Data Engineer"]},
        ]
        artifact = train_profiles(examples)
        self.assertEqual((artifact["source_count"], artifact["unique_count"], artifact["duplicate_count"]), (3, 2, 1))
        data = artifact["roles"]["Data Engineer"]
        self.assertEqual(data["example_count"], 2)
        self.assertEqual(data["skill_counts"], {"python": 1, "sql": 2, "etl": 1})
        self.assertEqual(artifact["roles"]["Observability Engineer"]["example_count"], 1)
        self.assertNotIn("react", data["skill_counts"])
        self.assertNotIn("kibana", data["skill_counts"])

    def test_artifact_contains_only_generic_aggregate_values(self):
        artifact = train_profiles([{
            "text": "PrivateCandidateName secret@example.com ExampleCorporation /private/secret.pdf\nPrivateProjectName Python RAG FastAPI",
            "roles": ["AI Engineer"], "path": "/private/path.pdf", "text_sha256": "abc123secret",
        }])
        serialized = json.dumps(artifact).lower()
        for private_token in ["privatecandidatename", "secret@example", "examplecorporation", "/private", "privateprojectname", "abc123secret", "text_sha256", "path"]:
            self.assertNotIn(private_token, serialized)
        self.assertEqual(artifact["roles"]["AI Engineer"]["skill_counts"], {"python": 1, "rag": 1, "fastapi": 1})

    def test_manifest_wrapper_cli_is_reproducible_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "01.txt").write_text("Private Person Python JSON automation", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"examples": [{"id": "01", "text_path": "01.txt", "path": "/Users/private/resume.pdf", "text_sha256": "privatehash", "roles": ["Automation Engineer"]}]}))
            output = root / "output.json"
            main(["--manifest", str(manifest), "--output", str(output)])
            first = output.read_bytes()
            main(["--manifest", str(manifest), "--output", str(output)])
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(json.loads(first), train_from_manifest(manifest))
            self.assertNotIn(b"privatehash", first)
            self.assertNotIn(b"Private Person", first)
            with patch.object(roles, "MODEL_PATH", output):
                self.assertEqual(roles.training_metadata()["source_count"], 1)
                self.assertEqual(roles.training_metadata()["trained_roles"], ["Automation Engineer"])

    def test_manifest_list_and_relative_text_path_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example.txt").write_text("Figma user flows screenshot curation", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps([{"text_path": "example.txt", "roles": ["Content Analyst"]}]))
            self.assertEqual(train_from_manifest(manifest)["roles"]["Content Analyst"]["example_count"], 1)

    def test_labels_required_and_no_evidence_does_not_claim_training(self):
        with self.assertRaises(ValueError):
            train_profiles([{"text": "Python"}])
        with self.assertRaises(ValueError):
            train_profiles([{"text": "Python", "roles": ["Imaginary Role"]}])
        artifact = train_profiles([{"text": "General collaboration experience", "roles": ["AI Engineer"]}])
        self.assertEqual(artifact["unique_count"], 1)
        self.assertEqual(artifact["roles"], {})

    def test_original_pdf_manifest_path_is_reproducible_without_adjacent_text(self):
        from io import BytesIO
        from PyPDF2 import PdfWriter
        from PyPDF2.generic import DecodedStreamObject, DictionaryObject, NameObject
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            page = writer.pages[0]
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})})})
            stream = DecodedStreamObject()
            stream.set_data(b"BT /F1 12 Tf 50 740 Td (Private Person Python RAG FastAPI) Tj ET")
            page[NameObject("/Contents")] = stream
            output = BytesIO()
            writer.write(output)
            (root / "source.pdf").write_bytes(output.getvalue())
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"examples": [{"id": "01", "path": "source.pdf", "roles": ["AI Engineer"]}]}))
            artifact = train_from_manifest(manifest)
            self.assertEqual(artifact["roles"]["AI Engineer"]["skill_counts"], {"python": 1, "rag": 1, "fastapi": 1})
            self.assertFalse((root / "01.txt").exists())
            self.assertNotIn("Private Person", json.dumps(artifact))

    def test_committed_profile_provenance_and_privacy(self):
        artifact = json.loads(roles.MODEL_PATH.read_text())
        self.assertEqual((artifact["source_count"], artifact["unique_count"], artifact["duplicate_count"]), (12, 11, 1))
        self.assertEqual(artifact["roles"]["AI Engineer"]["example_count"], 2)
        self.assertEqual(len(artifact["roles"]), 10)
        for role, profile in artifact["roles"].items():
            self.assertEqual(set(profile), {"example_count", "skill_counts"})
            self.assertTrue(set(profile["skill_counts"]).issubset(roles.ROLE_REQUIREMENTS[role]))
        serialized = json.dumps(artifact).lower()
        for token in ["dhanush", "stellantis", "mediinsight", "@", "/users/", "sha256", "text_path"]:
            self.assertNotIn(token, serialized)


if __name__ == "__main__":
    unittest.main()
