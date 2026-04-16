import json
import math
import os
import re
import subprocess

from collections import OrderedDict

import bpy
import mathutils as mu
from mathutils import Matrix, Vector


NEGATIVE_Y_THRESHOLD = 1.0e-9
NEGATIVE_Y_CLOSE_THRESHOLD = 1.0e-5
FALLBACK_BONE_AXIS = Vector((0.0, 1.0, 0.0))
EXPORT_BONE_SCALE = 100.0

DEFAULT_S5_FPS = 30
MIN_ANIM_NODE_ID = 600
DEFAULT_START_PREV_KEYFRAME = -123456789
ACTION_ANIM_FPS_PROP = "s5_anim_fps"
ACTION_EXPORT_NAME_PROP = "s5_export_name"
ACTION_START_PREV_KEYFRAME_PROP = "s5_import_prev_keyframe"
ACTION_ANIM_FORMAT_PROP = "s5_anim_format"
ANIM_FORMAT_HIERARCHICAL = "hierarchical"
ANIM_FORMAT_COMPRESSED = "compressed"
ANIM_FORMAT_NODES = "nodes"
DEFAULT_ANIM_FORMAT = ANIM_FORMAT_HIERARCHICAL


def get_converter_exe_location():
    addon_dir = os.path.dirname(__file__)
    return os.path.join(addon_dir, "S5Converter.exe")


def set_clipping_for_all_screens(clip_start, clip_end):
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if hasattr(space, "clip_start") and hasattr(space, "clip_end"):
                    space.clip_start = clip_start
                    space.clip_end = clip_end


def compose_matrix(left, right):
    return left @ right


def frame_dict_to_matrix(frame_data):
    rotation_rows = frame_data["rotationMatrix"]
    position = frame_data["position"]

    matrix = Matrix.Identity(4)
    for row_index, row in enumerate(rotation_rows):
        matrix[row_index][0] = row["x"]
        matrix[row_index][1] = row["y"]
        matrix[row_index][2] = row["z"]

    matrix[3][0] = position["x"]
    matrix[3][1] = position["y"]
    matrix[3][2] = position["z"]
    return matrix


def bone_axis_to_matrix(axis, roll):
    normalized_axis = axis.normalized()
    orientation = Matrix().to_3x3()
    theta = 1.0 + normalized_axis.y

    if theta > NEGATIVE_Y_CLOSE_THRESHOLD or ((normalized_axis.x or normalized_axis.z) and theta > NEGATIVE_Y_THRESHOLD):
        orientation[1][0] = -normalized_axis.x
        orientation[0][1] = normalized_axis.x
        orientation[1][1] = normalized_axis.y
        orientation[2][1] = normalized_axis.z
        orientation[1][2] = -normalized_axis.z

        if theta > NEGATIVE_Y_CLOSE_THRESHOLD:
            orientation[0][0] = 1.0 - normalized_axis.x * normalized_axis.x / theta
            orientation[2][2] = 1.0 - normalized_axis.z * normalized_axis.z / theta
            orientation[0][2] = -normalized_axis.x * normalized_axis.z / theta
            orientation[2][0] = orientation[0][2]
        else:
            denominator = normalized_axis.x * normalized_axis.x + normalized_axis.z * normalized_axis.z
            orientation[0][0] = (normalized_axis.x + normalized_axis.z) * (normalized_axis.x - normalized_axis.z) / -denominator
            orientation[2][2] = -orientation[0][0]
            orientation[0][2] = 2.0 * normalized_axis.x * normalized_axis.z / denominator
            orientation[2][0] = orientation[0][2]
    else:
        orientation[0][0] = -1.0
        orientation[1][1] = -1.0

    roll_matrix = mu.Matrix.Rotation(roll, 3, normalized_axis)
    return compose_matrix(roll_matrix, orientation)


def matrix_to_bone_axis_roll(matrix):
    axis = matrix.col[1]
    if axis.length < 1.0e-8:
        return FALLBACK_BONE_AXIS.copy(), 0.0

    axis_matrix = bone_axis_to_matrix(axis, 0.0)
    try:
        inverse_axis_matrix = axis_matrix.inverted()
    except Exception:
        return FALLBACK_BONE_AXIS.copy(), 0.0

    roll_matrix = compose_matrix(inverse_axis_matrix, matrix)
    roll = math.atan2(roll_matrix[0][2], roll_matrix[2][2])
    return axis, roll


