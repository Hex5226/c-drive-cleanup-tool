# ============================================
# CleanC 涓€閿墦鍖咃紙onedir + Velopack 鏇存柊鍖咃級
# 鐢ㄦ硶锛氬彸閿?浣跨敤 PowerShell 杩愯"
# 鎵撳寘缁撴灉鍦?Releases 鐩綍锛屽彂甯冨墠鍏堣繍琛屾湰鑴氭湰
# ============================================

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$PROJECT = "F:\CleanC_Project"
# 鍔ㄦ€佸畾浣?Marvis 杩愯鏃?Python锛堢増鏈洰褰曚細闅忓崌绾у彉鍖栵紝涓嶈兘鍐欐锛?$PYTHON = Get-ChildItem "E:\Program Files\Tencent\Marvis\MarvisAgent\*\runtime\python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $PYTHON) {
    Write-Host "鏈壘鍒?Marvis 杩愯鏃?Python锛岃鎵嬪姩淇敼鏈剼鏈腑鐨?\$PYTHON 璺緞" -ForegroundColor Red
    Read-Host "鎸夊洖杞﹂€€鍑?
    exit 1
}
$VERSION = "3.2.2"

Set-Location $PROJECT

Write-Host "绗?姝ワ細PyInstaller 鎵撳寘 onedir ..." -ForegroundColor Cyan
& $PYTHON -m PyInstaller --clean --noconfirm CleanC_onedir.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller 鎵撳寘澶辫触锛? -ForegroundColor Red
    Read-Host "鎸夊洖杞﹂€€鍑?
    exit 1
}

Write-Host "绗?姝ワ細vpk 鐢熸垚瀹夎鍖呭拰鏇存柊鍖?..." -ForegroundColor Cyan
vpk pack --packId CleanC --packVersion $VERSION --packDir "$PROJECT\dist\CleanC" --mainExe CleanC.exe --packTitle "C鐩樻竻鐞嗗伐鍏? --packAuthors "-_Hex" --shortcuts None --icon "$PROJECT\assets\CleanC.ico" --outputDir "$PROJECT\Releases"
if ($LASTEXITCODE -ne 0) {
    Write-Host "vpk 鎵撳寘澶辫触锛? -ForegroundColor Red
    Read-Host "鎸夊洖杞﹂€€鍑?
    exit 1
}

Write-Host "绗?姝ワ細PyInstaller 鎵撳寘瀹夎鍚戝 ..." -ForegroundColor Cyan
& $PYTHON -m PyInstaller --onefile --windowed --uac-admin --clean --noupx --name "CleanC瀹夎鍚戝" --icon "$PROJECT\assets\CleanC.ico" --add-data "$PROJECT\assets\CleanC.ico;." --add-binary "$PROJECT\Releases\CleanC-win-Setup.exe;." "$PROJECT\CleanC_Installer.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "瀹夎鍚戝鎵撳寘澶辫触锛? -ForegroundColor Red
    Read-Host "鎸夊洖杞﹂€€鍑?
    exit 1
}
Copy-Item "$PROJECT\dist\CleanC瀹夎鍚戝.exe" "$PROJECT\Releases\CleanC瀹夎鍚戝.exe" -Force

Write-Host "鎵撳寘瀹屾垚锛佷骇鐗╁湪 Releases 鐩綍锛? -ForegroundColor Green
Get-ChildItem "$PROJECT\Releases" | Select-Object Name, Length | Format-Table -AutoSize
Write-Host "涓嬩竴姝ワ細杩愯 鍙戝竷鍒癎itee.ps1 鍜?鍙戝竷鍒癎itHub.ps1 涓婁紶鏇存柊鍖? -ForegroundColor Yellow
Read-Host "鎸夊洖杞﹂€€鍑?







