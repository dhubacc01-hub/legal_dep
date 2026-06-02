$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$localEnvPath = Join-Path $projectRoot ".env.local.ps1"
$venvActivatePath = Join-Path $projectRoot ".venv\\Scripts\\Activate.ps1"

if (Test-Path $localEnvPath) {
  . $localEnvPath
}

if (Test-Path $venvActivatePath) {
  . $venvActivatePath
}

python -m uvicorn app.main:app --reload
