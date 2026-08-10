"""Prepare the final handbook figure set from authentic Blender captures.

The source images are lossless screenshots produced by blender_ui_capture.py
in Blender 5.0.1. Most figures are copied byte-for-byte. Figure 3 combines
the full Weight Paint view with the matching Object Data Properties crop so
the bone-name/vertex-group relationship is readable on one handbook page.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw


HANDBOOK_DIR = Path(__file__).resolve().parents[1]
CAPTURE_DIR = HANDBOOK_DIR / "_focused_capture"
IMAGE_DIR = HANDBOOK_DIR / "images"


COPY_MAP = {
    "fig-02-armature-bones-detail.png": "detail-unit-armature.png",
    "fig-06-pb-factory-overview.png": "detail-factory-overview.png",
    "fig-07-building-geometry-validation-detail.png": "detail-factory-geometry-tools.png",
    "fig-09-building-bone-manager-detail.png": "detail-factory-bone-manager.png",
    "fig-10-building-sphere-detail.png": "detail-factory-sphere.png",
    "fig-11-building-particle-detail.png": "detail-factory-particle-tools.png",
    "fig-16-unit-overview.png": "detail-unit-overview.png",
    "fig-17-unit-mesh-edit-detail.png": "detail-unit-topology.png",
    "fig-18-unit-armature-detail.png": "detail-unit-armature.png",
    "fig-19-unit-weight-paint-detail.png": "detail-unit-weight-paint.png",
    "fig-20-unit-selection-sphere-detail.png": "detail-unit-selection-sphere.png",
}


def require(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def build_weight_relationship_figure() -> None:
    weight_path = require(CAPTURE_DIR / "detail-unit-weight-paint.png")
    groups_path = require(CAPTURE_DIR / "detail-unit-vertex-groups.png")
    output = IMAGE_DIR / "fig-03-vertex-groups-weights-detail.png"

    with Image.open(weight_path) as weight_source, Image.open(groups_path) as groups_source:
        weight = weight_source.convert("RGB")
        groups = groups_source.convert("RGB")

        # Keep the active group name in the Weight Paint header and the whole
        # character, while removing unused viewport space on the far right.
        main = weight.crop((0, 0, 1380, weight.height))
        canvas = Image.new("RGB", (1800, weight.height), (28, 28, 28))
        canvas.paste(main, (0, 0))

        panel_x = 1410
        panel_y = max(0, (canvas.height - groups.height) // 2)
        canvas.paste(groups, (panel_x, panel_y))

        # A restrained Blender-blue frame links the close-up to the main view
        # without altering any captured labels or values.
        draw = ImageDraw.Draw(canvas)
        accent = (77, 145, 196)
        draw.line((1393, 38, 1393, canvas.height - 38), fill=accent, width=4)
        draw.rounded_rectangle(
            (panel_x - 5, panel_y - 5, panel_x + groups.width + 5, panel_y + groups.height + 5),
            radius=8,
            outline=accent,
            width=4,
        )
        canvas.save(output, format="PNG", optimize=True)


def build_mesh_components_figure() -> None:
    source_path = require(CAPTURE_DIR / "detail-factory-topology.png")
    output = IMAGE_DIR / "fig-01-mesh-components-detail.png"
    with Image.open(source_path) as source:
        bitmap = source.convert("RGB")
        # Retain the Edit Mode/header controls while removing the unrelated
        # far-right sidebar. This makes vertices, edges, and triangular faces
        # materially larger on the handbook page.
        crop = bitmap.crop((0, 0, min(1120, bitmap.width), bitmap.height))
        crop.save(output, format="PNG", optimize=True)


def build_geometry_material_figure() -> None:
    source_path = require(CAPTURE_DIR / "detail-factory-geometry-material.png")
    output = IMAGE_DIR / "fig-08-building-geometry-material-detail.png"
    with Image.open(source_path) as source:
        bitmap = source.convert("RGB")
        # Focus on the selected Kran Geometry entry and its export-facing
        # object/material fields.  Removing the unrelated viewport and Mesh
        # Validation area makes every field readable in the printed handbook.
        left = min(220, bitmap.width)
        top = min(540, bitmap.height)
        crop = bitmap.crop((left, top, bitmap.width, bitmap.height))
        crop.save(output, format="PNG", optimize=True)


def build_action_timeline_figures() -> None:
    source_path = require(CAPTURE_DIR / "detail-factory-action-timeline.png")
    with Image.open(source_path) as source:
        bitmap = source.convert("RGB")
        # The useful evidence is in the Action Editor header, channel list,
        # key columns and keyed frames.  The lower editor was mostly empty and
        # made those labels unnecessarily small on paper.
        crop = bitmap.crop((0, 0, bitmap.width, min(330, bitmap.height)))
        for destination_name in (
            "fig-12-building-animation-detail.png",
            "fig-14-building-animation-export-detail.png",
        ):
            crop.save(IMAGE_DIR / destination_name, format="PNG", optimize=True)


def build_menu_figures() -> None:
    """Create focused menu evidence with restrained editorial outlines."""

    accent = (226, 75, 60)
    menu_specs = {
        "detail-import-menu.png": {
            "fig-04-import-menu-detail.png": (224, 299, 480, 380),
            "fig-15-unit-import-detail.png": (224, 339, 480, 360),
        },
        "detail-export-menu.png": {
            "fig-05-export-menu-detail.png": (224, 279, 480, 360),
            "fig-13-building-export-detail.png": (224, 279, 480, 300),
            "fig-21-unit-animation-detail.png": (224, 339, 480, 360),
            "fig-22-unit-export-detail.png": (224, 319, 480, 340),
        },
    }
    for source_name, destinations in menu_specs.items():
        source_path = require(CAPTURE_DIR / source_name)
        with Image.open(source_path) as source:
            bitmap = source.convert("RGB")
            for destination_name, box in destinations.items():
                annotated = bitmap.copy()
                draw = ImageDraw.Draw(annotated)
                draw.rounded_rectangle(box, radius=6, outline=accent, width=3)
                annotated.save(IMAGE_DIR / destination_name, format="PNG", optimize=True)


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for destination_name, source_name in COPY_MAP.items():
        source = require(CAPTURE_DIR / source_name)
        shutil.copy2(source, IMAGE_DIR / destination_name)
    build_mesh_components_figure()
    build_weight_relationship_figure()
    build_geometry_material_figure()
    build_action_timeline_figures()
    build_menu_figures()

    expected = sorted(COPY_MAP) + [
        "fig-01-mesh-components-detail.png",
        "fig-03-vertex-groups-weights-detail.png",
        "fig-04-import-menu-detail.png",
        "fig-05-export-menu-detail.png",
        "fig-08-building-geometry-material-detail.png",
        "fig-12-building-animation-detail.png",
        "fig-13-building-export-detail.png",
        "fig-14-building-animation-export-detail.png",
        "fig-15-unit-import-detail.png",
        "fig-21-unit-animation-detail.png",
        "fig-22-unit-export-detail.png",
    ]
    for name in sorted(expected):
        path = require(IMAGE_DIR / name)
        with Image.open(path) as bitmap:
            print(f"{name}: {bitmap.width}x{bitmap.height}")


if __name__ == "__main__":
    main()
