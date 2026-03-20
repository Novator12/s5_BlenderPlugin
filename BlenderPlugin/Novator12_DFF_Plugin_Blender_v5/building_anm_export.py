import json
import os

from bpy.props import EnumProperty, StringProperty
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


def _ensure_filepath_extension(filepath, extension):
    root, _old_ext = os.path.splitext(filepath)
    return root + extension if root else filepath + extension


class BuildingAnmExportOperator(Operator, ExportHelper):
    bl_idname = "export_anim.building_anm"
    bl_label = "Novator-Export-Buidling-Anm (.anm/.json)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm;*.json", options={"HIDDEN"})
    file_format: EnumProperty(
        name="Format",
        items=(
            ("ANM", ".anm", "Export as .anm"),
            ("JSON", ".json", "Export as .json"),
        ),
        default="ANM",
    )

    def check(self, _context):
        desired_ext = ".anm" if self.file_format == "ANM" else ".json"
        updated_path = _ensure_filepath_extension(self.filepath, desired_ext)
        if updated_path != self.filepath:
            self.filepath = updated_path
            return True
        return False

    def draw(self, _context):
        self.layout.prop(self, "file_format")

    def execute(self, context):
        current_frame = context.scene.frame_current
        export_path = _ensure_filepath_extension(self.filepath, ".anm" if self.file_format == "ANM" else ".json")
        try:
            payload = _build_active_animation_payload(context, export_path)
            if self.file_format == "ANM":
                convert_json_to_anm_external(payload, export_path)
            else:
                with open(export_path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=4)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            context.scene.frame_set(current_frame)
