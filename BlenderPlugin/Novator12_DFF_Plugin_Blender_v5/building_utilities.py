import bmesh
import bpy
import json
import math
import mathutils as mu
import os
import re
import subprocess

from collections import OrderedDict
from mathutils import Matrix, Vector

from .particle_effects_data import PARTICLE_EFFECT_LUT


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

# ===== transforms.py =====

NEGATIVE_Y_THRESHOLD = 1.0e-9
NEGATIVE_Y_CLOSE_THRESHOLD = 1.0e-5
FALLBACK_BONE_AXIS = Vector((0.0, 1.0, 0.0))


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

# ===== blender_helpers.py =====

def assign_active_object_material(material_name):
    active_object = bpy.context.object
    material = bpy.data.materials.get(material_name)

    if material is None:
        material = bpy.data.materials.new(name=material_name)

    material_slots = active_object.data.materials
    if material_slots:
        material_slots[0] = material
    else:
        material_slots.append(material)

    return material


def link_object_in_active_collection(obj):
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

# ===== export_helpers.py =====

EXPORT_BONE_SCALE = 100.0


def edit_bone_to_matrix(edit_bone):
    head_position = edit_bone.head
    tail_axis = (edit_bone.tail - head_position) / EXPORT_BONE_SCALE
    orientation_matrix = bone_axis_to_matrix(tail_axis, edit_bone.roll)

    transform_matrix = orientation_matrix.to_4x4()
    transform_matrix.translation = head_position
    return transform_matrix


def vector_to_js_triplet(vector):
    def normalize_number(value):
        return int(value) if value == int(value) else round(value, 6)

    return {
        "x": normalize_number(vector[0]),
        "y": normalize_number(vector[1]),
        "z": normalize_number(vector[2]),
    }


def bone_name_to_node_id(bone_name):
    node_suffix = bone_name[10:]
    return int(node_suffix) if node_suffix else -1


def determine_bone_names(armature_object):
    bone_count = len(armature_object.pose.bones)
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="EDIT")

    return [
        armature_object.data.edit_bones[frame_index].name
        for frame_index in range(bone_count)
    ]


def determine_bone_names_sorted(armature_object):
    return sorted(determine_bone_names(armature_object))


def get_bone_by_name(bones, bone_name):
    for bone in bones:
        if bone.name == bone_name:
            return bone
    return None


def extract_index_from_frame_name(frame_name):
    try:
        parts = frame_name.split("_")
        if len(parts) == 2 and parts[1].isdigit():
            stripped = parts[1].lstrip("0")
            return int(stripped) if stripped else 0
        if len(parts) >= 3 and parts[1].isdigit():
            stripped = parts[1].lstrip("0")
            return int(stripped) if stripped else 0
    except Exception:
        return -1
    return -1

# ===== building_armature_builder.py =====

BONE_NAME_PADDING = 3
BONE_DISPLAY_LENGTH = 100.0


def _extract_frame_metadata(frame_container):
    frame_data = frame_container["frame"]
    extension = frame_container.get("extension")

    metadata = {
        "parent_index": frame_data["parentFrameIndex"],
        "matrix": frame_dict_to_matrix(frame_data).transposed(),
        "node_id": None,
        "user_data": None,
        "hanim_data": None,
    }

    if extension:
        metadata["node_id"] = extension.get("hanimPLG", {}).get("nodeID")
        metadata["user_data"] = extension.get("userDataPLG")
        metadata["hanim_data"] = extension.get("hanimPLG")

    return metadata


def _infer_bone_type(user_data):
    for property_line in user_data.get("3dsmax User Properties", []):
        if "Effect=BuildingDecalWithSnow" in property_line or "decal=flat" in property_line:
            return "DECAL"
        if "Effect=SimpleObjectWithSnow" in property_line:
            return "BUILDING"
    return None


def _sync_bone_manager_entry(scene, frame_index, node_id, user_data):
    if not hasattr(scene, "bone_items") or node_id is None or user_data is None:
        return

    bone_type = _infer_bone_type(user_data)
    if bone_type is None:
        return

    existing_node_ids = {item.bone_name for item in scene.bone_items}
    node_id_text = str(node_id)
    if node_id_text in existing_node_ids:
        return

    bone_item = scene.bone_items.add()
    bone_item.bone_index = str(frame_index)
    bone_item.bone_name = node_id_text
    bone_item.bone_type = bone_type
    scene.bone_active_index = len(scene.bone_items) - 1


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


def build_armature_from_frames(frame_containers, use_connect):
    scene = bpy.context.scene
    metadata_entries = [_extract_frame_metadata(frame_container) for frame_container in frame_containers]

    frames = [entry["matrix"] for entry in metadata_entries]
    hierarchy = [entry["parent_index"] for entry in metadata_entries]
    node_ids = [entry["node_id"] for entry in metadata_entries]

    for frame_index, entry in enumerate(metadata_entries):
        _sync_bone_manager_entry(scene, frame_index, entry["node_id"], entry["user_data"])

    armature = bpy.data.armatures.new("Armature_Skin")
    armature_object = bpy.data.objects.new("Armature_Skin", armature)
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
    return armature_object, bone_names, frames, hierarchy

# ===== building_geometry_builder.py =====

