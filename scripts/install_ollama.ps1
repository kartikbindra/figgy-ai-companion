$ErrorActionPreference = "Stop"

$destDir = "$env:LOCALAPPDATA\Programs\Ollama"
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
}

$zipPath = "$env:TEMP\ollama-windows-amd64.zip"
$url = "https://github.com/ollama/ollama/releases/download/v0.40.15/ollama-windows-amd64.zip"

Write-Host "Downloading Ollama v0.40.15 from $url..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
(New-Object System.Net.WebClient).DownloadFile($url, $zipPath)

Write-Host "Extracting to $destDir..."
Expand-Archive -Path $zipPath -DestinationPath $destDir -Force

$ollamaExe = "$destDir\ollama.exe"
if (Test-Path $ollamaExe) {
    Write-Host "Ollama installed successfully at $ollamaExe!"
    
    # Add to current process PATH and user PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$destDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$destDir", "User")
        Write-Host "Added $destDir to User PATH."
    }
} else {
    Write-Error "ollama.exe not found after extraction."
}
