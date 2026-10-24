# Role profiles and training

The analyzer supports 20 curated roles. Automatic ranking uses canonical skills and aliases, domain-specific skill rarity, career intent in the introductory summary, and locally learned skill frequencies. Role percentages remain the fraction of curated role requirements detected; learned frequencies affect ordering, not those percentages.

The separate structure score checks five areas: recognized skills, education, experience or project evidence, project details, and an introductory summary. Each contributes 20 points. This measures section completeness only; it does not grade writing quality, verify experience or predict hiring outcomes. Adding more keywords cannot replace absent sections.

## Current example set

The initial training run consumed 12 supplied PDFs. Two files had identical extracted content, leaving 11 unique resume variants and 10 roles with labeled examples. Some variants have more than one relevant role label. Labels were reviewed from the resumes' stated career intent and scope; filenames alone do not determine them.

This is a small collection of tailored variants from one candidate, not independent examples from 11 people. The learned profiles help calibrate role matching to these examples. No held-out accuracy, broad generalization, seniority assessment or hiring prediction is claimed. Roles without examples use curated requirements.

## What is learned

1. Extract canonical skills from each labeled example.
2. Normalize case, Unicode and whitespace to deduplicate content; merge labels without counting duplicate files twice.
3. For each role, count only skills that belong to that role's curated requirements.
4. Save aggregate skill counts and sample counts in `backend/data/role_profiles.json`.
5. At analysis time, use those frequencies as a bounded ranking contribution alongside role coverage and introductory intent. A missing or invalid artifact falls back to curated matching.

Shared skills such as Python and Git cannot add unrelated requirements to a role. Projects suggested for future practice come from role-specific templates; they are never presented as work the candidate has already done. Job-description keyword coverage is calculated separately from the selected career goal.

## Privacy and retraining

Source PDFs, extracted text, names, contact details, employers and original project titles are not stored in the learned artifact. The artifact contains only canonical skills, role labels, aggregate counts and methodological limitations. Normal web uploads are analyzed without persistence or automatic retraining.

Keep personal training manifests and reports under ignored `.local/training/`. A manifest uses explicit reviewed labels:

```json
{
  "examples": [
    {"path": "/private/resumes/design.pdf", "roles": ["UI/UX Designer"]},
    {"path": "/private/resumes/analytics.pdf", "roles": ["Data Analyst", "Business Intelligence Developer"]}
  ]
}
```

From the repository root:

```bash
python -m backend.training --manifest .local/training/manifest.json --output backend/data/role_profiles.json
python -m backend.evaluate --manifest .local/training/manifest.json --output .local/training/evaluation.json
python -m unittest discover -s backend/tests -v
```

The evaluation command sends each available PDF through an in-process API test client, so source documents are not uploaded to a remote service. An optional `text_path` points to an ignored local text snapshot; `text_sha256` verifies the reviewed content. If an original moves or changes, evaluation can replay the verified snapshot and explicitly reports `cached_text` instead of `pdf_api`. Missing or mismatched sources fail rather than silently evaluating different content. Optional `expected_projects` counts check manually reviewed extraction results. Corpus checks are training-set regression checks, not an independent test of generalization. Use a larger, independently labeled and consented dataset with separate evaluation data before claiming predictive accuracy.