def _is_empty_geometry(geometry_data):
    return len(geometry_data["morphTargets"][0]) <= 1


def _extract_uv_coordinates(geometry_data, empty_geometry, bm):
    if empty_geometry:
        return [], [], None

    primary_uvs = [
        (coords["u"], coords["v"])
        for coords in geometry_data["textureCoordinates"][0]
    ]

    secondary_uvs = []
    secondary_layer = None
    if len(geometry_data["textureCoordinates"]) > 1:
        secondary_layer = bm.loops.layers.uv.new("UVMap_Snow")
        secondary_uvs = [
            (coords["u"], coords["v"])
            for coords in geometry_data["textureCoordinates"][1]
        ]

    return primary_uvs, secondary_uvs, secondary_layer


def _populate_vertices(bm, deform_layer, geometry_data, empty_geometry, frame_rest_matrix):
    if empty_geometry:
        bm.verts.ensure_lookup_table()
        return

    morph_target = geometry_data["morphTargets"][0]
    for vertex_index, json_vertex in enumerate(morph_target["vertices"]):
        vertex_position = frame_rest_matrix @ mu.Vector((json_vertex["x"], json_vertex["y"], json_vertex["z"], 1.0))
        vertex = bm.verts.new(vertex_position.to_3d())

        vertex.normal = mu.Vector((
            morph_target["normals"][vertex_index]["x"],
            morph_target["normals"][vertex_index]["y"],
            morph_target["normals"][vertex_index]["z"],
        ))
        vertex[deform_layer][0] = 1.0

    bm.verts.index_update()
    bm.verts.ensure_lookup_table()


def _populate_faces(bm, uv_layer, snow_uv_layer, geometry_data, empty_geometry, primary_uvs, secondary_uvs):
    if empty_geometry:
        return

    for triangle in geometry_data["triangles"]:
        try:
            vertices = [bm.verts[triangle["v1"]], bm.verts[triangle["v2"]], bm.verts[triangle["v3"]]]
            face = bm.faces.new(vertices)
            bm.faces.index_update()

            for vertex in vertices:
                loop = next(loop for loop in face.loops if loop.vert == vertex)
                u_coord, v_coord = primary_uvs[vertex.index]
                loop[uv_layer].uv = (u_coord, 1.0 - v_coord)

                if secondary_uvs and snow_uv_layer is not None:
                    snow_u, snow_v = secondary_uvs[vertex.index]
                    loop[snow_uv_layer].uv = (snow_u, 1.0 - snow_v)
        except ValueError as exc:
            print(f"Face creation skipped: {exc}")


def _build_mesh_object(geometry_data, armature_object, frame_rest_matrix, bone_name, mesh_index):
    empty_geometry = _is_empty_geometry(geometry_data)

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    bm = bmesh.new()
    deform_layer = bm.verts.layers.deform.verify()
    uv_layer = bm.loops.layers.uv.verify()
    primary_uvs, secondary_uvs, snow_uv_layer = _extract_uv_coordinates(geometry_data, empty_geometry, bm)

    _populate_vertices(bm, deform_layer, geometry_data, empty_geometry, frame_rest_matrix)
    _populate_faces(bm, uv_layer, snow_uv_layer, geometry_data, empty_geometry, primary_uvs, secondary_uvs)

    mesh = bpy.data.meshes.new("mesh")
    bm.to_mesh(mesh)
    bm.free()

    mesh_name = f"Mesh{mesh_index:02d}"
    mesh_object = bpy.data.objects.new(mesh_name, mesh)
    mesh_object.vertex_groups.new(name=bone_name)

    armature_modifier = mesh_object.modifiers.new(type="ARMATURE", name="skeleton")
    armature_modifier.object = armature_object

    link_object_in_active_collection(mesh_object)

    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="EDIT")

    if empty_geometry:
        mesh_object.data.name = "Empty-Geometry"
    else:
        texture_name = geometry_data["materials"][0]["textures"][0]["texture"]
        assign_active_object_material(texture_name)
        mesh_object.data.name = texture_name

    return mesh_object, mesh_name, empty_geometry


def _attach_sphere_proxy(geometry_data, mesh_object, empty_geometry):
    sphere_data = geometry_data["morphTargets"][0].get("sphere")
    if sphere_data is None:
        return

    if empty_geometry:
        sphere_name = "Empty-Geometry-Sphere"
    else:
        texture_name = geometry_data["materials"][0]["textures"][0]["texture"]
        sphere_name = "Decal-Sphere" if "Decals" in texture_name else "Building-Sphere"

    previous_mode = mesh_object.mode if mesh_object and mesh_object.mode else None
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=sphere_data["radius"],
        location=(sphere_data["x"], sphere_data["y"], sphere_data["z"]),
    )
    sphere_object = bpy.context.object
    sphere_object.name = sphere_name

    if sphere_object == mesh_object:
        raise RuntimeError("Sphere creation stayed in mesh edit context")

    sphere_object.parent = mesh_object
    sphere_object.hide_render = True
    sphere_object.display_type = "WIRE"

    if previous_mode == "EDIT" and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="EDIT")


