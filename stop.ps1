# Quant Insight 종료 스크립트
# 8000(백엔드) + 3000(프론트엔드) 포트 사용 프로세스 종료

$ErrorActionPreference = "SilentlyContinue"

# UTF-8 출력 강제
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp 65001 > $null

Write-Host ""
Write-Host "Quant Insight 종료 중..." -ForegroundColor Yellow

function Stop-PortOwner($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    $killed = 0
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "  [killed] 포트 $port  -  $($proc.ProcessName) (PID $($c.OwningProcess))" -ForegroundColor DarkGray
            $killed++
        }
    }
    if ($killed -eq 0) {
        Write-Host "  [info] 포트 $port 사용 중인 프로세스 없음" -ForegroundColor DarkGray
    }
}

Stop-PortOwner 8000
Stop-PortOwner 3000

Write-Host ""
Write-Host "종료 완료" -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2
