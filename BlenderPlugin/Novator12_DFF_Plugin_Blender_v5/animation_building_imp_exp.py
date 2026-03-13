# ------------------------------------------Plugin Info -----------------------------------------------------------------------------------
# pyright: reportInvalidTypeForm=false

import bpy
import os
import subprocess
import json
import re
import mathutils as mu
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import StringProperty

DEFAULT_S5_FPS = 24
MIN_ANIM_NODE_ID = 600
DEFAULT_START_PREV_KEYFRAME = -123456789


# ------------------------------------------------------------
# Path / console helpers
# ------------------------------------------------------------

def get_converter_exe_location():
    addon_dir = os.path.dirname(__file__)
    exe_loc = os.path.join(addon_dir, "RW_inline.exe")
    return exe_loc


def safe_decode_console(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1", errors="replace")


# ------------------------------------------------------------
# Basic helpers
# ------------------------------------------------------------

def ensure_armature_active() -> bpy.types.Object:
    ob = bpy.context.object
    if not ob or ob.type != "ARMATURE":
        ob = next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)
    if not ob:
        raise RuntimeError("Keine Armature gefunden/ausgewählt.")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    return ob


def root_id_from_filename(path: str) -> int:
    """
    Erwartet Dateinamen wie:
    pb_university2_astrodome_601.anm
    pb_university2_astrodome_601.json
    pb_farm3_600.anm
    pb_farm3_600.json

    Gültige Anim-Root-IDs sind >= 600.
    """
    name = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r'_(\d+)$', name)
    if not m:
        raise RuntimeError(f"Keine Root-ID im Dateinamen gefunden: {name}")

    root_id = int(m.group(1))
    if root_id < MIN_ANIM_NODE_ID:
        raise RuntimeError(
            f"Ungültige Anim-Root-ID im Dateinamen: {root_id}. "
            f"Erwartet wird eine NodeID >= {MIN_ANIM_NODE_ID}."
        )
    return root_id


def nodeid_from_bonename(bname: str) -> int | None:
    """
    Erwartet Bone-Namen wie:
    frame_109_601
    frame_110_603
    """
    parts = bname.split("_")
    if len(parts) >= 3 and parts[-1].isdigit():
        return int(parts[-1])
    return None


def frame_index_from_bonename(bname: str) -> int:
    parts = bname.split("_")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 10**9


def find_bone_by_nodeid(arm_ob: bpy.types.Object, node_id: int):
    suf = "_" + str(node_id)
    for b in arm_ob.data.bones:
        if b.name.endswith(suf):
            return b
    return None


def get_bone_hanim_data(bone) -> dict | None:
    """
    Liest die beim Modellimport gespeicherten hanimData vom Bone.
    """
    if not bone:
        return None

    if "hanimData" not in bone:
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


def detect_animation_root_bone(arm_ob: bpy.types.Object):
    """
    Erkennt den wahrscheinlichsten Anim-Root im Rig.
    Kandidaten sind Bones mit NodeID >= 600, deren Parent keine Anim-Node ist.
    Bei mehreren Kandidaten gewinnt der mit dem größten Anim-Subtree.
    """
    candidates = []

    for bone in arm_ob.data.bones:
        node_id = nodeid_from_bonename(bone.name)
        if node_id is None or node_id < MIN_ANIM_NODE_ID:
            continue

        parent_node_id = nodeid_from_bonename(bone.parent.name) if bone.parent else None
        if parent_node_id is not None and parent_node_id >= MIN_ANIM_NODE_ID:
            continue

        subtree_count = len(collect_subtree_node_ids(bone))
        candidates.append((subtree_count, frame_index_from_bonename(bone.name), node_id, bone))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][3]