def _write_geometry_tool_metadata(scene, geometry_data, mesh_name, empty_geometry):
    geometry_entry = scene.geometry_tool_items.add()
    geometry_entry.mesh_name = mesh_name
    geometry_entry.materials.clear()

    if empty_geometry:
        geometry_entry.bin_mesh_data = "Empty-Geometry"
        material_entry = geometry_entry.materials.add()
        material_entry.name = "Empty-Geometry"
        material_entry.ambient = False
        material_entry.specular = False
        material_entry.diffuse = False
        material_entry.uv_trans = False
        material_entry.dual_tex = False
        material_entry.snow_texture = "Empty-Geometry"
        material_entry.texture_alpha = ""
        return

    extension = geometry_data.get("extension", {})
    bin_mesh = extension.get("BinMeshPLG")
    if bin_mesh is None:
        geometry_entry.bin_mesh_data = "No data"
    else:
        geometry_entry.bin_mesh_data = json.dumps({
            "Flags": bin_mesh.get("Flags", {}),
            "Meshes": bin_mesh.get("Meshes", []),
        })

    for material in geometry_data.get("materials", []):
        material_entry = geometry_entry.materials.add()
        texture_info = material.get("textures", [{}])[0]
        material_entry.name = texture_info.get("texture", "Unknown")
        material_entry.texture_alpha = texture_info.get("textureAlpha", "")

        surface_props = material.get("SurfaceProps", {})
        material_entry.ambient = bool(surface_props.get("ambient", 1))
        material_entry.specular = bool(surface_props.get("specular", 0))
        material_entry.diffuse = bool(surface_props.get("diffuse", 1))

        material_fx = material.get("extension", {}).get("MaterialFXMat", {})
        fx_type = material_fx.get("Data1", {}).get("Type", "")
        if fx_type == "DualTexture":
            material_entry.dual_tex = True
            material_entry.snow_texture = material_fx.get("Data1", {}).get("Texture1", {}).get("texture", "No data")
        elif fx_type == "UVTransformMat":
            material_entry.uv_trans = True
            material_entry.snow_texture = "UVTransformMat"
        else:
            material_entry.snow_texture = "No data"


def build_building_geometry(geometry_data, armature_object, frame_rest_matrix, bone_name, mesh_index):
    mesh_object, mesh_name, empty_geometry = _build_mesh_object(
        geometry_data,
        armature_object,
        frame_rest_matrix,
        bone_name,
        mesh_index,
    )
    _attach_sphere_proxy(geometry_data, mesh_object, empty_geometry)
    _write_geometry_tool_metadata(bpy.context.scene, geometry_data, mesh_name, empty_geometry)
    return mesh_index + 1

# ===== building_geometry_payload_builder.py =====

def _entry_value(entry, key, default=None):
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _transform_vertices(mesh_object, inverse_rest_matrix):
    vertices = []
    for vertex in mesh_object.data.vertices:
        transformed = (inverse_rest_matrix @ vertex.co.to_4d()).to_3d()
        vertices.append(OrderedDict((
            ("x", transformed[0]),
            ("y", transformed[1]),
            ("z", transformed[2]),
        )))
    return vertices


def _collect_normals(mesh_object):
    normals = []
    for vertex in mesh_object.data.vertices:
        normals.append(OrderedDict((
            ("x", vertex.normal.x),
            ("y", vertex.normal.y),
            ("z", vertex.normal.z),
        )))
    return normals


def _collect_bounding_sphere(mesh_object):
    for child in mesh_object.children:
        if child.type == "MESH" and child.data and child.data.name.startswith("Sphere"):
            sphere = OrderedDict()
            sphere["x"] = child.location.x
            sphere["y"] = child.location.y
            sphere["z"] = child.location.z
            sphere["radius"] = child.dimensions.x / 2
            return sphere
    return None


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


def _build_bin_mesh_extension(metadata_entry):
    default_flags = {"UnIndexed": False, "Type": "TriStrip"}
    raw_bin_mesh = metadata_entry.get("bin_mesh_data", "No data") if metadata_entry else "No data"

    if raw_bin_mesh and raw_bin_mesh != "No data":
        try:
            parsed = json.loads(raw_bin_mesh)
            return {
                "Flags": parsed.get("Flags", default_flags),
                "Meshes": parsed.get("Meshes", []),
            }
        except json.JSONDecodeError:
            print(f"[WARN] Invalid bin_mesh_data JSON, using default BinMeshPLG.")

    return {
        "Flags": default_flags,
        "Meshes": [],
    }


def _collect_triangles(mesh_object):
    triangles = []
    for polygon in mesh_object.data.polygons:
        triangle = OrderedDict()
        triangle["v1"] = polygon.vertices[0]
        triangle["v2"] = polygon.vertices[1]
        triangle["v3"] = polygon.vertices[2]
        triangle["materialId"] = 0
        triangles.append(triangle)
    return triangles


def _find_geometry_metadata(mesh_object, geometry_metadata):
    if geometry_metadata and mesh_object.name in geometry_metadata:
        return geometry_metadata[mesh_object.name]

    for entry in bpy.context.scene.geometry_tool_items:
        if entry.mesh_name == mesh_object.name:
            return {
                "materials": entry.materials,
                "bin_mesh_data": entry.bin_mesh_data,
            }

    print(f"[WARN] Kein Geometry-Eintrag für Mesh '{mesh_object.name}' gefunden.")
    return None


