[CmdletBinding()]
param(
    [string]$BlenderPath = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",

    [string]$OutputDirectory,

    [ValidateSet(
        "detail_import_menu",
        "detail_export_menu",
        "detail_factory_overview",
        "detail_factory_topology",
        "detail_factory_uv_layout",
        "detail_factory_material_nodes",
        "detail_factory_geometry_tools",
        "detail_factory_geometry_material",
        "detail_factory_particle_tools",
        "detail_factory_sphere",
        "detail_factory_bone_manager",
        "detail_factory_action_timeline",
        "detail_unit_overview",
        "detail_unit_topology",
        "detail_unit_armature",
        "detail_unit_weight_paint",
        "detail_unit_vertex_groups",
        "detail_unit_uv_layout",
        "detail_unit_selection_sphere"
    )]
    [string[]]$Mode = @(
        "detail_import_menu",
        "detail_export_menu",
        "detail_factory_overview",
        "detail_factory_topology",
        "detail_factory_uv_layout",
        "detail_factory_material_nodes",
        "detail_factory_geometry_tools",
        "detail_factory_geometry_material",
        "detail_factory_particle_tools",
        "detail_factory_sphere",
        "detail_factory_bone_manager",
        "detail_factory_action_timeline",
        "detail_unit_overview",
        "detail_unit_topology",
        "detail_unit_armature",
        "detail_unit_weight_paint",
        "detail_unit_vertex_groups",
        "detail_unit_uv_layout",
        "detail_unit_selection_sphere"
    ),

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$handbookDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $handbookDirectory "..\.."))
$captureScript = Join-Path $PSScriptRoot "blender_ui_capture.py"
$factoryBlend = Join-Path $handbookDirectory "_test\PB_Factory.blend"
$unitDff = Join-Path $handbookDirectory "_test\pu_leadersword4.dff"
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $handbookDirectory "_focused_capture"
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

$requiredFiles = @($BlenderPath, $captureScript, $factoryBlend, $unitDff)
foreach ($requiredFile in $requiredFiles) {
    if (-not [System.IO.File]::Exists($requiredFile)) {
        throw "Required capture input does not exist: $requiredFile"
    }
}

$specifications = [ordered]@{
    detail_import_menu             = @{ Asset = "General"; File = "detail-import-menu.png" }
    detail_export_menu             = @{ Asset = "General"; File = "detail-export-menu.png" }
    detail_factory_overview       = @{ Asset = "Factory"; File = "detail-factory-overview.png" }
    detail_factory_topology       = @{ Asset = "Factory"; File = "detail-factory-topology.png" }
    detail_factory_uv_layout      = @{ Asset = "Factory"; File = "detail-factory-uv-layout.png" }
    detail_factory_material_nodes = @{ Asset = "Factory"; File = "detail-factory-material-nodes.png" }
    detail_factory_geometry_tools = @{ Asset = "Factory"; File = "detail-factory-geometry-tools.png" }
    detail_factory_geometry_material = @{ Asset = "Factory"; File = "detail-factory-geometry-material.png" }
    detail_factory_particle_tools = @{ Asset = "Factory"; File = "detail-factory-particle-tools.png" }
    detail_factory_sphere         = @{ Asset = "Factory"; File = "detail-factory-sphere.png" }
    detail_factory_bone_manager   = @{ Asset = "Factory"; File = "detail-factory-bone-manager.png" }
    detail_factory_action_timeline = @{ Asset = "Factory"; File = "detail-factory-action-timeline.png" }
    detail_unit_overview          = @{ Asset = "Unit"; File = "detail-unit-overview.png" }
    detail_unit_topology          = @{ Asset = "Unit"; File = "detail-unit-topology.png" }
    detail_unit_armature          = @{ Asset = "Unit"; File = "detail-unit-armature.png" }
    detail_unit_weight_paint      = @{ Asset = "Unit"; File = "detail-unit-weight-paint.png" }
    detail_unit_vertex_groups     = @{ Asset = "Unit"; File = "detail-unit-vertex-groups.png" }
    detail_unit_uv_layout         = @{ Asset = "Unit"; File = "detail-unit-uv-layout.png" }
    detail_unit_selection_sphere  = @{ Asset = "Unit"; File = "detail-unit-selection-sphere.png" }
}

