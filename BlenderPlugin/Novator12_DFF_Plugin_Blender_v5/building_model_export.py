import json
import os
import re

from collections import OrderedDict

import bpy

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .Comfort.io_utils import save_building_model_payload
from .Comfort.mesh_utils import build_geometry_format, collect_texture_coordinates
from .particle_effects_data import PARTICLE_EFFECT_LUT
from .Comfort.transform_utils import (
    bone_name_to_node_id,
    edit_bone_to_matrix,
    get_converter_exe_location,
)
from .Comfort.validation_utils import raise_for_export_preflight


def vector_to_js_triplet(vector):
    return OrderedDict((
        ("x", vector[0]),
        ("y", vector[1]),
        ("z", vector[2]),
    ))


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
            print("[WARN] Invalid bin_mesh_data JSON, using default BinMeshPLG.")

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
    payload["textureCoordinates"] = collect_texture_coordinates(mesh_object, vertex_count)
    payload["format"] = build_geometry_format(mesh_object, payload["textureCoordinates"])
    payload["extension"] = {"BinMeshPLG": _build_bin_mesh_extension(metadata_entry)}
    payload["triangles"] = _collect_triangles(mesh_object)
    payload["materials"] = _build_material_payloads(mesh_object, metadata_entry)
    return payload


def build_building_atomic_entry(frame_index, geometry_index, particle_data, bone_type_data, atomic_material_fx_data, particle_data_map):
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
        bone_index_text = str(frame_index)
        for bone_data in bone_type_data:
            if bone_data["index"] != bone_index_text:
                continue

            bone_type = bone_data["type"]
            if bone_type == "DECAL":
                atomic_entry["extension"] = {
                    "RightToRender": "RpATOMIC",
                    "MaterialEffectsPLG": False,
                }
            elif bone_type == "BUILDING":
                atomic_entry["extension"] = {
                    "RightToRender": "RpATOMIC",
                }
            break

    if particle_data:
        for effect_entry in particle_data:
            if effect_entry["name"] != str(frame_index):
                continue

            effect_key = effect_entry["type"]
            if effect_key in PARTICLE_EFFECT_LUT:
                atomic_entry["extension"] = PARTICLE_EFFECT_LUT[effect_key]
            elif frame_index in particle_data_map:
                atomic_entry["extension"] = particle_data_map[frame_index]
            break

    return atomic_entry


def extend_export_order(node_ids, export_order, start_node_id):
    if start_node_id in export_order:
        start_index = export_order.index(start_node_id)
        return export_order[start_index:]
    return export_order


def get_child_frame_indices(hierarchy, parent_index):
    return [index for index, current_parent in enumerate(hierarchy) if current_parent == parent_index]


def collect_descendant_indices(hierarchy, root_index):
    descendants = [root_index]
    for child_index in get_child_frame_indices(hierarchy, root_index):
        descendants.extend(collect_descendant_indices(hierarchy, child_index))
    return descendants


def collect_animation_bone_indices(hierarchy, keyframe_count):
    return collect_descendant_indices(hierarchy, keyframe_count)


def determine_export_order(node_ids, hierarchy):
    export_order = sorted(node_ids)
    animation_start = next((node_id for node_id in export_order if node_id >= 500), None)
    if animation_start is None:
        return export_order

    export_order = extend_export_order(node_ids, export_order, animation_start)
    root_index = node_ids.index(animation_start)
    descendant_indices = collect_animation_bone_indices(hierarchy, root_index)

    ordered_node_ids = [node_ids[index] for index in descendant_indices]
    return [node_id for node_id in export_order if node_id in ordered_node_ids]