def _build_material_fx_extension(material_entry):
    extension = OrderedDict()

    if _entry_value(material_entry, "uv_trans", False):
        extension["MaterialFXMat"] = {
            "Data1": {
                "Type": "UVTransformMat",
                "Texture1": None,
                "Texture2": None,
                "Coefficient": None,
                "FrameBufferAlpha": None,
                "SrcBlendMode": None,
                "DstBlendMode": None,
            },
            "Data2": {
                "Type": "None",
                "Texture1": None,
                "Texture2": None,
                "Coefficient": None,
                "FrameBufferAlpha": None,
                "SrcBlendMode": None,
                "DstBlendMode": None,
            },
            "Flags": "UVTransform",
        }
        extension["MaterialUVAnim"] = {"Name": ["13 - Default"]}
    elif _entry_value(material_entry, "dual_tex", False):
        extension["MaterialFXMat"] = {
            "Data1": {
                "Type": "DualTexture",
                "Texture1": {
                    "texture": _entry_value(material_entry, "snow_texture", ""),
                    "TexPadding": [0],
                    "textureAlpha": "",
                    "TextureAlphaPadding": [0, 116, 28, 196],
                    "FilterAddressing": {
                        "FilterMode": "Linear_MipMap_Linear",
                        "AddressModeU": "Wrap",
                        "AddressModeV": "Wrap",
                    },
                    "UnusedInt1": 0,
                    "extension": {},
                },
                "Texture2": None,
                "Coefficient": None,
                "FrameBufferAlpha": None,
                "SrcBlendMode": "rwBLENDSRCALPHA",
                "DstBlendMode": "rwBLENDINVSRCALPHA",
            },
            "Data2": {
                "Type": "None",
                "Texture1": None,
                "Texture2": None,
                "Coefficient": None,
                "FrameBufferAlpha": None,
                "SrcBlendMode": None,
                "DstBlendMode": None,
            },
            "Flags": "DualTexture",
        }

    return extension


def _build_texture_payload(material_entry):
    base_texture_name = re.sub(r"\.\d+$", "", _entry_value(material_entry, "name", ""))
    texture_alpha = _entry_value(material_entry, "texture_alpha", "")
    texture = OrderedDict()
    texture["texture"] = base_texture_name
    texture["textureAlpha"] = texture_alpha
    texture["FilterAddressing"] = {
        "FilterMode": "Linear_MipMap_Linear",
        "AddressModeU": "Wrap",
        "AddressModeV": "Wrap",
    }
    texture["UnusedInt1"] = 0
    texture["extension"] = {}

    if texture_alpha == base_texture_name + "alpha":
        texture["TextureAlphaPadding"] = [0, 0]
        texture["TexPadding"] = [0, 0, 0]
    elif _entry_value(material_entry, "uv_trans", False):
        texture["TextureAlphaPadding"] = [0, 183, 81, 184]
        texture["TexPadding"] = [0, 0]
    else:
        texture["TextureAlphaPadding"] = [0, 7, 46, 196]
        texture["TexPadding"] = [0, 0]

    return texture


def _build_material_payloads(mesh_object, geometry_metadata):
    if geometry_metadata is None:
        return []

    material_entries = geometry_metadata["materials"]
    if any(_entry_value(material, "name", "") == "Empty-Geometry" for material in material_entries):
        return []

    materials = []
    for material_entry in material_entries:
        material = OrderedDict()
        material["color"] = {"alpha": 255, "red": 255, "green": 255, "blue": 255}
        material["UnknownInt1"] = 0
        material["UnknownInt2"] = 237627844
        material["SurfaceProps"] = {
            "ambient": int(_entry_value(material_entry, "ambient", 0)),
            "specular": int(_entry_value(material_entry, "specular", 0)),
            "diffuse": int(_entry_value(material_entry, "diffuse", 0)),
        }
        material["extension"] = _build_material_fx_extension(material_entry)
        material["textures"] = [_build_texture_payload(material_entry)]
        materials.append(material)

    return materials


def build_building_geometry_payload(mesh_object, inverse_rest_matrix, geometry_metadata):
    print("build_building_geometry_payload")
    vertex_count = len(mesh_object.data.vertices)
    metadata_entry = _find_geometry_metadata(mesh_object, geometry_metadata)

    payload = OrderedDict()
    vertices = _transform_vertices(mesh_object, inverse_rest_matrix)
    normals = _collect_normals(mesh_object)

    morph_target = OrderedDict()
    if vertices and normals:
        morph_target["vertices"] = vertices
        morph_target["normals"] = normals

    sphere = _collect_bounding_sphere(mesh_object)
    if sphere is not None:
        morph_target["sphere"] = sphere

    payload["morphTargets"] = [morph_target]
    payload["textureCoordinates"] = _collect_texture_coordinates(mesh_object, vertex_count)
    payload["format"] = _build_geometry_format(mesh_object, payload["textureCoordinates"])
    payload["extension"] = {"BinMeshPLG": _build_bin_mesh_extension(metadata_entry)}
    payload["triangles"] = _collect_triangles(mesh_object)
    payload["materials"] = _build_material_payloads(mesh_object, metadata_entry)
    return payload

