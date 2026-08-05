import json
import os

import bmesh
import bpy
import mathutils as mu

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .Comfort.constants import BONE_NAME_PADDING, BUILDING_BONE_DISPLAY_LENGTH
from .Comfort.io_utils import load_building_model_payload
from .particle_effects_data import PARTICLE_EFFECT_LUT
from .Comfort.transform_utils import (
    frame_dict_to_matrix,
    get_converter_exe_location,
    link_object_in_active_collection,
    matrix_to_bone_axis_roll,
    set_clipping_for_all_screens,
)

KNOWN_PARTICLE_EFFECTS = set(PARTICLE_EFFECT_LUT)


def _assign_active_object_material(material_name):
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
        edit_bone.tail = edit_bone.head + bone_axis * BUILDING_BONE_DISPLAY_LENGTH
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
        _assign_active_object_material(texture_name)
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


def _write_geometry_tool_metadata(scene, geometry_data, mesh_object, empty_geometry):
    geometry_entry = scene.geometry_tool_items.add()
    geometry_entry.mesh_name = mesh_object.name
    geometry_entry.mesh_object = mesh_object
    geometry_entry.linked_to_object = True
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
    _write_geometry_tool_metadata(bpy.context.scene, geometry_data, mesh_object, empty_geometry)
    return mesh_index + 1


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
            particle_data_map[int(frame_index)] = particle_standard
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
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")

    return updated_atomic_fx_data, updated_particle_data


def read_building_model(path, atomic_material_fx_data, particle_data_map):
    converter_path = get_converter_exe_location()
    payload = load_building_model_payload(path, converter_path)
    return import_building_clump(payload, False, atomic_material_fx_data, particle_data_map)


class BuildingImportOperator(Operator, ImportHelper):
    bl_idname = "import_model.building"
    bl_label = "Novator-Import-Buidling (.dff/.json)"
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff;*.json", options={"HIDDEN"})

    def execute(self, context):
        from . import import_building_model_state

        file_ext = os.path.splitext(self.filepath)[1].lower()
        if file_ext not in {".dff", ".json"}:
            self.report({"ERROR"}, "Unsupported building import type: {}".format(file_ext or "<none>"))
            return {"CANCELLED"}

        try:
            set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)
            import_building_model_state(self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
