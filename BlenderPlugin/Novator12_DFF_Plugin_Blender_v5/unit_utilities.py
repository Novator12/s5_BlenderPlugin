import bmesh
import bpy
import json
import os

from collections import OrderedDict
import mathutils as mu
from mathutils import Matrix

from .building_utilities import (
    DEFAULT_S5_FPS,
    _build_geometry_format,
    _collect_texture_coordinates,
    accumulate_rest_matrix,
    bone_name_to_node_id,
    build_converter_track_for_bone,
    build_matrix_from_s5_key,
    collect_armature_actions,
    collect_keyed_frames_for_bone,
    convert_anm_to_json_external,
    convert_json_to_anm_external,
    create_import_action,
    determine_fps,
    edit_bone_to_matrix,
    ensure_action_anim_fps,
    ensure_action_export_name,
    ensure_armature_active,
    find_bone_by_node_id,
    frame_dict_to_matrix,
    get_posebone_local_anim_matrix,
    get_action_anim_fps,
    get_converter_exe_location,
    isolate_action_for_export,
    insert_posebone_keys,
    link_object_in_active_collection,
    load_building_model_payload,
    matrix_to_bone_axis_roll,
    parse_animation_data,
    parse_converter_nodes,
    posebone_set_from_local_matrix,
    quat_to_s5_json,
    resolve_start_prev_keyframe_value,
    restore_action_after_export,
    root_id_from_filename,
    save_building_model_payload,
    set_action_anim_format,
    set_action_anim_fps,
    set_scene_frame,
    s5_quat_to_blender,
    s5_time_to_frame,
    s5_vec_to_blender,
    store_imported_animation_metadata,
    vec_to_s5_json,
)


BONE_NAME_PADDING = 3
BONE_DISPLAY_LENGTH = 10.0 # BoneSize in Blender
WEIGHT_EPSILON = 1.0e-6


def load_unit_model_payload(path, converter_path):
    return load_building_model_payload(path, converter_path)


def unit_name_from_path(path):
    return os.path.splitext(os.path.basename(path))[0]


def _extract_frame_metadata(frame_container):
    frame_data = frame_container["frame"]
    extension = frame_container.get("extension", {})
    hanim_data = extension.get("hanimPLG")

    return {
        "parent_index": frame_data["parentFrameIndex"],
        "matrix": frame_dict_to_matrix(frame_data).transposed(),
        "node_id": None if hanim_data is None else hanim_data.get("nodeID"),
        "user_data": extension.get("userDataPLG"),
        "hanim_data": hanim_data,
    }


def _accumulate_world_matrix(frames, hierarchy, start_index):
    world_matrix = frames[start_index]
    parent_index = hierarchy[start_index]

    while parent_index != -1:
        world_matrix = frames[parent_index] @ world_matrix
        parent_index = hierarchy[parent_index]

    return world_matrix


def _format_bone_name(frame_index, node_id):
    base_name = "frame_{:0{width}d}".format(frame_index, width=BONE_NAME_PADDING)
    return f"{base_name}_{node_id}" if node_id is not None else base_name


def _build_hanim_node_index_map(frame_containers, node_ids):
    node_id_to_frame_index = {}
    for frame_index, node_id in enumerate(node_ids):
        if node_id is not None and node_id not in node_id_to_frame_index:
            node_id_to_frame_index[node_id] = frame_index

    for frame_container in frame_containers:
        extension = frame_container.get("extension", {})
        hanim_data = extension.get("hanimPLG")
        if not hanim_data:
            continue

        nodes = hanim_data.get("nodes", [])
        if not nodes:
            continue

        node_index_to_frame_index = {}
        for node_entry in nodes:
            node_index = node_entry.get("nodeIndex")
            node_id = node_entry.get("nodeID")
            frame_index = node_id_to_frame_index.get(node_id)
            if node_index is None or frame_index is None:
                continue
            node_index_to_frame_index[int(node_index)] = frame_index
        return node_index_to_frame_index

    return {}


def _extract_root_hanim_payload(frame_containers):
    for frame_container in frame_containers:
        extension = frame_container.get("extension", {})
        hanim_data = extension.get("hanimPLG")
        if not hanim_data:
            continue

        nodes = hanim_data.get("nodes", [])
        parents = hanim_data.get("parents")
        if nodes:
            return nodes, parents

    return None, None


