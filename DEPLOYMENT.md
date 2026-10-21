# Deploy to Vercel

Deploy the frontend and Python API together from [Ambitidhanushraj/resume-analyzer](https://github.com/Ambitidhanushraj/resume-analyzer). The root `vercel.json` uses [Vercel Services](https://vercel.com/docs/services), currently available in beta, to build both parts independently on one domain.

## Connect GitHub

1. In Vercel, add a project and import `Ambitidhanushraj/resume-analyzer`. Authorize Vercel to access the repository when prompted.
2. Keep **Root Directory at the repository root**. The committed configuration selects Create React App in `frontend/` and FastAPI in `backend/` with entrypoint `main:app`. Leave project-wide build and output overrides unset.
3. Use `main` as the production branch and deploy. Subsequent pushes to `main` automatically create production deployments; other branches can create previews through the Git integration.
4. Confirm the project’s Git settings show the correct repository and production branch. A local CLI deployment alone does not establish Git integration.

The frontend uses Node.js 22 and builds to `frontend/build`. The backend uses Python 3.12 from `backend/.python-version` and installs the lean, pinned `backend/requirements.txt`. No spaCy model download is required.

## Routing and environment

Top-level rewrites send `/api/*` to FastAPI and every other path to the frontend. Services preserve the request path, so the backend receives `/api/analyze` unchanged. See [service routing](https://vercel.com/docs/services/routing).

No production environment variables are required. Leave `REACT_APP_API_URL` unset so browser requests use the deployment’s own origin. Remove any stale value pointing to a former backend host, then redeploy: Create React App reads environment variables at build time.

Locally, the frontend defaults to `http://localhost:8000`. The API allows local browser origins `http://localhost:3000` and `http://localhost:3001`; deployed traffic uses the same origin and does not require cross-origin access.

## Verify the deployed application

Replace the example URL with the deployment URL returned by Vercel:

```bash
curl --fail https://YOUR-PROJECT.vercel.app/api/health
curl --fail -F 'file=@/absolute/path/resume.pdf' -F 'job_description=Frontend developer using React and JavaScript' https://YOUR-PROJECT.vercel.app/api/analyze
```

Expect a healthy JSON response from the first request and analysis JSON from the second. A false `nlp_model_loaded` value is expected without the optional spaCy model; core analysis uses deterministic text extraction and heuristics.

In a browser, confirm the page and static assets load, then upload a text-based PDF with and without a job description. Check skills, extracted sections, scores and suggestions; use **Analyze another** to repeat. Also verify malformed, scanned or oversized PDFs show useful errors. Do not treat a successful frontend build as proof that the API works.

## Limits and troubleshooting

- Upload limit: 4 MiB per PDF; job descriptions: 20,000 characters. This leaves room for multipart data under Vercel’s [4.5 MB request body limit](https://vercel.com/docs/functions/limitations).
- If `/api/health` returns HTML, check the root directory and root `vercel.json`; the request must reach the backend service.
- If the UI calls another host, remove the old `REACT_APP_API_URL` value and redeploy.
- If a build fails, inspect the failing service’s build logs. Verify the frontend lockfile is committed and Python dependencies match `backend/requirements.txt`.
- If deployment protection shows a login page, test through an authenticated session or the production domain according to the project’s access settings.

This application has no persistent resume store and needs no database. Its scores indicate keyword and section coverage; they are not a trained model’s assessment or an ATS acceptance guarantee.