def resolve_export_root_id(arm_ob: bpy.types.Object, filepath: str) -> int:
    """
    Nutzt bevorzugt die Root-ID aus dem Dateinamen.
    Fällt andernfalls auf automatische Rig-Erkennung zurück.
    """
    try:
        return root_id_from_filename(filepath)
    except Exception as exc:
        print(f"[INFO] Keine gültige Root-ID im Dateinamen, nutze Auto-Erkennung: {exc}")

    root_bone = detect_animation_root_bone(arm_ob)
    if not root_bone:
        raise RuntimeError(
            "Keine Root-ID im Dateinamen gefunden und kein Anim-Root im Rig erkannt. "
            "Bitte Dateiname wie '*_600.anm' verwenden oder Rig prüfen."
        )

    root_id = nodeid_from_bonename(root_bone.name)
    if root_id is None:
        raise RuntimeError(f"Automatisch erkannter Root-Bone hat keine gültige NodeID: {root_bone.name}")

    print(f"[INFO] Auto-erkanntes Export-Root: bone={root_bone.name}, nodeID={root_id}")
    return root_id


# ------------------------------------------------------------
# Bone traversal / subtree helpers
# ------------------------------------------------------------

def collect_anim_bones_for_building(root_bone) -> list:
    """
    Fallback:
    Root selbst ist Teil der animierten Kette.
    Danach rekursiv die Kinder.
    Nur Bones mit NodeID >= 600 sind für Animation relevant.
    """
    ordered = []

    def rec(b):
        nid = nodeid_from_bonename(b.name)
        if nid is not None and nid >= MIN_ANIM_NODE_ID:
            ordered.append(b)

        kids = sorted(list(b.children), key=lambda x: (frame_index_from_bonename(x.name), x.name))
        for c in kids:
            rec(c)

    rec(root_bone)
    return ordered


def collect_subtree_node_ids(root_bone) -> set[int]:
    """
    Nur der Anim-Root aus dem Dateinamen und dessen Kinder/Subchildren sind relevant.
    Zusätzlich nur NodeIDs >= 600.
    """
    ids = set()

    def rec(b):
        nid = nodeid_from_bonename(b.name)
        if nid is not None and nid >= MIN_ANIM_NODE_ID:
            ids.add(nid)
        for c in b.children:
            rec(c)

    rec(root_bone)
    return ids


def collect_parent_chain(root_bone) -> list:
    """
    Root, Parent, ParentParent, ...
    Wird nur verwendet, um irgendwo eine HAnim-nodes-Liste zu finden.
    Die eigentliche Bone-Auswahl bleibt trotzdem auf den Root-Subtree gefiltert.
    """
    chain = []
    cur = root_bone
    while cur is not None:
        chain.append(cur)
        cur = cur.parent
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
                if node_id >= MIN_ANIM_NODE_ID:
                    ordered_ids.append(node_id)
            except Exception:
                pass

    return ordered_ids


def get_hanim_node_order_for_animation(arm_ob: bpy.types.Object, root_bone) -> list[int]:
    """
    Holt die HAnim-Node-Reihenfolge, filtert aber IMMER hart auf:
    root bone + children + subchildren des Anim-Roots
    und nur NodeIDs >= 600.

    Suchreihenfolge für die Quelle der HAnim-Liste:
    1. Root-Bone selbst
    2. Parent-Kette des Roots
    3. Alle Bones im Armature
    """
    allowed_ids = collect_subtree_node_ids(root_bone)

    print(f"[INFO] erlaubte subtree node ids: {sorted(allowed_ids)}")

    # 1) Root selbst
    ordered_ids = extract_hanim_node_ids_from_bone(root_bone)
    if ordered_ids:
        filtered = [nid for nid in ordered_ids if nid in allowed_ids]
        print(f"[INFO] hanim nodes direkt von Root {root_bone.name}: {ordered_ids}")
        print(f"[INFO] hanim nodes gefiltert auf subtree: {filtered}")
        if filtered:
            return filtered

    # 2) Parent-Kette
    for bone in collect_parent_chain(root_bone)[1:]:
        ordered_ids = extract_hanim_node_ids_from_bone(bone)
        if ordered_ids:
            filtered = [nid for nid in ordered_ids if nid in allowed_ids]
            print(f"[INFO] hanim nodes von Parent/Fallback-Bone {bone.name}: {ordered_ids}")
            print(f"[INFO] hanim nodes gefiltert auf subtree: {filtered}")
            if filtered:
                return filtered

    # 3) Notfalls alle Bones, aber weiterhin hart auf Subtree gefiltert
    for bone in arm_ob.data.bones:
        if bone == root_bone:
            continue
        ordered_ids = extract_hanim_node_ids_from_bone(bone)
        if ordered_ids:
            filtered = [nid for nid in ordered_ids if nid in allowed_ids]
            if filtered:
                print(f"[INFO] hanim nodes von globalem Fallback-Bone {bone.name}: {ordered_ids}")
                print(f"[INFO] hanim nodes gefiltert auf subtree: {filtered}")
                return filtered

    return []


