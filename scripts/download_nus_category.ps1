param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Regular", "Running", "QuickRotation", "Zooming", "Parallax", "Crowd")]
    [string] $Category,

    [string] $ZipDir = "data\sources\NUS_raw_zips",
    [string] $ExtractRoot = "data\sources\NUS_extracted",
    [int] $MaxTimeSeconds = 900,
    [int] $SpeedTimeSeconds = 30,
    [int] $SpeedLimitBytes = 1024,
    [int] $ChunkSizeMB = 0,
    [switch] $Extract
)

$ErrorActionPreference = "Stop"

$urls = @{
    "Regular"       = "http://liushuaicheng.org/SIGGRAPH2013/data/Regular.zip"
    "Running"       = "http://liushuaicheng.org/SIGGRAPH2013/data/Running.zip"
    "QuickRotation" = "http://liushuaicheng.org/SIGGRAPH2013/data/QuickRotation.zip"
    "Zooming"       = "http://liushuaicheng.org/SIGGRAPH2013/data/Zooming.zip"
    "Parallax"      = "http://liushuaicheng.org/SIGGRAPH2013/data/Parallax.zip"
    "Crowd"         = "http://liushuaicheng.org/SIGGRAPH2013/data/Crowd.zip"
}

function Resolve-WorkspacePath([string] $PathText) {
    $path = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathText))
    $root = [System.IO.Path]::GetFullPath((Get-Location).Path)
    if (-not $path.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved path is outside workspace: $path"
    }
    return $path
}

$zipDirAbs = Resolve-WorkspacePath $ZipDir
$extractRootAbs = Resolve-WorkspacePath $ExtractRoot
New-Item -ItemType Directory -Force -Path $zipDirAbs | Out-Null
New-Item -ItemType Directory -Force -Path $extractRootAbs | Out-Null

$zipPath = Join-Path $zipDirAbs "$Category.zip"
$url = $urls[$Category]

Write-Host "Downloading $Category"
Write-Host "  url: $url"
Write-Host "  zip: $zipPath"

$remoteLength = $null
try {
    $head = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 30
    $remoteLength = [int64]$head.Headers["Content-Length"]
    Write-Host "  remote_size_bytes: $remoteLength"
} catch {
    Write-Host "  warning: could not read remote Content-Length; continuing with curl resume"
}

if ((Test-Path -LiteralPath $zipPath) -and $remoteLength) {
    $localLength = (Get-Item -LiteralPath $zipPath).Length
    if ($localLength -eq $remoteLength) {
        Write-Host "  local file already complete; skip download"
    } elseif ($localLength -gt $remoteLength) {
        Write-Host "  local file is larger than remote; truncating to remote size"
        $fs = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write)
        try {
            $fs.SetLength($remoteLength)
        } finally {
            $fs.Close()
        }
    }
}

if (-not ((Test-Path -LiteralPath $zipPath) -and $remoteLength -and ((Get-Item -LiteralPath $zipPath).Length -eq $remoteLength))) {
    if ($ChunkSizeMB -gt 0 -and $remoteLength) {
        $chunkSize = [int64]$ChunkSizeMB * 1024 * 1024
        $partDir = Join-Path $zipDirAbs "$Category.parts"
        New-Item -ItemType Directory -Force -Path $partDir | Out-Null
        $partPaths = @()
        for ($start = [int64]0; $start -lt $remoteLength; $start += $chunkSize) {
            $end = [Math]::Min($start + $chunkSize - 1, $remoteLength - 1)
            $partPath = Join-Path $partDir ("{0:D12}-{1:D12}.part" -f $start, $end)
            $partPaths += $partPath
            $expectedSize = $end - $start + 1
            if ((Test-Path -LiteralPath $partPath) -and ((Get-Item -LiteralPath $partPath).Length -eq $expectedSize)) {
                Write-Host "  part exists: $partPath"
                continue
            }
            Write-Host "  downloading range $start-$end -> $partPath"
            curl.exe -L `
                --range "$start-$end" `
                --retry 3 `
                --retry-delay 5 `
                --max-time $MaxTimeSeconds `
                --speed-time $SpeedTimeSeconds `
                --speed-limit $SpeedLimitBytes `
                -A "Mozilla/5.0" `
                -o $partPath `
                $url
            $part = Get-Item -LiteralPath $partPath
            if ($part.Length -ne $expectedSize) {
                throw "Part size mismatch: $partPath expected=$expectedSize actual=$($part.Length)"
            }
        }

        Write-Host "  assembling chunks -> $zipPath"
        $out = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
        try {
            foreach ($partPath in $partPaths) {
                $bytes = [System.IO.File]::ReadAllBytes($partPath)
                $out.Write($bytes, 0, $bytes.Length)
            }
        } finally {
            $out.Close()
        }
    } else {
    curl.exe -L -C - `
        --retry 3 `
        --retry-delay 5 `
        --max-time $MaxTimeSeconds `
        --speed-time $SpeedTimeSeconds `
        --speed-limit $SpeedLimitBytes `
        -A "Mozilla/5.0" `
        -o $zipPath `
        $url
    }
}

$zip = Get-Item -LiteralPath $zipPath
Write-Host "downloaded_size_bytes: $($zip.Length)"

if ($Extract) {
    Write-Host "Extracting $zipPath -> $extractRootAbs"
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRootAbs -Force
    $target = Join-Path $extractRootAbs $Category
    if (Test-Path -LiteralPath $target) {
        $aviCount = (Get-ChildItem -LiteralPath $target -File -Filter "*.avi" | Measure-Object).Count
        Write-Host "extracted_dir: $target"
        Write-Host "avi_count: $aviCount"
    } else {
        Write-Host "warning: expected extracted directory not found: $target"
    }
}
