$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.tools\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = Join-Path $root '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Create a Python virtual environment and install backend/requirements.txt first. See README.md.' }
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCommand) { $node = $nodeCommand.Source }
else {
    $runtime = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\runtimes\cua_node'
    $node = Get-ChildItem -Path "$runtime\*\bin\node.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $node) { throw 'Install Node.js 22.12 or newer first.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'node_modules\vite\bin\vite.js'))) { throw 'Run npm install in the repository root first.' }
New-Item -ItemType Directory -Path (Join-Path $root '.tools') -Force | Out-Null
foreach ($port in @(8000, 5173)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { Write-Output "Port $port is already running. Reusing the existing server."; continue }
    if ($port -eq 8000) {
        $process = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root '.tools\backend.log') -RedirectStandardError (Join-Path $root '.tools\backend-error.log')
    } else {
        $process = Start-Process -FilePath $node -ArgumentList @('node_modules\vite\bin\vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root '.tools\frontend.log') -RedirectStandardError (Join-Path $root '.tools\frontend-error.log')
    }
    if ($process.WaitForExit(1500)) { throw "Server on port $port exited. See the error log in .tools." }
    Write-Output "Started port $port (PID $($process.Id))."
}
Write-Output 'GridLink: http://127.0.0.1:5173'
Write-Output 'API docs: http://127.0.0.1:8000/docs'
Write-Output 'Logs are in .tools. To stop a server, use Stop-Process -Id with its printed PID.'
