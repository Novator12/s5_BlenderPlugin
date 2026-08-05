import json
import os

import bpy
import mathutils as mu

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .Comfort.anim_utils import (
    build_converter_track_for_bone,
    collect_armature_actions,
    collect_keyed_frames_for_bone,
    ensure_action_anim_fps,
    ensure_action_export_name,
    ensure_armature_active,
    find_bone_by_node_id,
    get_action_anim_fps,
    isolate_action_for_export,
    quat_to_s5_json,
    resolve_start_prev_keyframe_value,
    restore_action_after_export,
    root_id_from_filename,
    vec_to_s5_json,
)
from .Comfort.constants import DEFAULT_S5_FPS, ROOT_HANIM_NODES_PROP, ROOT_HANIM_PARENTS_PROP
from .Comfort.io_utils import convert_json_to_anm_external
from .Comfort.json_utils import json_loads_or_default


def _load_unit_root_hanim_payload(arm_ob):
    return (
        json_loads_or_default(arm_ob.get(ROOT_HANIM_NODES_PROP, "null"), None),
        json_loads_or_default(arm_ob.get(ROOT_HANIM_PARENTS_PROP, "null"), None),
    )


def determine_unit_bone_names_sorted(armature_object):
    bone_names = [bone.name for bone in armature_object.data.bones]
    return sorted(
        bone_names,
        key=lambda name: int(name.split("_")[1]) if len(name.split("_")) > 1 and name.split("_")[1].isdigit() else 10 ** 9,
    )


def bone_name_to_node_id(bone_name):
    node_suffix = bone_name[10:]
    return int(node_suffix) if node_suffix else -1


def resolve_unit_animation_root_id(arm_ob: bpy.types.Object, filepath: str | None = None) -> int:
    if filepath:
        try:
            return root_id_from_filename(filepath)
        except Exception:
            pass

    root_hanim_nodes, root_hanim_parents = _load_unit_root_hanim_payload(arm_ob)
    if root_hanim_nodes:
        if root_hanim_parents and len(root_hanim_parents) == len(root_hanim_nodes):
            for node_entry, parent_index in zip(root_hanim_nodes, root_hanim_parents):
                if int(parent_index) == -1 and node_entry.get("nodeID") is not None:
                    return int(node_entry["nodeID"])

        for node_entry in root_hanim_nodes:
            if int(node_entry.get("nodeID", -1)) == 2000:
                return 2000

        ordered_nodes = sorted(
            (entry for entry in root_hanim_nodes if entry.get("nodeID") is not None),
            key=lambda entry: int(entry.get("nodeIndex", 10 ** 9)),
        )
        if ordered_nodes:
            return int(ordered_nodes[0]["nodeID"])

    root_bone = find_bone_by_node_id(arm_ob, 2000)
    if root_bone is not None:
        return 2000

    for bone_name in determine_unit_bone_names_sorted(arm_ob):
        node_id = bone_name_to_node_id(bone_name)
        if node_id != -1:
            return int(node_id)

    raise RuntimeError("Keine Unit-Animations-Root-ID im Rig gefunden.")


def collect_unit_animation_bones(arm_ob: bpy.types.Object, root_id: int | None = None) -> list:
    root_hanim_nodes, root_hanim_parents = _load_unit_root_hanim_payload(arm_ob)
    if root_hanim_nodes:
        ordered_nodes = sorted(
            root_hanim_nodes,
            key=lambda entry: int(entry.get("nodeIndex", 10 ** 9)),
        )

        allowed_node_indices = None
        if root_id is not None and root_hanim_parents and len(root_hanim_parents) == len(root_hanim_nodes):
            root_index = None
            for node_entry in ordered_nodes:
                if int(node_entry.get("nodeID", -1)) == int(root_id):
                    root_index = int(node_entry.get("nodeIndex", -1))
                    break

            if root_index is not None and root_index >= 0:
                children_by_parent = {}
                for node_entry, parent_index in zip(ordered_nodes, root_hanim_parents):
                    node_index = int(node_entry.get("nodeIndex", -1))
                    if node_index < 0:
                        continue
                    children_by_parent.setdefault(int(parent_index), []).append(node_index)

                allowed_node_indices = set()
                pending = [root_index]
                while pending:
                    current = pending.pop()
                    if current in allowed_node_indices:
                        continue
                    allowed_node_indices.add(current)
                    pending.extend(children_by_parent.get(current, []))

        animation_bones = []
        for node_entry in ordered_nodes:
            node_index = int(node_entry.get("nodeIndex", -1))
            if allowed_node_indices is not None and node_index not in allowed_node_indices:
                continue

            node_id = node_entry.get("nodeID")
            if node_id is None:
                continue

            bone = find_bone_by_node_id(arm_ob, int(node_id))
            if bone is not None:
                animation_bones.append(bone)

        if animation_bones:
            return animation_bones

    animation_bones = []
    for bone_name in determine_unit_bone_names_sorted(arm_ob):
        node_id = bone_name_to_node_id(bone_name)
        if node_id == -1:
            continue

        bone = arm_ob.data.bones.get(bone_name)
        if bone is not None:
            animation_bones.append(bone)

    return animation_bones


