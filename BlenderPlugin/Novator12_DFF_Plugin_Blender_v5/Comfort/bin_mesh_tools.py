import traceback

from copy import deepcopy

import bpy

from bpy.types import Operator, Panel

from .bin_mesh_utils import bin_mesh_to_json, validate_bin_mesh
from .constants import SCENE_BIN_MESH_REPORT_PROP


def _ensure_object_mode(context):
    if context.mode == "EDIT_MESH" and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def _entry_mesh_object(entry):
    mesh_object = getattr(entry, "mesh_object", None)
    try:
        if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
            return mesh_object
    except ReferenceError:
        pass

    mesh_name = str(getattr(entry, "mesh_name", "") or "").strip()
    mesh_object = bpy.data.objects.get(mesh_name)
    if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
        return mesh_object
    return None


def _selected_geometry_entry(context):
    scene = context.scene
    active_object = context.active_object
    if active_object is not None and active_object.type == "MESH":
        for index, entry in enumerate(scene.geometry_tool_items):
            if _entry_mesh_object(entry) != active_object:
                continue
            if scene.geometry_tool_index != index:
                scene.geometry_tool_index = index
            return entry, index
        return None, -1

    index = scene.geometry_tool_index
    if index < 0 or index >= len(scene.geometry_tool_items):
        return None, index
    return scene.geometry_tool_items[index], index


def _is_empty_geometry_entry(entry):
    return entry.bin_mesh_data == "Empty-Geometry" or (
        entry.mesh_name == "Empty-Geometry" and _entry_mesh_object(entry) is None
    )


def _bin_mesh_generation_input_errors(mesh_object, material_count):
    errors = []
    mesh_data = mesh_object.data
    if not mesh_data.vertices:
        errors.append("Mesh has no vertices.")
    if not mesh_data.polygons:
        errors.append("Mesh has no faces.")
    if not mesh_object.vertex_groups:
        errors.append("Mesh has no vertex group for its bone assignment.")
    if material_count <= 0:
        errors.append("Geometry entry has no materials.")

    non_triangles = [polygon.index for polygon in mesh_data.polygons if len(polygon.vertices) != 3]
    if non_triangles:
        preview = ", ".join(str(index) for index in non_triangles[:8])
        if len(non_triangles) > 8:
            preview += ", ..."
        errors.append(f"Mesh is not triangulated. Face indices: {preview}")

    invalid_material_faces = [
        polygon.index
        for polygon in mesh_data.polygons
        if polygon.material_index < 0 or polygon.material_index >= material_count
    ]
    if invalid_material_faces:
        preview = ", ".join(str(index) for index in invalid_material_faces[:8])
        if len(invalid_material_faces) > 8:
            preview += ", ..."
        errors.append(
            f"Faces reference a material outside 0..{material_count - 1}. Face indices: {preview}"
        )
    return errors