# ===== building_atomic_builder.py =====

def build_building_atomic_entry(frame_index, geometry_index, particle_data, bone_type_data, atomic_material_fx_data, particle_data_map):
    print("build_building_atomic_entry")

    atomic_entry = OrderedDict()
    atomic_entry["frameIndex"] = frame_index
    atomic_entry["geometryIndex"] = geometry_index
    atomic_entry["Flags"] = {
        "CollisionTest": True,
        "RenderShadow": False,
        "Render": True,
    }
    atomic_entry["UnknownInt1"] = 0
    atomic_entry["extension"] = {}

    if frame_index in atomic_material_fx_data and "MaterialFXAtomic_EffectsEnabled" in atomic_material_fx_data[frame_index]:
        atomic_entry["extension"] = {"MaterialFXAtomic_EffectsEnabled": True}
        return atomic_entry

    if bone_type_data:
        for bone_data in bone_type_data:
            if str(frame_index) == bone_data["index"]:
                atomic_entry["extension"] = {"MaterialFXAtomic_EffectsEnabled": True}
                return atomic_entry

    if frame_index in particle_data_map:
        atomic_entry["extension"]["ParticleStandard"] = particle_data_map[frame_index]
        return atomic_entry

    if particle_data:
        for particle in particle_data:
            if str(frame_index) != particle["name"]:
                continue

            effect_key = str(particle["type"]).strip()
            if effect_key == "Ubisoft":
                return atomic_entry

            if effect_key in PARTICLE_EFFECT_LUT:
                atomic_entry["extension"] = PARTICLE_EFFECT_LUT[effect_key]
            else:
                print(f"[WARN] Unbekannter Partikeleffekt: '{effect_key}' – kein Eintrag im LUT")
            return atomic_entry

    return atomic_entry

# ===== building_frame_builder.py =====

def extend_export_order(node_ids, export_order, start_node_id):
    for node_id in range(start_node_id, start_node_id + 100):
        if node_id in node_ids and node_id not in export_order:
            export_order.append(node_id)


def get_child_frame_indices(hierarchy, parent_index):
    return [index for index, current_parent in enumerate(hierarchy) if current_parent == parent_index]


def collect_descendant_indices(hierarchy, root_index):
    descendant_indices = [root_index]
    for child_index in reversed(get_child_frame_indices(hierarchy, root_index)):
        descendant_indices.extend(collect_descendant_indices(hierarchy, child_index))
    return descendant_indices


def collect_animation_bone_indices(hierarchy, keyframe_count):
    first_bone_index = len(hierarchy) - keyframe_count
    return collect_descendant_indices(hierarchy, first_bone_index)


def determine_export_order(node_ids, hierarchy):
    export_order = []
    first_bone_id = node_ids[1]

    if 500 <= first_bone_id < 600:
        animation_indices = collect_animation_bone_indices(hierarchy, len(hierarchy) - 1)
        for bone_index in animation_indices:
            node_id = node_ids[bone_index]
            if node_id not in export_order:
                export_order.append(node_id)
    else:
        export_order.append(first_bone_id)

    for start_node_id in (600, 400, 300, 200):
        extend_export_order(node_ids, export_order, start_node_id)

    for node_id in node_ids:
        if node_id not in export_order:
            export_order.append(node_id)

    return export_order


def build_default_user_data(node_id, bone_type_data):
    if bone_type_data is not None:
        for bone in bone_type_data:
            if bone["name"] == str(node_id):
                if bone["type"] == "DECAL":
                    return {"3dsmax User Properties": ["decal=flat", "Effect=BuildingDecalWithSnow"]}
                if bone["type"] == "BUILDING":
                    return {"3dsmax User Properties": ["Effect=SimpleObjectWithSnow"]}

        if node_id >= 200:
            return {"3dsmax User Properties": [f"tag = {node_id}"]}

    if node_id >= 200:
        return {"3dsmax User Properties": [f"tag = {node_id}"]}
    return None


def build_frame_extension(frame_index, node_id, user_data, bone_type_data, hanim_data):
    extension = OrderedDict()

    resolved_user_data = user_data or build_default_user_data(node_id, bone_type_data)
    if resolved_user_data is not None:
        extension["userDataPLG"] = resolved_user_data

    if frame_index != 0:
        if hanim_data is not None:
            extension["hanimPLG"] = hanim_data
        else:
            extension["hanimPLG"] = {
                "flags": {
                    "SubHierarchy": False,
                    "NoMatrices": False,
                    "UpdateModellingMatrices": False,
                    "UpdateLTMs": False,
                    "LocalSpaceMatrices": False,
                },
                "keyFrameSize": 0,
                "nodeID": node_id,
                "nodes": [],
                "parents": None,
                "ReBuildNodesArray": False,
            }

    if frame_index == 1 and hanim_data is None:
        extension["hanimPLG"]["nodes"] = []
        extension["hanimPLG"]["flags"] = {
            "SubHierarchy": False,
            "NoMatrices": False,
            "UpdateModellingMatrices": False,
            "UpdateLTMs": False,
            "LocalSpaceMatrices": False,
        }
        extension["hanimPLG"]["keyFrameSize"] = 36
        extension["hanimPLG"]["ReBuildNodesArray"] = True

    return extension


