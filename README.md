# Resume Analyzer

[Open the live app](https://resume-analyzer-coral-eight.vercel.app) · [API health](https://resume-analyzer-coral-eight.vercel.app/api/health)

A React and FastAPI application that extracts text from PDF resumes and highlights skills, education, experience, certifications and projects. An optional job description adds keyword matches, missing skills and suggestions.

Analysis uses a fixed skills vocabulary, section detection and heuristic scoring. Scores are guidance, not predictions from a trained model or a guarantee that a commercial applicant tracking system will accept a resume. Scanned PDFs need OCR before upload.

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

With the virtual environment activated:

```bash
npm run test:backend
npm run test:frontend
npm run build
```

Upload a text-based PDF up to 4 MiB. A job description can contain up to 20,000 characters. Verify results with and without a description, then try another resume. Uploaded documents are processed in memory; the app does not persist them.

## API

- `POST /api/analyze`: multipart form with `file` and optional `job_description`; returns extracted sections, heuristic scores, role matches and suggestions.
- `GET /api/health`: service health and optional NLP model status.
- [Local API documentation](http://localhost:8000/docs).

## Deploy

The [GitHub repository](https://github.com/Ambitidhanushraj/resume-analyzer) contains a root `vercel.json` that deploys both services to one Vercel project. Production requests use the same origin; no API key or separate backend host is required. See [DEPLOYMENT.md](DEPLOYMENT.md) for Git integration, routing and deployment verification.
