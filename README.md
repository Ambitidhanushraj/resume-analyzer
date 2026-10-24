# Resume Analyzer

[Open the live app](https://resume-analyzer-coral-eight.vercel.app) · [API health](https://resume-analyzer-coral-eight.vercel.app/api/health)

A React and FastAPI application that extracts text from PDF resumes and highlights skills, education, experience, certifications and projects. Choose a target role or use automatic matching across software, embedded systems, design, content analysis, data/BI, AI, automation, monitoring, cloud, quality and security. An optional job description adds an independent keyword comparison.

Role ranking combines curated requirements with locally learned, deduplicated skill-frequency profiles. Displayed percentages measure skill coverage, not hiring probability or an ATS guarantee. Extracted resume projects remain separate from suggested future learning projects. Scanned PDFs need OCR before upload. See [MODEL_CARD.md](MODEL_CARD.md) for training, provenance and limits.

## Run locally

Use Node.js 22, npm and Python 3.12. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
python -m uvicorn backend.main:app --reload --port 8000
```

Keep that terminal running. In another terminal at the repository root:

```bash
PORT=3001 npm start
```

Open [the app](http://localhost:3001). See [RUN_PROJECT.md](RUN_PROJECT.md) for Windows instructions and troubleshooting.

## Verify

Regression tests cover domain matching, profile training, PDF formats, job-description matching, project extraction, upload validation, API errors and the role-selection/result/reset UI.

With the virtual environment activated:

```bash
npm run test:backend
npm run test:frontend
npm run build
```

Upload a text-based PDF up to 4 MiB. A job description can contain up to 20,000 characters. Verify results with automatic matching, a selected role and a description, then try another resume. Uploaded documents are processed in memory; the app does not persist them or silently add them to training data.

## API

- `POST /api/analyze`: multipart form with `file`, optional `job_description` and optional `target_role`; returns extracted sections, coverage scores, role matches, supporting projects and future project ideas.
- `GET /api/roles`: available roles grouped by domain, reference counts and training metadata.
- `GET /api/health`: service health and optional NLP model status.
- [Local API documentation](http://localhost:8000/docs).

## Deploy

The [GitHub repository](https://github.com/Ambitidhanushraj/resume-analyzer) contains a root `vercel.json` that deploys both services to one Vercel project. Production requests use the same origin; no API key or separate backend host is required. See [DEPLOYMENT.md](DEPLOYMENT.md) for Git integration, routing and deployment verification.