def build_anim_bone_list_from_hanim(arm_ob: bpy.types.Object, root_bone) -> list:
    """
    Nutzt die HAnim-Reihenfolge, aber nur für:
    Root + Children + Subchildren des Anim-Roots.
    """
    ordered_ids = get_hanim_node_order_for_animation(arm_ob, root_bone)

    bones = []
    seen = set()

    print(f"[INFO] hanim ordered ids (final): {ordered_ids}")

    for node_id in ordered_ids:
        bone = find_bone_by_nodeid(arm_ob, node_id)
        if bone and bone.name not in seen:
            bones.append(bone)
            seen.add(bone.name)
        else:
            print(f"[WARN] Kein Bone im Rig für hanim nodeID {node_id}")

    return bones


# ------------------------------------------------------------
# Timing helpers
# ------------------------------------------------------------

def estimate_fps_from_tracks(tracks) -> int:
    """
    Für converter/nodes[] fallback.
    Für HierarchicalAnim nutzen wir fest 30 FPS.
    """
    dts = []
    for track in tracks:
        times = [float(k["time"]) for k in track]
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
    if source_format == "hierarchical":
        return DEFAULT_S5_FPS
    return estimate_fps_from_tracks(tracks)


def s5_time_to_frame(t: float, fps: int) -> int:
    return int(round(t * fps))


def generate_prev_keyframe_sentinel(source_name: str, root_id: int, bone_count: int) -> int:
    _ = source_name
    _ = root_id
    _ = bone_count
    return DEFAULT_START_PREV_KEYFRAME


# ------------------------------------------------------------
# Converter-format helpers (duration + nodes[])
# ------------------------------------------------------------

def build_matrix_from_converter_key(k: dict) -> mu.Matrix:
    p = k["position"]
    q = k["quaternion"]

    loc = mu.Vector((
        float(p["x"]),
        float(p["y"]),
        float(p["z"]),
    ))
    quat = mu.Quaternion((
        float(q["w"]),
        float(q["x"]),
        float(q["y"]),
        float(q["z"]),
    ))

    m = quat.to_matrix().to_4x4()
    m.translation = loc
    return m


def parse_converter_nodes(js: dict) -> tuple[float, list[list[dict]]]:
    duration = float(js.get("duration", 0.0))
    nodes = js.get("nodes", [])
    if not nodes:
        raise RuntimeError("JSON hat keine nodes[] Tracks.")

    tracks = []
    for track_idx, node_track in enumerate(nodes):
        tr = []
        for key_idx, k in enumerate(node_track):
            tr.append({
                "time": float(k["time"]),
                "matrix": build_matrix_from_converter_key(k),
                "raw": k,
                "track_index": track_idx,
                "key_index": key_idx,
            })
        tracks.append(tr)

    return duration, tracks


# ------------------------------------------------------------
# Raw S5 HierarchicalAnim helpers
# ------------------------------------------------------------

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
    t = s5_vec_to_blender(key["T"])
    q = s5_quat_to_blender(key["Q"])
    m = q.to_matrix().to_4x4()
    m.translation = t
    return m