def generate_bin_meshes(context, entry_indices):
    from .. import AtomicMaterialFX_Data, ParticleDataList
    from ..building_model_export import build_building_export_json, collect_building_scene_export_payload
    from .io_utils import convert_binary_dff_to_json, convert_json_to_binary_dff
    from .transform_utils import get_converter_exe_location

    scene = context.scene
    targets = {}
    errors = []
    for entry_index in entry_indices:
        if entry_index < 0 or entry_index >= len(scene.geometry_tool_items):
            errors.append(f"Geometry {entry_index + 1}: Entry does not exist.")
            continue

        entry = scene.geometry_tool_items[entry_index]
        mesh_object = _entry_mesh_object(entry)
        if mesh_object is None:
            errors.append(f"Geometry {entry_index + 1}: No linked mesh object.")
            continue

        input_errors = _bin_mesh_generation_input_errors(mesh_object, len(entry.materials))
        if input_errors:
            errors.extend(
                f"Geometry {entry_index + 1} ({mesh_object.name}): {message}"
                for message in input_errors
            )
            continue
        targets[mesh_object.name] = (entry_index, entry, mesh_object)

    if not targets:
        return [], errors

    bone_type_data, particle_data, geometry_data = collect_building_scene_export_payload(scene)
    geometry_data = deepcopy(geometry_data or {})
    missing_metadata = []
    for mesh_name in targets:
        metadata = geometry_data.get(mesh_name)
        if metadata is None:
            errors.append(f"{mesh_name}: No Geometry metadata found.")
            missing_metadata.append(mesh_name)
            continue
        metadata["bin_mesh_data"] = "No data"
    for mesh_name in missing_metadata:
        targets.pop(mesh_name, None)
    if not targets:
        return [], errors

    source_indices = {}
    payload = build_building_export_json(
        context,
        bone_type_data,
        particle_data,
        geometry_data,
        AtomicMaterialFX_Data,
        ParticleDataList,
        geometry_source_indices=source_indices,
        strict_mesh_triangles=True,
        geometry_target_names=set(targets),
        include_geometry_texture_coordinates=False,
    )
    converter_path = get_converter_exe_location()
    binary_data = convert_json_to_binary_dff(payload, converter_path)
    converted_payload = convert_binary_dff_to_json(binary_data, converter_path)
    converted_geometries = converted_payload.get("clump", {}).get("geometries", [])

    generated = []
    pending_updates = []
    for mesh_name, (entry_index, entry, mesh_object) in targets.items():
        geometry_index = source_indices.get(mesh_name)
        if geometry_index is None or geometry_index >= len(converted_geometries):
            errors.append(
                f"Geometry {entry_index + 1} ({mesh_name}): Mesh was skipped by the isolated converter payload."
            )
            continue

        generated_bin_mesh = (
            converted_geometries[geometry_index]
            .get("extension", {})
            .get("BinMeshPLG")
        )
        report = validate_bin_mesh(mesh_object, generated_bin_mesh, len(entry.materials))
        if not report["valid"]:
            errors.append(
                f"Geometry {entry_index + 1} ({mesh_name}): S5Converter returned an invalid BinMesh: "
                + "; ".join(report["errors"][:3])
            )
            continue

        pending_updates.append((entry, bin_mesh_to_json(report["bin_mesh"])))
        generated.append(mesh_name)

    for entry, bin_mesh_json in pending_updates:
        entry.bin_mesh_data = bin_mesh_json
    return generated, errors


def _set_bin_mesh_report(scene, lines):
    setattr(scene, SCENE_BIN_MESH_REPORT_PROP, "\n".join(lines).rstrip())


def _log_bin_mesh_errors(mesh_name, errors):
    for error in errors:
        print(f"[BinMesh Validation] Mesh '{mesh_name}': {error}")


def _selection_error_message(context):
    active_object = context.active_object
    if active_object is not None and active_object.type == "MESH":
        return f"Active mesh '{active_object.name}' has no Geometry Tool entry."
    return "No Geometry entry selected."


def _generation_exception_message(exc):
    extracted = traceback.extract_tb(exc.__traceback__)
    if not extracted:
        return f"BinMesh generation failed: {exc}"
    frame = extracted[-1]
    filename = frame.filename.replace("\\", "/").rsplit("/", 1)[-1]
    return (
        f"BinMesh generation failed in {filename}:{frame.lineno} "
        f"({frame.name}): {exc}"
    )