def build_unit_armature_from_frames(frame_containers, use_connect):
    metadata_entries = [_extract_frame_metadata(frame_container) for frame_container in frame_containers]
    frames = [entry["matrix"] for entry in metadata_entries]
    hierarchy = [entry["parent_index"] for entry in metadata_entries]
    node_ids = [entry["node_id"] for entry in metadata_entries]
    node_index_to_frame_index = _build_hanim_node_index_map(frame_containers, node_ids)
    root_hanim_nodes, root_hanim_parents = _extract_root_hanim_payload(frame_containers)

    armature = bpy.data.armatures.new("Armature_UnitSkin")
    armature_object = bpy.data.objects.new("Armature_UnitSkin", armature)
    link_object_in_active_collection(armature_object)

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.edit_bones
    bone_names = []

    for frame_index, entry in enumerate(metadata_entries):
        bone_name = _format_bone_name(frame_index, node_ids[frame_index])
        bone_names.append(bone_name)

        edit_bone = edit_bones.new(bone_name)
        world_matrix = _accumulate_world_matrix(frames, hierarchy, frame_index)
        bone_axis, bone_roll = matrix_to_bone_axis_roll(world_matrix.to_3x3())

        edit_bone.head = world_matrix.to_translation()
        edit_bone.tail = edit_bone.head + bone_axis * BONE_DISPLAY_LENGTH
        edit_bone.roll = bone_roll

        parent_index = hierarchy[frame_index]
        if parent_index != -1:
            edit_bone.parent = edit_bones[parent_index]
            if use_connect:
                edit_bone.use_connect = True

        if entry["user_data"] is not None:
            edit_bone["userData"] = entry["user_data"]
        if entry["hanim_data"] is not None:
            edit_bone["hanimData"] = entry["hanim_data"]

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    armature.show_names = True
    armature_object.show_in_front = True
    if root_hanim_nodes is not None:
        armature_object["s5_root_hanim_nodes"] = json.dumps(root_hanim_nodes)
    if root_hanim_parents is not None:
        armature_object["s5_root_hanim_parents"] = json.dumps(root_hanim_parents)
    return armature_object, bone_names, node_index_to_frame_index


def _extract_uv_coordinates(geometry_data, bm):
    primary_uvs = [
        (coords["u"], coords["v"])
        for coords in geometry_data.get("textureCoordinates", [[]])[0]
    ] if geometry_data.get("textureCoordinates") else []

    secondary_uvs = []
    secondary_layer = None
    if len(geometry_data.get("textureCoordinates", [])) > 1:
        secondary_layer = bm.loops.layers.uv.new("UVMap_2")
        secondary_uvs = [
            (coords["u"], coords["v"])
            for coords in geometry_data["textureCoordinates"][1]
        ]

    return primary_uvs, secondary_uvs, secondary_layer


def _populate_vertices(bm, geometry_data):
    morph_target = geometry_data["morphTargets"][0]

    for vertex_index, json_vertex in enumerate(morph_target.get("vertices", [])):
        vertex = bm.verts.new((json_vertex["x"], json_vertex["y"], json_vertex["z"]))

        normals = morph_target.get("normals", [])
        if vertex_index < len(normals):
            normal = normals[vertex_index]
            vertex.normal = (normal["x"], normal["y"], normal["z"])

    bm.verts.index_update()
    bm.verts.ensure_lookup_table()


def _populate_faces(bm, uv_layer, snow_uv_layer, geometry_data, primary_uvs, secondary_uvs):
    for triangle in geometry_data.get("triangles", []):
        try:
            vertices = [bm.verts[triangle["v1"]], bm.verts[triangle["v2"]], bm.verts[triangle["v3"]]]
            face = bm.faces.new(vertices)
            bm.faces.index_update()
            face.material_index = int(triangle.get("materialId", 0))

            for vertex in vertices:
                loop = next(loop for loop in face.loops if loop.vert == vertex)
                if vertex.index < len(primary_uvs):
                    u_coord, v_coord = primary_uvs[vertex.index]
                    loop[uv_layer].uv = (u_coord, 1.0 - v_coord)

                if secondary_uvs and snow_uv_layer is not None and vertex.index < len(secondary_uvs):
                    snow_u, snow_v = secondary_uvs[vertex.index]
                    loop[snow_uv_layer].uv = (snow_u, 1.0 - snow_v)
        except ValueError:
            continue


def _ensure_material_slot(mesh, material_name):
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)
    mesh.materials.append(material)


def _assign_unit_materials(mesh_object, geometry_data, mesh_index):
    materials = geometry_data.get("materials", [])
    if not materials:
        _ensure_material_slot(mesh_object.data, "UnitMaterial{:02d}".format(mesh_index))
        return

    for material_index, material_data in enumerate(materials):
        textures = material_data.get("textures", [])
        if textures:
            material_name = textures[0].get("texture", "UnitMaterial{:02d}_{:02d}".format(mesh_index, material_index))
        else:
            material_name = "UnitMaterial{:02d}_{:02d}".format(mesh_index, material_index)
        _ensure_material_slot(mesh_object.data, material_name)
        material = mesh_object.data.materials[-1]
        material["s5_material_payload"] = json.dumps(material_data)
        material["s5_texture_name"] = material_name
        material["s5_texture_alpha"] = textures[0].get("textureAlpha", "") if textures else ""

        surface_props = material_data.get("SurfaceProps", {})
        material["s5_ambient"] = int(surface_props.get("ambient", 1))
        material["s5_specular"] = int(surface_props.get("specular", 0))
        material["s5_diffuse"] = int(surface_props.get("diffuse", 1))

        material_fx = material_data.get("extension", {}).get("MaterialFXMat", {}).get("Data1", {})
        material["s5_dual_tex"] = material_fx.get("Type", "") == "DualTexture"
        texture_1 = material_fx.get("Texture1") or {}
        material["s5_spec_texture"] = texture_1.get("texture", "")