def build_default_user_data(node_id, bone_type_data):
    if bone_type_data is not None:
        for bone in bone_type_data:
            if bone["name"] == str(node_id):
                bone_type = bone["type"]
                if bone_type == "BUILDING":
                    return {"3dsmax User Properties": ["Effect=SimpleObjectWithSnow"]}
                if bone_type == "DECAL":
                    return {"3dsmax User Properties": ["Effect=BuildingDecalWithSnow", "decal=flat"]}
        if node_id >= 200:
            return {"3dsmax User Properties": [f"tag = {node_id}"]}

    if node_id >= 200:
        return {"3dsmax User Properties": [f"tag = {node_id}"]}
    return None


def _build_building_hanim_hierarchy(node_ids, hierarchy, export_order):
    frame_index_by_node_id = {}
    for frame_index, node_id in enumerate(node_ids):
        if node_id == -1 or node_id in frame_index_by_node_id:
            continue
        frame_index_by_node_id[node_id] = frame_index

    ordered_frame_indices = []
    seen_frames = set()

    for node_id in export_order:
        if node_id == -1:
            continue
        frame_index = frame_index_by_node_id.get(node_id)
        if frame_index is None or frame_index in seen_frames:
            continue
        ordered_frame_indices.append(frame_index)
        seen_frames.add(frame_index)

    for frame_index, node_id in enumerate(node_ids):
        if node_id == -1 or frame_index in seen_frames:
            continue
        ordered_frame_indices.append(frame_index)
        seen_frames.add(frame_index)

    node_index_by_frame = {
        frame_index: node_index
        for node_index, frame_index in enumerate(ordered_frame_indices)
    }

    children = {frame_index: [] for frame_index in ordered_frame_indices}
    for frame_index in ordered_frame_indices:
        parent_frame_index = hierarchy[frame_index]
        if parent_frame_index in node_index_by_frame:
            children[parent_frame_index].append(frame_index)

    nodes = []
    parents = []
    for frame_index in ordered_frame_indices:
        parent_frame_index = hierarchy[frame_index]
        sibling_frames = children.get(parent_frame_index, [])
        parents.append(node_index_by_frame.get(parent_frame_index, -1))
        nodes.append({
            "flags": {
                "HasChildren": len(children.get(frame_index, [])) > 0,
                "LastSibling": True if not sibling_frames else sibling_frames[-1] == frame_index,
            },
            "nodeID": node_ids[frame_index],
            "nodeIndex": node_index_by_frame[frame_index],
        })

    return nodes, parents


def _find_building_hanim_root_frame(node_ids, hierarchy, export_order):
    ordered_frame_indices = []
    seen_frames = set()

    for node_id in export_order:
        if node_id == -1:
            continue
        for frame_index, current_node_id in enumerate(node_ids):
            if current_node_id == node_id and frame_index not in seen_frames:
                ordered_frame_indices.append(frame_index)
                seen_frames.add(frame_index)
                break

    for frame_index, node_id in enumerate(node_ids):
        if node_id == -1 or frame_index in seen_frames:
            continue
        ordered_frame_indices.append(frame_index)
        seen_frames.add(frame_index)

    valid_frame_indices = set(ordered_frame_indices)
    for frame_index in ordered_frame_indices:
        parent_frame_index = hierarchy[frame_index]
        if parent_frame_index not in valid_frame_indices:
            return frame_index

    return ordered_frame_indices[0] if ordered_frame_indices else 0


def build_frame_extension(frame_index, node_id, user_data, bone_type_data, hanim_data, root_frame_index, hanim_nodes, hanim_parents):
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

    if frame_index == root_frame_index and "hanimPLG" in extension:
        extension["hanimPLG"]["nodes"] = hanim_nodes
        extension["hanimPLG"]["parents"] = hanim_parents
        extension["hanimPLG"]["keyFrameSize"] = 36
        extension["hanimPLG"]["ReBuildNodesArray"] = False

    return extension


