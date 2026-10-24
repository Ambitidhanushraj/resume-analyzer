"""Learn privacy-preserving role skill frequencies from private labeled texts.

Usage: python -m backend.training --manifest /private/manifest.json \
    --output backend/data/role_profiles.json

The manifest may be a list or {"examples": [...]}. Each example requires
"roles" (canonical role names), and either "text", "text_path", a PDF "path",
or an "id" whose extracted text is in <manifest directory>/<id>.txt. PDF paths and
hashes in a private manifest are intentionally never copied to the artifact.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

from .roles import PROFILE_LIMITATIONS, PROFILE_METHOD, ROLE_REQUIREMENTS, extract_skills


def normalize_text(text):
    """Deduplicate formatting-only variants as well as byte-identical texts."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


def train_profiles(examples):
    """Return only aggregate canonical requirements/counts, never raw evidence."""
    source_count = 0
    unique = {}
    for example in examples:
        source_count += 1
        text = example.get("text")
        labels = example.get("roles")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Every example must contain nonempty extracted text.")
        if not isinstance(labels, list) or not labels or any(role not in ROLE_REQUIREMENTS for role in labels):
            raise ValueError("Every example needs at least one valid canonical role in its roles array.")
        normalized = normalize_text(text)
        if normalized in unique:
            # Duplicate labels are unioned but never contribute a second vote.
            unique[normalized]["roles"].update(labels)
        else:
            unique[normalized] = {"skills": set(extract_skills(text)), "roles": set(labels)}
    per_role = {}
    for role, requirements in ROLE_REQUIREMENTS.items():
        labeled = [item for item in unique.values() if role in item["roles"]]
        frequencies = Counter(skill for item in labeled for skill in requirements if skill in item["skills"])
        # A labeled example with no recognized role requirements cannot provide
        # learned evidence; retain provenance but do not claim a trained profile.
        if labeled and frequencies:
            per_role[role] = {
                "example_count": len(labeled),
                "skill_counts": {skill: frequencies[skill] for skill in requirements if frequencies[skill]},
            }
    return {
        "schema_version": 1,
        "method": PROFILE_METHOD,
        "source_count": source_count,
        "unique_count": len(unique),
        "duplicate_count": source_count - len(unique),
        "limitations": list(PROFILE_LIMITATIONS),
        "roles": per_role,
    }


def train_from_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("examples") if isinstance(manifest, dict) else manifest
    if not isinstance(entries, list):
        raise ValueError("Manifest must be a list or an object with an examples array.")
    examples = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Manifest examples must be objects.")
        if "text" in entry:
            text = entry["text"]
        else:
            text_path = entry.get("text_path")
            if text_path:
                text_path = Path(text_path)
                if not text_path.is_absolute():
                    text_path = manifest_path.parent / text_path
            elif entry.get("path"):
                pdf_path = Path(entry["path"])
                if not pdf_path.is_absolute():
                    pdf_path = manifest_path.parent / pdf_path
                from PyPDF2 import PdfReader
                try:
                    reader = PdfReader(str(pdf_path))
                    text = "\n".join(page.extract_text() or "" for page in reader.pages)
                except Exception as exc:
                    raise ValueError("A manifest PDF could not be read as a text-based PDF.") from exc
                examples.append({"text": text, "roles": entry.get("roles")})
                continue
            else:
                example_id = str(entry.get("id", ""))
                if not re.fullmatch(r"[A-Za-z0-9_-]+", example_id):
                    raise ValueError("Each example requires a text_path, text, or simple id.")
                text_path = manifest_path.parent / f"{example_id}.txt"
            text = text_path.read_text(encoding="utf-8")
        examples.append({"text": text, "roles": entry.get("roles")})
    return train_profiles(examples)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        artifact = train_from_manifest(args.manifest)
    except (OSError, ValueError, TypeError) as exc:
        # No resume contents are included in exceptions or CLI output.
        parser.exit(2, f"Training failed: {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Learned {len(artifact['roles'])} role profile(s) from {artifact['unique_count']} unique example(s); ignored {artifact['duplicate_count']} duplicate(s).")


if __name__ == "__main__":
    main()
