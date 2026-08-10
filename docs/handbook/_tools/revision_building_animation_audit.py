from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import bpy


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
OUTPUT_ROOT = REPO_ROOT / "docs" / "handbook" / "_revision_test_output" / "building"


def activate_armature() -> bpy.types.Object:
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    return armature


def attempt(label: str, callback, output: Path | None = None) -> dict[str, object]:
    try:
        result = callback()
        return {
            "label": label,
            "status": "PASS",
            "operator": sorted(result),
            "output": str(output) if output else None,
            "bytes": output.stat().st_size if output and output.exists() else None,
        }
    except Exception as exc:
        return {
            "label": label,
            "status": "FAIL",
            "exception": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    armature = activate_armature()
    action = armature.animation_data.action if armature.animation_data else None
    before = {
        "armature": armature.name,
        "action": action.name if action else None,
        "range": list(action.frame_range) if action else None,
        "scene_fps": bpy.context.scene.render.fps,
    }
    json_path = OUTPUT_ROOT / "PB_Factory_600_revision.json"
    anm_path = OUTPUT_ROOT / "PB_Factory_600_revision.anm"
    steps = [
        attempt(
            "animation_json_export",
            lambda: bpy.ops.export_anim.building_anm(
                filepath=str(json_path), file_format="JSON", export_scope="ACTIVE"
            ),
            json_path,
        ),
        attempt(
            "animation_anm_export",
            lambda: bpy.ops.export_anim.building_anm(
                filepath=str(anm_path), file_format="ANM", export_scope="ACTIVE"
            ),
            anm_path,
        ),
    ]

    reimport = None
    model_path = OUTPUT_ROOT / "PB_Factory_revision.dff"
    if anm_path.exists() and model_path.exists():
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.import_model.building(filepath=str(model_path))
        armature = activate_armature()
        result = attempt(
            "animation_anm_reimport",
            lambda: bpy.ops.import_anim.building_anm(filepath=str(anm_path)),
        )
        imported_action = armature.animation_data.action if armature.animation_data else None
        result["action"] = imported_action.name if imported_action else None
        result["range"] = list(imported_action.frame_range) if imported_action else None
        reimport = result

    print(
        "HANDBOOK_BUILDING_ANIMATION_AUDIT="
        + json.dumps({"before": before, "exports": steps, "reimport": reimport}),
        flush=True,
    )


if __name__ == "__main__":
    main()
