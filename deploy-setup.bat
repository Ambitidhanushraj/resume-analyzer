@echo off
setlocal
cd /d "%~dp0"

REM Read-only deployment preflight.
for %%T in (git node npm) do (
    where %%T >nul 2>&1
    if errorlevel 1 (
        echo Missing %%T. Install it before continuing.
        exit /b 1
    )
)

for %%F in (vercel.json frontend\package.json frontend\package-lock.json backend\requirements.txt backend\.python-version) do (
    if not exist "%%F" (
        echo Missing required file: %%F
        exit /b 1
    )
)

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 exit /b 1
echo Deployment files found. No files or environment settings were changed.
echo Run the tests and production build described in README.md.
echo Push to your GitHub repository, then import it into Vercel at the repository root.
echo Use main as the production branch; leave REACT_APP_API_URL unset for same-origin API access.
echo See DEPLOYMENT.md for Git connection and live upload verification.
