from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import bpy


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ADDON_PARENT = REPO_ROOT / "BlenderPlugin"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("building", "unit"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def ensure_addon() -> None:
    if hasattr(bpy.ops.import_model, "unit") and hasattr(bpy.ops.export_model, "building"):
        return
    sys.path.insert(0, str(ADDON_PARENT))
    addon = __import__("Novator12_DFF_Plugin_Blender_v5")
    addon.register()


def activate_armature() -> bpy.types.Object:
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    bpy.ops.object.select_all(action="DESELECT")
    armature.hide_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    return armature


def file_result(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def run_export(label: str, callback, path: Path) -> dict[str, object]:
    try:
        result = callback()
        return {"label": label, "status": "PASS", "operator": sorted(result), **file_result(path)}
    except Exception as exc:
        return {
            "label": label,
            "status": "FAIL",
            "exception": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            **file_result(path),
        }


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_addon()

    if args.kind == "unit":
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        import_result = bpy.ops.import_model.unit(filepath=str(source))
    else:
        import_result = {"BLEND_ALREADY_OPEN"}

    armature = activate_armature()
    base = source.stem
    json_path = output_dir / f"{base}_revision.json"
    dff_path = output_dir / f"{base}_revision.dff"
    operator = bpy.ops.export_model.building if args.kind == "building" else bpy.ops.export_model.unit
    exports = [
        run_export(
            "json_export",
            lambda: operator(filepath=str(json_path), file_format="JSON"),
            json_path,
        ),
        run_export(
            "dff_export",
            lambda: operator(filepath=str(dff_path), file_format="DFF"),
            dff_path,
        ),
    ]
    report = {
        "kind": args.kind,
        "source": str(source),
        "import_result": sorted(import_result),
        "armature": armature.name,
        "exports": exports,
    }
    print("HANDBOOK_REVISION_AUDIT=" + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