def _determine_unit_mesh_name(unit_name, mesh_index, mesh_count):
    if mesh_count <= 1:
        return unit_name
    return "{}{}".format(unit_name, mesh_index)


def _build_unit_mesh_object(geometry_data, armature_object, mesh_name, mesh_index):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.verify()
    primary_uvs, secondary_uvs, snow_uv_layer = _extract_uv_coordinates(geometry_data, bm)

    _populate_vertices(bm, geometry_data)
    _populate_faces(bm, uv_layer, snow_uv_layer, geometry_data, primary_uvs, secondary_uvs)

    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    mesh_object = bpy.data.objects.new(mesh_name, mesh)
    link_object_in_active_collection(mesh_object)

    armature_modifier = mesh_object.modifiers.new(type="ARMATURE", name="skeleton")
    armature_modifier.object = armature_object

    _assign_unit_materials(mesh_object, geometry_data, mesh_index)

    return mesh_object


def _unpack_vertex_bone_slots(packed_value):
    packed_int = int(packed_value)
    return [
        packed_int & 0xFF,
        (packed_int >> 8) & 0xFF,
        (packed_int >> 16) & 0xFF,
        (packed_int >> 24) & 0xFF,
    ]


def _resolve_frame_index_from_skin_slot(slot, used_bones, node_index_to_frame_index):
    if slot in node_index_to_frame_index:
        return node_index_to_frame_index[slot]

    if 0 <= slot < len(used_bones):
        node_index = int(used_bones[slot])
        mapped_frame_index = node_index_to_frame_index.get(node_index)
        if mapped_frame_index is not None:
            return mapped_frame_index

    return None


def _assign_skinning(mesh_object, geometry_data, bone_names, node_index_to_frame_index):
    skin_plg = geometry_data.get("extension", {}).get("SkinPLG")
    if not skin_plg:
        return

    used_bones = skin_plg.get("UsedBones", [])
    vertex_bone_indices = skin_plg.get("VertexBoneIndices", [])
    vertex_bone_weights = skin_plg.get("VertexBoneWeights", [])
    weight_keys = ("w0", "w1", "w2", "w3")

    for vertex_index, packed_indices in enumerate(vertex_bone_indices):
        if vertex_index >= len(vertex_bone_weights):
            break

        weights = vertex_bone_weights[vertex_index]
        bone_slots = _unpack_vertex_bone_slots(packed_indices)
        assignments = {}

        for channel_index, weight_key in enumerate(weight_keys):
            weight = float(weights.get(weight_key, 0.0))
            if weight <= WEIGHT_EPSILON:
                continue

            frame_index = _resolve_frame_index_from_skin_slot(
                bone_slots[channel_index],
                used_bones,
                node_index_to_frame_index,
            )
            if frame_index is None:
                continue

            bone_name = bone_names[frame_index]
            assignments[bone_name] = assignments.get(bone_name, 0.0) + weight

        total_weight = sum(assignments.values())
        if total_weight <= WEIGHT_EPSILON:
            continue

        for bone_name, combined_weight in assignments.items():
            vertex_group = mesh_object.vertex_groups.get(bone_name)
            if vertex_group is None:
                vertex_group = mesh_object.vertex_groups.new(name=bone_name)

            vertex_group.add([vertex_index], combined_weight / total_weight, "REPLACE")


def _create_selection_sphere(mesh_object, sphere_data):
    if sphere_data is None:
        return

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=sphere_data["radius"],
        location=(sphere_data["x"], sphere_data["y"], sphere_data["z"]),
    )
    sphere_object = bpy.context.object
    sphere_object.name = "{}_SelectionSphere".format(mesh_object.name)
    sphere_object.parent = mesh_object
    sphere_object.display_type = "WIRE"
    sphere_object.hide_render = True

    mesh_object["sphere_name"] = sphere_object.name
    sphere_object["linked_mesh"] = mesh_object.name
    sphere_object["s5_sphere_type"] = "SelectionSphere"


def build_unit_geometry(geometry_data, armature_object, bone_names, node_index_to_frame_index, mesh_name, mesh_index):
    mesh_object = _build_unit_mesh_object(geometry_data, armature_object, mesh_name, mesh_index)
    _assign_skinning(mesh_object, geometry_data, bone_names, node_index_to_frame_index)

    morph_target = geometry_data.get("morphTargets", [{}])[0]
    _create_selection_sphere(mesh_object, morph_target.get("sphere"))
    return mesh_object


