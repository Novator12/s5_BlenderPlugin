import json
import os
import re

import bpy
import mathutils as mu

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .Comfort.anim_utils import (
    build_converter_track_for_bone,
    collect_armature_actions,
    collect_keyed_frames_for_bone,
    ensure_action_export_name,
    ensure_armature_active,
    find_bone_by_node_id,
    get_action_anim_fps,
    isolate_action_for_export,
    quat_to_s5_json,
    resolve_start_prev_keyframe_value,
    restore_action_after_export,
    vec_to_s5_json,
)
from .Comfort.constants import DEFAULT_S5_FPS
from .Comfort.io_utils import convert_json_to_anm_external


MIN_ANIM_NODE_ID = 600


def is_building_anim_node_id(node_id: int | None) -> bool:
    if node_id is None:
        return False
    return 500 <= int(node_id) < 600 or int(node_id) >= MIN_ANIM_NODE_ID


def root_id_from_filename(path: str) -> int:
    name = os.path.splitext(os.path.basename(path))[0]
    match = re.search(r"_(\d+)$", name)
    if not match:
        raise RuntimeError(f"Keine Root-ID im Dateinamen gefunden: {name}")

    root_id = int(match.group(1))
    if not is_building_anim_node_id(root_id):
        raise RuntimeError(
            f"Ungültige Anim-Root-ID im Dateinamen: {root_id}. "
            f"Erwartet wird eine NodeID im Bereich 500-599 oder >= {MIN_ANIM_NODE_ID}."
        )
    return root_id


def parse_node_id_from_bone_name(bname: str) -> int | None:
    parts = bname.split("_")
    if len(parts) >= 3 and parts[-1].isdigit():
        return int(parts[-1])
    return None


def parse_frame_index_from_bone_name(bname: str) -> int:
    parts = bname.split("_")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 10**9


def get_bone_hanim_data(bone) -> dict | None:
    if not bone or "hanimData" not in bone:
        return None

    data = bone["hanimData"]
    try:
        return data.to_dict()
    except Exception:
        pass

    try:
        return dict(data)
    except Exception:
        return data


def collect_subtree_node_ids(root_bone) -> set[int]:
    ids = set()

    def rec(bone):
        node_id = parse_node_id_from_bone_name(bone.name)
        if is_building_anim_node_id(node_id):
            ids.add(node_id)
        for child in bone.children:
            rec(child)

    rec(root_bone)
    return ids


def collect_parent_chain(root_bone) -> list:
    chain = []
    current = root_bone
    while current is not None:
        chain.append(current)
        current = current.parent
    return chain


def extract_hanim_node_ids_from_bone(bone) -> list[int]:
    hdata = get_bone_hanim_data(bone)
    if not hdata:
        return []

    nodes = hdata.get("nodes", [])
    ordered_ids = []
    for entry in nodes:
        node_id = None
        if isinstance(entry, dict):
            node_id = entry.get("nodeID")
            if node_id is None:
                node_id = entry.get("NodeID")
        else:
            try:
                node_id = entry["nodeID"]
            except Exception:
                try:
                    node_id = entry["NodeID"]
                except Exception:
                    node_id = None

        if node_id is not None:
            try:
                node_id = int(node_id)
                if is_building_anim_node_id(node_id):
                    ordered_ids.append(node_id)
            except Exception:
                pass

    return ordered_ids


def collect_hanim_node_order_for_animation(arm_ob: bpy.types.Object, root_bone) -> list[int]:
    allowed_ids = collect_subtree_node_ids(root_bone)

    ordered_ids = extract_hanim_node_ids_from_bone(root_bone)
    if ordered_ids:
        filtered = [nid for nid in ordered_ids if nid in allowed_ids]
        if filtered:
            return filtered

    for bone in collect_parent_chain(root_bone)[1:]:
        ordered_ids = extract_hanim_node_ids_from_bone(bone)
        if ordered_ids:
            filtered = [nid for nid in ordered_ids if nid in allowed_ids]
            if filtered:
                return filtered

    for bone in arm_ob.data.bones:
        if bone == root_bone:
            continue
        ordered_ids = extract_hanim_node_ids_from_bone(bone)
        if ordered_ids:
            filtered = [nid for nid in ordered_ids if nid in allowed_ids]
            if filtered:
                return filtered

    return []


def collect_animation_bones_from_hanim(arm_ob: bpy.types.Object, root_bone) -> list:
    ordered_ids = collect_hanim_node_order_for_animation(arm_ob, root_bone)

    bones = []
    seen = set()
    for node_id in ordered_ids:
        bone = find_bone_by_node_id(arm_ob, node_id)
        if bone and bone.name not in seen:
            bones.append(bone)
            seen.add(bone.name)
    return bones


def collect_anim_bones_for_building(root_bone) -> list:
    ordered = []

    def rec(bone):
        node_id = parse_node_id_from_bone_name(bone.name)
        if is_building_anim_node_id(node_id):
            ordered.append(bone)

        children = sorted(list(bone.children), key=lambda child: (parse_frame_index_from_bone_name(child.name), child.name))
        for child in children:
            rec(child)

    rec(root_bone)
    return ordered


def detect_animation_root_bone(arm_ob: bpy.types.Object):
    candidates = []

    for bone in arm_ob.data.bones:
        node_id = parse_node_id_from_bone_name(bone.name)
        if not is_building_anim_node_id(node_id):
            continue

        parent_node_id = parse_node_id_from_bone_name(bone.parent.name) if bone.parent else None
        if is_building_anim_node_id(parent_node_id):
            continue

        subtree_count = len(collect_subtree_node_ids(bone))
        candidates.append((subtree_count, parse_frame_index_from_bone_name(bone.name), node_id, bone))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][3]


def resolve_export_root_id(arm_ob: bpy.types.Object, filepath: str) -> int:
    try:
        return root_id_from_filename(filepath)
    except Exception as exc:
        print(f"[INFO] Keine gültige Root-ID im Dateinamen, nutze Auto-Erkennung: {exc}")

    root_bone = detect_animation_root_bone(arm_ob)
    if not root_bone:
        raise RuntimeError(
            "Keine Root-ID im Dateinamen gefunden und kein Anim-Root im Rig erkannt. "
            "Bitte Dateiname wie '*_502.anm' oder '*_600.anm' verwenden oder Rig prüfen."
        )

    root_id = parse_node_id_from_bone_name(root_bone.name)
    if root_id is None:
        raise RuntimeError(f"Automatisch erkannter Root-Bone hat keine gültige NodeID: {root_bone.name}")

    print(f"[INFO] Auto-erkanntes Export-Root: bone={root_bone.name}, nodeID={root_id}")
    return root_id


def build_animation_export_json(
    arm_ob: bpy.types.Object,
    root_id: int,
    action: bpy.types.Action,
    frame_start: int,
    frame_end: int,
    fps: int,
    source_name: str,
) -> dict:
    root_bone = find_bone_by_node_id(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    anim_bones = collect_animation_bones_from_hanim(arm_ob, root_bone)
    if not anim_bones:
        anim_bones = collect_anim_bones_for_building(root_bone)

    if not anim_bones:
        raise RuntimeError(f"Keine animierbaren Bones unter Root {root_id} gefunden.")

    track_frames = []
    for bone in anim_bones:
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

    for bone, frames in zip(anim_bones, track_frames):
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