def build_building_frame_entries(bone_names_sorted, hierarchy, rest_matrices, user_data_entries, bone_type_data, hanim_data_entries):
    print("build_building_frame_entries")
    node_ids = [bone_name_to_node_id(bone_name) for bone_name in bone_names_sorted]
    export_order = determine_export_order(node_ids, hierarchy)

    print(f"Bone names sorted: {bone_names_sorted}")
    print(f"Export order: {export_order}")

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
            vector_to_js_triplet(rotation[0]),
            vector_to_js_triplet(rotation[1]),
            vector_to_js_triplet(rotation[2]),
        ]
        frame_entry["extension"] = build_frame_extension(
            frame_index,
            node_id,
            user_data_entries[frame_index],
            bone_type_data,
            hanim_data_entries[frame_index],
        )
        frame_entries.append(frame_entry)

    return frame_entries

# ===== building_export_builder.py =====

def resolve_armature_for_export(context):
    scene = context.scene
    active_object = context.object

    if active_object is None or active_object.type != "ARMATURE":
        active_object = next((obj for obj in scene.objects if obj.type == "ARMATURE"), None)

    if active_object is None:
        raise RuntimeError(
            "Kein Armature-Objekt gefunden. Bitte Armature auswählen oder im Scene-Tree vorhanden haben."
        )

    context.view_layer.objects.active = active_object
    active_object.select_set(True)
    return active_object


def collect_armature_export_state(armature_object):
    bone_names_sorted = determine_bone_names_sorted(armature_object)

    if not bpy.ops.object.mode_set.poll():
        raise RuntimeError("Kann nicht in EDIT-Mode wechseln (kein aktives Armature im passenden Kontext).")

    bpy.ops.object.mode_set(mode="EDIT")
    try:
        hierarchy = []
        rest_matrices = []
        user_data_entries = []
        hanim_data_entries = []

        for bone_name in bone_names_sorted:
            bone = get_bone_by_name(armature_object.data.edit_bones, bone_name)
            if bone is None:
                print(f"[WARN] Bone {bone_name} not found!")
                continue

            user_data_entries.append(bone.get("userData").to_dict() if "userData" in bone else None)
            hanim_data_entries.append(bone.get("hanimPLG").to_dict() if "hanimPLG" in bone else None)

            parent_index = extract_index_from_frame_name(bone.parent.name) if bone.parent else -1
            hierarchy.append(parent_index)

            relative_matrix = edit_bone_to_matrix(bone)
            if bone.parent:
                parent_matrix = edit_bone_to_matrix(bone.parent)
                relative_matrix = parent_matrix.inverted() @ relative_matrix

            rest_matrices.append(relative_matrix)

        return {
            "bone_names_sorted": bone_names_sorted,
            "hierarchy": hierarchy,
            "rest_matrices": rest_matrices,
            "user_data_entries": user_data_entries,
            "hanim_data_entries": hanim_data_entries,
        }
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def get_bone_index_by_name(bone_names, bone_name):
    for index, current_name in enumerate(bone_names):
        if current_name == bone_name:
            return index
    return -1


def collect_meshes_for_armature(armature_object):
    return sorted(
        [
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object == armature_object for mod in obj.modifiers)
        ],
        key=lambda obj: int(re.search(r"\d+$", obj.name).group()) if re.search(r"\d+$", obj.name) else -1,
    )


def accumulate_rest_matrix(rest_matrices, hierarchy, frame_index):
    accumulated_matrix = rest_matrices[frame_index]
    parent_index = hierarchy[frame_index]
    visited = set()

    while parent_index != -1 and parent_index not in visited:
        visited.add(parent_index)
        accumulated_matrix = rest_matrices[parent_index] @ accumulated_matrix
        parent_index = hierarchy[parent_index]

    return accumulated_matrix


def build_building_export_json(
    context,
    bone_type_data,
    particle_data,
    geometry_data,
    atomic_material_fx_data,
    particle_data_map,
    *,
    frame_entries_builder,
    geometry_payload_builder,
    atomic_entry_builder,
):
    armature_object = resolve_armature_for_export(context)
    armature_state = collect_armature_export_state(armature_object)

    bone_names_sorted = armature_state["bone_names_sorted"]
    hierarchy = armature_state["hierarchy"]
    rest_matrices = armature_state["rest_matrices"]

    clump = OrderedDict()
    clump["frames"] = frame_entries_builder(
        bone_names_sorted,
        hierarchy,
        rest_matrices,
        armature_state["user_data_entries"],
        bone_type_data,
        armature_state["hanim_data_entries"],
    )
    clump["atomics"] = []
    clump["geometries"] = []

    for geometry_index, mesh_object in enumerate(collect_meshes_for_armature(armature_object)):
        if not mesh_object.vertex_groups:
            print(f"[WARN] Mesh ohne Vertex Group übersprungen: {mesh_object.name}")
            continue

        bone_name = mesh_object.vertex_groups[0].name
        frame_index = get_bone_index_by_name(bone_names_sorted, bone_name)
        if frame_index == -1:
            print(f"[WARN] Bone not found for mesh: {mesh_object.name}")
            continue

        frame_rest_matrix = accumulate_rest_matrix(rest_matrices, hierarchy, frame_index)
        clump["geometries"].append(
            geometry_payload_builder(mesh_object, frame_rest_matrix.inverted(), geometry_data)
        )
        clump["atomics"].append(
            atomic_entry_builder(
                frame_index,
                geometry_index,
                particle_data,
                bone_type_data,
                atomic_material_fx_data,
                particle_data_map,
            )
        )

    return {"clump": clump}

