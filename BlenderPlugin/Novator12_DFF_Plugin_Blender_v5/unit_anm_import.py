import json
import os

import bpy
import mathutils as mu

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .Comfort.anim_utils import (
    create_import_action,
    determine_fps,
    ensure_armature_active,
    insert_posebone_keys,
    parse_animation_data,
    posebone_set_from_local_matrix,
    s5_quat_to_blender,
    s5_time_to_frame,
    set_action_anim_fps,
    set_action_anim_format,
    set_scene_frame,
    store_imported_animation_metadata,
)
from .Comfort.io_utils import convert_anm_to_json_external
from .unit_anm_export import collect_unit_animation_bones, resolve_unit_animation_root_id


def _build_matrix_from_compressed_key(key: dict, offset: dict, scalar: dict) -> mu.Matrix:
    packed_translation = key.get("T", {})
    translation = mu.Vector((
        float(offset.get("x", 0.0)) + float(scalar.get("x", 0.0)) * float(packed_translation.get("x", 0.0)),
        float(offset.get("y", 0.0)) + float(scalar.get("y", 0.0)) * float(packed_translation.get("y", 0.0)),
        float(offset.get("z", 0.0)) + float(scalar.get("z", 0.0)) * float(packed_translation.get("z", 0.0)),
    ))
    quaternion = s5_quat_to_blender(key["Q"])
    matrix = quaternion.to_matrix().to_4x4()
    matrix.translation = translation
    return matrix


def parse_compressed_anim_tracks(js: dict) -> tuple[float, list[list[dict]]]:
    compressed = js.get("CompressedAnim")
    if not compressed:
        raise RuntimeError("JSON enthält kein 'CompressedAnim'.")

    duration = float(compressed.get("Duration", compressed.get("duration", 0.0)))
    keyframes = compressed.get("KeyFrames", [])
    if not keyframes:
        raise RuntimeError("CompressedAnim enthält keine KeyFrames.")

    offset = compressed.get("Offset") or {}
    scalar = compressed.get("Scalar") or {}
    starts = []
    by_prev = {}

    for idx, key in enumerate(keyframes):
        prev = int(key.get("PrevKeyFrame", -1))
        time_val = float(key.get("Time", 0.0))
        if time_val == 0.0 and prev < 0:
            starts.append(idx)
        by_prev.setdefault(prev, []).append(idx)

    if not starts:
        raise RuntimeError("Keine Start-KeyFrames in CompressedAnim gefunden.")

    for prev_idx in by_prev:
        by_prev[prev_idx].sort(key=lambda item: (float(keyframes[item]["Time"]), item))

    tracks = []
    for start_idx in starts:
        chain = []
        current = start_idx
        visited = set()

        while current not in visited:
            visited.add(current)
            key = keyframes[current]
            chain.append({
                "time": float(key["Time"]),
                "matrix": _build_matrix_from_compressed_key(key, offset, scalar),
                "raw": key,
                "index": current,
            })

            next_candidates = by_prev.get(current, [])
            if not next_candidates:
                break

            current = next_candidates[0]

        tracks.append(chain)

    tracks.sort(key=lambda track: track[0]["index"])
    return duration, tracks


def parse_unit_animation_data(js: dict) -> tuple[float, list[list[dict]], str]:
    if "CompressedAnim" in js:
        duration, tracks = parse_compressed_anim_tracks(js)
        return duration, tracks, "compressed"

    duration, tracks, source_format = parse_animation_data(js)
    return duration, tracks, source_format


def parse_unit_animation_json(json_path: str) -> tuple[float, list[list[dict]], str]:
    with open(json_path, "r", encoding="utf-8") as handle:
        js = json.load(handle)
    return parse_unit_animation_data(js)


def apply_unit_tracks_to_armature(
    arm_ob: bpy.types.Object,
    root_id: int,
    duration: float,
    tracks: list[list[dict]],
    source_format: str,
    action_source_name: str | None = None,
):
    animation_bones = collect_unit_animation_bones(arm_ob, root_id)
    if not animation_bones:
        raise RuntimeError(f"Keine animierbaren Unit-Bones für Root {root_id} gefunden.")

    used_track_count = min(len(tracks), len(animation_bones))
    if used_track_count == 0:
        raise RuntimeError("Keine passenden Tracks/Bones für die Unit-Animation gefunden.")

    fps = determine_fps(source_format, tracks)
    scene = bpy.context.scene
    scene.render.fps = fps if fps > 0 else 30
    scene.render.fps_base = 1.0
    scene.frame_start = 0
    scene.frame_end = max(0, int(round(duration * scene.render.fps)))

    action = create_import_action(arm_ob, action_source_name or f"UnitSkinAction_{root_id}")
    set_action_anim_fps(action, scene.render.fps)
    set_action_anim_format(action, source_format)

    bpy.context.view_layer.objects.active = arm_ob
    arm_ob.select_set(True)
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="POSE")

    for track_index in range(used_track_count):
        bone = animation_bones[track_index]
        pose_bone = arm_ob.pose.bones.get(bone.name)
        if pose_bone is None:
            continue

        pose_bone.rotation_mode = "QUATERNION"
        for key in tracks[track_index]:
            frame = s5_time_to_frame(float(key["time"]), scene.render.fps)
            set_scene_frame(scene, frame)
            posebone_set_from_local_matrix(arm_ob, pose_bone, key["matrix"])
            insert_posebone_keys(pose_bone, frame)

    try:
        action_frame_end = max(0, int(round(action.frame_range[1] - action.frame_range[0])))
    except Exception:
        action_frame_end = max(0, int(round(duration * scene.render.fps)))

    scene.frame_start = 0
    scene.frame_end = action_frame_end
    scene.frame_set(0)
    bpy.context.view_layer.update()
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")
    return action


def apply_unit_animation_json_to_armature(json_path: str, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_unit_animation_json(json_path)
    root_id = resolve_unit_animation_root_id(arm_ob, source_name_for_root)
    action = apply_unit_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format, source_name_for_root)
    with open(json_path, "r", encoding="utf-8") as handle:
        js = json.load(handle)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


def apply_unit_animation_data_to_armature(js: dict, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_unit_animation_data(js)
    root_id = resolve_unit_animation_root_id(arm_ob, source_name_for_root)
    action = apply_unit_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format, source_name_for_root)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


class UnitAnmImportOperator(Operator, ImportHelper):
    bl_idname = "import_anim.unit_anm"
    bl_label = "Novator-Import-Unit-Anm (.anm/.json)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm;*.json", options={"HIDDEN"})

    def execute(self, context):
        file_ext = os.path.splitext(self.filepath)[1].lower()

        try:
            armature_object = ensure_armature_active()
            if file_ext == ".anm":
                payload = convert_anm_to_json_external(self.filepath)
                apply_unit_animation_data_to_armature(payload, armature_object, self.filepath)
            elif file_ext == ".json":
                apply_unit_animation_json_to_armature(self.filepath, armature_object, self.filepath)
            else:
                self.report({"ERROR"}, "Unsupported animation import type: {}".format(file_ext or "<none>"))
                return {"CANCELLED"}
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