def import_unit_clump(js, unit_name, use_connect=False):
    clump_data = js["clump"]
    armature_object, bone_names, node_index_to_frame_index = build_unit_armature_from_frames(clump_data["frames"], use_connect)
    mesh_count = len(clump_data.get("atomics", []))

    for mesh_index, atomic_entry in enumerate(clump_data.get("atomics", []), start=1):
        geometry_index = atomic_entry["geometryIndex"]
        geometry_data = clump_data["geometries"][geometry_index]
        mesh_name = _determine_unit_mesh_name(unit_name, mesh_index, mesh_count)
        mesh_object = build_unit_geometry(
            geometry_data,
            armature_object,
            bone_names,
            node_index_to_frame_index,
            mesh_name,
            mesh_index,
        )
        mesh_object["s5_atomic_frame_index"] = int(atomic_entry.get("frameIndex", 0))
        mesh_object["s5_atomic_extension"] = json.dumps(atomic_entry.get("extension", {}))
        mesh_object["s5_bin_mesh_plg"] = json.dumps(geometry_data.get("extension", {}).get("BinMeshPLG", {}))
        mesh_object["s5_triangles"] = json.dumps(geometry_data.get("triangles", []))
        mesh_object["s5_skin_plg"] = json.dumps(geometry_data.get("extension", {}).get("SkinPLG", {}))
        if "userDataPLG" in geometry_data.get("extension", {}):
            mesh_object["s5_geometry_user_data"] = json.dumps(geometry_data["extension"].get("userDataPLG"))

    return armature_object


def resolve_unit_armature_for_export(context):
    active_object = context.object
    if active_object is None or active_object.type != "ARMATURE":
        active_object = next((obj for obj in context.scene.objects if obj.type == "ARMATURE"), None)

    if active_object is None:
        raise RuntimeError("Kein Armature-Objekt für den Unit-Export gefunden.")

    context.view_layer.objects.active = active_object
    active_object.select_set(True)
    return active_object


def determine_unit_bone_names_sorted(armature_object):
    bone_names = [bone.name for bone in armature_object.data.bones]
    return sorted(
        bone_names,
        key=lambda name: int(name.split("_")[1]) if len(name.split("_")) > 1 and name.split("_")[1].isdigit() else 10 ** 9,
    )


def collect_unit_armature_export_state(armature_object):
    bone_names_sorted = determine_unit_bone_names_sorted(armature_object)

    if not bpy.ops.object.mode_set.poll():
        raise RuntimeError("Kann nicht in EDIT-Mode wechseln (kein aktives Armature im passenden Kontext).")

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        hierarchy = []
        rest_matrices = []
        hanim_data_entries = []
        node_ids = []

        for bone_name in bone_names_sorted:
            bone = armature_object.data.edit_bones.get(bone_name)
            if bone is None:
                continue

            parent_index = -1
            if bone.parent is not None and bone.parent.name in bone_names_sorted:
                parent_index = bone_names_sorted.index(bone.parent.name)
            hierarchy.append(parent_index)

            relative_matrix = edit_bone_to_matrix(bone)
            if bone.parent:
                parent_matrix = edit_bone_to_matrix(bone.parent)
                relative_matrix = parent_matrix.inverted() @ relative_matrix
            rest_matrices.append(relative_matrix)

            hanim_data = bone.get("hanimData")
            hanim_data_entries.append(hanim_data.to_dict() if hanim_data is not None else None)
            node_ids.append(bone_name_to_node_id(bone_name))

        return {
            "bone_names_sorted": bone_names_sorted,
            "hierarchy": hierarchy,
            "rest_matrices": rest_matrices,
            "hanim_data_entries": hanim_data_entries,
            "node_ids": node_ids,
            "root_hanim_nodes": json.loads(armature_object.get("s5_root_hanim_nodes", "null")),
            "root_hanim_parents": json.loads(armature_object.get("s5_root_hanim_parents", "null")),
        }
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def _build_unit_hanim_nodes(node_ids, hierarchy, root_hanim_nodes=None, root_hanim_parents=None):
    if root_hanim_nodes:
        node_id_to_frame_index = {}
        for frame_index, node_id in enumerate(node_ids):
            if node_id != -1 and node_id not in node_id_to_frame_index:
                node_id_to_frame_index[node_id] = frame_index

        frame_index_to_node_index = {}
        for node_entry in root_hanim_nodes:
            node_id = node_entry.get("nodeID")
            node_index = node_entry.get("nodeIndex")
            frame_index = node_id_to_frame_index.get(node_id)
            if frame_index is None or node_index is None:
                continue
            frame_index_to_node_index[frame_index] = int(node_index)

        if frame_index_to_node_index:
            preserved_nodes = []
            for node_entry in root_hanim_nodes:
                preserved_nodes.append({
                    "flags": dict(node_entry.get("flags", {})),
                    "nodeID": node_entry.get("nodeID"),
                    "nodeIndex": node_entry.get("nodeIndex"),
                })
            return preserved_nodes, root_hanim_parents, frame_index_to_node_index

    frame_index_to_node_index = {}
    node_entries = []

    for frame_index, node_id in enumerate(node_ids):
        if node_id == -1:
            continue
        node_index = len(node_entries)
        frame_index_to_node_index[frame_index] = node_index
        node_entries.append({
            "frame_index": frame_index,
            "nodeID": node_id,
        })

    parents = []
    children = {entry["frame_index"]: [] for entry in node_entries}
    for entry in node_entries:
        frame_index = entry["frame_index"]
        parent_frame_index = hierarchy[frame_index]
        if parent_frame_index in frame_index_to_node_index:
            children[parent_frame_index].append(frame_index)

    formatted_nodes = []
    for entry in node_entries:
        frame_index = entry["frame_index"]
        parent_frame_index = hierarchy[frame_index]
        parent_node_index = frame_index_to_node_index.get(parent_frame_index, -1)
        parents.append(parent_node_index)

        sibling_frames = children.get(parent_frame_index, [])
        last_sibling = True if not sibling_frames else sibling_frames[-1] == frame_index
        formatted_nodes.append({
            "flags": {
                "HasChildren": len(children.get(frame_index, [])) > 0,
                "LastSibling": last_sibling,
            },
            "nodeID": entry["nodeID"],
            "nodeIndex": frame_index_to_node_index[frame_index],
        })

    return formatted_nodes, parents, frame_index_to_node_index