def link_object_in_active_collection(obj):
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj


def edit_bone_to_matrix(edit_bone):
    head_position = edit_bone.head
    tail_axis = (edit_bone.tail - head_position) / EXPORT_BONE_SCALE
    orientation_matrix = bone_axis_to_matrix(tail_axis, edit_bone.roll)

    transform_matrix = orientation_matrix.to_4x4()
    transform_matrix.translation = head_position
    return transform_matrix


def bone_name_to_node_id(bone_name):
    node_suffix = bone_name[10:]
    return int(node_suffix) if node_suffix else -1


def _collect_texture_coordinates(mesh_object, vertex_count):
    texture_coordinate_sets = []
    for uv_layer in mesh_object.data.uv_layers:
        layer_coordinates = [None] * vertex_count
        has_uvs = False

        for polygon in mesh_object.data.polygons:
            for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                uv = uv_layer.data[loop_index].uv
                layer_coordinates[vertex_index] = OrderedDict((
                    ("u", uv.x),
                    ("v", 1 - uv.y),
                ))
                has_uvs = True

        if has_uvs:
            texture_coordinate_sets.append(layer_coordinates)

    return texture_coordinate_sets


def _build_geometry_format(mesh_object, texture_coordinate_sets):
    if not texture_coordinate_sets:
        return {
            "TriStrip": False,
            "Positions": False,
            "NumTextureCoordinates": 0,
            "PreLit": False,
            "Normals": False,
            "Light": False,
            "ModulateMaterialColor": False,
            "Native": False,
            "NativeInstance": False,
        }

    return {
        "TriStrip": True,
        "Positions": True,
        "NumTextureCoordinates": 2 if len(mesh_object.data.uv_layers) > 1 else 1,
        "PreLit": False,
        "Normals": True,
        "Light": True,
        "ModulateMaterialColor": False,
        "Native": False,
        "NativeInstance": False,
    }


def accumulate_rest_matrix(rest_matrices, hierarchy, frame_index):
    accumulated_matrix = rest_matrices[frame_index]
    parent_index = hierarchy[frame_index]
    visited = set()

    while parent_index != -1 and parent_index not in visited:
        visited.add(parent_index)
        accumulated_matrix = rest_matrices[parent_index] @ accumulated_matrix
        parent_index = hierarchy[parent_index]

    return accumulated_matrix