[System.IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
Add-Type -AssemblyName System.Drawing

function Complete-FocusedCrop {
    param([Parameter(Mandatory = $true)][string]$FinalPath)

    if ([System.IO.File]::Exists($FinalPath)) {
        return
    }
    $directory = [System.IO.Path]::GetDirectoryName($FinalPath)
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($FinalPath)
    $fullPath = Join-Path $directory ".${stem}-full.png"
    $cropSpecPath = Join-Path $directory ".${stem}-crop.json"
    if (-not [System.IO.File]::Exists($fullPath) -or -not [System.IO.File]::Exists($cropSpecPath)) {
        throw "Focused capture did not create a final PNG or its full-frame crop pair: $FinalPath"
    }

    $cropSpec = Get-Content -Raw $cropSpecPath | ConvertFrom-Json
    $source = [System.Drawing.Image]::FromFile($fullPath)
    try {
        $left = [Math]::Max(0, [Math]::Round($cropSpec.x0 * $source.Width / $cropSpec.screen_width))
        $right = [Math]::Min($source.Width, [Math]::Round($cropSpec.x1 * $source.Width / $cropSpec.screen_width))
        $top = [Math]::Max(0, [Math]::Round(($cropSpec.screen_height - $cropSpec.y1) * $source.Height / $cropSpec.screen_height))
        $bottom = [Math]::Min($source.Height, [Math]::Round(($cropSpec.screen_height - $cropSpec.y0) * $source.Height / $cropSpec.screen_height))
        $width = [int]($right - $left)
        $height = [int]($bottom - $top)
        if ($width -lt 160 -or $height -lt 160) {
            throw "Calculated crop is implausibly small (${width}x${height}) for $FinalPath"
        }

        $cropped = New-Object System.Drawing.Bitmap(
            $width,
            $height,
            [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
        )
        $graphics = [System.Drawing.Graphics]::FromImage($cropped)
        try {
            $graphics.DrawImage(
                $source,
                [System.Drawing.Rectangle]::new(0, 0, $width, $height),
                [System.Drawing.Rectangle]::new([int]$left, [int]$top, $width, $height),
                [System.Drawing.GraphicsUnit]::Pixel
            )
            $cropped.Save($FinalPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $graphics.Dispose()
            $cropped.Dispose()
        }
    }
    finally {
        $source.Dispose()
    }
    Remove-Item -LiteralPath $fullPath -Force
    Remove-Item -LiteralPath $cropSpecPath -Force
}

foreach ($captureMode in $Mode) {
    $specification = $specifications[$captureMode]
    if ($null -eq $specification) {
        throw "No capture specification exists for mode: $captureMode"
    }
    $outputPath = Join-Path $OutputDirectory $specification.File
    if ([System.IO.File]::Exists($outputPath) -and -not $Force) {
        throw "Output already exists: $outputPath. Review it, then pass -Force to replace it."
    }
    if ([System.IO.File]::Exists($outputPath) -and $Force) {
        Remove-Item -LiteralPath $outputPath -Force
    }

    $arguments = [System.Collections.Generic.List[string]]::new()
    $arguments.Add("--factory-startup")
    $arguments.Add("--window-geometry")
    $arguments.Add("40")
    $arguments.Add("40")
    $arguments.Add("2048")
    $arguments.Add("1152")
    if ($specification.Asset -eq "Factory") {
        # The source file is loaded before the Python script so its saved
        # add-on metadata is available to focused Geometry/Particle captures.
        $arguments.Add($factoryBlend)
    }
    $arguments.Add("--python")
    $arguments.Add($captureScript)
    $arguments.Add("--")
    $arguments.Add("--mode")
    $arguments.Add($captureMode)
    $arguments.Add("--output")
    $arguments.Add($outputPath)
    if ($Force) {
        $arguments.Add("--allow-overwrite")
    }

    Write-Host "Capturing $captureMode -> $outputPath"
    & $BlenderPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Blender exited with code $LASTEXITCODE while capturing $captureMode"
    }
    Complete-FocusedCrop -FinalPath $outputPath
    if (-not [System.IO.File]::Exists($outputPath)) {
        throw "Blender did not create the expected capture: $outputPath"
    }

    $bitmap = [System.Drawing.Image]::FromFile($outputPath)
    try {
        if ($bitmap.Width -lt 160 -or $bitmap.Height -lt 160) {
            throw "Capture is implausibly small ($($bitmap.Width)x$($bitmap.Height)): $outputPath"
        }
        Write-Host "Verified $($bitmap.Width)x$($bitmap.Height): $outputPath"
    }
    finally {
        $bitmap.Dispose()
    }
}

Write-Host "Focused Blender 5.0.1 capture set complete: $OutputDirectory"
