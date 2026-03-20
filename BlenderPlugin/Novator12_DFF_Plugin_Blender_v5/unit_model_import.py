from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .building_utilities import get_converter_exe_location, set_clipping_for_all_screens
from .unit_utilities import (
    import_unit_clump,
    load_unit_model_payload,
)


def read_unit_model(path):
    converter_path = get_converter_exe_location()
    payload = load_unit_model_payload(path, converter_path)
    return import_unit_clump(payload, False)


class UnitDffImportOperator(Operator, ImportHelper):
    bl_idname = "import_model.unit_dff"
    bl_label = "Novator-Import-Unit-Dff (.dff)"
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff", options={"HIDDEN"})

    def execute(self, context):
        from . import import_unit_model_state

        try:
            set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)
            import_unit_model_state(self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class UnitDffJsonImportOperator(Operator, ImportHelper):
    bl_idname = "import_model.unit_dff_json"
    bl_label = "Novator-Import-Unit-Dff-Json (.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        from . import import_unit_model_state

        try:
            set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)
            import_unit_model_state(self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
