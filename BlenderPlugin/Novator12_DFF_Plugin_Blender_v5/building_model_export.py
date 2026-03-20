import os

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper

import bpy

from .building_utilities import (
    build_building_atomic_entry,
    build_building_export_json,
    build_building_frame_entries,
    build_building_geometry_payload,
    collect_building_scene_export_payload,
    get_converter_exe_location,
    save_building_model_payload,
)


def build_building_export_payload(bone_type_data, particle_data, geometry_data, atomic_material_fx_data, particle_data_map):
    return build_building_export_json(
        bpy.context,
        bone_type_data,
        particle_data,
        geometry_data,
        atomic_material_fx_data,
        particle_data_map,
        frame_entries_builder=build_building_frame_entries,
        geometry_payload_builder=build_building_geometry_payload,
        atomic_entry_builder=build_building_atomic_entry,
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
