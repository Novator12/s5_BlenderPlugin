from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .building_utilities import (
    get_converter_exe_location,
    import_building_clump as run_building_import,
    load_building_model_payload,
    set_clipping_for_all_screens,
)


def read_building_model(path, atomic_material_fx_data, particle_data_map):
    converter_path = get_converter_exe_location()
    payload = load_building_model_payload(path, converter_path)
    return run_building_import(payload, False, atomic_material_fx_data, particle_data_map)


class BuildingDffImportOperator(Operator, ImportHelper):
    bl_idname = "import_model.building_dff"
    bl_label = "Novator-Import-Buidling-Dff (.dff)"
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff", options={"HIDDEN"})

    def execute(self, context):
        from . import import_building_model_state

        try:
            set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)
            import_building_model_state(self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BuildingDffJsonImportOperator(Operator, ImportHelper):
    bl_idname = "import_model.building_dff_json"
    bl_label = "Novator-Import-Buidling-Dff-Json(.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        from . import import_building_model_state

        try:
            set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)
            import_building_model_state(self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
