# InstaOhangBot Environment Setup Script
param (
    [string]$TargetDir = (Get-Location).Path
)

Write-Host "========== InstaOhangBot Muhitini Sozlash ==========" -ForegroundColor Cyan

$binDir = Join-Path $TargetDir "bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}

# 1. FFmpeg download
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
if (!(Test-Path $ffmpegExe)) {
    Write-Host "[1/3] FFmpeg yuklab olinmoqda..." -ForegroundColor Yellow
    $ffmpegZip = Join-Path $binDir "ffmpeg.zip"
    $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
        Write-Host "FFmpeg unzip qilinmoqda..." -ForegroundColor Yellow
        Expand-Archive -Path $ffmpegZip -DestinationPath (Join-Path $binDir "ffmpeg_temp") -Force
        
        $foundFfmpeg = Get-ChildItem -Path (Join-Path $binDir "ffmpeg_temp") -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
        $foundFfprobe = Get-ChildItem -Path (Join-Path $binDir "ffmpeg_temp") -Filter "ffprobe.exe" -Recurse | Select-Object -First 1
        
        if ($foundFfmpeg) {
            Copy-Item -Path $foundFfmpeg.FullName -Destination $ffmpegExe -Force
        }
        if ($foundFfprobe) {
            Copy-Item -Path $foundFfprobe.FullName -Destination (Join-Path $binDir "ffprobe.exe") -Force
        }
        
        Remove-Item -Path $ffmpegZip -Force -ErrorAction SilentlyContinue
        Remove-Item -Path (Join-Path $binDir "ffmpeg_temp") -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "[+] FFmpeg tayyor!" -ForegroundColor Green
    } catch {
        Write-Host "[!] FFmpeg yuklashda xatolik: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[+] FFmpeg allaqachon mavjud." -ForegroundColor Green
}

# 2. Check Python or install standalone embedded Python
$pythonExe = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (!$pythonExe) {
    $pythonInBin = Join-Path $binDir "python\python.exe"
    if (!(Test-Path $pythonInBin)) {
        Write-Host "[2/3] Python 3.11 standalone yuklanmoqda..." -ForegroundColor Yellow
        $pythonZip = Join-Path $binDir "python.zip"
        $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
        
        Invoke-WebRequest -Uri $pyUrl -OutFile $pythonZip -UseBasicParsing
        $pyTarget = Join-Path $binDir "python"
        Expand-Archive -Path $pythonZip -DestinationPath $pyTarget -Force
        Remove-Item -Path $pythonZip -Force -ErrorAction SilentlyContinue
        
        # Enable site-packages in embed python
        $pthFile = Get-ChildItem -Path $pyTarget -Filter "python*._pth" | Select-Object -First 1
        if ($pthFile) {
            $content = Get-Content -Path $pthFile.FullName
            $content = $content -replace '#import site', 'import site'
            Set-Content -Path $pthFile.FullName -Value $content
        }

        # Download get-pip.py
        Write-Host "Pip o'rnatilmoqda..." -ForegroundColor Yellow
        $getPip = Join-Path $pyTarget "get-pip.py"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
        & (Join-Path $pyTarget "python.exe") $getPip --no-warn-script-location
        Remove-Item $getPip -Force -ErrorAction SilentlyContinue
    }
    $pythonExe = Join-Path $binDir "python\python.exe"
}

Write-Host "[+] Python joylashuvi: $pythonExe" -ForegroundColor Green

# 3. Requirements install
Write-Host "[3/3] Kutubxonalar o'rnatilmoqda (aiogram, yt-dlp, etc.)..." -ForegroundColor Yellow
$reqFile = Join-Path $TargetDir "requirements.txt"
& $pythonExe -m pip install --upgrade pip setuptools wheel --no-warn-script-location
& $pythonExe -m pip install -r $reqFile --no-warn-script-location

Write-Host "========== BARCHASI MUVAFFAQIYATLI SOZLANDI! ==========" -ForegroundColor Green
