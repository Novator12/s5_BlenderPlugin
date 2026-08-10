from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import bpy


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ADDON_PARENT = REPO_ROOT / "BlenderPlugin"
ADDON_NAME = "Novator12_DFF_Plugin_Blender_v5"
GAME_ROOT = Path(
    r"D:\Programme (x86)\Ubisoft\Blue Byte\DIE SIEDLER - Das Erbe der Könige - Gold Edition"
)
MODEL_ROOT = GAME_ROOT / "base" / "data" / "graphics" / "models"
ANIM_ROOT = GAME_ROOT / "base" / "data" / "graphics" / "animations"
OUTPUT_ROOT = REPO_ROOT / "docs" / "handbook" / "_test_output"

BUILDING_MODEL = MODEL_ROOT / "pb_farm2.dff"
BUILDING_ANIMATION = ANIM_ROOT / "pb_farm2_600.anm"
UNIT_MODEL = MODEL_ROOT / "cu_banditsoldiersword1.dff"
UNIT_ANIMATION = ANIM_ROOT / "cu_banditsoldiersword1_idle1.anm"


def op_result(value):
    return sorted(value) if isinstance(value, set) else value


def scene_snapshot(label: str) -> dict:
    objects = list(bpy.data.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    armatures = [obj for obj in objects if obj.type == "ARMATURE"]
    actions = list(bpy.data.actions)
    return {
        "label": label,
        "object_count": len(objects),
        "object_types": {
            object_type: sum(1 for obj in objects if obj.type == object_type)
            for object_type in sorted({obj.type for obj in objects})
        },
        "object_names": [obj.name for obj in objects],
        "mesh_count": len(meshes),
        "mesh_vertices": sum(len(obj.data.vertices) for obj in meshes),
        "mesh_edges": sum(len(obj.data.edges) for obj in meshes),
        "mesh_faces": sum(len(obj.data.polygons) for obj in meshes),
        "mesh_names": [obj.name for obj in meshes],
        "materials": sorted({slot.material.name for obj in meshes for slot in obj.material_slots if slot.material}),
        "armatures": [
            {
                "name": obj.name,
                "bone_count": len(obj.data.bones),
                "bone_names": [bone.name for bone in obj.data.bones],
            }
            for obj in armatures
        ],
        "actions": [
            {
                "name": action.name,
                "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])],
                "fps": getattr(action, "s5_anim_fps", None),
                "anim_format": getattr(action, "s5_anim_format", None),
                "export_name": getattr(action, "s5_export_name", None),
            }
            for action in actions
        ],
        "sphere_objects": [
            obj.name
            for obj in objects
            if obj.type == "MESH" and ("sphere" in obj.name.lower() or obj.display_type == "WIRE")
        ],
        "geometry_entries": len(getattr(bpy.context.scene, "geometry_tool_items", [])),
        "bone_mappings": len(getattr(bpy.context.scene, "bone_items", [])),
        "particle_effects": len(getattr(bpy.context.scene, "particle_effects", [])),
    }


def activate_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No armature found after import")
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    armature = armatures[0]
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    return armature


def clear_scene() -> dict:
    result = bpy.ops.scene.clear_all_objects()
    return {"operator": op_result(result), "snapshot": scene_snapshot("after_clear_scene")}


def file_info(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def run_step(report: dict, name: str, callback):
    try:
        report["steps"][name] = {"status": "PASS", "result": callback()}
    except Exception as exc:
        report["steps"][name] = {
            "status": "FAIL",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ADDON_PARENT))
    addon = __import__(ADDON_NAME)
    addon.register()

    report = {
        "blender_version": bpy.app.version_string,
        "blender_version_tuple": list(bpy.app.version),
        "addon": ADDON_NAME,
        "addon_bl_info": {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in addon.bl_info.items()
        },
        "inputs": {
            "building_model": file_info(BUILDING_MODEL),
            "building_animation": file_info(BUILDING_ANIMATION),
            "unit_model": file_info(UNIT_MODEL),
            "unit_animation": file_info(UNIT_ANIMATION),
        },
        "steps": {},
    }

    def building_import():
        result = bpy.ops.import_model.building(filepath=str(BUILDING_MODEL))
        return {"operator": op_result(result), "snapshot": scene_snapshot("building_import")}

    def building_animation_import():
        armature = activate_armature()
        result = bpy.ops.import_anim.building_anm(filepath=str(BUILDING_ANIMATION))
        return {
            "active_armature": armature.name,
            "operator": op_result(result),
            "snapshot": scene_snapshot("building_animation_import"),
        }

    def building_json_export():
        output = OUTPUT_ROOT / "pb_farm2_roundtrip.json"
        result = bpy.ops.export_model.building(filepath=str(output), file_format="JSON")
        return {"operator": op_result(result), "output": file_info(output)}

    def building_dff_export():
        output = OUTPUT_ROOT / "pb_farm2_roundtrip.dff"
        result = bpy.ops.export_model.building(filepath=str(output), file_format="DFF")
        return {"operator": op_result(result), "output": file_info(output)}

    def building_animation_json_export():
        activate_armature()
        output = OUTPUT_ROOT / "pb_farm2_roundtrip_600.json"
        result = bpy.ops.export_anim.building_anm(
            filepath=str(output), file_format="JSON", export_scope="ACTIVE"
        )
        return {"operator": op_result(result), "output": file_info(output)}

    def building_animation_anm_export():
        activate_armature()
        output = OUTPUT_ROOT / "pb_farm2_roundtrip_600.anm"
        result = bpy.ops.export_anim.building_anm(
            filepath=str(output), file_format="ANM", export_scope="ACTIVE"
        )
        return {"operator": op_result(result), "output": file_info(output)}

    def building_roundtrip_reimport():
        clear_scene()
        output = OUTPUT_ROOT / "pb_farm2_roundtrip.dff"
        result = bpy.ops.import_model.building(filepath=str(output))
        return {"operator": op_result(result), "snapshot": scene_snapshot("building_roundtrip")}

    run_step(report, "building_import_dff", building_import)
    run_step(report, "building_animation_import_anm", building_animation_import)
    run_step(report, "building_export_json", building_json_export)
    run_step(report, "building_export_dff", building_dff_export)
    run_step(report, "building_animation_export_json", building_animation_json_export)
    run_step(report, "building_animation_export_anm", building_animation_anm_export)
    run_step(report, "building_roundtrip_reimport_dff", building_roundtrip_reimport)
    run_step(report, "clear_before_unit", clear_scene)

    def unit_import():
        result = bpy.ops.import_model.unit(filepath=str(UNIT_MODEL))
        return {"operator": op_result(result), "snapshot": scene_snapshot("unit_import")}

    def unit_animation_import():
        armature = activate_armature()
        result = bpy.ops.import_anim.unit_anm(filepath=str(UNIT_ANIMATION))
        return {
            "active_armature": armature.name,
            "operator": op_result(result),
            "snapshot": scene_snapshot("unit_animation_import"),
        }

    def unit_json_export():
        activate_armature()
        output = OUTPUT_ROOT / "cu_banditsoldiersword1_roundtrip.json"
        result = bpy.ops.export_model.unit(filepath=str(output), file_format="JSON")
        return {"operator": op_result(result), "output": file_info(output)}

    def unit_dff_export():
        activate_armature()
        output = OUTPUT_ROOT / "cu_banditsoldiersword1_roundtrip.dff"
        result = bpy.ops.export_model.unit(filepath=str(output), file_format="DFF")
        return {"operator": op_result(result), "output": file_info(output)}

    def unit_animation_json_export():
        activate_armature()
        output = OUTPUT_ROOT / "cu_banditsoldiersword1_idle1_roundtrip.json"
        result = bpy.ops.export_anim.unit_anm(
            filepath=str(output), file_format="JSON", export_scope="ACTIVE"
        )
        return {"operator": op_result(result), "output": file_info(output)}

    def unit_animation_anm_export():
        activate_armature()
        output = OUTPUT_ROOT / "cu_banditsoldiersword1_idle1_roundtrip.anm"
        result = bpy.ops.export_anim.unit_anm(
            filepath=str(output), file_format="ANM", export_scope="ACTIVE"
        )
        return {"operator": op_result(result), "output": file_info(output)}

    def unit_roundtrip_reimport():
        clear_scene()
        output = OUTPUT_ROOT / "cu_banditsoldiersword1_roundtrip.dff"
        result = bpy.ops.import_model.unit(filepath=str(output))
        return {"operator": op_result(result), "snapshot": scene_snapshot("unit_roundtrip")}

    run_step(report, "unit_import_dff", unit_import)
    run_step(report, "unit_animation_import_anm", unit_animation_import)
    run_step(report, "unit_export_json", unit_json_export)
    run_step(report, "unit_export_dff", unit_dff_export)
    run_step(report, "unit_animation_export_json", unit_animation_json_export)
    run_step(report, "unit_animation_export_anm", unit_animation_anm_export)
    run_step(report, "unit_roundtrip_reimport_dff", unit_roundtrip_reimport)

    report_path = REPO_ROOT / "docs" / "handbook" / "runtime_audit.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"HANDBOOK_AUDIT_FILE={report_path}")
    print("HANDBOOK_AUDIT_JSON=" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