# ===== building_import_pipeline.py =====

KNOWN_PARTICLE_EFFECTS = {
    "smoke10",
    "fire02",
    "woodchip",
    "PB_Weathermachine_lightning",
    "sulfur_spray",
    "salimTrapIcon",
    "TMP_resourceGold_Sparkle",
    "XD_StoneSparkles",
    "smoke11",
    "XF_Leaves",
    "smoke12",
    "fire01",
    "firewheel",
}


def accumulate_frame_world_matrix(frames, hierarchy, frame_index):
    world_matrix = frames[frame_index]
    parent_index = hierarchy[frame_index]

    while hierarchy[parent_index] != -1:
        world_matrix = frames[parent_index] @ world_matrix
        parent_index = hierarchy[parent_index]

    return world_matrix


def import_clump_geometry(clump_data, use_connect):
    armature_object, bone_names, frames, hierarchy = build_armature_from_frames(clump_data["frames"], use_connect)
    mesh_index = 1

    for atomic_entry in clump_data["atomics"]:
        frame_index = atomic_entry["frameIndex"]
        geometry_index = atomic_entry["geometryIndex"]
        frame_world_matrix = accumulate_frame_world_matrix(frames, hierarchy, frame_index)
        geometry_data = clump_data["geometries"][geometry_index]

        mesh_index = build_building_geometry(
            geometry_data,
            armature_object,
            frame_world_matrix,
            bone_names[frame_index],
            mesh_index,
        )


def sync_imported_particle_effects(clump_data, particle_data_map):
    scene = bpy.context.scene
    if not hasattr(scene, "particle_effects"):
        return particle_data_map

    used_frame_indices = set()
    for atomic_entry in clump_data["atomics"]:
        frame_index = atomic_entry.get("frameIndex")
        if frame_index in used_frame_indices:
            continue

        extension = atomic_entry.get("extension", {})
        particle_standard = extension.get("ParticleStandard")

        if "ParticleStandard" in extension:
            particle_data_map[frame_index] = particle_standard
            effect_item = scene.particle_effects.add()
            effect_item.bone_index = str(frame_index)
            effect_item.effect_type = "Ubisoft"
            scene.particle_effects_index = len(scene.particle_effects) - 1
            used_frame_indices.add(frame_index)
            continue

        if not particle_standard or "Emitters" not in particle_standard:
            continue

        for emitter in particle_standard["Emitters"]:
            particle_texture = emitter.get("EmitterStandard", {}).get("ParticleTexture", {})
            texture_name = particle_texture.get("texture", "").lower()

            matched_effect = next(
                (effect_name for effect_name in KNOWN_PARTICLE_EFFECTS if effect_name.lower() in texture_name),
                None,
            )
            if matched_effect is None:
                continue

            effect_item = scene.particle_effects.add()
            effect_item.bone_index = str(frame_index)
            effect_item.effect_type = matched_effect
            scene.particle_effects_index = len(scene.particle_effects) - 1
            used_frame_indices.add(frame_index)
            break

    return particle_data_map


def collect_atomic_material_fx_state(clump_data, atomic_material_fx_data):
    for atomic_entry in clump_data["atomics"]:
        extension = atomic_entry.get("extension")
        frame_index = atomic_entry.get("frameIndex")
        if extension and "MaterialFXAtomic_EffectsEnabled" in extension and frame_index not in atomic_material_fx_data:
            atomic_material_fx_data[frame_index] = {
                "MaterialFXAtomic_EffectsEnabled": extension["MaterialFXAtomic_EffectsEnabled"]
            }

    return atomic_material_fx_data


def hide_import_proxy_meshes():
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "Sphere" in obj.name:
            obj.hide_set(True)
            obj.hide_render = True


def import_building_clump(js, use_connect, atomic_material_fx_data, particle_data_map):
    print("import_building_clump")
    clump_data = js["clump"]

    import_clump_geometry(clump_data, use_connect)
    updated_particle_data = sync_imported_particle_effects(clump_data, particle_data_map)
    updated_atomic_fx_data = collect_atomic_material_fx_state(clump_data, atomic_material_fx_data)
    hide_import_proxy_meshes()

    return updated_atomic_fx_data, updated_particle_data

# ===== building_model_io.py =====

