import bmesh
import bpy
import os

from .building_utilities import (
    frame_dict_to_matrix,
    link_object_in_active_collection,
    load_building_model_payload,
    matrix_to_bone_axis_roll,
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
    base_name = f"frame_{frame_index:0{BONE_NAME_PADDING}d}"
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


def build_unit_armature_from_frames(frame_containers, use_connect):
    metadata_entries = [_extract_frame_metadata(frame_container) for frame_container in frame_containers]
    frames = [entry["matrix"] for entry in metadata_entries]
    hierarchy = [entry["parent_index"] for entry in metadata_entries]
    node_ids = [entry["node_id"] for entry in metadata_entries]
    node_index_to_frame_index = _build_hanim_node_index_map(frame_containers, node_ids)

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
        build_unit_geometry(
            geometry_data,
            armature_object,
            bone_names,
            node_index_to_frame_index,
            mesh_name,
            mesh_index,
        )

    return armature_object