def build_unit_frame_entries(hierarchy, rest_matrices, hanim_data_entries, node_ids, root_hanim_nodes=None, root_hanim_parents=None):
    hanim_nodes, hanim_parents, frame_index_to_node_index = _build_unit_hanim_nodes(
        node_ids,
        hierarchy,
        root_hanim_nodes,
        root_hanim_parents,
    )
    root_frame_index = next(
        (frame_index for frame_index, node_id in enumerate(node_ids) if node_id == 2000),
        next((frame_index for frame_index, node_id in enumerate(node_ids) if node_id != -1), 0),
    )

    frame_entries = []
    for frame_index, parent_index in enumerate(hierarchy):
        transform = rest_matrices[frame_index]
        position = transform.to_translation()
        rotation = transform.to_3x3().transposed()
        node_id = node_ids[frame_index]

        frame_entry = OrderedDict()
        frame_entry["frame"] = OrderedDict()
        frame_entry["frame"]["parentFrameIndex"] = parent_index
        frame_entry["frame"]["position"] = {
            "x": position[0],
            "y": position[1],
            "z": position[2],
        }
        frame_entry["frame"]["rotationMatrix"] = [
            {"x": rotation[0][0], "y": rotation[0][1], "z": rotation[0][2]},
            {"x": rotation[1][0], "y": rotation[1][1], "z": rotation[1][2]},
            {"x": rotation[2][0], "y": rotation[2][1], "z": rotation[2][2]},
        ]
        frame_entry["frame"]["UnknownIntProbablyUnused"] = 3

        extension = OrderedDict()
        if node_id != -1:
            hanim_data = hanim_data_entries[frame_index] or {}
            flags = hanim_data.get("flags", {})
            extension["hanimPLG"] = {
                "nodeID": node_id,
                "flags": {
                    "SubHierarchy": bool(flags.get("SubHierarchy", False)),
                    "NoMatrices": bool(flags.get("NoMatrices", False)),
                    "UpdateModellingMatrices": bool(flags.get("UpdateModellingMatrices", False)),
                    "UpdateLTMs": bool(flags.get("UpdateLTMs", False)),
                    "LocalSpaceMatrices": bool(flags.get("LocalSpaceMatrices", False)),
                },
                "keyFrameSize": 0,
                "nodes": [],
                "parents": None,
                "ReBuildNodesArray": False,
            }

            if frame_index == root_frame_index:
                extension["hanimPLG"]["flags"] = {
                    "SubHierarchy": False,
                    "NoMatrices": False,
                    "UpdateModellingMatrices": True,
                    "UpdateLTMs": True,
                    "LocalSpaceMatrices": True,
                }
                extension["hanimPLG"]["keyFrameSize"] = 36
                extension["hanimPLG"]["nodes"] = hanim_nodes
                extension["hanimPLG"]["parents"] = hanim_parents

        frame_entry["extension"] = extension
        frame_entries.append(frame_entry)

    return frame_entries, frame_index_to_node_index


def collect_unit_meshes_for_armature(armature_object):
    meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.get("linked_mesh"):
            continue
        if any(mod.type == "ARMATURE" and mod.object == armature_object for mod in obj.modifiers):
            meshes.append(obj)

    return sorted(meshes, key=lambda obj: obj.name)


def _collect_unit_normals(mesh_object):
    return [
        OrderedDict((("x", vertex.normal.x), ("y", vertex.normal.y), ("z", vertex.normal.z)))
        for vertex in mesh_object.data.vertices
    ]


def _collect_unit_vertices(mesh_object):
    return [
        OrderedDict((("x", vertex.co.x), ("y", vertex.co.y), ("z", vertex.co.z)))
        for vertex in mesh_object.data.vertices
    ]


def _collect_unit_sphere(mesh_object):
    for child in mesh_object.children:
        if child.type != "MESH":
            continue
        if child.get("linked_mesh") != mesh_object.name:
            continue

        sphere = OrderedDict()
        sphere["x"] = child.location.x
        sphere["y"] = child.location.y
        sphere["z"] = child.location.z
        sphere["radius"] = child.dimensions.x / 2.0
        return sphere
    return None


