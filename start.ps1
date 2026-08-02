# Quant Insight 원클릭 실행 스크립트
# - 백엔드 (FastAPI) 자동 기동
# - 프론트엔드 (Next.js) 자동 기동
# - 의존성 자동 설치 (최초 1회)
# - 헬스체크 후 브라우저 자동 오픈
#
# 사용법:
#   1. start.bat 더블클릭  (권장)
#   2. PowerShell:  ./start.ps1

$ErrorActionPreference = "Stop"

# UTF-8 출력 강제 (한글 깨짐 방지)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp 65001 > $null

$root = $PSScriptRoot

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Quant Insight 시작 중..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ─── 1. 사전 확인 ──────────────────────────────────
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python 이 설치돼 있지 않음. https://python.org 에서 3.11+ 설치." -ForegroundColor Red
    Read-Host "엔터를 눌러 종료"
    exit 1
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "[ERROR] Node.js 가 설치돼 있지 않음. https://nodejs.org 에서 LTS 설치." -ForegroundColor Red
    Read-Host "엔터를 눌러 종료"
    exit 1
}

# ─── 2. 백엔드 venv ──────────────────────────────
$backendDir = Join-Path $root "backend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[setup] 백엔드 가상환경 생성 중 ..." -ForegroundColor Yellow
    python -m venv (Join-Path $backendDir ".venv")
    Write-Host "[setup] 백엔드 의존성 설치 중 ..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")
} else {
    Write-Host "[ok] 백엔드 venv 존재" -ForegroundColor Green
    # apscheduler 누락 시 자동 설치
    $hasSched = & $venvPython -c "import apscheduler" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[setup] apscheduler 설치 중 ..." -ForegroundColor Yellow
        & $venvPython -m pip install apscheduler
    }
}

# ─── 3. 프론트엔드 node_modules ──────────────────
$frontendDir = Join-Path $root "frontend"
$nodeModules = Join-Path $frontendDir "node_modules"

if (-not (Test-Path $nodeModules)) {
    Write-Host "[setup] 프론트엔드 의존성 설치 중 (몇 분 소요) ..." -ForegroundColor Yellow
    Push-Location $frontendDir
    npm install
    Pop-Location
} else {
    Write-Host "[ok] node_modules 존재" -ForegroundColor Green
}

# ─── 4. 포트 충돌 정리 ───────────────────────────
function Stop-PortOwner($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "[cleanup] 포트 $port 사용 프로세스 종료 (PID $($c.OwningProcess))" -ForegroundColor DarkGray
        } catch {}
    }
}
Stop-PortOwner 8000
Stop-PortOwner 3000
Start-Sleep -Seconds 1

# ─── 5. 백엔드 기동 (새 창) ──────────────────────
Write-Host ""
Write-Host "[start] 백엔드 (FastAPI :8000) ..." -ForegroundColor Cyan
# 자식 PowerShell 창에도 UTF-8 인코딩 적용 + PYTHONIOENCODING=utf-8
$utf8Init = "chcp 65001 > `$null; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); `$env:PYTHONIOENCODING='utf-8'; `$env:PYTHONUTF8='1';"
$backendArgs = @(
    "-NoExit",
    "-Command",
    "$utf8Init Set-Location '$backendDir'; & '$venvPython' -m uvicorn app.main:app --reload --port 8000"
)
Start-Process powershell -ArgumentList $backendArgs -WindowStyle Normal | Out-Null

# ─── 6. 프론트엔드 기동 (새 창) ──────────────────
Write-Host "[start] 프론트엔드 (Next.js :3000) ..." -ForegroundColor Cyan
$frontendArgs = @(
    "-NoExit",
    "-Command",
    "$utf8Init Set-Location '$frontendDir'; npm run dev"
)
Start-Process powershell -ArgumentList $frontendArgs -WindowStyle Normal | Out-Null

# ─── 7. 헬스체크 ─────────────────────────────────
Write-Host ""
Write-Host "[wait] 서비스 기동 대기 ..." -ForegroundColor Yellow

function Wait-Endpoint($url, $name, $maxTries) {
    for ($i = 1; $i -le $maxTries; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                Write-Host "  [ok] $name 가동 ($i 번째 시도)" -ForegroundColor Green
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 1
        if ($i % 5 -eq 0) { Write-Host "  [wait] $name 대기 중 ... ($i 초)" -ForegroundColor DarkGray }
    }
    Write-Host "  [warn] $name 응답 없음 ($maxTries 초 초과). 창에서 로그 확인 필요." -ForegroundColor Yellow
    return $false
}

$backendOk = Wait-Endpoint "http://127.0.0.1:8000/api/health" "백엔드" 30
$frontendOk = Wait-Endpoint "http://127.0.0.1:3000" "프론트엔드" 60

# ─── 8. 브라우저 오픈 ────────────────────────────
Write-Host ""
if ($frontendOk) {
    Write-Host "[open] 브라우저에서 대시보드 열기 ..." -ForegroundColor Cyan
    Start-Process "http://localhost:3000/dashboard"
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  실행 완료" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  대시보드:  http://localhost:3000/dashboard"
Write-Host "  매수신호:  http://localhost:3000/buy-signals"
Write-Host "  관심종목:  http://localhost:3000/watchlist"
Write-Host "  백테스트:  http://localhost:3000/backtest"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host ""
Write-Host "  종료하려면 stop.bat 실행 또는 양쪽 PowerShell 창 닫기" -ForegroundColor DarkGray
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 사용자가 출력 확인할 수 있도록 대기
Read-Host "이 창은 닫아도 됩니다. 엔터로 종료"