def build_building_frame_entries(bone_names_sorted, hierarchy, rest_matrices, user_data_entries, bone_type_data, hanim_data_entries):
    node_ids = [bone_name_to_node_id(bone_name) for bone_name in bone_names_sorted]
    export_order = determine_export_order(node_ids, hierarchy)
    hanim_nodes, hanim_parents = _build_building_hanim_hierarchy(node_ids, hierarchy, export_order)
    root_frame_index = _find_building_hanim_root_frame(node_ids, hierarchy, export_order)

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
            root_frame_index,
            hanim_nodes,
            hanim_parents,
        )
        frame_entries.append(frame_entry)

    return frame_entries


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
    meshes = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object == armature_object for mod in obj.modifiers)
    ]

    scene = getattr(bpy.context, "scene", None)
    geometry_order = []
    if scene is not None and hasattr(scene, "geometry_tool_items"):
        geometry_order = [entry.mesh_name for entry in scene.geometry_tool_items]

    if geometry_order:
        index_by_name = {name: index for index, name in enumerate(geometry_order)}
        return sorted(
            meshes,
            key=lambda obj: (
                index_by_name.get(obj.name, 10**9),
                int(re.search(r"\d+$", obj.name).group()) if re.search(r"\d+$", obj.name) else 10**9,
                obj.name,
            ),
        )

    return sorted(
        meshes,
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
):
    armature_object = resolve_armature_for_export(context)
    armature_state = collect_armature_export_state(armature_object)

    bone_names_sorted = armature_state["bone_names_sorted"]
    hierarchy = armature_state["hierarchy"]
    rest_matrices = armature_state["rest_matrices"]

    clump = OrderedDict()
    clump["frames"] = build_building_frame_entries(
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
            build_building_geometry_payload(mesh_object, frame_rest_matrix.inverted(), geometry_data)
        )
        clump["atomics"].append(
            build_building_atomic_entry(
                frame_index,
                geometry_index,
                particle_data,
                bone_type_data,
                atomic_material_fx_data,
                particle_data_map,
            )
        )

    return {"clump": clump}


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


def build_building_export_payload(bone_type_data, particle_data, geometry_data, atomic_material_fx_data, particle_data_map):
    return build_building_export_json(
        bpy.context,
        bone_type_data,
        particle_data,
        geometry_data,
        atomic_material_fx_data,
        particle_data_map,
    )


def write_building_model(path, bone_type_data, particle_data, geometry_data, atomic_material_fx_data, particle_data_map):
    converter_path = get_converter_exe_location()
    payload = build_building_export_payload(
        bone_type_data,
        particle_data,
        geometry_data,
        atomic_material_fx_data,
        particle_data_map,
    )
    raise_for_export_preflight(payload, "Building export preflight failed")
    save_building_model_payload(path, payload, converter_path)


def _ensure_filepath_extension(filepath, extension):
    root, _old_ext = os.path.splitext(filepath)
    return root + extension if root else filepath + extension


class BuildingExportOperator(Operator, ExportHelper):
    bl_idname = "export_model.building"
    bl_label = "Novator-Export-Buidling (.dff/.json)"
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff;*.json", options={"HIDDEN"})
    file_format: EnumProperty(
        name="Format",
        items=(
            ("DFF", ".dff", "Export as .dff"),
            ("JSON", ".json", "Export as .json"),
        ),
        default="DFF",
    )

    def check(self, _context):
        desired_ext = ".dff" if self.file_format == "DFF" else ".json"
        updated_path = _ensure_filepath_extension(self.filepath, desired_ext)
        if updated_path != self.filepath:
            self.filepath = updated_path
            return True
        return False

    def draw(self, _context):
        self.layout.prop(self, "file_format")

    def execute(self, context):
        from . import export_building_model_state

        bone_type_data, particle_data, geometry_data = collect_building_scene_export_payload(context.scene)
        export_path = _ensure_filepath_extension(self.filepath, ".dff" if self.file_format == "DFF" else ".json")
        try:
            export_building_model_state(export_path, bone_type_data, particle_data, geometry_data)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
