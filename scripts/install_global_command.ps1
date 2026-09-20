# Install hcscoder-v2 globally into WindowsApps and User PATH
$appsDir = "C:\Users\hcsme\AppData\Local\Microsoft\WindowsApps"
Copy-Item "E:\AI\bin\hcscoder-v2.cmd" $appsDir -Force
Copy-Item "E:\AI\bin\hcscoder-v2.ps1" $appsDir -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*E:\AI\bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;E:\AI\bin", "User")
    Write-Host "[+] Added E:\AI\bin to User Path"
}

Write-Host "[+] Successfully installed hcscoder-v2 to $appsDir and User PATH"
