import json
import os

from collections import OrderedDict

import bpy

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

from .Comfort.constants import (
    ATOMIC_EXTENSION_PROP,
    ATOMIC_FRAME_INDEX_PROP,
    GEOMETRY_USER_DATA_PROP,
    MATERIAL_AMBIENT_PROP,
    MATERIAL_DIFFUSE_PROP,
    MATERIAL_DUAL_TEX_PROP,
    MATERIAL_PAYLOAD_PROP,
    MATERIAL_SPECULAR_PROP,
    MATERIAL_SPEC_TEXTURE_PROP,
    ROOT_HANIM_NODES_PROP,
    ROOT_HANIM_PARENTS_PROP,
    TEXTURE_ALPHA_PROP,
    TEXTURE_NAME_PROP,
)
from .Comfort.io_utils import save_building_model_payload
from .Comfort.json_utils import json_loads_or_default
from .Comfort.mesh_utils import build_geometry_format, collect_texture_coordinates
from .Comfort.transform_utils import (
    accumulate_rest_matrix,
    bone_name_to_node_id,
    edit_bone_to_matrix,
    get_converter_exe_location,
)
from .Comfort.validation_utils import raise_for_export_preflight


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
            "root_hanim_nodes": json_loads_or_default(armature_object.get(ROOT_HANIM_NODES_PROP, "null"), None),
            "root_hanim_parents": json_loads_or_default(armature_object.get(ROOT_HANIM_PARENTS_PROP, "null"), None),
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

        extension = OrderedDict()
        if frame_index != 0:
            if hanim_data_entries[frame_index] is not None:
                extension["hanimPLG"] = hanim_data_entries[frame_index]
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

        frame_entry["extension"] = extension
        frame_entries.append(frame_entry)

    return frame_entries, frame_index_to_node_index


def collect_unit_meshes_for_armature(armature_object):
    meshes = [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object == armature_object for mod in obj.modifiers)
    ]

    if not meshes:
        return []

    name_to_mesh = {mesh.name: mesh for mesh in meshes}
    root_name = min(name_to_mesh)
    root_mesh = name_to_mesh[root_name]

    ordered = [root_mesh]
    children = sorted(
        (mesh for mesh in meshes if mesh != root_mesh),
        key=lambda mesh: mesh.name,
    )
    ordered.extend(children)
    return ordered


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
        if child.type == "MESH" and child.get("s5_sphere_type") == "SelectionSphere":
            return {
                "x": float(child.location.x),
                "y": float(child.location.y),
                "z": float(child.location.z),
                "radius": float(child.dimensions.x / 2.0),
            }
    return None


def _collect_unit_triangles(mesh_object):
    triangles_raw = mesh_object.get("s5_triangles")
    if triangles_raw:
        try:
            stored_triangles = json.loads(triangles_raw, object_pairs_hook=OrderedDict)
            if isinstance(stored_triangles, list) and stored_triangles:
                return stored_triangles
        except Exception:
            pass

    triangles = []
    for polygon in mesh_object.data.polygons:
        triangle = OrderedDict()
        triangle["v1"] = polygon.vertices[0]
        triangle["v2"] = polygon.vertices[1]
        triangle["v3"] = polygon.vertices[2]
        triangle["materialId"] = int(getattr(polygon, "material_index", 0))
        triangles.append(triangle)
    return triangles


def _material_prop(material, key, default):
    return material.get(key, default) if material is not None else default


