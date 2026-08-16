# ============================================
# CleanC 一键发布到 Gitee（主源）
# 用法：先改下面的仓库地址和 token，再右键"使用 PowerShell 运行"
# 说明：Gitee 的 Gitea API 与 vpk 不兼容，这里用 Gitee 官方 API 直接上传
# ============================================

# ── 改成你自己的 ──────────────────────────
$GITEE_REPO = "https://gitee.com/Hex5226/c-drive-cleanup-tool"
$GITEE_TOKEN = "你的Gitee私人令牌"
# ─────────────────────────────────────────

$RELEASES_DIR = "F:\CleanC_Project\Releases"

if ($GITEE_REPO -match "你的用户名" -or $GITEE_TOKEN -eq "你的Gitee私人令牌") {
    Write-Host "请先编辑本脚本，填入你的 Gitee 仓库地址和私人令牌！" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

if (-not (Test-Path "$RELEASES_DIR\releases.win.json")) {
    Write-Host "没找到更新包，请先运行打包脚本生成 Releases 目录。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# 从 releases.win.json 解析版本号
$json = Get-Content "$RELEASES_DIR\releases.win.json" -Raw | ConvertFrom-Json
$VERSION = $json.Assets[0].Version
$OWNER = ($GITEE_REPO -replace "https://gitee.com/", "").Split("/")[0]
$REPO = ($GITEE_REPO -replace "https://gitee.com/", "").Split("/")[1]
$API = "https://gitee.com/api/v5/repos/$OWNER/$REPO"

Write-Host "版本: $VERSION  仓库: $OWNER/$REPO" -ForegroundColor Cyan

# 1. 检查/创建 tag（Gitee 要求 release 的 tag 必须已存在）
Write-Host "检查 tag $VERSION ..." -ForegroundColor Cyan
$tags = Invoke-RestMethod -Uri "$API/tags?access_token=$GITEE_TOKEN&per_page=100" -TimeoutSec 20
if ($tags.name -contains $VERSION) {
    Write-Host "tag 已存在，跳过创建" -ForegroundColor Yellow
} else {
    Write-Host "创建 tag $VERSION ..." -ForegroundColor Cyan
    $tagBody = @{ tag_name = $VERSION; refs = "master"; message = "CleanC $VERSION" } | ConvertTo-Json
    $tagCreated = Invoke-RestMethod -Method Post -Uri "$API/tags?access_token=$GITEE_TOKEN" -ContentType "application/json" -Body $tagBody -TimeoutSec 20
    if ($tagCreated.name) {
        Write-Host "tag 创建成功" -ForegroundColor Green
    } else {
        Write-Host "tag 创建失败" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
}

# 2. 查找或创建 release（tag = 版本号）
Write-Host "检查 release $VERSION ..." -ForegroundColor Cyan
$existing = Invoke-RestMethod -Uri "$API/releases/tags/$VERSION?access_token=$GITEE_TOKEN" -TimeoutSec 20
if ($existing.id) {
    $RELEASE_ID = $existing.id
    Write-Host "release 已存在 (id=$RELEASE_ID)，跳过创建" -ForegroundColor Yellow
} else {
    Write-Host "创建 release $VERSION ..." -ForegroundColor Cyan
    $body = @{ tag_name = $VERSION; name = "CleanC $VERSION"; body = "CleanC $VERSION 发布"; target_commitish = "master" } | ConvertTo-Json
    $created = Invoke-RestMethod -Method Post -Uri "$API/releases?access_token=$GITEE_TOKEN" -ContentType "application/json" -Body $body -TimeoutSec 20
    if ($created.id) {
        $RELEASE_ID = $created.id
        Write-Host "release 创建成功 (id=$RELEASE_ID)" -ForegroundColor Green
    } else {
        Write-Host "release 创建失败" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
}

# 2. 上传所有资产（已存在的跳过）
$FILES = @(
    "CleanC-win-Setup.exe",
    "CleanC-win-Portable.zip",
    "CleanC-$VERSION-full.nupkg",
    "CleanC-$VERSION-delta.nupkg",
    "releases.win.json",
    "RELEASES"
)

foreach ($f in $FILES) {
    $path = Join-Path $RELEASES_DIR $f
    if (-not (Test-Path $path)) {
        Write-Host "跳过（文件不存在）: $f" -ForegroundColor Yellow
        continue
    }
    Write-Host "上传 $f ..." -ForegroundColor Cyan
    $resp = curl.exe -s -X POST "$API/releases/$RELEASE_ID/attach_files?access_token=$GITEE_TOKEN&name=$f" -F "file=@$path" | ConvertFrom-Json
    if ($resp.id) {
        Write-Host "  成功" -ForegroundColor Green
    } else {
        Write-Host "  失败或已存在: $($resp | ConvertTo-Json -Compress)" -ForegroundColor Yellow
    }
}

Write-Host "`n发布完成！用户可在程序里点"检查更新"获取 $VERSION。" -ForegroundColor Green
Read-Host "按回车退出"