def parse_hierarchical_anim_tracks(js: dict) -> tuple[float, list[list[dict]]]:
    """
    Parst die rohe S5-Struktur:
    {
      "HierarchicalAnim": {
        "Duration": ...,
        "KeyFrames": [...]
      }
    }

    Regel:
    - Start-KeyFrames: Time == 0 und PrevKeyFrame < 0
    - Nachfolger eines Keys: KeyFrames mit PrevKeyFrame == current_index
    """
    ha = js.get("HierarchicalAnim")
    if not ha:
        raise RuntimeError("JSON enthält kein 'HierarchicalAnim'.")

    duration = float(ha.get("Duration", ha.get("duration", 0.0)))
    keyframes = ha.get("KeyFrames", [])
    if not keyframes:
        raise RuntimeError("HierarchicalAnim enthält keine KeyFrames.")

    starts = []
    by_prev = {}

    for idx, k in enumerate(keyframes):
        prev = int(k.get("PrevKeyFrame", -1))
        time_val = float(k.get("Time", 0.0))

        if time_val == 0.0 and prev < 0:
            starts.append(idx)

        # DAS hat in deiner aktuellen Datei gefehlt
        by_prev.setdefault(prev, []).append(idx)

    if not starts:
        raise RuntimeError("Keine Start-KeyFrames gefunden.")

    for prev_idx in by_prev:
        by_prev[prev_idx].sort(key=lambda i: (float(keyframes[i]["Time"]), i))

    tracks = []
    for start_idx in starts:
        chain = []
        current = start_idx
        visited = set()

        while current not in visited:
            visited.add(current)
            k = keyframes[current]

            chain.append({
                "time": float(k["Time"]),
                "matrix": build_matrix_from_s5_key(k),
                "raw": k,
                "index": current,
            })

            next_candidates = by_prev.get(current, [])
            if not next_candidates:
                break

            current = next_candidates[0]

        tracks.append(chain)

    tracks.sort(key=lambda tr: tr[0]["index"])
    return duration, tracks


def parse_animation_data(js: dict) -> tuple[float, list[list[dict]], str]:
    if "HierarchicalAnim" in js:
        duration, tracks = parse_hierarchical_anim_tracks(js)
        return duration, tracks, "hierarchical"

    if "nodes" in js:
        duration, tracks = parse_converter_nodes(js)
        return duration, tracks, "nodes"

    raise RuntimeError("Unbekanntes JSON-Format. Erwartet HierarchicalAnim oder nodes[].")


def extract_start_prev_keyframe_value(js: dict) -> int | None:
    ha = js.get("HierarchicalAnim")
    if not ha:
        return None

    keyframes = ha.get("KeyFrames", [])
    for key in keyframes:
        try:
            time_val = float(key.get("Time", 0.0))
            prev_val = int(key.get("PrevKeyFrame"))
        except Exception:
            continue

        if time_val == 0.0 and prev_val < 0:
            return prev_val

    return None


def parse_animation_json(json_path: str) -> tuple[float, list[list[dict]], str]:
    with open(json_path, "r", encoding="utf-8") as f:
        js = json.load(f)
    return parse_animation_data(js)


# ------------------------------------------------------------
# Pose application
# ------------------------------------------------------------

def get_bone_rest_local_matrix(arm_ob: bpy.types.Object, bone_name: str) -> mu.Matrix:
    """
    Rest-Lokalmatrix des Bones relativ zum Parent.
    """
    bone = arm_ob.data.bones.get(bone_name)
    if not bone:
        raise RuntimeError(f"Bone nicht gefunden: {bone_name}")

    if bone.parent:
        return bone.parent.matrix_local.inverted() @ bone.matrix_local

    return bone.matrix_local.copy()


def posebone_set_from_local_matrix(arm_ob: bpy.types.Object, pb: bpy.types.PoseBone, local_anim_mtx: mu.Matrix):
    """
    local_anim_mtx ist die lokale Bone-Matrix aus der S5-Animation.
    Blender matrix_basis erwartet aber die Delta-Transform relativ zur Restpose.
    """
    rest_local = get_bone_rest_local_matrix(arm_ob, pb.name)

    try:
        basis_mtx = rest_local.inverted() @ local_anim_mtx
    except Exception:
        basis_mtx = local_anim_mtx

    pb.matrix_basis = basis_mtx


def insert_posebone_keys(pb: bpy.types.PoseBone, frame: int):
    pb.keyframe_insert(data_path="location", frame=frame)
    pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    pb.keyframe_insert(data_path="scale", frame=frame)


