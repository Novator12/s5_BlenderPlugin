from bpy.props import StringProperty
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


class BuildingDffExportOperator(Operator, ExportHelper):
    bl_idname = "export_model.building_dff"
    bl_label = "Novator-Export-Buidling-Dff (.dff)"
    filename_ext = ".dff"

    def execute(self, context):
        from . import export_building_model_state

        bone_type_data, particle_data, geometry_data = collect_building_scene_export_payload(context.scene)
        try:
            export_building_model_state(self.filepath, bone_type_data, particle_data, geometry_data)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BuildingDffJsonExportOperator(Operator, ExportHelper):
    bl_idname = "export_model.building_dff_json"
    bl_label = "Novator-Export-Buidling-Dff-Json(.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        from . import export_building_model_state

        bone_type_data, particle_data, geometry_data = collect_building_scene_export_payload(context.scene)
        try:
            export_building_model_state(self.filepath, bone_type_data, particle_data, geometry_data)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
