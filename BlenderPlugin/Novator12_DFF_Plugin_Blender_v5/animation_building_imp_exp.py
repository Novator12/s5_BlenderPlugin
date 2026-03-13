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
    return apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format)


def apply_animation_data_to_armature(js: dict, arm_ob: bpy.types.Object, source_name_for_root: str):
    duration, tracks, source_format = parse_animation_data(js)
    root_id = root_id_from_filename(source_name_for_root)
    return apply_tracks_to_armature(arm_ob, root_id, duration, tracks, source_format)


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
            self.report({'INFO'}, "Export noch nicht implementiert.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}