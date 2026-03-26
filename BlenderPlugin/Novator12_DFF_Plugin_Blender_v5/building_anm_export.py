import json
import os

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .building_utilities import (
    DEFAULT_S5_FPS,
    build_animation_export_json,
    collect_armature_actions,
    convert_json_to_anm_external,
    ensure_action_anim_fps,
    ensure_action_export_name,
    ensure_armature_active,
    get_action_anim_fps,
    isolate_action_for_export,
    restore_action_after_export,
    resolve_export_root_id,
)


def _resolve_armature_for_ui(context):
    armature_object = getattr(context, "object", None)
    if armature_object is not None and armature_object.type == "ARMATURE":
        return armature_object

    scene = getattr(context, "scene", None)
    if scene is None:
        return None

    return next((obj for obj in scene.objects if obj.type == "ARMATURE"), None)


def _resolve_action_frame_range(action, scene):
    if action is None:
        return float(scene.frame_start), float(scene.frame_end)

    try:
        frame_start = float(action.frame_range[0])
        frame_end = float(action.frame_range[1])
    except Exception:
        frame_start = float(scene.frame_start)
        frame_end = float(scene.frame_end)

    if frame_end < frame_start:
        frame_end = frame_start
    return frame_start, frame_end


def _build_animation_payload(context, filepath, action=None):
    armature_object = ensure_armature_active()
    active_action = action
    if active_action is None and armature_object.animation_data:
        active_action = armature_object.animation_data.action
    if active_action is None:
        raise RuntimeError("Keine aktive Action auf der Armature gefunden.")

    scene = context.scene
    frame_start, frame_end = _resolve_action_frame_range(active_action, scene)
    fps = get_action_anim_fps(active_action, DEFAULT_S5_FPS)
    root_id = resolve_export_root_id(armature_object, filepath)

    return build_animation_export_json(
        arm_ob=armature_object,
        root_id=root_id,
        action=active_action,
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
    export_scope: EnumProperty(
        name="Actions",
        items=(
            ("ACTIVE", "Active Action", "Export only the active action"),
            ("ALL", "All Actions", "Export all actions of the selected armature"),
        ),
        default="ACTIVE",
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
        self.layout.prop(self, "export_scope")
        armature_object = _resolve_armature_for_ui(_context)
        actions = collect_armature_actions(armature_object) if armature_object is not None else []

        if self.export_scope == "ACTIVE":
            active_action = None
            if armature_object is not None and armature_object.animation_data:
                active_action = armature_object.animation_data.action

            box = self.layout.box()
            if active_action is None:
                box.label(text="Keine aktive Action gefunden.")
            else:
                box.label(text="Active: {}".format(active_action.name))
        else:
            self.layout.label(text="Beim Multi-Export wird nur der Zielordner verwendet.")
            if not actions:
                self.layout.label(text="Keine Actions gefunden.")
            for action in actions:
                box = self.layout.box()
                box.label(text=action.name)

    def execute(self, context):
        current_frame = context.scene.frame_current
        export_path = _ensure_filepath_extension(self.filepath, ".anm" if self.file_format == "ANM" else ".json")
        try:
            if self.export_scope == "ACTIVE":
                payload = _build_animation_payload(context, export_path)
                if self.file_format == "ANM":
                    convert_json_to_anm_external(payload, export_path)
                else:
                    with open(export_path, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, indent=4)
            else:
                armature_object = ensure_armature_active()
                actions = collect_armature_actions(armature_object)
                if not actions:
                    raise RuntimeError("Keine Actions auf der selektierten Armature gefunden.")

                export_directory = os.path.dirname(export_path) or export_path
                os.makedirs(export_directory, exist_ok=True)
                extension = ".anm" if self.file_format == "ANM" else ".json"

                for action in actions:
                    export_name = ensure_action_export_name(action)
                    action_path = os.path.join(export_directory, export_name + extension)
                    original_action, original_track_mutes = isolate_action_for_export(armature_object, action)
                    try:
                        payload = _build_animation_payload(context, action_path, action=action)
                    finally:
                        restore_action_after_export(armature_object, original_action, original_track_mutes)

                    if self.file_format == "ANM":
                        convert_json_to_anm_external(payload, action_path)
                    else:
                        with open(action_path, "w", encoding="utf-8") as handle:
                            json.dump(payload, handle, indent=4)

            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            context.scene.frame_set(current_frame)