def convert_binary_dff_to_json(binary_data, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    process = subprocess.Popen(
        [converter_path, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _stderr = process.communicate(input=binary_data)
    return json.loads(stdout.decode("utf-8"))


def convert_json_to_binary_dff(payload, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    process = subprocess.Popen(
        [converter_path, "--export"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    stdout, _stderr = process.communicate(input=payload_bytes)
    return stdout


def load_building_model_payload(path, converter_path):
    if path.endswith(".dff"):
        with open(path, "rb") as handle:
            return convert_binary_dff_to_json(handle.read(), converter_path)

    with open(path, "r") as handle:
        return json.load(handle)


def save_building_model_payload(path, payload, converter_path):
    if path.endswith(".json"):
        with open(path, "w") as handle:
            json.dump(payload, handle, indent=4)
        return

    binary_payload = convert_json_to_binary_dff(payload, converter_path)
    with open(path, "wb") as handle:
        handle.write(binary_payload)


def collect_building_scene_export_payload(scene):
    bone_type_data = [
        {"index": bone.bone_index, "name": bone.bone_name, "type": bone.bone_type}
        for bone in scene.bone_items
    ] or None

    particle_data = [
        {"name": particle.bone_index, "type": particle.effect_type}
        for particle in scene.particle_effects
    ] or None

    geometry_data = {
        geo.mesh_name: {
            "materials": [
                {
                    "name": mat.name,
                    "ambient": mat.ambient,
                    "specular": mat.specular,
                    "diffuse": mat.diffuse,
                    "uv_trans": mat.uv_trans,
                    "dual_tex": mat.dual_tex,
                    "snow_texture": mat.snow_texture,
                    "texture_alpha": mat.texture_alpha,
                }
                for mat in geo.materials
            ],
            "bin_mesh_data": geo.bin_mesh_data,
        }
        for geo in scene.geometry_tool_items
    } or None

    return bone_type_data, particle_data, geometry_data

# ===== building_animation_io.py =====

DEFAULT_S5_FPS = 24
MIN_ANIM_NODE_ID = 600
DEFAULT_START_PREV_KEYFRAME = -123456789


# ------------------------------------------------------------
# Path / console helpers
# ------------------------------------------------------------

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


def parse_node_id_from_bone_name(bname: str) -> int | None:
    """
    Erwartet Bone-Namen wie:
    frame_109_601
    frame_110_603
    """
    parts = bname.split("_")
    if len(parts) >= 3 and parts[-1].isdigit():
        return int(parts[-1])
    return None


def parse_frame_index_from_bone_name(bname: str) -> int:
    parts = bname.split("_")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 10**9


def find_bone_by_node_id(arm_ob: bpy.types.Object, node_id: int):
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
        node_id = parse_node_id_from_bone_name(bone.name)
        if node_id is None or node_id < MIN_ANIM_NODE_ID:
            continue

        parent_node_id = parse_node_id_from_bone_name(bone.parent.name) if bone.parent else None
        if parent_node_id is not None and parent_node_id >= MIN_ANIM_NODE_ID:
            continue

        subtree_count = len(collect_subtree_node_ids(bone))
        candidates.append((subtree_count, parse_frame_index_from_bone_name(bone.name), node_id, bone))

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

    root_id = parse_node_id_from_bone_name(root_bone.name)
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
        nid = parse_node_id_from_bone_name(b.name)
        if nid is not None and nid >= MIN_ANIM_NODE_ID:
            ordered.append(b)

        kids = sorted(list(b.children), key=lambda x: (parse_frame_index_from_bone_name(x.name), x.name))
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
        nid = parse_node_id_from_bone_name(b.name)
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


def collect_hanim_node_order_for_animation(arm_ob: bpy.types.Object, root_bone) -> list[int]:
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


def collect_animation_bones_from_hanim(arm_ob: bpy.types.Object, root_bone) -> list:
    """
    Nutzt die HAnim-Reihenfolge, aber nur für:
    Root + Children + Subchildren des Anim-Roots.
    """
    ordered_ids = collect_hanim_node_order_for_animation(arm_ob, root_bone)

    bones = []
    seen = set()

    print(f"[INFO] hanim ordered ids (final): {ordered_ids}")

    for node_id in ordered_ids:
        bone = find_bone_by_node_id(arm_ob, node_id)
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
    root_bone = find_bone_by_node_id(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    anim_bones = collect_animation_bones_from_hanim(arm_ob, root_bone)
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
    root_bone = find_bone_by_node_id(arm_ob, root_id)
    if not root_bone:
        raise RuntimeError(f"Root-Bone für NodeID {root_id} nicht im Rig gefunden.")

    # Primär: Reihenfolge aus HAnim, aber nur innerhalb des Root-Subtrees
    anim_bones = collect_animation_bones_from_hanim(arm_ob, root_bone)

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
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

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
        print("[S5Converter stderr]")
        print(stderr_text)

    if p.returncode != 0:
        raise RuntimeError(f"S5Converter Fehler:\n{stderr_text}")

    try:
        return json.loads(stdout_text)
    except Exception as e:
        raise RuntimeError(f"S5Converter lieferte kein gültiges JSON zurück: {e}")


def convert_json_to_anm_external(js: dict, anm_path: str):
    if anm_path.endswith(".json"):
        with open(anm_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        return

    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

    p = subprocess.Popen([exe, "--export"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    js_str = json.dumps(js)
    bytes_data = js_str.encode("utf-8")
    outs, errs = p.communicate(input=bytes_data)

    stderr_text = safe_decode_console(errs)
    if stderr_text:
        print("[S5Converter stderr]")
        print(stderr_text)

    try:
        with open(anm_path, "wb") as outfile:
            outfile.write(outs)
    except BrokenPipeError as e:
        print("[ERROR] BrokenPipe beim Schreiben in Datei {}: {}".format(anm_path, e))

