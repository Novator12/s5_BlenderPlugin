import json
import os

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .building_utilities import (
    DEFAULT_S5_FPS,
    build_animation_export_json,
    convert_json_to_anm_external,
    ensure_armature_active,
    resolve_export_root_id,
)


def _build_active_animation_payload(context, filepath):
    armature_object = ensure_armature_active()
    if not armature_object.animation_data or not armature_object.animation_data.action:
        raise RuntimeError("Keine aktive Action auf der Armature gefunden.")

    action = armature_object.animation_data.action
    scene = context.scene
    frame_start = int(scene.frame_start)
    frame_end = int(scene.frame_end)
    fps = int(scene.render.fps) if scene.render.fps > 0 else DEFAULT_S5_FPS
    root_id = resolve_export_root_id(armature_object, filepath)

    return build_animation_export_json(
        arm_ob=armature_object,
        root_id=root_id,
        action=action,
        frame_start=frame_start,
        frame_end=frame_end,
        fps=fps,
        source_name=os.path.basename(filepath),
    )


class BuildingAnmExportOperator(Operator, ExportHelper):
    bl_idname = "export_anim.building_anm"
    bl_label = "Novator-Export-Buidling-Anm(.anm)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={"HIDDEN"})

    def execute(self, context):
        current_frame = context.scene.frame_current
        try:
            payload = _build_active_animation_payload(context, self.filepath)
            convert_json_to_anm_external(payload, self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            context.scene.frame_set(current_frame)


class BuildingAnmJsonExportOperator(Operator, ExportHelper):
    bl_idname = "export_anim.building_anm_json"
    bl_label = "Novator-Export-Buidling-Anm-Json(.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        current_frame = context.scene.frame_current
        try:
            payload = _build_active_animation_payload(context, self.filepath)
            with open(self.filepath, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            context.scene.frame_set(current_frame)
