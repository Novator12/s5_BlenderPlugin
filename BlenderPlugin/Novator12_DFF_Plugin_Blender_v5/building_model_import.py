import os

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
