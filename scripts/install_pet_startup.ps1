# User-level normal companion autostart. Preview by default; never replaces another shortcut.
[CmdletBinding()]
param([switch]$Install, [string]$Receipt)
$ErrorActionPreference = 'Stop'
if ($Receipt -and (Test-Path -LiteralPath $Receipt)) { throw 'Receipt already exists; choose a new path.' }
$taskProfile = [Environment]::GetFolderPath('UserProfile')
$taskBase = Join-Path $taskProfile '.codex\tomc'
$taskPython = Join-Path $taskBase 'hourglass-ui\Scripts\pythonw.exe'
$taskLauncher = Join-Path $taskBase 'pet.pyw'
$taskStartup = [Environment]::GetFolderPath('Startup')
$taskShortcut = Join-Path $taskStartup 'TOMC Cat.lnk'
foreach ($taskFile in @($taskPython, $taskLauncher)) {
    if (-not (Test-Path -LiteralPath $taskFile -PathType Leaf)) { throw 'Installed normal companion is missing.' }
}
if (-not (Test-Path -LiteralPath $taskStartup -PathType Container)) { throw 'User Startup directory is missing.' }
$taskArgs = '"' + $taskLauncher + '"'
$taskShell = New-Object -ComObject WScript.Shell
$taskExists = Test-Path -LiteralPath $taskShortcut
if ($taskExists) {
    $taskLink = $taskShell.CreateShortcut($taskShortcut)
    if ($taskLink.TargetPath -ne $taskPython -or $taskLink.Arguments -ne $taskArgs) {
        throw 'An existing shortcut differs; it was not changed.'
    }
}
$taskStatus = if ($taskExists) { 'already_installed' } else { 'preview' }
if ($Install -and -not $taskExists) {
    if (Test-Path -LiteralPath $taskShortcut) { throw 'Startup shortcut appeared during installation.' }
    $taskLink = $taskShell.CreateShortcut($taskShortcut)
    $taskLink.TargetPath = $taskPython
    $taskLink.Arguments = $taskArgs
    $taskLink.WorkingDirectory = $taskBase
    $taskLink.Description = 'Start the normal TOMC companion at Windows sign-in.'
    $taskLink.WindowStyle = 7
    $taskLink.Save()
    $taskVerify = $taskShell.CreateShortcut($taskShortcut)
    if ($taskVerify.TargetPath -ne $taskPython -or $taskVerify.Arguments -ne $taskArgs) {
        throw 'Startup shortcut verification failed.'
    }
    $taskStatus = 'installed'
}
$taskReport = [ordered]@{
    checked_utc = [DateTime]::UtcNow.ToString('o')
    status = $taskStatus
    shortcut = $taskShortcut
    target = $taskPython
    arguments = $taskArgs
    trigger = 'windows_user_sign_in'
    demo = $false
    other_shortcuts_changed = $false
    sha256 = $(if (Test-Path -LiteralPath $taskShortcut) { (Get-FileHash -LiteralPath $taskShortcut -Algorithm SHA256).Hash } else { $null })
}
$taskJson = $taskReport | ConvertTo-Json -Depth 4
if ($Receipt) {
    if (Test-Path -LiteralPath $Receipt) { throw 'Receipt already exists; choose a new path.' }
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($Receipt), $taskJson, [Text.UTF8Encoding]::new($false))
}
$taskJson