def clear_existing_action(arm_ob: bpy.types.Object):
    if arm_ob.animation_data and arm_ob.animation_data.action:
        old_action = arm_ob.animation_data.action
        arm_ob.animation_data.action = None
        return old_action
    return None


def store_imported_animation_metadata(arm_ob: bpy.types.Object, action: bpy.types.Action, js: dict):
    prev_keyframe_value = extract_start_prev_keyframe_value(js)
    if prev_keyframe_value is None:
        return

    arm_ob["s5_import_prev_keyframe"] = int(prev_keyframe_value)
    if action is not None:
        action["s5_import_prev_keyframe"] = int(prev_keyframe_value)


def resolve_start_prev_keyframe_value(
    arm_ob: bpy.types.Object,
    action: bpy.types.Action,
    source_name: str,
    root_id: int,
    bone_count: int,
) -> int:
    if action is not None and "s5_import_prev_keyframe" in action:
        try:
            return int(action["s5_import_prev_keyframe"])
        except Exception:
            pass

    if "s5_import_prev_keyframe" in arm_ob:
        try:
            return int(arm_ob["s5_import_prev_keyframe"])
        except Exception:
            pass

    return generate_prev_keyframe_sentinel(source_name, root_id, bone_count)


# ------------------------------------------------------------
# Export helpers
# ------------------------------------------------------------

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
    """
    Rekonstruiert die lokale S5-Bone-Matrix aus Restpose + matrix_basis.
    """
    rest_local = get_bone_rest_local_matrix(arm_ob, pb.name)
    return rest_local @ pb.matrix_basis.copy()


def collect_keyed_frames_for_bone(
    action: bpy.types.Action,
    bone_name: str,
    frame_start: int,
    frame_end: int,
) -> list[int]:
    """
    Holt echte Keyframes aus klassischem oder Layered-Action-Setup.
    Fallback bleibt Vollsampling des Frame-Bereichs.
    """
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
                channelbag = None

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

    for fc in fcurves:
        data_path = getattr(fc, "data_path", "")
        if not data_path.startswith(prefix):
            continue
        for kp in getattr(fc, "keyframe_points", []):
            frame = int(round(kp.co.x))
            if frame_start <= frame <= frame_end:
                frames.add(frame)

    if not frames:
        if frame_end < frame_start:
            return [frame_start]
        return list(range(frame_start, frame_end + 1))

    frames.add(frame_start)
    frames.add(frame_end)
    return sorted(frames)


def build_converter_track_for_bone(
    scene: bpy.types.Scene,
    arm_ob: bpy.types.Object,
    bone,
    frames: list[int],
    fps: int,
    base_frame: int,
) -> list[dict]:
    pb = arm_ob.pose.bones.get(bone.name)
    if not pb:
        raise RuntimeError(f"PoseBone nicht gefunden: {bone.name}")

    track = []
    pb.rotation_mode = "QUATERNION"

    for frame in frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        local_anim_mtx = get_posebone_local_anim_matrix(arm_ob, pb)
        loc = local_anim_mtx.to_translation()
        quat = local_anim_mtx.to_quaternion()

        track.append({
            "time": float((frame - base_frame) / fps),
            "position": vec_to_converter_json(loc),
            "quaternion": quat_to_converter_json(quat),
        })

    return track


