# Run Resume Analyzer locally

Open the repository folder in your editor and use two terminals. Install Python 3.12 and Node.js 22 first.

## macOS or Linux

In the first terminal, from the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn backend.main:app --reload --port 8000
```

In the second terminal, from the repository root:

```bash
npm --prefix frontend ci
PORT=3001 npm start
```

## Windows PowerShell

In the first terminal, from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

In the second terminal:

```powershell
npm --prefix frontend ci
$env:PORT = "3001"
npm start
```

Open [Resume Analyzer](http://localhost:3001). Keep both terminals running. Check [API health](http://localhost:8000/api/health) or [interactive API docs](http://localhost:8000/docs) if an upload fails.

## Use and check

1. Optionally paste a job description of up to 20,000 characters.
2. Upload a text-based PDF no larger than 4 MiB.
3. Review extracted sections, skills, role matches and suggestions. Scores measure heuristic section/keyword coverage; they do not guarantee ATS acceptance.
4. Select **Analyze another** and test a second PDF. Scanned PDFs without readable text require OCR outside this app.

Run checks from the repository root with the Python virtual environment activated:

```bash
npm run test:backend
npm run test:frontend
npm run build
```

On Windows, use `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v` for the backend tests. Runtime-only setup can install `requirements.txt`; `backend/requirements-dev.txt` also includes the HTTP test client.

## Troubleshooting

- **Port already in use:** check whether the app is already running before starting another server. Open the URLs above, or stop the old process from its terminal.
- **Frontend cannot reach the API:** confirm the backend is on port 8000. A stale `REACT_APP_API_URL` in your frontend environment can override the local default; update it deliberately and restart the frontend.
- **Missing frontend package:** run `npm --prefix frontend ci` from the repository root.
- **No readable PDF text:** upload a PDF with selectable text; image-only scans are unsupported.
- **`nlp_model_loaded` is false:** expected without the optional spaCy model. The standard installation supports core analysis without it.

Use `localhost` for the frontend address; local CORS allows ports 3000 and 3001. Stop the servers with Ctrl+C. No `.env` file is needed for the default local setup.
