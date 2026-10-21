#!/usr/bin/env bash
set -euo pipefail

# Read-only deployment preflight; run from any directory.
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

for tool in git node npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing $tool. Install it before continuing."
    exit 1
  fi
done

for file in vercel.json frontend/package.json frontend/package-lock.json backend/requirements.txt backend/.python-version; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file"
    exit 1
  fi
done

git rev-parse --is-inside-work-tree >/dev/null
echo "Deployment files found. No files or environment settings were changed."
echo "Run the tests and production build described in README.md."
echo "Push to your GitHub repository, then import it into Vercel at the repository root."
echo "Use main as the production branch; leave REACT_APP_API_URL unset for same-origin API access."
echo "See DEPLOYMENT.md for Git connection and live upload verification."