def convert_binary_dff_to_json(binary_data, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    process = subprocess.Popen(
        [converter_path, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(input=binary_data)
    stderr_text = stderr.decode("utf-8", "replace").strip()
    if process.returncode != 0:
        raise RuntimeError(f"S5Converter import failed with exit code {process.returncode}: {stderr_text or 'no stderr output'}")
    if stderr_text:
        raise RuntimeError(f"S5Converter import reported an error: {stderr_text}")
    return json.loads(stdout.decode("utf-8"))


def _collect_invalid_texture_coordinate_entries(payload):
    invalid_entries = []
    clump = payload.get("clump") if isinstance(payload, dict) else None
    geometries = clump.get("geometries", []) if isinstance(clump, dict) else []

    for geometry_index, geometry in enumerate(geometries):
        texture_layers = geometry.get("textureCoordinates", [])
        for layer_index, layer in enumerate(texture_layers):
            if not isinstance(layer, list):
                invalid_entries.append((geometry_index, layer_index, None, type(layer).__name__))
                continue

            for coord_index, uv in enumerate(layer):
                if not isinstance(uv, dict) or "u" not in uv or "v" not in uv:
                    invalid_entries.append((geometry_index, layer_index, coord_index, uv))

    return invalid_entries


def convert_json_to_binary_dff(payload, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    invalid_entries = _collect_invalid_texture_coordinate_entries(payload)
    if invalid_entries:
        preview = ", ".join(
            f"geom {geometry_index}, layer {layer_index}, index {coord_index}: {value!r}"
            for geometry_index, layer_index, coord_index, value in invalid_entries[:8]
        )
        raise RuntimeError(
            "JSON enthaelt ungueltige textureCoordinates-Eintraege. "
            "Erwartet wird pro UV ein Objekt mit 'u' und 'v'. "
            f"Beispiele: {preview}"
        )

    process = subprocess.Popen(
        [converter_path, "--export"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    stdout, stderr = process.communicate(input=payload_bytes)
    stderr_text = stderr.decode("utf-8", "replace").strip()
    if process.returncode != 0:
        raise RuntimeError(f"S5Converter export failed with exit code {process.returncode}: {stderr_text or 'no stderr output'}")
    if stderr_text:
        raise RuntimeError(f"S5Converter export reported an error: {stderr_text}")
    if not stdout:
        raise RuntimeError("S5Converter export lieferte keine DFF-Daten (0 Bytes stdout).")
    return stdout


def load_building_model_payload(path, converter_path):
    if path.endswith(".dff"):
        with open(path, "rb") as handle:
            return convert_binary_dff_to_json(handle.read(), converter_path)

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_building_model_payload(path, payload, converter_path):
    if path.endswith(".json"):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
        return

    binary_payload = convert_json_to_binary_dff(payload, converter_path)
    with open(path, "wb") as handle:
        handle.write(binary_payload)


def is_building_anim_node_id(node_id: int | None) -> bool:
    if node_id is None:
        return False
    return 500 <= int(node_id) < 600 or int(node_id) >= MIN_ANIM_NODE_ID


def safe_decode_console(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1", errors="replace")


def ensure_armature_active() -> bpy.types.Object:
    ob = bpy.context.object
    if not ob or ob.type != "ARMATURE":
        ob = next((obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"), None)
    if not ob:
        raise RuntimeError("Keine Armature gefunden/ausgewaehlt.")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob


def root_id_from_filename(path: str) -> int:
    name = os.path.splitext(os.path.basename(path))[0]
    match = re.search(r"_(\d+)$", name)
    if not match:
        raise RuntimeError(f"Keine Root-ID im Dateinamen gefunden: {name}")

    root_id = int(match.group(1))
    if not is_building_anim_node_id(root_id):
        raise RuntimeError(
            f"Ungueltige Anim-Root-ID im Dateinamen: {root_id}. "
            f"Erwartet wird eine NodeID im Bereich 500-599 oder >= {MIN_ANIM_NODE_ID}."
        )
    return root_id


def find_bone_by_node_id(arm_ob: bpy.types.Object, node_id: int):
    suffix = "_" + str(node_id)
    for bone in arm_ob.data.bones:
        if bone.name.endswith(suffix):
            return bone
    return None


def estimate_fps_from_tracks(tracks) -> int:
    dts = []
    for track in tracks:
        times = [float(key["time"]) for key in track]
        for a, b in zip(times, times[1:]):
            dt = b - a
            if dt > 1e-6:
                dts.append(dt)

    if not dts:
        return DEFAULT_S5_FPS

    base_dt = min(dts)
    if base_dt >= 1.0:
        return DEFAULT_S5_FPS

    fps = int(round(1.0 / base_dt)) if base_dt > 0 else DEFAULT_S5_FPS
    return max(1, fps)


def determine_fps(source_format: str, tracks) -> int:
    if source_format in {ANIM_FORMAT_HIERARCHICAL, ANIM_FORMAT_COMPRESSED}:
        return DEFAULT_S5_FPS
    return estimate_fps_from_tracks(tracks)


def s5_time_to_frame(t: float, fps: int) -> float:
    return float(t * fps)


def split_subframe(frame: float) -> tuple[int, float]:
    base_frame = math.floor(float(frame))
    subframe = float(frame) - float(base_frame)
    if subframe >= 0.999999:
        return int(base_frame) + 1, 0.0
    if subframe <= 0.000001:
        return int(base_frame), 0.0
    return int(base_frame), subframe


def set_scene_frame(scene: bpy.types.Scene, frame: float):
    base_frame, subframe = split_subframe(frame)
    scene.frame_set(base_frame, subframe=subframe)


def generate_prev_keyframe_sentinel(source_name: str, root_id: int, bone_count: int) -> int:
    _ = source_name
    _ = root_id
    _ = bone_count
    return DEFAULT_START_PREV_KEYFRAME


def build_matrix_from_converter_key(key: dict) -> mu.Matrix:
    position = key["position"]
    quaternion = key["quaternion"]

    location = mu.Vector((
        float(position["x"]),
        float(position["y"]),
        float(position["z"]),
    ))
    rotation = mu.Quaternion((
        float(quaternion["w"]),
        float(quaternion["x"]),
        float(quaternion["y"]),
        float(quaternion["z"]),
    ))

    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = location
    return matrix


def parse_converter_nodes(js: dict) -> tuple[float, list[list[dict]]]:
    duration = float(js.get("duration", 0.0))
    nodes = js.get("nodes", [])
    if not nodes:
        raise RuntimeError("JSON hat keine nodes[] Tracks.")

    tracks = []
    for track_index, node_track in enumerate(nodes):
        track = []
        for key_index, key in enumerate(node_track):
            track.append({
                "time": float(key["time"]),
                "matrix": build_matrix_from_converter_key(key),
                "raw": key,
                "track_index": track_index,
                "key_index": key_index,
            })
        tracks.append(track)

    return duration, tracks


def s5_quat_to_blender(qdata):
    return mu.Quaternion((
        float(qdata["Real"]),
        float(qdata["Imaginary"]["x"]),
        float(qdata["Imaginary"]["y"]),
        float(qdata["Imaginary"]["z"]),
    ))


def s5_vec_to_blender(vdata):
    return mu.Vector((
        float(vdata["x"]),
        float(vdata["y"]),
        float(vdata["z"]),
    ))


def build_matrix_from_s5_key(key: dict) -> mu.Matrix:
    translation = s5_vec_to_blender(key["T"])
    rotation = s5_quat_to_blender(key["Q"])
    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = translation
    return matrix


def parse_hierarchical_anim_tracks(js: dict) -> tuple[float, list[list[dict]]]:
    hierarchical_anim = js.get("HierarchicalAnim")
    if not hierarchical_anim:
        raise RuntimeError("JSON enthaelt kein 'HierarchicalAnim'.")

    duration = float(hierarchical_anim.get("Duration", hierarchical_anim.get("duration", 0.0)))
    keyframes = hierarchical_anim.get("KeyFrames", [])
    if not keyframes:
        raise RuntimeError("HierarchicalAnim enthaelt keine KeyFrames.")

    starts = []
    by_prev = {}

    for index, key in enumerate(keyframes):
        prev = int(key.get("PrevKeyFrame", -1))
        time_value = float(key.get("Time", 0.0))
        if time_value == 0.0 and prev < 0:
            starts.append(index)
        by_prev.setdefault(prev, []).append(index)

    if not starts:
        raise RuntimeError("Keine Start-KeyFrames gefunden.")

    for prev_index in by_prev:
        by_prev[prev_index].sort(key=lambda item: (float(keyframes[item]["Time"]), item))

    tracks = []
    for start_index in starts:
        chain = []
        current = start_index
        visited = set()

        while current not in visited:
            visited.add(current)
            key = keyframes[current]
            chain.append({
                "time": float(key["Time"]),
                "matrix": build_matrix_from_s5_key(key),
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


def parse_animation_data(js: dict) -> tuple[float, list[list[dict]], str]:
    if "HierarchicalAnim" in js:
        duration, tracks = parse_hierarchical_anim_tracks(js)
        return duration, tracks, ANIM_FORMAT_HIERARCHICAL

    if "nodes" in js:
        duration, tracks = parse_converter_nodes(js)
        return duration, tracks, ANIM_FORMAT_NODES

    raise RuntimeError("Unbekanntes JSON-Format. Erwartet HierarchicalAnim oder nodes[].")


def extract_start_prev_keyframe_value(js: dict) -> int | None:
    hierarchical_anim = js.get("HierarchicalAnim")
    if not hierarchical_anim:
        return None

    keyframes = hierarchical_anim.get("KeyFrames", [])
    for key in keyframes:
        try:
            time_value = float(key.get("Time", 0.0))
            prev_value = int(key.get("PrevKeyFrame"))
        except Exception:
            continue

        if time_value == 0.0 and prev_value < 0:
            return prev_value

    return None


def get_bone_rest_local_matrix(arm_ob: bpy.types.Object, bone_name: str) -> mu.Matrix:
    bone = arm_ob.data.bones.get(bone_name)
    if not bone:
        raise RuntimeError(f"Bone nicht gefunden: {bone_name}")

    if bone.parent:
        return bone.parent.matrix_local.inverted() @ bone.matrix_local
    return bone.matrix_local.copy()


def posebone_set_from_local_matrix(arm_ob: bpy.types.Object, pb: bpy.types.PoseBone, local_anim_mtx: mu.Matrix):
    rest_local = get_bone_rest_local_matrix(arm_ob, pb.name)

    try:
        basis_matrix = rest_local.inverted() @ local_anim_mtx
    except Exception:
        basis_matrix = local_anim_mtx

    pb.matrix_basis = basis_matrix


def insert_posebone_keys(pb: bpy.types.PoseBone, frame: float):
    pb.keyframe_insert(data_path="location", frame=frame)
    pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    pb.keyframe_insert(data_path="scale", frame=frame)


def action_name_from_source(source_name: str) -> str:
    base_name = os.path.splitext(os.path.basename(source_name or "Animation"))[0]
    return base_name or "Animation"


def ensure_action_export_name(action: bpy.types.Action, fallback_name: str | None = None) -> str:
    if action is None:
        return fallback_name or "Animation"

    export_name = getattr(action, ACTION_EXPORT_NAME_PROP, "")
    if isinstance(export_name, str) and export_name.strip():
        export_name = export_name.strip()
        setattr(action, ACTION_EXPORT_NAME_PROP, export_name)
        return export_name

    legacy_export_name = action.get(ACTION_EXPORT_NAME_PROP)
    if isinstance(legacy_export_name, str) and legacy_export_name.strip():
        export_name = legacy_export_name.strip()
        setattr(action, ACTION_EXPORT_NAME_PROP, export_name)
        return export_name

    export_name = action_name_from_source(fallback_name or action.name)
    setattr(action, ACTION_EXPORT_NAME_PROP, export_name)
    return export_name


def sanitize_anim_fps_value(value, fallback: int = DEFAULT_S5_FPS) -> int:
    try:
        fps = int(round(float(value)))
    except Exception:
        fps = int(fallback)
    return max(1, fps)


def parse_int_string_value(value, error_message: str) -> int:
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        raise ValueError(error_message)

    if text[0] in "+-":
        sign = text[0]
        digits = text[1:]
        if not digits.isdigit():
            raise ValueError(error_message)
        return int(sign + digits)

    if not text.isdigit():
        raise ValueError(error_message)

    return int(text)


def parse_action_anim_fps(action: bpy.types.Action | None, fallback: int = DEFAULT_S5_FPS) -> int:
    if action is None:
        return sanitize_anim_fps_value(fallback, fallback)

    return max(1, parse_int_string_value(getattr(action, ACTION_ANIM_FPS_PROP, fallback), "FPS-Input is no integer value"))


def parse_action_start_prev_keyframe(action: bpy.types.Action | None, fallback: int = DEFAULT_START_PREV_KEYFRAME) -> int:
    if action is None:
        return int(fallback)

    return parse_int_string_value(
        getattr(action, ACTION_START_PREV_KEYFRAME_PROP, fallback),
        "Start-Prev-Keyframe is no integer value",
    )


def ensure_action_anim_fps(action: bpy.types.Action | None, fallback: int = DEFAULT_S5_FPS) -> int:
    fps = sanitize_anim_fps_value(fallback, fallback)
    if action is None:
        return fps

    stored = getattr(action, ACTION_ANIM_FPS_PROP, None)
    if stored is None:
        stored = action.get(ACTION_ANIM_FPS_PROP)
    fps = sanitize_anim_fps_value(stored if stored is not None else fallback, fallback)
    setattr(action, ACTION_ANIM_FPS_PROP, str(fps))
    return fps


def get_action_anim_fps(action: bpy.types.Action | None, fallback: int = DEFAULT_S5_FPS) -> int:
    return ensure_action_anim_fps(action, fallback)


def set_action_anim_fps(action: bpy.types.Action | None, fps: int):
    if action is None:
        return
    setattr(action, ACTION_ANIM_FPS_PROP, str(sanitize_anim_fps_value(fps)))


def sanitize_anim_format_value(value, fallback: str = DEFAULT_ANIM_FORMAT) -> str:
    text = str(value).strip().lower()
    if text in {ANIM_FORMAT_HIERARCHICAL, ANIM_FORMAT_COMPRESSED, ANIM_FORMAT_NODES}:
        return text
    return fallback


def ensure_action_anim_format(action: bpy.types.Action | None, fallback: str = DEFAULT_ANIM_FORMAT) -> str:
    anim_format = sanitize_anim_format_value(fallback, DEFAULT_ANIM_FORMAT)
    if action is None:
        return anim_format

    stored = getattr(action, ACTION_ANIM_FORMAT_PROP, None)
    if stored is None:
        stored = action.get(ACTION_ANIM_FORMAT_PROP)
    anim_format = sanitize_anim_format_value(stored if stored is not None else fallback, fallback)
    setattr(action, ACTION_ANIM_FORMAT_PROP, anim_format)
    return anim_format


def set_action_anim_format(action: bpy.types.Action | None, anim_format: str):
    if action is None:
        return
    setattr(action, ACTION_ANIM_FORMAT_PROP, sanitize_anim_format_value(anim_format))


def build_unique_action_name(base_name: str) -> str:
    candidate = base_name or "Animation"
    if bpy.data.actions.get(candidate) is None:
        return candidate

    suffix = 1
    while bpy.data.actions.get(f"{candidate}.{suffix:03d}") is not None:
        suffix += 1
    return f"{candidate}.{suffix:03d}"


def ensure_action_stashed_in_muted_nla(arm_ob: bpy.types.Object, action: bpy.types.Action, clear_active: bool = False):
    arm_ob.animation_data_create()
    animation_data = arm_ob.animation_data
    if action is None:
        return None

    for track in animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action == action:
                track.mute = True
                if clear_active and animation_data.action == action:
                    animation_data.action = None
                return track

    track = animation_data.nla_tracks.new()
    track.name = action.name
    frame_start = int(round(action.frame_range[0]))
    strip = track.strips.new(action.name, frame_start, action)
    strip.action_frame_start = action.frame_range[0]
    strip.action_frame_end = action.frame_range[1]
    track.mute = True
    if clear_active and animation_data.action == action:
        animation_data.action = None
    return track


def stash_active_action_in_muted_nla(arm_ob: bpy.types.Object):
    arm_ob.animation_data_create()
    animation_data = arm_ob.animation_data
    active_action = animation_data.action
    if active_action is None:
        return None

    return ensure_action_stashed_in_muted_nla(arm_ob, active_action, clear_active=True)


def create_import_action(arm_ob: bpy.types.Object, source_name: str) -> bpy.types.Action:
    arm_ob.animation_data_create()
    if arm_ob.animation_data.action is not None:
        stash_active_action_in_muted_nla(arm_ob)

    action_base_name = action_name_from_source(source_name)
    action_name = build_unique_action_name(action_base_name)
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    setattr(action, ACTION_EXPORT_NAME_PROP, action_base_name)
    set_action_anim_fps(action, DEFAULT_S5_FPS)
    set_action_anim_format(action, DEFAULT_ANIM_FORMAT)
    arm_ob.animation_data.action = action
    return action


def collect_armature_actions(arm_ob: bpy.types.Object) -> list[bpy.types.Action]:
    actions = []
    seen = set()
    animation_data = getattr(arm_ob, "animation_data", None)
    if animation_data is None:
        return actions

    if animation_data.action is not None:
        actions.append(animation_data.action)
        seen.add(animation_data.action.name_full)

    for track in animation_data.nla_tracks:
        for strip in track.strips:
            action = strip.action
            if action is None or action.name_full in seen:
                continue
            actions.append(action)
            seen.add(action.name_full)

    return actions


def isolate_action_for_export(arm_ob: bpy.types.Object, action: bpy.types.Action):
    arm_ob.animation_data_create()
    animation_data = arm_ob.animation_data
    original_action = animation_data.action
    original_track_mutes = [track.mute for track in animation_data.nla_tracks]

    for track in animation_data.nla_tracks:
        track.mute = True

    animation_data.action = action
    return original_action, original_track_mutes


def restore_action_after_export(arm_ob: bpy.types.Object, original_action, original_track_mutes):
    animation_data = getattr(arm_ob, "animation_data", None)
    if animation_data is None:
        return

    animation_data.action = original_action
    for track, mute_state in zip(animation_data.nla_tracks, original_track_mutes):
        track.mute = mute_state


def store_imported_animation_metadata(arm_ob: bpy.types.Object, action: bpy.types.Action, js: dict):
    prev_keyframe_value = extract_start_prev_keyframe_value(js)
    if prev_keyframe_value is None:
        return

    arm_ob["s5_import_prev_keyframe"] = int(prev_keyframe_value)
    if action is not None:
        setattr(action, ACTION_START_PREV_KEYFRAME_PROP, str(int(prev_keyframe_value)))


def resolve_start_prev_keyframe_value(
    arm_ob: bpy.types.Object,
    action: bpy.types.Action,
    source_name: str,
    root_id: int,
    bone_count: int,
) -> int:
    if action is not None:
        try:
            return parse_action_start_prev_keyframe(action)
        except Exception:
            pass
        try:
            return int(action.get(ACTION_START_PREV_KEYFRAME_PROP))
        except Exception:
            pass

    if "s5_import_prev_keyframe" in arm_ob:
        try:
            return int(arm_ob["s5_import_prev_keyframe"])
        except Exception:
            pass

    return generate_prev_keyframe_sentinel(source_name, root_id, bone_count)


def quat_to_converter_json(q: mu.Quaternion) -> dict:
    return {
        "w": float(q.w),
        "x": float(q.x),
        "y": float(q.y),
        "z": float(q.z),
    }


def vec_to_converter_json(v: mu.Vector) -> dict:
    return {
        "x": float(v.x),
        "y": float(v.y),
        "z": float(v.z),
    }


def quat_to_s5_json(q: mu.Quaternion) -> dict:
    return {
        "Real": float(q.w),
        "Imaginary": {
            "x": float(q.x),
            "y": float(q.y),
            "z": float(q.z),
        },
    }


def vec_to_s5_json(v: mu.Vector) -> dict:
    return {
        "x": float(v.x),
        "y": float(v.y),
        "z": float(v.z),
    }


def get_posebone_local_anim_matrix(arm_ob: bpy.types.Object, pb: bpy.types.PoseBone) -> mu.Matrix:
    rest_local = get_bone_rest_local_matrix(arm_ob, pb.name)
    return rest_local @ pb.matrix_basis.copy()


def collect_keyed_frames_for_bone(
    action: bpy.types.Action,
    bone_name: str,
    frame_start: float,
    frame_end: float,
) -> list[float]:
    prefix = f'pose.bones["{bone_name}"].'
    frames = set()
    fcurves = []

    try:
        fcurves.extend(list(action.fcurves))
    except Exception:
        pass

    try:
        slots = list(getattr(action, "slots", []))
        layers = list(getattr(action, "layers", []))
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                if slots:
                    for slot in slots:
                        try:
                            channelbag = strip.channelbag(slot)
                            if channelbag:
                                fcurves.extend(list(channelbag.fcurves))
                        except Exception:
                            continue
                else:
                    try:
                        channelbag = strip.channelbag(action_slot=None)
                        if channelbag:
                            fcurves.extend(list(channelbag.fcurves))
                    except Exception:
                        pass
    except Exception:
        pass

    for fcurve in fcurves:
        data_path = getattr(fcurve, "data_path", "")
        if not data_path.startswith(prefix):
            continue
        for keyframe in getattr(fcurve, "keyframe_points", []):
            frame = float(keyframe.co.x)
            if frame_start <= frame <= frame_end:
                frames.add(frame)

    if not frames:
        if frame_end < frame_start:
            return [frame_start]
        current = int(math.floor(frame_start))
        final_frame = int(math.ceil(frame_end))
        return [float(frame) for frame in range(current, final_frame + 1)]

    frames.add(frame_start)
    frames.add(frame_end)
    return sorted(frames)


def build_converter_track_for_bone(
    scene: bpy.types.Scene,
    arm_ob: bpy.types.Object,
    bone,
    frames: list[float],
    fps: int,
    base_frame: float,
) -> list[dict]:
    pose_bone = arm_ob.pose.bones.get(bone.name)
    if not pose_bone:
        raise RuntimeError(f"PoseBone nicht gefunden: {bone.name}")

    track = []
    pose_bone.rotation_mode = "QUATERNION"

    for frame in frames:
        set_scene_frame(scene, frame)
        bpy.context.view_layer.update()

        local_anim_matrix = get_posebone_local_anim_matrix(arm_ob, pose_bone)
        location = local_anim_matrix.to_translation()
        rotation = local_anim_matrix.to_quaternion()

        track.append({
            "time": float((frame - base_frame) / fps),
            "position": vec_to_converter_json(location),
            "quaternion": quat_to_converter_json(rotation),
        })

    return track


def convert_anm_to_json_external(anm_path: str) -> dict:
    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

    with open(anm_path, "rb") as handle:
        binary_data = handle.read()

    process = subprocess.Popen(
        [exe, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    outs, errs = process.communicate(input=binary_data)

    stdout_text = safe_decode_console(outs)
    stderr_text = safe_decode_console(errs)

    if stderr_text:
        print("[S5Converter stderr]")
        print(stderr_text)

    if process.returncode != 0:
        raise RuntimeError(f"S5Converter Fehler:\n{stderr_text}")

    try:
        return json.loads(stdout_text)
    except Exception as exc:
        raise RuntimeError(f"S5Converter lieferte kein gueltiges JSON zurueck: {exc}")


def convert_json_to_anm_external(js: dict, anm_path: str):
    if anm_path.endswith(".json"):
        with open(anm_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        return

    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

    process = subprocess.Popen(
        [exe, "--export"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    bytes_data = json.dumps(js).encode("utf-8")
    outs, errs = process.communicate(input=bytes_data)

    stderr_text = safe_decode_console(errs)
    if stderr_text:
        print("[S5Converter stderr]")
        print(stderr_text)

    try:
        with open(anm_path, "wb") as outfile:
            outfile.write(outs)
    except BrokenPipeError as exc:
        print("[ERROR] BrokenPipe beim Schreiben in Datei {}: {}".format(anm_path, exc))


__all__ = [
    "ACTION_ANIM_FPS_PROP",
    "ACTION_ANIM_FORMAT_PROP",
    "ACTION_EXPORT_NAME_PROP",
    "ACTION_START_PREV_KEYFRAME_PROP",
    "ANIM_FORMAT_COMPRESSED",
    "ANIM_FORMAT_HIERARCHICAL",
    "ANIM_FORMAT_NODES",
    "DEFAULT_ANIM_FORMAT",
    "DEFAULT_S5_FPS",
    "DEFAULT_START_PREV_KEYFRAME",
    "_build_geometry_format",
    "_collect_texture_coordinates",
    "accumulate_rest_matrix",
    "bone_name_to_node_id",
    "build_converter_track_for_bone",
    "build_matrix_from_s5_key",
    "collect_armature_actions",
    "collect_keyed_frames_for_bone",
    "convert_anm_to_json_external",
    "convert_json_to_anm_external",
    "create_import_action",
    "determine_fps",
    "edit_bone_to_matrix",
    "ensure_action_anim_fps",
    "ensure_action_anim_format",
    "ensure_action_export_name",
    "ensure_action_stashed_in_muted_nla",
    "ensure_armature_active",
    "find_bone_by_node_id",
    "frame_dict_to_matrix",
    "get_action_anim_fps",
    "get_converter_exe_location",
    "get_posebone_local_anim_matrix",
    "insert_posebone_keys",
    "isolate_action_for_export",
    "link_object_in_active_collection",
    "load_building_model_payload",
    "matrix_to_bone_axis_roll",
    "parse_action_anim_fps",
    "parse_action_start_prev_keyframe",
    "parse_animation_data",
    "parse_converter_nodes",
    "posebone_set_from_local_matrix",
    "quat_to_s5_json",
    "resolve_start_prev_keyframe_value",
    "restore_action_after_export",
    "root_id_from_filename",
    "s5_quat_to_blender",
    "s5_time_to_frame",
    "s5_vec_to_blender",
    "save_building_model_payload",
    "set_action_anim_format",
    "set_action_anim_fps",
    "set_clipping_for_all_screens",
    "set_scene_frame",
    "store_imported_animation_metadata",
    "vec_to_s5_json",
]