def _collect_unit_triangles(mesh_object):
    stored_triangles_raw = mesh_object.get("s5_triangles")
    if stored_triangles_raw:
        try:
            stored_triangles = json.loads(stored_triangles_raw, object_pairs_hook=OrderedDict)
        except Exception:
            stored_triangles = None
        else:
            vertex_count = len(mesh_object.data.vertices)
            is_valid = all(
                0 <= triangle.get("v1", -1) < vertex_count
                and 0 <= triangle.get("v2", -1) < vertex_count
                and 0 <= triangle.get("v3", -1) < vertex_count
                for triangle in stored_triangles
            )
            if is_valid and len(stored_triangles) != len(mesh_object.data.polygons):
                return stored_triangles

    triangles = []
    for polygon in mesh_object.data.polygons:
        triangle = OrderedDict()
        triangle["v1"] = polygon.vertices[0]
        triangle["v2"] = polygon.vertices[1]
        triangle["v3"] = polygon.vertices[2]
        triangle["materialId"] = polygon.material_index
        triangles.append(triangle)
    return triangles


def _material_prop(material, key, default):
    return material.get(key, default) if material is not None else default


def _build_unit_material_payloads(mesh_object):
    materials = []
    for material in mesh_object.data.materials:
        if material is None:
            continue

        base_texture = _material_prop(material, "s5_texture_name", material.name)
        texture_alpha = _material_prop(material, "s5_texture_alpha", "")
        dual_tex = bool(_material_prop(material, "s5_dual_tex", False))
        spec_texture = _material_prop(material, "s5_spec_texture", "")

        raw_template = material.get("s5_material_payload")
        if raw_template:
            try:
                material_payload = json.loads(raw_template, object_pairs_hook=OrderedDict)
            except Exception:
                material_payload = OrderedDict()
        else:
            material_payload = OrderedDict()

        if not material_payload:
            material_payload["UnknownInt1"] = 0
            material_payload["color"] = {
                "red": 255,
                "green": 255,
                "blue": 255,
                "alpha": 255,
            }
            material_payload["UnknownInt2"] = 237627844
            material_payload["SurfaceProps"] = {}
            material_payload["textures"] = [{}]
            material_payload["extension"] = {}

        surface_props = material_payload.setdefault("SurfaceProps", {})
        surface_props["ambient"] = int(_material_prop(material, "s5_ambient", 1))
        surface_props["specular"] = int(_material_prop(material, "s5_specular", 0))
        surface_props["diffuse"] = int(_material_prop(material, "s5_diffuse", 1))

        textures = material_payload.setdefault("textures", [{}])
        if not textures:
            textures.append({})
        base_texture_entry = textures[0]
        base_texture_entry["texture"] = base_texture
        base_texture_entry["TexPadding"] = base_texture_entry.get("TexPadding", [0, 0])
        base_texture_entry["textureAlpha"] = texture_alpha
        base_texture_entry["TextureAlphaPadding"] = base_texture_entry.get("TextureAlphaPadding", [0, 7, 46, 196])
        base_texture_entry["FilterAddressing"] = base_texture_entry.get("FilterAddressing", {
            "FilterMode": "Linear_MipMap_Linear",
            "AddressModeU": "Wrap",
            "AddressModeV": "Wrap",
        })
        base_texture_entry["UnusedInt1"] = base_texture_entry.get("UnusedInt1", 0)
        base_texture_entry["extension"] = base_texture_entry.get("extension", {})

        material_payload["extension"] = material_payload.get("extension", {})

        if dual_tex and spec_texture:
            material_fx = material_payload["extension"].setdefault("MaterialFXMat", {})
            data1 = material_fx.setdefault("Data1", {})
            data1["Type"] = "DualTexture"
            texture_1 = data1.setdefault("Texture1", {})
            texture_1["texture"] = spec_texture
            texture_1["TexPadding"] = texture_1.get("TexPadding", [0])
            texture_1["textureAlpha"] = texture_1.get("textureAlpha", "")
            texture_1["TextureAlphaPadding"] = texture_1.get("TextureAlphaPadding", [0, 116, 28, 196])
            texture_1["FilterAddressing"] = texture_1.get("FilterAddressing", {
                "FilterMode": "Linear_MipMap_Linear",
                "AddressModeU": "Wrap",
                "AddressModeV": "Wrap",
            })
            texture_1["UnusedInt1"] = texture_1.get("UnusedInt1", 0)
            texture_1["extension"] = texture_1.get("extension", {})
            data1["Texture2"] = data1.get("Texture2")
            data1["Coefficient"] = data1.get("Coefficient")
            data1["FrameBufferAlpha"] = data1.get("FrameBufferAlpha")
            data1["SrcBlendMode"] = data1.get("SrcBlendMode", "rwBLENDSRCALPHA")
            data1["DstBlendMode"] = data1.get("DstBlendMode", "rwBLENDINVSRCALPHA")

            data2 = material_fx.setdefault("Data2", {})
            data2["Type"] = data2.get("Type", "None")
            data2["Texture1"] = data2.get("Texture1")
            data2["Texture2"] = data2.get("Texture2")
            data2["Coefficient"] = data2.get("Coefficient")
            data2["FrameBufferAlpha"] = data2.get("FrameBufferAlpha")
            data2["SrcBlendMode"] = data2.get("SrcBlendMode")
            data2["DstBlendMode"] = data2.get("DstBlendMode")
            material_fx["Flags"] = "DualTexture"

        materials.append(material_payload)

    return materials