class GEOMETRY_OT_validate_bin_mesh(Operator):
    bl_idname = "geometry_tools.validate_bin_mesh"
    bl_label = "Validate BinMesh"
    bl_description = "Validates the active mesh's Geometry entry, or the selected Geometry entry when no mesh is active"

    def execute(self, context):
        _ensure_object_mode(context)
        entry, entry_index = _selected_geometry_entry(context)
        if entry is None:
            self.report({"ERROR"}, _selection_error_message(context))
            return {"CANCELLED"}

        if _is_empty_geometry_entry(entry):
            lines = [
                f"BinMesh: Geometry {entry_index + 1} ({entry.mesh_name})",
                "INFO: Empty Geometry does not use a BinMesh.",
            ]
            _set_bin_mesh_report(context.scene, lines)
            self.report({"INFO"}, "Empty Geometry does not use a BinMesh.")
            return {"FINISHED"}

        mesh_object = _entry_mesh_object(entry)
        if mesh_object is None:
            self.report({"ERROR"}, "Selected Geometry entry has no linked mesh object.")
            return {"CANCELLED"}

        report = validate_bin_mesh(mesh_object, entry.bin_mesh_data, len(entry.materials))
        lines = [f"BinMesh: Geometry {entry_index + 1} ({mesh_object.name})"]
        if report["valid"]:
            lines.append("OK: Schema, indices, materials, and TriStrip topology are valid.")
            self.report({"INFO"}, f"BinMesh for '{mesh_object.name}' is valid.")
        else:
            lines.append("ERROR: BinMesh is invalid.")
            _log_bin_mesh_errors(mesh_object.name, report["errors"])
            self.report({"WARNING"}, f"BinMesh for '{mesh_object.name}' is invalid.")
        _set_bin_mesh_report(context.scene, lines)
        return {"FINISHED"}


class GEOMETRY_OT_generate_bin_mesh(Operator):
    bl_idname = "geometry_tools.generate_bin_mesh"
    bl_label = "Generate BinMesh"
    bl_description = "Generates a BinMesh for the active mesh's Geometry entry with an isolated, UV-free S5Converter payload"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        entry, entry_index = _selected_geometry_entry(context)
        if entry is None:
            self.report({"ERROR"}, _selection_error_message(context))
            return {"CANCELLED"}
        if _is_empty_geometry_entry(entry):
            _set_bin_mesh_report(
                context.scene,
                [
                    f"BinMesh: Geometry {entry_index + 1} ({entry.mesh_name})",
                    "INFO: Empty Geometry does not use a BinMesh.",
                ],
            )
            self.report({"INFO"}, "Empty Geometry does not use a BinMesh.")
            return {"CANCELLED"}

        try:
            generated, errors = generate_bin_meshes(context, [entry_index])
        except Exception as exc:
            traceback.print_exc()
            message = _generation_exception_message(exc)
            _set_bin_mesh_report(context.scene, [f"ERROR: {message}"])
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        lines = [f"OK: Generated BinMesh: {name}" for name in generated]
        lines.extend(f"ERROR: {message}" for message in errors)
        _set_bin_mesh_report(context.scene, lines)
        if not generated:
            self.report({"ERROR"}, errors[0] if errors else "BinMesh could not be generated.")
            return {"CANCELLED"}
        self.report({"INFO"}, f"BinMesh for '{generated[0]}' was generated and validated.")
        return {"FINISHED"}


class GEOMETRY_OT_delete_bin_mesh(Operator):
    bl_idname = "geometry_tools.delete_bin_mesh"
    bl_label = "Delete BinMesh"
    bl_description = "Deletes the active mesh's stored BinMesh, or the selected Geometry entry when no mesh is active"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        entry, entry_index = _selected_geometry_entry(context)
        if entry is None:
            self.report({"ERROR"}, _selection_error_message(context))
            return {"CANCELLED"}
        if _is_empty_geometry_entry(entry):
            entry.bin_mesh_data = "Empty-Geometry"
            self.report({"INFO"}, "Empty Geometry has no BinMesh to delete.")
            return {"CANCELLED"}

        entry.bin_mesh_data = "No data"
        mesh_object = _entry_mesh_object(entry)
        name = mesh_object.name if mesh_object is not None else entry.mesh_name
        _set_bin_mesh_report(context.scene, [f"OK: Deleted BinMesh: Geometry {entry_index + 1} ({name})"])
        self.report({"INFO"}, f"Deleted BinMesh for '{name}'.")
        return {"FINISHED"}