def build_unit_animation_export_json(
    arm_ob: bpy.types.Object,
    root_id: int,
    action: bpy.types.Action,
    frame_start: float,
    frame_end: float,
    fps: int,
    source_name: str,
) -> dict:
    animation_bones = collect_unit_animation_bones(arm_ob, root_id)
    if not animation_bones:
        raise RuntimeError(f"Keine animierbaren Unit-Bones für Root {root_id} gefunden.")

    track_frames = []
    for bone in animation_bones:
        track_frames.append(collect_keyed_frames_for_bone(action, bone.name, frame_start, frame_end))

    non_empty_frames = [frames for frames in track_frames if frames]
    if non_empty_frames:
        export_frame_start = min(min(frames) for frames in non_empty_frames)
        export_frame_end = max(max(frames) for frames in non_empty_frames)
    else:
        export_frame_start = frame_start
        export_frame_end = frame_end

    duration = max(0.0, float(export_frame_end - export_frame_start) / fps)
    track_entries = []

    for bone, frames in zip(animation_bones, track_frames):
        track = build_converter_track_for_bone(
            scene=bpy.context.scene,
            arm_ob=arm_ob,
            bone=bone,
            frames=frames,
            fps=fps,
            base_frame=export_frame_start,
        )

        entries = []
        for key in track:
            entries.append({
                "Time": float(key["time"]),
                "Q": quat_to_s5_json(mu.Quaternion((
                    key["quaternion"]["w"],
                    key["quaternion"]["x"],
                    key["quaternion"]["y"],
                    key["quaternion"]["z"],
                ))),
                "T": vec_to_s5_json(mu.Vector((
                    key["position"]["x"],
                    key["position"]["y"],
                    key["position"]["z"],
                ))),
            })
        track_entries.append(entries)

    keyframes = []
    last_indices = []
    start_prev_keyframe = resolve_start_prev_keyframe_value(
        arm_ob=arm_ob,
        action=action,
        source_name=source_name,
        root_id=root_id,
        bone_count=len(track_entries),
    )

    for entries in track_entries:
        if not entries:
            continue
        start_entry = dict(entries[0])
        start_entry["PrevKeyFrame"] = start_prev_keyframe
        keyframes.append(start_entry)
        last_indices.append(len(keyframes) - 1)

    for track_idx, entries in enumerate(track_entries):
        if not entries:
            continue
        prev_key_index = last_indices[track_idx]
        for entry in entries[1:]:
            out_entry = dict(entry)
            out_entry["PrevKeyFrame"] = prev_key_index
            keyframes.append(out_entry)
            prev_key_index = len(keyframes) - 1

    return {
        "$schema": "https://github.com/mcb5637/S5Converter/raw/refs/heads/master/schema.json",
        "HierarchicalAnim": {
            "InterpolatorTypeId": "HierarchicalAnim",
            "Flags": 0,
            "Duration": duration,
            "KeyFrames": keyframes,
        },
        "BuildNum": 10,
        "VersionNum": 225282,
        "ConvertRadians": True,
    }


def _resolve_armature_for_ui(context):
    armature_object = getattr(context, "object", None)
    if armature_object is not None and armature_object.type == "ARMATURE":
        return armature_object

    scene = getattr(context, "scene", None)
    if scene is None:
        return None

    return next((obj for obj in scene.objects if obj.type == "ARMATURE"), None)


def _ensure_filepath_extension(filepath, extension):
    root, _old_ext = os.path.splitext(filepath)
    return root + extension if root else filepath + extension


def build_active_unit_animation_payload(context, filepath):
    armature_object = ensure_armature_active()
    if not armature_object.animation_data or not armature_object.animation_data.action:
        raise RuntimeError("Keine aktive Action auf der Armature gefunden.")

    action = armature_object.animation_data.action
    scene = context.scene
    frame_start = float(action.frame_range[0]) if action is not None else float(scene.frame_start)
    frame_end = float(action.frame_range[1]) if action is not None else float(scene.frame_end)
    ensure_action_anim_fps(action, DEFAULT_S5_FPS)
    fps = get_action_anim_fps(action, DEFAULT_S5_FPS)
    root_id = resolve_unit_animation_root_id(armature_object, filepath)

    return build_unit_animation_export_json(
        arm_ob=armature_object,
        root_id=root_id,
        action=action,
        frame_start=frame_start,
        frame_end=frame_end,
        fps=fps,
        source_name=os.path.basename(filepath),
    )


def build_unit_animation_payload_for_action(context, filepath, action):
    armature_object = ensure_armature_active()
    scene = context.scene
    frame_start = float(action.frame_range[0]) if action is not None else float(scene.frame_start)
    frame_end = float(action.frame_range[1]) if action is not None else float(scene.frame_end)
    ensure_action_anim_fps(action, DEFAULT_S5_FPS)
    fps = get_action_anim_fps(action, DEFAULT_S5_FPS)
    root_id = resolve_unit_animation_root_id(armature_object, filepath)

    return build_unit_animation_export_json(
        arm_ob=armature_object,
        root_id=root_id,
        action=action,
        frame_start=frame_start,
        frame_end=frame_end,
        fps=fps,
        source_name=os.path.basename(filepath),
    )


class UnitAnmExportOperator(Operator, ExportHelper):
    bl_idname = "export_anim.unit_anm"
    bl_label = "Novator-Export-Unit-Anm (.anm/.json)"
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
                payload = build_active_unit_animation_payload(context, export_path)
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
                        payload = build_unit_animation_payload_for_action(context, action_path, action)
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
