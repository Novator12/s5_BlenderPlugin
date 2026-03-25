import os

from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .unit_utilities import (
    apply_unit_animation_data_to_armature,
    apply_unit_animation_json_to_armature,
    convert_anm_to_json_external,
    ensure_armature_active,
)


class UnitAnmImportOperator(Operator, ImportHelper):
    bl_idname = "import_anim.unit_anm"
    bl_label = "Novator-Import-Unit-Anm (.anm/.json)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm;*.json", options={"HIDDEN"})

    def execute(self, context):
        file_ext = os.path.splitext(self.filepath)[1].lower()

        try:
            armature_object = ensure_armature_active()
            if file_ext == ".anm":
                payload = convert_anm_to_json_external(self.filepath)
                apply_unit_animation_data_to_armature(payload, armature_object, self.filepath)
            elif file_ext == ".json":
                apply_unit_animation_json_to_armature(self.filepath, armature_object, self.filepath)
            else:
                self.report({"ERROR"}, "Unsupported animation import type: {}".format(file_ext or "<none>"))
                return {"CANCELLED"}
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