class GEOMETRY_OT_generate_all_invalid_bin_meshes(Operator):
    bl_idname = "geometry_tools.generate_all_invalid_bin_meshes"
    bl_label = "Generate All Invalid BinMeshes"
    bl_description = "Regenerates every invalid linked BinMesh independently of UV validation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        invalid_indices = []
        for entry_index, entry in enumerate(context.scene.geometry_tool_items):
            mesh_object = _entry_mesh_object(entry)
            if mesh_object is None:
                continue
            report = validate_bin_mesh(mesh_object, entry.bin_mesh_data, len(entry.materials))
            if not report["valid"]:
                invalid_indices.append(entry_index)

        if not invalid_indices:
            _set_bin_mesh_report(context.scene, ["OK: All linked BinMeshes are valid."])
            self.report({"INFO"}, "All linked BinMeshes are valid.")
            return {"FINISHED"}

        try:
            generated, errors = generate_bin_meshes(context, invalid_indices)
        except Exception as exc:
            traceback.print_exc()
            message = _generation_exception_message(exc)
            _set_bin_mesh_report(context.scene, [f"ERROR: {message}"])
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        lines = [f"OK: Generated BinMesh: {name}" for name in generated]
        lines.extend(f"ERROR: {message}" for message in errors)
        _set_bin_mesh_report(context.scene, lines)
        if errors:
            self.report(
                {"WARNING"},
                f"Generated {len(generated)} BinMeshes; {len(errors)} entries failed. See BinMesh Validation.",
            )
        else:
            self.report({"INFO"}, f"Generated and validated {len(generated)} BinMeshes.")
        return {"FINISHED"}


class GEOMETRY_OT_delete_all_bin_meshes(Operator):
    bl_idname = "geometry_tools.delete_all_bin_meshes"
    bl_label = "Delete All BinMeshes"
    bl_description = "Deletes all stored BinMeshes while preserving Empty Geometry markers"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        deleted_count = 0
        for entry in context.scene.geometry_tool_items:
            if _is_empty_geometry_entry(entry):
                entry.bin_mesh_data = "Empty-Geometry"
                continue
            if entry.bin_mesh_data != "No data":
                entry.bin_mesh_data = "No data"
                deleted_count += 1
        _set_bin_mesh_report(context.scene, [f"OK: Deleted {deleted_count} stored BinMeshes."])
        self.report({"INFO"}, f"Deleted {deleted_count} stored BinMeshes.")
        return {"FINISHED"}


class GEOMETRY_PT_bin_mesh(Panel):
    bl_idname = "VIEW3D_PT_geometry_bin_mesh"
    bl_label = "BinMesh Validation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Geometry Tools"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator(GEOMETRY_OT_validate_bin_mesh.bl_idname, icon="CHECKMARK", text="Validate")
        row.operator(GEOMETRY_OT_generate_bin_mesh.bl_idname, icon="FILE_REFRESH", text="Generate")
        layout.operator(GEOMETRY_OT_delete_bin_mesh.bl_idname, icon="TRASH", text="Delete BinMesh")
        layout.operator(
            GEOMETRY_OT_generate_all_invalid_bin_meshes.bl_idname,
            icon="MOD_TRIANGULATE",
            text="Generate All Invalid BinMeshes",
        )
        layout.operator(
            GEOMETRY_OT_delete_all_bin_meshes.bl_idname,
            icon="TRASH",
            text="Delete All BinMeshes",
        )

        report = getattr(context.scene, SCENE_BIN_MESH_REPORT_PROP, "")
        if report:
            box = layout.box()
            for line in report.splitlines():
                icon = "CHECKMARK" if line.startswith("OK:") else "CANCEL" if line.startswith("ERROR:") else "INFO"
                box.label(text=line, icon=icon)
