# ============================================
# CleanC 一键发布到 GitHub（备源）
# 用法：先改下面的仓库地址和 token，再右键"使用 PowerShell 运行"
# ============================================

# ── 改成你自己的 ──────────────────────────
$GITHUB_REPO = "https://github.com/Hex5226/c-drive-cleanup-tool"
$GITHUB_TOKEN = "你的GitHub私人令牌"
# ─────────────────────────────────────────

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

$RELEASES_DIR = "F:\CleanC_Project\Releases"

if ($GITHUB_REPO -match "你的用户名" -or $GITHUB_TOKEN -eq "你的GitHub私人令牌") {
    Write-Host "请先编辑本脚本，填入你的 GitHub 仓库地址和私人令牌！" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

if (-not (Test-Path "$RELEASES_DIR\RELEASES")) {
    Write-Host "没找到更新包，请先运行打包脚本生成 Releases 目录。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

Write-Host "开始上传到 GitHub ..." -ForegroundColor Cyan
vpk upload github --outputDir $RELEASES_DIR --repoUrl $GITHUB_REPO --token $GITHUB_TOKEN --publish True

if ($LASTEXITCODE -eq 0) {
    Write-Host "发布成功！" -ForegroundColor Green
} else {
    Write-Host "发布失败，请检查仓库地址和令牌是否正确。" -ForegroundColor Red
}
Read-Host "按回车退出"
