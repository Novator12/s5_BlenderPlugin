param(
    [Parameter(Mandatory = $true)]
    [int]$BlenderProcessId,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [ValidateSet("Window", "Client", "CustomClient")]
    [string]$RegionMode = "Window",

    [ValidateRange(0, 32768)]
    [int]$CropX = 0,

    [ValidateRange(0, 32768)]
    [int]$CropY = 0,

    [ValidateRange(0, 32768)]
    [int]$CropWidth = 0,

    [ValidateRange(0, 32768)]
    [int]$CropHeight = 0,

    [ValidateRange(1, 60)]
    [int]$WaitForWindowSeconds = 15,

    [ValidateRange(0, 5000)]
    [int]$SettleMilliseconds = 500,

    [switch]$Force
)

Add-Type -AssemblyName System.Drawing
if (-not ("HandbookWindowCapture" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class HandbookWindowCapture
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int command);

    [DllImport("user32.dll")]
    public static extern bool SetProcessDpiAwarenessContext(IntPtr value);

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
    }
}
"@
}

[void][HandbookWindowCapture]::SetProcessDpiAwarenessContext([IntPtr](-4))
$deadline = [DateTime]::UtcNow.AddSeconds($WaitForWindowSeconds)
$handle = [IntPtr]::Zero
do {
    $process = Get-Process -Id $BlenderProcessId -ErrorAction Stop
    $process.Refresh()
    $handle = $process.MainWindowHandle
    if ($handle -ne [IntPtr]::Zero) {
        break
    }
    Start-Sleep -Milliseconds 100
} while ([DateTime]::UtcNow -lt $deadline)
if ($handle -eq [IntPtr]::Zero) {
    throw "Blender PID $BlenderProcessId did not expose a visible main window within $WaitForWindowSeconds seconds."
}

[void][HandbookWindowCapture]::ShowWindowAsync($handle, 9) # SW_RESTORE
[void][HandbookWindowCapture]::SetForegroundWindow($handle)
Start-Sleep -Milliseconds $SettleMilliseconds

[HandbookWindowCapture+RECT]$windowRect = New-Object HandbookWindowCapture+RECT
if (-not [HandbookWindowCapture]::GetWindowRect($handle, [ref]$windowRect)) {
    throw "GetWindowRect failed for Blender PID $BlenderProcessId."
}
[HandbookWindowCapture+RECT]$clientRect = New-Object HandbookWindowCapture+RECT
if (-not [HandbookWindowCapture]::GetClientRect($handle, [ref]$clientRect)) {
    throw "GetClientRect failed for Blender PID $BlenderProcessId."
}
[HandbookWindowCapture+POINT]$clientOrigin = New-Object HandbookWindowCapture+POINT
$clientOrigin.X = 0
$clientOrigin.Y = 0
if (-not [HandbookWindowCapture]::ClientToScreen($handle, [ref]$clientOrigin)) {
    throw "ClientToScreen failed for Blender PID $BlenderProcessId."
}

$clientWidth = $clientRect.Right - $clientRect.Left
$clientHeight = $clientRect.Bottom - $clientRect.Top
switch ($RegionMode) {
    "Window" {
        $sourceX = $windowRect.Left
        $sourceY = $windowRect.Top
        $width = $windowRect.Right - $windowRect.Left
        $height = $windowRect.Bottom - $windowRect.Top
    }
    "Client" {
        $sourceX = $clientOrigin.X
        $sourceY = $clientOrigin.Y
        $width = $clientWidth
        $height = $clientHeight
    }
    "CustomClient" {
        if ($CropWidth -le 0 -or $CropHeight -le 0) {
            throw "CustomClient requires positive -CropWidth and -CropHeight."
        }
        if ($CropX + $CropWidth -gt $clientWidth -or $CropY + $CropHeight -gt $clientHeight) {
            throw "Custom client crop ($CropX,$CropY,$CropWidth,$CropHeight) exceeds the client area ${clientWidth}x${clientHeight}."
        }
        $sourceX = $clientOrigin.X + $CropX
        $sourceY = $clientOrigin.Y + $CropY
        $width = $CropWidth
        $height = $CropHeight
    }
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
if ([System.IO.File]::Exists($resolvedOutput) -and -not $Force) {
    throw "Capture output already exists: $resolvedOutput. Pass -Force only after reviewing the target."
}
if ($width -lt 64 -or $height -lt 64) {
    throw "Refusing implausibly small capture area ${width}x${height}."
}

$bitmap = New-Object System.Drawing.Bitmap(
    $width,
    $height,
    [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $graphics.CopyFromScreen(
        $sourceX,
        $sourceY,
        0,
        0,
        [System.Drawing.Size]::new($width, $height),
        [System.Drawing.CopyPixelOperation]::SourceCopy
    )
    [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($resolvedOutput)) | Out-Null
    $bitmap.Save($resolvedOutput, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output "CAPTURE=$resolvedOutput MODE=$RegionMode SIZE=${width}x${height} SOURCE=($sourceX,$sourceY) PID=$BlenderProcessId"
}
finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}