def _matrix_to_skin_matrix(matrix):
    skin_matrix = OrderedDict()
    skin_matrix["Pad1"] = -858993460
    skin_matrix["Pad2"] = -858993460
    skin_matrix["Pad3"] = -858993460
    skin_matrix["Right"] = {
        "x": matrix[0][0],
        "y": matrix[1][0],
        "z": matrix[2][0],
    }
    skin_matrix["Up"] = {
        "x": matrix[0][1],
        "y": matrix[1][1],
        "z": matrix[2][1],
    }
    skin_matrix["At"] = {
        "x": matrix[0][2],
        "y": matrix[1][2],
        "z": matrix[2][2],
    }
    skin_matrix["Pos"] = {
        "x": matrix[0][3],
        "y": matrix[1][3],
        "z": matrix[2][3],
    }
    skin_matrix["Flags"] = {
        "Normal": True,
        "Orthogonal": True,
        "Identity": False,
    }
    return skin_matrix


def _pack_unit_bone_indices(node_indices):
    return (
        (node_indices[0] & 0xFF)
        | ((node_indices[1] & 0xFF) << 8)
        | ((node_indices[2] & 0xFF) << 16)
        | ((node_indices[3] & 0xFF) << 24)
    )


def _collect_unit_skin_payload(mesh_object, bone_names_sorted, frame_index_to_node_index, rest_matrices, hierarchy):
    group_index_to_name = {group.index: group.name for group in mesh_object.vertex_groups}
    bone_name_to_frame_index = {name: index for index, name in enumerate(bone_names_sorted)}

    used_bones = []
    used_bones_seen = set()
    vertex_bone_indices = []
    vertex_bone_weights = []
    max_weight = 0

    for vertex in mesh_object.data.vertices:
        influences = []
        for group_ref in vertex.groups:
            bone_name = group_index_to_name.get(group_ref.group)
            if bone_name not in bone_name_to_frame_index:
                continue

            frame_index = bone_name_to_frame_index[bone_name]
            node_index = frame_index_to_node_index.get(frame_index)
            if node_index is None:
                continue

            weight = float(group_ref.weight)
            if weight <= WEIGHT_EPSILON:
                continue
            influences.append((node_index, weight))

        influences.sort(key=lambda item: item[1], reverse=True)
        influences = influences[:4]
        max_weight = max(max_weight, len(influences))

        total_weight = sum(weight for _, weight in influences)
        if total_weight > WEIGHT_EPSILON:
            influences = [(node_index, weight / total_weight) for node_index, weight in influences]

        packed_node_indices = [0, 0, 0, 0]
        packed_weights = [0.0, 0.0, 0.0, 0.0]
        for influence_index, (node_index, weight) in enumerate(influences):
            packed_node_indices[influence_index] = node_index
            packed_weights[influence_index] = weight
            if node_index not in used_bones_seen:
                used_bones_seen.add(node_index)
                used_bones.append(node_index)

        vertex_bone_indices.append(_pack_unit_bone_indices(packed_node_indices))
        vertex_bone_weights.append({
            "w0": packed_weights[0],
            "w1": packed_weights[1],
            "w2": packed_weights[2],
            "w3": packed_weights[3],
        })

    node_index_to_frame = {node_index: frame_index for frame_index, node_index in frame_index_to_node_index.items()}
    max_node_index = max(node_index_to_frame.keys(), default=-1)
    skin_to_bone_matrices = []
    identity_matrix = Matrix.Identity(4)

    for node_index in range(max_node_index + 1):
        frame_index = node_index_to_frame.get(node_index)
        if frame_index is None:
            inverse_bind_matrix = identity_matrix
        else:
            world_rest_matrix = accumulate_rest_matrix(rest_matrices, hierarchy, frame_index)
            inverse_bind_matrix = world_rest_matrix.inverted()
        skin_to_bone_matrices.append(_matrix_to_skin_matrix(inverse_bind_matrix))

    return {
        "MaxWeight": max_weight,
        "UsedBones": used_bones,
        "VertexBoneIndices": vertex_bone_indices,
        "VertexBoneWeights": vertex_bone_weights,
        "SkinToBoneMatrices": skin_to_bone_matrices,
        "SplitData": {
            "BoneLimit": 0,
            "MeshBoneRemapIndices": None,
            "MeshBoneRLECount": None,
            "MeshBoneRLE": None,
        },
    }


