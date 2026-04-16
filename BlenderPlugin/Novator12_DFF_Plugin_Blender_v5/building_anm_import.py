import json
import os

import bpy

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .Comfort.anim_utils import (
    create_import_action,
    determine_fps,
    ensure_armature_active,
    find_bone_by_node_id,
    insert_posebone_keys,
    parse_animation_data,
    posebone_set_from_local_matrix,
    s5_time_to_frame,
    set_action_anim_fps,
    set_action_anim_format,
    set_scene_frame,
    store_imported_animation_metadata,
)
from .building_anm_export import collect_anim_bones_for_building, collect_animation_bones_from_hanim, resolve_export_root_id
from .Comfort.io_utils import convert_anm_to_json_external


def parse_animation_json(json_path: str) -> tuple[float, list[list[dict]], str]:
    with open(json_path, "r", encoding="utf-8") as handle:
        js = json.load(handle)
    return parse_animation_data(js)


def apply_tracks_to_armature(
    arm_ob: bpy.types.Object,
    root_id: int,
    duration: float,
    tracks: list[list[dict]],
    source_format: str,
    action_source_name: str | None = None,
):
    root_bone = find_bone_by_node_id(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    anim_bones = collect_animation_bones_from_hanim(arm_ob, root_bone)
    if not anim_bones:
        anim_bones = collect_anim_bones_for_building(root_bone)

    if not anim_bones:
        raise RuntimeError(f"Keine animierbaren Bones unter Root {root_id} gefunden.")

    used_track_count = min(len(tracks), len(anim_bones))
    if used_track_count == 0:
        raise RuntimeError("Keine passenden Tracks/Bones gefunden.")

    fps = determine_fps(source_format, tracks)
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    scene.frame_start = 0
    scene.frame_end = max(0, int(round(duration * fps)))

    action = create_import_action(arm_ob, action_source_name or f"SkinAction_{root_id}")
    set_action_anim_fps(action, fps)
    set_action_anim_format(action, source_format)

    bpy.context.view_layer.objects.active = arm_ob
    arm_ob.select_set(True)
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="POSE")

    for track_index in range(used_track_count):
        bone = anim_bones[track_index]
        pose_bone = arm_ob.pose.bones.get(bone.name)
        if pose_bone is None:
            continue

        pose_bone.rotation_mode = "QUATERNION"
        for key in tracks[track_index]:
            frame = s5_time_to_frame(float(key["time"]), fps)
            set_scene_frame(scene, frame)
            posebone_set_from_local_matrix(arm_ob, pose_bone, key["matrix"])
            insert_posebone_keys(pose_bone, frame)

    try:
        action_frame_end = max(0, int(round(action.frame_range[1] - action.frame_range[0])))
    except Exception:
        action_frame_end = max(0, int(round(duration * fps)))

    scene.frame_start = 0
    scene.frame_end = action_frame_end
    scene.frame_set(0)
    bpy.context.view_layer.update()
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    return action


def apply_animation_json_to_armature(json_path: str, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_animation_json(json_path)
    root_id = resolve_export_root_id(arm_ob, source_name_for_root)
    action = apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format, source_name_for_root)
    with open(json_path, "r", encoding="utf-8") as handle:
        js = json.load(handle)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


def apply_animation_data_to_armature(js: dict, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_animation_data(js)
    root_id = resolve_export_root_id(arm_ob, source_name_for_root)
    action = apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format, source_name_for_root)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


class BuildingAnmImportOperator(Operator, ImportHelper):
    bl_idname = "import_anim.building_anm"
    bl_label = "Novator-Import-Buidling-Anm (.anm/.json)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm;*.json", options={"HIDDEN"})

    def execute(self, context):
        file_ext = os.path.splitext(self.filepath)[1].lower()

        try:
            armature_object = ensure_armature_active()
            if file_ext == ".anm":
                payload = convert_anm_to_json_external(self.filepath)
                apply_animation_data_to_armature(payload, armature_object, self.filepath)
            elif file_ext == ".json":
                apply_animation_json_to_armature(self.filepath, armature_object, self.filepath)
            else:
                self.report({"ERROR"}, "Unsupported animation import type: {}".format(file_ext or "<none>"))
                return {"CANCELLED"}
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