def _build_unit_material_payloads(mesh_object):
    materials = []
    for material in mesh_object.data.materials:
        if material is None:
            continue

        raw_template = material.get(MATERIAL_PAYLOAD_PROP)
        if raw_template:
            try:
                material_payload = json.loads(raw_template, object_pairs_hook=OrderedDict)
                materials.append(material_payload)
                continue
            except Exception:
                pass

        material_payload = OrderedDict()
        material_payload["color"] = {"alpha": 255, "red": 255, "green": 255, "blue": 255}
        material_payload["UnknownInt1"] = 0
        material_payload["UnknownInt2"] = 237627844
        material_payload["SurfaceProps"] = {
            "ambient": int(_material_prop(material, MATERIAL_AMBIENT_PROP, 1)),
            "specular": int(_material_prop(material, MATERIAL_SPECULAR_PROP, 0)),
            "diffuse": int(_material_prop(material, MATERIAL_DIFFUSE_PROP, 1)),
        }

        extension = OrderedDict()
        if bool(_material_prop(material, MATERIAL_DUAL_TEX_PROP, False)):
            extension["MaterialFXMat"] = {
                "Data1": {
                    "Type": "DualTexture",
                    "Texture1": {
                        "texture": _material_prop(material, MATERIAL_SPEC_TEXTURE_PROP, ""),
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
        material_payload["extension"] = extension

        texture = OrderedDict()
        texture_name = _material_prop(material, TEXTURE_NAME_PROP, material.name)
        texture_alpha = _material_prop(material, TEXTURE_ALPHA_PROP, "")
        texture["texture"] = texture_name
        texture["textureAlpha"] = texture_alpha
        texture["FilterAddressing"] = {
            "FilterMode": "Linear_MipMap_Linear",
            "AddressModeU": "Wrap",
            "AddressModeV": "Wrap",
        }
        texture["UnusedInt1"] = 0
        texture["extension"] = {}
        if texture_alpha == texture_name + "alpha":
            texture["TextureAlphaPadding"] = [0, 0]
            texture["TexPadding"] = [0, 0, 0]
        else:
            texture["TextureAlphaPadding"] = [0, 7, 46, 196]
            texture["TexPadding"] = [0, 0]

        material_payload["textures"] = [texture]
        materials.append(material_payload)

    return materials


def _matrix_to_skin_matrix(matrix):
    values = []
    for row in matrix:
        for cell in row:
            values.append(float(cell))
    return values


def _pack_unit_bone_indices(node_indices):
    padded = list(node_indices[:4])
    while len(padded) < 4:
        padded.append(0)
    return (
        int(padded[0]) |
        (int(padded[1]) << 8) |
        (int(padded[2]) << 16) |
        (int(padded[3]) << 24)
    )


def _collect_unit_skin_payload(mesh_object, bone_names_sorted, frame_index_to_node_index, rest_matrices, hierarchy):
    vertex_bone_indices = []
    vertex_bone_weights = []
    used_node_indices = []
    used_node_index_lookup = {}

    for vertex in mesh_object.data.vertices:
        assignments = []
        for group in vertex.groups:
            if group.weight <= 0.0:
                continue

            group_name = mesh_object.vertex_groups[group.group].name
            if group_name not in bone_names_sorted:
                continue

            frame_index = bone_names_sorted.index(group_name)
            node_index = frame_index_to_node_index.get(frame_index)
            if node_index is None:
                continue

            assignments.append((node_index, float(group.weight)))

        assignments.sort(key=lambda item: item[1], reverse=True)
        assignments = assignments[:4]

        weight_sum = sum(weight for _node_index, weight in assignments)
        if weight_sum > 0.0:
            assignments = [(node_index, weight / weight_sum) for node_index, weight in assignments]

        packed_indices = []
        packed_weights = {"w0": 0.0, "w1": 0.0, "w2": 0.0, "w3": 0.0}
        for slot_index, (node_index, weight) in enumerate(assignments):
            if node_index not in used_node_index_lookup:
                used_node_index_lookup[node_index] = len(used_node_indices)
                used_node_indices.append(node_index)
            packed_indices.append(used_node_index_lookup[node_index])
            packed_weights[f"w{slot_index}"] = float(weight)

        vertex_bone_indices.append(_pack_unit_bone_indices(packed_indices))
        vertex_bone_weights.append(packed_weights)

    skin_to_bone_matrices = []
    for frame_index, node_index in sorted(frame_index_to_node_index.items(), key=lambda item: item[1]):
        world_matrix = accumulate_rest_matrix(rest_matrices, hierarchy, frame_index)
        skin_to_bone_matrices.append(_matrix_to_skin_matrix(world_matrix.inverted()))

    return {
        "UsedBones": used_node_indices,
        "VertexBoneIndices": vertex_bone_indices,
        "VertexBoneWeights": vertex_bone_weights,
        "SkinToBoneMatrices": skin_to_bone_matrices,
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
    payload["textureCoordinates"] = collect_texture_coordinates(mesh_object, vertex_count)
    payload["format"] = build_geometry_format(mesh_object, payload["textureCoordinates"])
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
    if GEOMETRY_USER_DATA_PROP in mesh_object:
        try:
            extension_payload["userDataPLG"] = json.loads(mesh_object[GEOMETRY_USER_DATA_PROP])
        except Exception:
            pass

    payload["extension"] = extension_payload
    return payload


def build_unit_atomic_entry(mesh_object, geometry_index):
    atomic_entry = OrderedDict()
    atomic_entry["frameIndex"] = int(mesh_object.get(ATOMIC_FRAME_INDEX_PROP, 0))
    atomic_entry["geometryIndex"] = geometry_index
    atomic_entry["Flags"] = {
        "CollisionTest": True,
        "RenderShadow": False,
        "Render": True,
    }
    atomic_entry["UnknownInt1"] = 0
    try:
        atomic_entry["extension"] = json_loads_or_default(mesh_object.get(ATOMIC_EXTENSION_PROP, "null"), {})
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


def _ensure_filepath_extension(filepath, extension):
    root, _old_ext = os.path.splitext(filepath)
    return root + extension if root else filepath + extension


def write_unit_model(path, context):
    converter_path = get_converter_exe_location()
    payload = build_unit_export_json(context)
    raise_for_export_preflight(payload, "Unit export preflight failed")
    save_building_model_payload(path, payload, converter_path)


class UnitExportOperator(Operator, ExportHelper):
    bl_idname = "export_model.unit"
    bl_label = "Novator-Export-Unit (.dff/.json)"
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
        from . import export_unit_model_state

        export_path = _ensure_filepath_extension(self.filepath, ".dff" if self.file_format == "DFF" else ".json")
        try:
            export_unit_model_state(export_path, context)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