def build_unit_geometry_payload(mesh_object, bone_names_sorted, frame_index_to_node_index, rest_matrices, hierarchy):
    vertex_count = len(mesh_object.data.vertices)

    payload = OrderedDict()
    morph_target = OrderedDict()
    morph_target["vertices"] = _collect_unit_vertices(mesh_object)
    morph_target["normals"] = _collect_unit_normals(mesh_object)

    sphere = _collect_unit_sphere(mesh_object)
    if sphere is not None:
        morph_target["sphere"] = sphere

    payload["morphTargets"] = [morph_target]
    payload["textureCoordinates"] = _collect_texture_coordinates(mesh_object, vertex_count)
    payload["format"] = _build_geometry_format(mesh_object, payload["textureCoordinates"])
    payload["triangles"] = _collect_unit_triangles(mesh_object)
    payload["materials"] = _build_unit_material_payloads(mesh_object)
    try:
        bin_mesh_plg = json.loads(mesh_object.get("s5_bin_mesh_plg", "null"))
    except Exception:
        bin_mesh_plg = None

    if not bin_mesh_plg:
        bin_mesh_plg = {
            "Flags": {"UnIndexed": False, "Type": "TriStrip"},
            "Meshes": [],
        }

    extension_payload = {
        "BinMeshPLG": bin_mesh_plg,
        "SkinPLG": _collect_unit_skin_payload(
            mesh_object,
            bone_names_sorted,
            frame_index_to_node_index,
            rest_matrices,
            hierarchy,
        ),
    }
    if "s5_geometry_user_data" in mesh_object:
        try:
            extension_payload["userDataPLG"] = json.loads(mesh_object["s5_geometry_user_data"])
        except Exception:
            pass

    payload["extension"] = extension_payload
    return payload


def build_unit_atomic_entry(mesh_object, geometry_index):
    atomic_entry = OrderedDict()
    atomic_entry["frameIndex"] = int(mesh_object.get("s5_atomic_frame_index", 0))
    atomic_entry["geometryIndex"] = geometry_index
    atomic_entry["Flags"] = {
        "CollisionTest": True,
        "RenderShadow": False,
        "Render": True,
    }
    atomic_entry["UnknownInt1"] = 0
    try:
        atomic_entry["extension"] = json.loads(mesh_object.get("s5_atomic_extension", "null")) or {}
    except Exception:
        atomic_entry["extension"] = {}
    return atomic_entry


def build_unit_export_json(context):
    armature_object = resolve_unit_armature_for_export(context)
    armature_state = collect_unit_armature_export_state(armature_object)

    bone_names_sorted = armature_state["bone_names_sorted"]
    hierarchy = armature_state["hierarchy"]
    rest_matrices = armature_state["rest_matrices"]
    hanim_data_entries = armature_state["hanim_data_entries"]
    node_ids = armature_state["node_ids"]

    frame_entries, frame_index_to_node_index = build_unit_frame_entries(
        hierarchy,
        rest_matrices,
        hanim_data_entries,
        node_ids,
        armature_state["root_hanim_nodes"],
        armature_state["root_hanim_parents"],
    )

    meshes = collect_unit_meshes_for_armature(armature_object)
    if not meshes:
        raise RuntimeError("Keine mit der Armature verbundene Unit-Meshes für den Export gefunden.")

    geometries = []
    atomics = []
    for geometry_index, mesh_object in enumerate(meshes):
        geometries.append(
            build_unit_geometry_payload(
                mesh_object,
                bone_names_sorted,
                frame_index_to_node_index,
                rest_matrices,
                hierarchy,
            )
        )
        atomics.append(build_unit_atomic_entry(mesh_object, geometry_index))

    clump = OrderedDict()
    clump["frames"] = frame_entries
    clump["atomics"] = atomics
    clump["geometries"] = geometries
    clump["Lights"] = []
    clump["extension"] = {}

    payload = OrderedDict()
    payload["$schema"] = "https://github.com/mcb5637/S5Converter/raw/refs/heads/master/schema.json"
    payload["clump"] = clump
    payload["BuildNum"] = 45
    payload["VersionNum"] = 225282
    payload["ConvertRadians"] = True
    return payload


def write_unit_model(path, context):
    converter_path = get_converter_exe_location()
    payload = build_unit_export_json(context)
    save_building_model_payload(path, payload, converter_path)


def _load_unit_root_hanim_payload(arm_ob):
    try:
        nodes = json.loads(arm_ob.get("s5_root_hanim_nodes", "null"))
    except Exception:
        nodes = None

    try:
        parents = json.loads(arm_ob.get("s5_root_hanim_parents", "null"))
    except Exception:
        parents = None

    return nodes, parents


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

    if len(tracks) != len(animation_bones):
        print(
            f"[WARN] Unit-Trackcount != Bonecount: "
            f"tracks={len(tracks)} bones={len(animation_bones)} -> benutze n={used_track_count}"
        )

    fps = determine_fps(source_format, tracks)
    scene = bpy.context.scene
    scene.render.fps = fps if fps > 0 else DEFAULT_S5_FPS
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
            print(f"[WARN] PoseBone nicht gefunden: {bone.name}")
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
    print(
        f"[INFO] Unit-Animation importiert. "
        f"format={source_format}, root_id={root_id}, fps={scene.render.fps}, "
        f"tracks={len(tracks)}, used={used_track_count}"
    )
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