def build_animation_export_json(
    arm_ob: bpy.types.Object,
    root_id: int,
    action: bpy.types.Action,
    frame_start: int,
    frame_end: int,
    fps: int,
    source_name: str,
) -> dict:
    root_bone = find_bone_by_nodeid(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    anim_bones = build_anim_bone_list_from_hanim(arm_ob, root_bone)
    if not anim_bones:
        print("[WARN] Keine hanimPLG Node-Reihenfolge gefunden -> fallback Hierarchie.")
        anim_bones = collect_anim_bones_for_building(root_bone)

    if not anim_bones:
        raise RuntimeError(f"Keine animierbaren Bones unter Root {root_id} gefunden.")

    duration = max(0.0, float(frame_end - frame_start) / fps)
    track_entries = []

    for bone in anim_bones:
        frames = collect_keyed_frames_for_bone(action, bone.name, frame_start, frame_end)
        track = build_converter_track_for_bone(
            scene=bpy.context.scene,
            arm_ob=arm_ob,
            bone=bone,
            frames=frames,
            fps=fps,
            base_frame=frame_start,
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


def convert_json_to_anm_external(js: dict, anm_path: str):
    debug_dir = r"C:/Users/olive/Downloads"
    debug_name = os.path.splitext(os.path.basename(anm_path))[0] + "_debug_export.json"
    debug_path = os.path.join(debug_dir, debug_name)

    try:
        os.makedirs(debug_dir, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        print(f"[INFO] Debug-JSON geschrieben: {debug_path}")
    except Exception as e:
        print(f"[WARN] Konnte Debug-JSON nicht schreiben: {e}")

    if anm_path.endswith(".json"):
        with open(anm_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        return

    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"RW_inline.exe nicht gefunden: {exe}")

    p = subprocess.Popen([exe, "--export"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    js_str = json.dumps(js)
    bytes_data = js_str.encode("utf-8")
    outs, errs = p.communicate(input=bytes_data)

    stderr_text = safe_decode_console(errs)
    if stderr_text:
        print("[RW_inline stderr]")
        print(stderr_text)

    try:
        with open(anm_path, "wb") as outfile:
            outfile.write(outs)
    except BrokenPipeError as e:
        print("[ERROR] BrokenPipe beim Schreiben in Datei {}: {}".format(anm_path, e))


# ------------------------------------------------------------
# Main animation application
# ------------------------------------------------------------

def apply_tracks_to_armature(
    arm_ob: bpy.types.Object,
    root_id: int,
    duration: float,
    tracks: list[list[dict]],
    source_format: str,
):
    root_bone = find_bone_by_nodeid(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    # Primär: Reihenfolge aus HAnim, aber nur innerhalb des Root-Subtrees
    anim_bones = build_anim_bone_list_from_hanim(arm_ob, root_bone)

    # Fallback: nur Root + Children + Subchildren
    if not anim_bones:
        print("[WARN] Keine hanimPLG Node-Reihenfolge gefunden -> fallback Hierarchie.")
        anim_bones = collect_anim_bones_for_building(root_bone)

    if not anim_bones:
        raise RuntimeError(f"Keine animierbaren Bones unter Root {root_id} gefunden.")

    n = min(len(tracks), len(anim_bones))
    if n == 0:
        raise RuntimeError("Keine passenden Tracks/Bones gefunden.")

    if len(tracks) != len(anim_bones):
        print(
            f"[WARN] Trackcount != Bonecount: "
            f"tracks={len(tracks)} bones={len(anim_bones)} -> benutze n={n}"
        )

    fps = determine_fps(source_format, tracks)

    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start = 0
    scene.frame_end = max(0, int(round(duration * fps)))

    arm_ob.animation_data_create()
    clear_existing_action(arm_ob)

    action_name = f"SkinAction_{root_id}"
    action = bpy.data.actions.new(action_name)
    arm_ob.animation_data.action = action

    bpy.context.view_layer.objects.active = arm_ob
    arm_ob.select_set(True)
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="POSE")

    print(f"[INFO] Root-Bone: {root_bone.name}")
    print(f"[INFO] Tracks: {len(tracks)}")
    print(f"[INFO] AnimBones: {len(anim_bones)}")
    print(f"[INFO] FPS: {fps}")

    for i, bone in enumerate(anim_bones[:20]):
        print(f"[INFO] Track {i} -> Bone {bone.name}")

    for i in range(n):
        bone = anim_bones[i]
        pb = arm_ob.pose.bones.get(bone.name)
        if not pb:
            print(f"[WARN] PoseBone nicht gefunden: {bone.name}")
            continue

        pb.rotation_mode = "QUATERNION"

        for key in tracks[i]:
            frame = s5_time_to_frame(float(key["time"]), fps)
            scene.frame_set(frame)

            local_anim_mtx = key["matrix"]
            posebone_set_from_local_matrix(arm_ob, pb, local_anim_mtx)
            insert_posebone_keys(pb, frame)

    scene.frame_set(scene.frame_start)
    print(
        f"[INFO] Animation importiert. "
        f"format={source_format}, root_id={root_id}, fps={fps}, tracks={len(tracks)}, used={n}"
    )
    return action


def apply_animation_json_to_armature(json_path: str, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_animation_json(json_path)
    root_id = root_id_from_filename(source_name_for_root)
    action = apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format)
    with open(json_path, "r", encoding="utf-8") as f:
        js = json.load(f)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


def apply_animation_data_to_armature(js: dict, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_animation_data(js)
    root_id = root_id_from_filename(source_name_for_root)
    action = apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format)
    store_imported_animation_metadata(arm_ob, action, js)
    return action


def convert_anm_to_json_external(anm_path: str) -> dict:
    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"RW_inline.exe nicht gefunden: {exe}")

    with open(anm_path, "rb") as f:
        binary_data = f.read()

    p = subprocess.Popen(
        [exe, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    outs, errs = p.communicate(input=binary_data)

    stdout_text = safe_decode_console(outs)
    stderr_text = safe_decode_console(errs)

    if stderr_text:
        print("[RW_inline stderr]")
        print(stderr_text)

    if p.returncode != 0:
        raise RuntimeError(f"RW_inline Fehler:\n{stderr_text}")

    try:
        return json.loads(stdout_text)
    except Exception as e:
        raise RuntimeError(f"RW_inline lieferte kein gültiges JSON zurück: {e}")


def convert_json_to_anm_external(js: dict, anm_path: str):
    if anm_path.endswith(".json"):
        with open(anm_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        return

    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"RW_inline.exe nicht gefunden: {exe}")

    p = subprocess.Popen([exe, "--export"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    js_str = json.dumps(js)
    bytes_data = js_str.encode("utf-8")
    outs, errs = p.communicate(input=bytes_data)

    stderr_text = safe_decode_console(errs)
    if stderr_text:
        print("[RW_inline stderr]")
        print(stderr_text)

    try:
        with open(anm_path, "wb") as outfile:
            outfile.write(outs)
    except BrokenPipeError as e:
        print("[ERROR] BrokenPipe beim Schreiben in Datei {}: {}".format(anm_path, e))


# ------------------------------------------------------------
# Operators
# ------------------------------------------------------------

class AnimationImporterANM(Operator, ImportHelper):
    bl_idname = "import_anim.anm"
    bl_label = "Novator-Import-Building-Animation (.anm)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})

    def execute(self, context):
        anm_path = self.filepath

        try:
            arm_ob = ensure_armature_active()
            js = convert_anm_to_json_external(anm_path)
            apply_animation_data_to_armature(js, arm_ob, anm_path)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class AnimationImporterJSON(Operator, ImportHelper):
    bl_idname = "import_anim.json_building"
    bl_label = "Novator-Import-Building-Animation JSON (.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        json_path = self.filepath
        try:
            arm_ob = ensure_armature_active()
            apply_animation_json_to_armature(json_path, arm_ob, json_path)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class AnimationExporterANM(Operator, ExportHelper):
    bl_idname = "export_anim.anm"
    bl_label = "Novator-Export-Animation (.anm)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})

    def execute(self, context):
        try:
            arm_ob = ensure_armature_active()
            if not arm_ob.animation_data or not arm_ob.animation_data.action:
                raise RuntimeError("Keine aktive Action auf der Armature gefunden.")

            action = arm_ob.animation_data.action
            scene = context.scene
            frame_start = int(scene.frame_start)
            frame_end = int(scene.frame_end)
            fps = int(scene.render.fps) if scene.render.fps > 0 else DEFAULT_S5_FPS
            root_id = resolve_export_root_id(arm_ob, self.filepath)

            current_frame = scene.frame_current
            try:
                js = build_animation_export_json(
                    arm_ob=arm_ob,
                    root_id=root_id,
                    action=action,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    fps=fps,
                    source_name=os.path.basename(self.filepath),
                )
                convert_json_to_anm_external(js, self.filepath)
            finally:
                scene.frame_set(current_frame)

            self.report({'INFO'}, f"Animation exportiert: {os.path.basename(self.filepath)}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
