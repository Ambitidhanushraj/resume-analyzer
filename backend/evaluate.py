"""Local corpus checks; PDF contents never leave this process or enter the report."""
import argparse
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import analyze, app, extract_pdf_text


def _example_source(example: dict, manifest_path: Path):
    """Keep a reviewed corpus stable when original files move or are revised."""
    def resolve(value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else manifest_path.parent / path

    if example.get("path"):
        source = resolve(example["path"])
        if source.is_file():
            payload = source.read_bytes()
            expected = example.get("text_sha256")
            if not expected or hashlib.sha256(extract_pdf_text(payload).encode()).hexdigest() == expected:
                return "pdf_api", payload
    if example.get("text_path"):
        cached = resolve(example["text_path"])
        if cached.is_file():
            text = cached.read_text()
            expected = example.get("text_sha256")
            if not expected or hashlib.sha256(text.encode()).hexdigest() == expected:
                return "cached_text", text
    return "unavailable", None


def evaluate_manifest(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    examples = manifest.get("examples", []) if isinstance(manifest, dict) else manifest
    rows = []
    with TestClient(app) as client:
        for index, example in enumerate(examples, 1):
            labels = example.get("roles", [])
            mode, content = _example_source(example, manifest_path)

            def run(role=None):
                if mode == "cached_text":
                    return 200, analyze(content, target_role=role).model_dump()
                if mode == "pdf_api":
                    response = client.post("/api/analyze", data={"target_role": role} if role else {}, files={
                        "file": ("example.pdf", content, "application/pdf"),
                    })
                    return response.status_code, response.json()
                return 404, {}

            status, result = run()
            checks = {"analysis_succeeds": status == 200}
            row = {"example": index, "mode": mode, "status": status, "checks": checks}
            if status == 200:
                checks["education_detected"] = bool(result["education"])
                checks["experience_detected"] = bool(result["experience"])
                checks["projects_detected"] = bool(result["projects"])
                if "expected_projects" in example:
                    checks["project_count_matches_review"] = len(result["projects"]) == example["expected_projects"]
                row.update({
                    "skill_count": len(result["skills"]),
                    "project_count": len(result["projects"]),
                    "automatic_roles": [role["title"] for role in result["recommendations"]],
                    "reviewed_roles": labels,
                })
                if labels:
                    row["reviewed_role_in_top_three"] = bool(set(labels) & set(row["automatic_roles"]))
                    selected_status, focused = run(labels[0])
                    checks["role_selection_applied"] = (
                        selected_status == 200
                        and focused.get("selected_role") == labels[0]
                        and focused.get("role_source") == "selected"
                    )
                    checks["role_project_plan_available"] = bool(focused.get("recommended_projects"))
            row["passed"] = all(checks.values())
            rows.append(row)
    return {
        "scope": "Training-corpus checks, using original PDFs or explicitly cached text when originals moved or changed; not held-out accuracy.",
        "source_count": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "examples": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Use an ignored local folder for personal corpus reports.")
    args = parser.parse_args()
    report = evaluate_manifest(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Local corpus checks passed: {report['passed']}/{report['source_count']}.")
    if report["passed"] != report["source_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
