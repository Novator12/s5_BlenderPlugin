import os
import re

import bmesh
import bpy
import mathutils as mu

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .Comfort.constants import (
    BONE_NAME_PADDING,
    BUILDING_BONE_DISPLAY_LENGTH,
    MESH_SPHERE_NAME_PROP,
    SPHERE_EXPORT_CENTER_PROP,
    SPHERE_EXPORT_RADIUS_PROP,
    SPHERE_LINKED_MESH_PROP,
)
from .Comfort.io_utils import load_building_model_payload
from .Comfort.geometry_tool_metadata import write_geometry_tool_metadata
from .particle_effects_data import PARTICLE_EFFECT_LUT
from .Comfort.transform_utils import (
    frame_dict_to_matrix,
    get_converter_exe_location,
    link_object_in_active_collection,
    matrix_to_bone_axis_roll,
    set_clipping_for_all_screens,
)

KNOWN_PARTICLE_EFFECTS = set(PARTICLE_EFFECT_LUT)


def _assign_mesh_materials(mesh_object, geometry_data):
    material_slots = mesh_object.data.materials
    material_slots.clear()

    for material_index, material_data in enumerate(geometry_data.get("materials", [])):
        textures = material_data.get("textures", [])
        texture_name = textures[0].get("texture", "") if textures else ""
        material_name = texture_name or f"GeometryMaterial{material_index + 1:02d}"
        material = bpy.data.materials.get(material_name)
        if material is None:
            material = bpy.data.materials.new(name=material_name)
        material_slots.append(material)


def _infer_bone_type(user_data):
    for property_line in user_data.get("3dsmax User Properties", []):
        if "Effect=BuildingDecalWithSnow" in property_line or "decal=flat" in property_line:
            return "DECAL"
        if "Effect=SimpleObjectWithSnow" in property_line:
            return "BUILDING"
    return None


def _user_data_has_tag(user_data):
    return any(
        re.match(r"^tag\s*=", str(property_line).strip(), flags=re.IGNORECASE)
        for property_line in user_data.get("3dsmax User Properties", [])
    )


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
    bone_item.include_tag = _user_data_has_tag(user_data)
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
            face.material_index = int(triangle.get("materialId", 0))
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
        _assign_mesh_materials(mesh_object, geometry_data)
        first_material = mesh_object.data.materials[0] if mesh_object.data.materials else None
        mesh_object.data.name = first_material.name if first_material is not None else mesh_name

    return mesh_object, mesh_name, empty_geometry


def _attach_sphere_proxy(geometry_data, mesh_object, empty_geometry, frame_rest_matrix):
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

    export_center = mu.Vector((sphere_data["x"], sphere_data["y"], sphere_data["z"]))
    display_center = (frame_rest_matrix @ export_center.to_4d()).to_3d()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=sphere_data["radius"], location=(0.0, 0.0, 0.0))
    sphere_object = bpy.context.object
    sphere_object.name = sphere_name

    if sphere_object == mesh_object:
        raise RuntimeError("Sphere creation stayed in mesh edit context")

    sphere_object.parent = mesh_object
    sphere_object.location = display_center
    sphere_object.hide_render = True
    sphere_object.hide_set(True)
    sphere_object.display_type = "WIRE"
    mesh_object[MESH_SPHERE_NAME_PROP] = sphere_object.name
    sphere_object[SPHERE_LINKED_MESH_PROP] = mesh_object.name
    sphere_object[SPHERE_EXPORT_CENTER_PROP] = list(export_center)
    sphere_object[SPHERE_EXPORT_RADIUS_PROP] = sphere_data["radius"]

    if previous_mode == "EDIT" and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="EDIT")


def _write_geometry_tool_metadata(scene, geometry_data, mesh_object, empty_geometry):
    return write_geometry_tool_metadata(scene, geometry_data, mesh_object, empty_geometry)


def build_building_geometry(geometry_data, armature_object, frame_rest_matrix, bone_name, mesh_index):
    mesh_object, mesh_name, empty_geometry = _build_mesh_object(
        geometry_data,
        armature_object,
        frame_rest_matrix,
        bone_name,
        mesh_index,
    )
    _attach_sphere_proxy(geometry_data, mesh_object, empty_geometry, frame_rest_matrix)
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

    def extract_particle_payload(extension):
        if not isinstance(extension, dict):
            return None, False

        wrapped_payload = extension.get("ParticleStandard")
        if isinstance(wrapped_payload, dict) and "Emitters" in wrapped_payload:
            return wrapped_payload, True

        if "Emitters" in extension:
            return extension, False

        return None, False

    used_frame_indices = set()
    for atomic_entry in clump_data["atomics"]:
        frame_index = atomic_entry.get("frameIndex")
        if frame_index in used_frame_indices:
            continue

        extension = atomic_entry.get("extension", {})
        particle_payload, wrapped_payload = extract_particle_payload(extension)
        if not particle_payload:
            continue

        particle_data_map[int(frame_index)] = particle_payload

        matched_effect = None
        for emitter in particle_payload["Emitters"]:
            particle_texture = emitter.get("EmitterStandard", {}).get("ParticleTexture", {})
            texture_name = particle_texture.get("texture", "").lower()

            matched_effect = next(
                (effect_name for effect_name in KNOWN_PARTICLE_EFFECTS if effect_name.lower() in texture_name),
                None,
            )
            if matched_effect is not None:
                break

        effect_item = scene.particle_effects.add()
        effect_item.bone_index = str(frame_index)
        effect_item.effect_type = "Ubisoft" if wrapped_payload or matched_effect is None else matched_effect
        scene.particle_effects_index = len(scene.particle_effects) - 1
        used_frame_indices.add(frame_index)
        continue

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
